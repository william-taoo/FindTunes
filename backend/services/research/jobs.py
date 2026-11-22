"""Single-process background jobs with progress, bounded admission and local JSONL traces."""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from .schema import SongIdentity, GROUPS
from .graph import research_song
from .providers import HTTPResearchProvider
from .model import LocalResearchModel, InferenceBudget

TRACE_DIR = Path(__file__).resolve().parents[2] / '.research-traces'


def budget(name, default, maximum):
    try:
        return min(maximum, max(30, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def canonical_identity(document):
    title = document['title']
    version = next((word for word in ('remix', 'live', 'acoustic', 'sped up', 'slowed')
                    if word in title.casefold()), 'original')
    return SongIdentity(genius_id=document['song_id'], title=title, artist=document['artist'], version=version)


def comparisons(seed, candidate):
    """Deterministic comparison of validated ratings, with their supporting finding indexes."""
    similarities, differences = [], []
    for group in GROUPS:
        seed_rows = {row['label']: row for row in seed['profile'][group]}
        for row in candidate['profile'][group]:
            other = seed_rows[row['label']]
            if row['level'] == 'unknown' or other['level'] == 'unknown':
                continue
            item = {'category': group, 'label': row['label'], 'seed_level': other['level'],
                    'candidate_level': row['level'], 'seed_finding_ids': other['finding_ids'],
                    'candidate_finding_ids': row['finding_ids'],
                    'explanation': f"{row['label']}: seed is {other['level']}; suggestion is {row['level']}."}
            (similarities if row['level'] == other['level'] else differences).append(item)
    return {'similarities': similarities, 'differences': differences,
            'limitation': 'No comparison is made for unknown dimensions. Ratings describe evidence, not measured audio.'}


def publish_profile(job, song_id, seed_id, payload):
    """A completed profile or provisional retrieval result can be rendered immediately."""
    if str(song_id) == str(seed_id):
        job['seed'] = payload
    elif str(song_id) in job['results']:
        job['results'][str(song_id)]['profile'] = payload


def has_analysis(payload):
    return bool(payload and (payload.get('vibe') or payload.get('findings') or any(
        row['level'] != 'unknown' for rows in payload.get('profile', {}).values() for row in rows)))


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.tasks = set()

    def start(self, seed_document, matches, mode='vibe'):
        mode = 'vibe' if mode == 'deep' else mode
        now = time.time()
        self.jobs = {key: value for key, value in self.jobs.items() if now - value['created_at'] < 1800}
        limit = 1 if mode == 'vibe' else 2
        if sum(job['status'] in ('queued', 'running') and job.get('mode', mode) == mode for job in self.jobs.values()) >= limit:
            return None
        if len(self.jobs) >= 50:
            completed = next((key for key, value in self.jobs.items() if value['status'] not in ('queued', 'running')), None)
            if completed:
                del self.jobs[completed]
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {'id': job_id, 'status': 'queued', 'created_at': now,
                            'mode': mode, 'progress': 'Queued for song vibes' if mode == 'vibe' else 'Queued for source lookup', 'seed': None, 'results': {}, 'errors': [], 'trace': []}
        task = asyncio.create_task(self.run(job_id, seed_document, matches, mode=mode))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job_id

    def snapshot(self, job_id):
        return self.jobs.get(job_id)

    async def run(self, job_id, seed_document, matches, mode='vibe'):
        from services.lyric_retrieval import make_genius_client, fetch_song_document, fetch_song_source_url
        job = self.jobs[job_id]
        started = time.monotonic()
        seconds = budget('RESEARCH_JOB_SECONDS', 120, 120) if mode == 'vibe' else 60
        deadline = started + seconds
        # One prose generation for the input song and each of three candidates.
        inference_budget = InferenceBudget(4)
        seed_task = None
        seed_link_task = None
        metadata_only = mode in ('quick', 'lyrics_links') and 'lines' not in seed_document
        inference_gate = asyncio.Semaphore(1)
        def trace(**event):
            event = {'elapsed_ms': round((time.monotonic() - started)*1000), **event}
            job['trace'].append(event)
            try:
                TRACE_DIR.mkdir(exist_ok=True)
                with (TRACE_DIR / f'{job_id}.jsonl').open('a', encoding='utf-8') as file:
                    file.write(json.dumps(event) + '\n')
            except OSError:
                pass

        async def profile(document, reference=None):
            per_song = min(deadline, time.monotonic() + (15 if mode == 'quick' else budget('RESEARCH_SONG_SECONDS', 60, 60)))
            provisional_sources = {}
            from .schema import unknown_profile
            provisional = {'mode': mode, 'song': canonical_identity(document).model_dump(),
                'profile': unknown_profile(), 'findings': [], 'sources': [], 'errors': [],
                'cached': False, 'analysis_status': 'running', 'outcome': 'searching', 'outcome_reason': None,
                'vibe': None, 'compares_to_seed': False}
            publish_profile(job, document['song_id'], seed_document['song_id'], provisional)
            def song_trace(**event):
                raw_sources = event.pop('sources', None)
                if raw_sources is not None:
                    for item in raw_sources:
                        provisional_sources[item['id']] = {**item, 'identity_verified': False}
                    publish_profile(job, document['song_id'], seed_document['song_id'], {**provisional,
                        'sources': list(provisional_sources.values()),
                        'outcome': 'sources_only' if mode == 'quick' else 'analyzing'})
                    event['source_count'] = len(provisional_sources)
                event.setdefault('song_id', document['song_id'])
                trace(**event)
            value = await research_song(canonical_identity(document), document, HTTPResearchProvider(),
                LocalResearchModel(song_trace, budget=inference_budget), per_song, song_trace,
                mode=mode, inference_gate=inference_gate, seed_profile=reference)
            publish_profile(job, document['song_id'], seed_document['song_id'], value)
            return value

        async def lyric_link(song_id):
            try:
                return await asyncio.wait_for(asyncio.to_thread(fetch_song_source_url, song_id),
                                              timeout=max(.01, min(12, deadline - time.monotonic())))
            except Exception as error:
                trace(agent='lyrics', action='source_link', status='failed', song_id=str(song_id), error=type(error).__name__)
                return None

        async def catalog_links(result, song_id):
            candidate_link = await lyric_link(song_id)
            seed_link = await asyncio.shield(seed_link_task)
            if candidate_link or seed_link:
                result['sources'] = {'seed': seed_link, 'candidate': candidate_link}

        async def catalog_sources(match, result):
            if mode == 'lyrics_links':
                await catalog_links(result, match['id'])
                return result['sources']
            metadata = match.get('metadata', {})
            artist = metadata.get('artist')
            if isinstance(artist, list):
                artist = next(iter(artist), None)
            if metadata.get('title') and artist:
                document = {'song_id': str(match['id']), 'title': metadata['title'], 'artist': artist}
                await asyncio.gather(catalog_links(result, match['id']), profile(document))
            else:
                await catalog_links(result, match['id'])
            return result['sources'] or (result['profile'] or {}).get('sources')

        async def candidate(match):
            result = {'status': 'running', 'profile': None, 'comparison': None,
                      'explanation': None, 'sources': None, 'errors': [], 'lyric_overlap': None, 'vibe_description': None}
            job['results'][str(match['id'])] = result
            try:
                if metadata_only:
                    result['status'] = 'evidence_only' if await catalog_sources(match, result) else 'unavailable'
                else:
                    # Request-scoped clients avoid sharing lyricsgenius state between workers.
                    document = await asyncio.to_thread(fetch_song_document, make_genius_client(), match['id'])
                    if document is None:
                        raise ValueError('Canonical lyric document unavailable')
                    result['sources'] = {'seed': seed_document['source_url'], 'candidate': document['source_url']}
                    from services.passage_retrieval import lyric_overlap
                    result['lyric_overlap'] = lyric_overlap(seed_document, document)
                    research = await profile(document, reference=seed_task)
                    result.update(profile=research, vibe_description=research.get('vibe'),
                        status='complete' if research.get('vibe') else 'evidence_only')
            except Exception as error:
                result.update(status='unavailable')
                result['errors'].append({'agent': 'candidate', 'code': type(error).__name__})
            trace(agent='job', action='candidate_complete', status=result['status'], song_id=str(match['id']))

        async def work():
            nonlocal seed_task, seed_link_task
            job.update(status='running', progress={'quick': 'Gathering written sources',
                       'vibe': 'Finding the input song’s vibe', 'lyrics_links': 'Looking up Genius lyric links'}[mode])
            # Seed and candidate retrieval can overlap. Comparisons wait only for the seed result.
            if mode != 'lyrics_links':
                seed_task = asyncio.create_task(profile(seed_document))
            if metadata_only:
                seed_link_task = asyncio.create_task(lyric_link(seed_document['song_id']))
            try:
                await asyncio.gather(*(candidate(match) for match in matches[:3]))
                if seed_task:
                    job['seed'] = await seed_task
            finally:
                pending = [task for task in (seed_task, seed_link_task) if task and not task.done()]
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            if mode != 'vibe':
                excerpts = (job['seed'] or {}).get('sources') or any(
                    (value['profile'] or {}).get('sources') for value in job['results'].values())
                links = any(value['sources'] for value in job['results'].values())
                job.update(status='complete' if excerpts or links else 'partial',
                           progress='Written sources ready' if excerpts else 'Genius lyric links ready' if links else 'Sources unavailable for these songs')
                return
            partial = any(value['status'] in ('unavailable', 'evidence_only') for value in job['results'].values()) or not has_analysis(job['seed'])
            job.update(status='partial' if partial else 'complete',
                       progress='Vibe lookup finished; some descriptions are unavailable' if partial else 'Song vibes ready')
        try:
            await asyncio.wait_for(work(), timeout=seconds)
        except asyncio.TimeoutError:
            job.update(status='partial', progress='Research deadline reached; recommendations remain available')
            job['errors'].append({'code': 'job_deadline', 'message': 'Enrichment deadline reached.'})
            for result in job['results'].values():
                if result['status'] == 'running':
                    result['status'] = 'unavailable'
        except Exception as error:
            job.update(status='unavailable', progress='Research unavailable; recommendations remain available')
            job['errors'].append({'code': type(error).__name__, 'message': 'Enrichment failed.'})
        finally:
            # Provisional evidence survives cancellation, but must no longer appear to be running.
            pending_profiles = [job.get('seed'), *[item.get('profile') for item in job['results'].values()]]
            for value in pending_profiles:
                if value and value.get('analysis_status') == 'running':
                    value['analysis_status'] = 'partial'
                    value['outcome'] = 'analysis_failed' if value.get('sources') else 'search_failed'
                    value['outcome_reason'] = 'timeout' if job['status'] == 'partial' else 'model_error'
                    value.setdefault('errors', []).append({'agent': 'job', 'code': 'TimeoutError',
                                                           'message': 'Analysis ended before a final profile; retrieved sources retained.'})
            for result in job['results'].values():
                if result['status'] == 'running':
                    result['status'] = 'evidence_only' if result.get('profile') or result.get('lyric_overlap') else 'unavailable'
            job['duration_ms'] = round((time.monotonic() - started)*1000)
            trace(agent='job', action='finished', status=job['status'], duration_ms=job['duration_ms'])


manager = JobManager()
