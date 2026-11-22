"""No credentials, database, model weights, or network needed."""
import asyncio
import copy
import sys
import time
import unittest
from unittest.mock import patch, Mock, AsyncMock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.research.schema import (SongIdentity, Source, Decision,
    SupportCheck, ProfileDraft, Rating, identity_matches, unknown_profile)
from services.research.schema import MusicalSelection, MusicalObservation, MusicalRating
from services.research.providers import source
from services.research.providers import HTTPResearchProvider
from services.research.graph import build_graph, research_song
from services.research.jobs import comparisons, JobManager
from services.local_llm import generation_lock, _lock
from services.research.model import LocalResearchModel

SONG = SongIdentity(genius_id='123', title='Test Song', artist='Test Artist')


class Provider:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.queries = []

    def capabilities(self):
        return {'search_reviews': True, 'search_context': True}

    async def search(self, name):
        self.calls.append(name)
        if self.fail and name == 'context':
            raise RuntimeError('Provider failed')
        return [source(f'https://example.com/{name}',
            'Test Song by Test Artist review', 'Test Song by Test Artist has driving drums.',
            'written_excerpt')]

    async def search_reviews(self, query):
        self.queries.append(query)
        return await self.search('reviews')

    async def search_context(self, query):
        return await self.search('context')



class Model:
    def __init__(self):
        self.calls = []

    async def describe_vibe(self, song, sources, deadline, reference=None):
        self.calls.append({'song': song, 'sources': sources, 'reference': reference})
        return ('Dreamy and relaxed, with a similarly intimate feel to your input song.' if reference else
                'Dreamy and relaxed, with an intimate atmosphere.')

    async def ask(self, *args):
        raise AssertionError('Vibe lookup must not invoke structured extraction or support checks')



class ResearchTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, provider=None, model=None, document=None):
        self.trace = []
        return await build_graph(provider or Provider(), model or Model(), lambda **event: self.trace.append(event)).ainvoke(
            {'song': SONG.model_dump(), 'document': document, 'deadline': time.monotonic()+5,
             'sources': [], 'findings': [], 'errors': []})

    async def test_one_search_and_one_plain_vibe_summary_without_checks(self):
        provider, model = Provider(), Model()
        result = await self.run_graph(provider, model)
        self.assertEqual(provider.calls, ['reviews'])
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(result['outcome'], 'vibe_ready')
        self.assertIn('Dreamy', result['vibe'])
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['profile'], unknown_profile())
        self.assertFalse(any(event['action'] in ('validate_claim', 'validate_rating', 'decision') for event in self.trace))


    async def test_failed_search_stops_without_model_calls(self):
        provider = Provider()
        provider.search_reviews = AsyncMock(side_effect=RuntimeError('Provider failed'))
        model = Mock()
        model.ask = AsyncMock(side_effect=AssertionError('No evidence'))
        result = await self.run_graph(provider, model)
        provider.search_reviews.assert_awaited_once()
        model.ask.assert_not_awaited()
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['errors'][0]['code'], 'RuntimeError')
        self.assertEqual(result['outcome'], 'search_failed')
        self.assertEqual(result['outcome_reason'], 'search_error')

    async def test_inference_timeout_does_not_discard_retrieved_sources(self):
        class TimeoutModel(Model):
            async def describe_vibe(self, *args, **kwargs):
                raise TimeoutError('Model unavailable')
        result = await self.run_graph(model=TimeoutModel())
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['outcome'], 'analysis_failed')
        self.assertEqual(result['outcome_reason'], 'timeout')


    async def test_quick_graph_never_calls_model_and_exposes_excerpts(self):
        class NoModel:
            async def ask(self, *args): raise AssertionError('Quick mode must not invoke inference')
        provider = Provider()
        result = await build_graph(provider, NoModel(), mode='quick').ainvoke({
            'song': SONG.model_dump(), 'document': None, 'deadline': time.monotonic()+5,
            'sources': [], 'findings': [], 'errors': []})
        self.assertEqual(provider.calls, ['reviews'])
        self.assertEqual(result['findings'], [])
        self.assertTrue(all(not item['identity_verified'] for item in result['sources']))
        self.assertEqual({item['research_role'] for item in result['sources']}, {'music'})
        self.assertEqual(result['outcome'], 'sources_only')

    async def test_each_request_researches_fresh_without_cache(self):
        provider = Provider()
        for mode in ('quick', 'deep', 'deep'):
            result = await research_song(SONG, None, provider, Model(), time.monotonic()+5,
                                         lambda **event: None, mode=mode)
            self.assertFalse(result['cached'])
            self.assertEqual(result['mode'], mode)
        self.assertEqual(provider.calls, ['reviews'] * 3)

    async def test_searches_overlap_while_inference_gate_is_busy(self):
        gate = asyncio.Semaphore(0)
        all_searched = asyncio.Event()
        class Parallel(Provider):
            async def search_reviews(self, query):
                self.calls.append('reviews')
                if len(self.calls) == 2:
                    all_searched.set()
                await asyncio.wait_for(all_searched.wait(), .5)
                return await self.search('result')
        provider = Parallel()
        tasks = [asyncio.create_task(research_song(SONG, None, provider, Model(),
            time.monotonic()+2, lambda **event: None, inference_gate=gate)) for _ in range(2)]
        try:
            await asyncio.wait_for(all_searched.wait(), .5)
            self.assertTrue(all(not task.done() for task in tasks))
        finally:
            gate.release()
            results = await asyncio.gather(*tasks)
        self.assertTrue(all(result['vibe'] for result in results))

    async def test_inference_gate_wait_obeys_song_deadline(self):
        result = await research_song(SONG, None, Provider(), Model(), time.monotonic()+.5,
                                    lambda **event: None, inference_gate=asyncio.Semaphore(0))
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['findings'], [])
        self.assertTrue(any(error['code'] == 'TimeoutError' for error in result['errors']))

    async def test_empty_search_stops_without_followup_in_both_modes(self):
        for mode in ('quick', 'deep'):
            provider = Provider()
            provider.search_reviews = AsyncMock(return_value=[])
            model = Mock()
            model.ask = AsyncMock(side_effect=AssertionError('No evidence'))
            result = await build_graph(provider, model, mode=mode).ainvoke({
                'song': SONG.model_dump(), 'deadline': time.monotonic()+5,
                'sources': [], 'findings': [], 'errors': []})
            provider.search_reviews.assert_awaited_once()
            model.ask.assert_not_awaited()
            self.assertEqual(result['findings'], [])
            self.assertEqual(result['outcome'], 'no_sources')

    async def test_query_looks_up_general_song_vibe(self):
        provider = Provider()
        await self.run_graph(provider)
        self.assertEqual(provider.calls, ['reviews'])
        for term in ('vibe', 'mood', 'atmosphere'):
            self.assertIn(term, provider.queries[0])

    async def test_plain_vibe_generation_uses_one_call_and_input_context(self):
        reference = {'song': SONG.model_dump(), 'vibe': 'Mellow and atmospheric.'}
        with patch('services.research.model.generate_local', return_value='Vibe: Dreamy, with a brighter feel than the input song.') as generation:
            result = await LocalResearchModel().describe_vibe(SONG.model_dump(), [source(
                'https://example.com/review', 'Test Song review', 'Airy vocals with a relaxed atmosphere.',
                'written_excerpt')], time.monotonic()+5, reference=reference)
        generation.assert_called_once()
        self.assertEqual(result, 'Dreamy, with a brighter feel than the input song.')
        messages = generation.call_args.args[0].to_messages()
        self.assertIn('plain prose', messages[0].content)
        self.assertIn('Mellow and atmospheric.', messages[1].content)

    async def test_empty_prose_fails_once_without_repair(self):
        with patch('services.research.model.generate_local', return_value='') as generation:
            with self.assertRaises(ValueError):
                await LocalResearchModel().describe_vibe(SONG.model_dump(), [], time.monotonic()+5)
            generation.assert_called_once()

    async def test_missing_input_vibe_still_allows_candidate_description(self):
        reference = asyncio.get_running_loop().create_future()
        reference.set_result({'song': SONG.model_dump(), 'vibe': None})
        model = Model()
        result = await research_song(SONG, None, Provider(), model, time.monotonic()+5,
                                     lambda **event: None, seed_profile=reference)
        self.assertTrue(result['vibe'])
        self.assertFalse(result['compares_to_seed'])
        self.assertIsNone(model.calls[0]['reference'])



    async def test_provider_requires_only_brave_and_filters_video_links(self):
        import httpx
        provider = HTTPResearchProvider()
        response = httpx.Response(200, json={'web': {'results': [
            {'url': 'https://example.com/review', 'title': 'Review', 'description': 'Driving drums'},
            {'url': 'https://www.youtube.com/watch?v=abcdefghijk', 'title': 'Video', 'description': 'Not written evidence'}]}})
        with patch.dict('os.environ', {'BRAVE_SEARCH_API_KEY': 'test-key'}, clear=True), patch.object(provider, '_get', return_value=response):
            self.assertEqual(provider.capabilities(), {'search_reviews': True, 'search_context': True})
            values = await provider.search_reviews('Test Song Test Artist review')
        self.assertEqual(len(values), 1)
        self.assertIsNone(values[0]['timestamp_seconds'])




    async def test_model_failure_preserves_sources_without_retry(self):
        class Broken(Model):
            async def describe_vibe(self, *args, **kwargs):
                self.calls.append('attempt')
                raise ValueError('Empty output')
        model = Broken()
        result = await self.run_graph(model=model)
        self.assertEqual(result['outcome'], 'analysis_failed')
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(result['sources']), 1)



    async def test_profile_payload_exposes_vibe_without_verified_claims(self):
        result = await research_song(SONG, None, Provider(), Model(),
                                     time.monotonic()+5, lambda **event: None)
        self.assertEqual(result['outcome'], 'vibe_ready')
        self.assertEqual(result['outcome_reason'], None)
        self.assertEqual(result['vibe_basis'], 'search_excerpts')
        self.assertFalse(result['compares_to_seed'])
        self.assertTrue(result['sources'])


    async def test_job_deadline_marks_search_and_analysis_failures_separately(self):
        import services.research.jobs as jobs
        document = {'song_id': '123', 'title': 'Test Song', 'artist': 'Test Artist'}
        for has_sources in (False, True):
            async def pending(song, doc, provider, model, deadline, trace, **kwargs):
                if has_sources:
                    trace(agent='music', action='evidence_ready', status='ok', sources=[source(
                        'https://example.com/review', 'Test Song by Test Artist',
                        'Test Song has driving drums.', 'written_excerpt')])
                await asyncio.sleep(5)
            manager = JobManager()
            with patch.object(jobs, 'research_song', side_effect=pending), \
                 patch.object(jobs, 'budget', return_value=.1):
                job_id = manager.start(document, [], mode='deep')
                await asyncio.gather(*manager.tasks)
            job = manager.snapshot(job_id)
            self.assertEqual(job['status'], 'partial')
            self.assertEqual(job['seed']['outcome'], 'analysis_failed' if has_sources else 'search_failed')
            self.assertEqual(job['seed']['outcome_reason'], 'timeout')
            self.assertEqual(bool(job['seed']['sources']), has_sources)


    async def test_provider_never_retries_transport_or_server_errors(self):
        import httpx
        for failure in ('transport', 'server'):
            client = AsyncMock()
            if failure == 'transport':
                client.get.side_effect = httpx.ConnectError('Unavailable')
            else:
                client.get.return_value = httpx.Response(503, request=httpx.Request('GET', 'https://example.com'))
            with patch('services.research.providers.httpx.AsyncClient') as factory:
                factory.return_value.__aenter__ = AsyncMock(return_value=client)
                factory.return_value.__aexit__ = AsyncMock(return_value=False)
                with self.assertRaises(httpx.HTTPError):
                    await HTTPResearchProvider()._get('https://example.com')
            client.get.assert_awaited_once()


    async def test_missing_provider_has_explicit_availability(self):
        provider = Provider()
        provider.capabilities = lambda: {}
        result = await self.run_graph(provider)
        self.assertEqual(provider.calls, [])
        self.assertTrue(any(error['code'] == 'provider_unavailable' for error in result['errors']))
        self.assertEqual(result['outcome'], 'search_failed')
        self.assertEqual(result['outcome_reason'], 'provider_unavailable')

    async def test_vibe_summary_does_not_run_lyric_interpretation(self):
        result = await self.run_graph(document={'lines': [{'text': 'I wait for you'}]})
        self.assertTrue(result['vibe'])
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['profile'], unknown_profile())



    async def test_deadline_handles_slow_provider(self):
        class Slow(Provider):
            async def search_reviews(self, query): await asyncio.sleep(5)
            async def search_context(self, query): await asyncio.sleep(5)
        result = await build_graph(Slow(), Model()).ainvoke({'song': SONG.model_dump(), 'document': None,
            'deadline': time.monotonic()+.03, 'sources': [], 'findings': [], 'errors': []})
        self.assertEqual(result['profile'], unknown_profile())
        self.assertTrue(any(error['code'] == 'TimeoutError' for error in result['errors']))

    async def test_json_schema_is_literal_and_repair_is_bounded(self):
        with patch('services.research.model.generate_local', side_effect=['invalid',
            '{"action":"finish","option":0,"reason":"Enough evidence"}']) as generation:
            result = await LocalResearchModel().ask(Decision, 'Choose an action.',
                {'available': ['finish']}, time.monotonic()+5)
            self.assertEqual(result.action, 'finish')
            self.assertEqual(generation.call_count, 2)
            self.assertIn('"properties"', generation.call_args[0][0].to_messages()[0].content)

    async def test_bad_json_cannot_cause_unbounded_retries(self):
        with patch('services.research.model.generate_local', return_value='invalid') as generation:
            with self.assertRaises(Exception):
                await LocalResearchModel().ask(Decision, 'Choose.', {}, time.monotonic()+5)
            self.assertEqual(generation.call_count, 2)



    async def test_stream_returns_candidates_without_inference(self):
        from app.routers import recommend
        matches = [{'id': '123', 'metadata': {'title': 'Test Song', 'artist': 'Test Artist'}}]
        with patch.object(recommend, 'retrieve_base', return_value=({}, matches)), \
             patch('services.rag.explain_match') as explanation:
            result = await recommend.recommend_stream('Test Song', 'Test Artist')
        self.assertEqual(result['recommendations'], matches)
        explanation.assert_not_called()

    async def test_job_describes_each_candidate_using_input_vibe(self):
        import services.research.jobs as jobs
        document = {'song_id': '123', 'title': 'Test Song', 'artist': 'Test Artist',
                    'source_url': 'https://genius.com/test',
                    'lines': [{'id': 'L1', 'section': 'Chorus', 'text': 'I wait for you'}]}
        model = Model()
        def fetch(client, song_id):
            if song_id == '2':
                raise ValueError('Unavailable song')
            return {**document, 'song_id': song_id}
        manager = JobManager()
        with patch.object(jobs, 'HTTPResearchProvider', return_value=Provider()), \
             patch.object(jobs, 'LocalResearchModel', return_value=model), \
             patch('services.lyric_retrieval.make_genius_client', return_value=Mock()), \
             patch('services.lyric_retrieval.fetch_song_document', side_effect=fetch), \
             patch('services.rag.explain_match', side_effect=AssertionError('No extra lyric model calls')):
            job_id = manager.start(document, [{'id': '1'}, {'id': '2'}, {'id': '3'}])
            await asyncio.gather(*manager.tasks)
        job = manager.snapshot(job_id)
        self.assertEqual(job['mode'], 'vibe')
        self.assertEqual(job['status'], 'partial')
        self.assertEqual(job['results']['2']['status'], 'unavailable')
        self.assertEqual(len(model.calls), 3)
        self.assertIsNone(model.calls[0]['reference'])
        for call in model.calls[1:]:
            self.assertEqual(call['reference']['vibe'], job['seed']['vibe'])
        for song_id in ('1', '3'):
            result = job['results'][song_id]
            self.assertTrue(result['profile']['compares_to_seed'])
            self.assertEqual(result['vibe_description'], result['profile']['vibe'])
            self.assertIsNone(result['explanation'])

    async def test_catalog_source_jobs_do_not_require_lyric_documents(self):
        import services.research.jobs as jobs
        seed = {'song_id': '123', 'title': 'Test Song', 'artist': 'Test Artist'}
        matches = [{'id': '456', 'metadata': {'title': 'Test Song', 'artist': ['Test Artist']}}]
        for mode in ('lyrics_links', 'quick', 'vibe'):
            with self.subTest(mode=mode):
                provider, model, manager = Provider(), Model(), JobManager()
                with patch.object(jobs, 'HTTPResearchProvider', return_value=provider), \
                     patch.object(jobs, 'LocalResearchModel', return_value=model), \
                     patch('services.lyric_retrieval.fetch_song_source_url', side_effect=lambda song_id: f'https://genius.com/{song_id}'), \
                     patch('services.lyric_retrieval.fetch_song_document', side_effect=AssertionError('Catalog lookup must skip lyrics pages')):
                    job_id = manager.start(seed, matches, mode=mode)
                    await asyncio.gather(*manager.tasks)
                job = manager.snapshot(job_id)
                result = job['results']['456']
                self.assertEqual(job['status'], 'complete')
                self.assertEqual(result['sources'], {'seed': 'https://genius.com/123', 'candidate': 'https://genius.com/456'})
                if mode == 'vibe':
                    self.assertEqual(len(provider.calls), 2)
                    self.assertEqual(len(model.calls), 2)
                    self.assertEqual(model.calls[1]['reference']['vibe'], job['seed']['vibe'])
                    self.assertEqual(result['status'], 'complete')
                elif mode == 'quick':
                    self.assertEqual(model.calls, [])
                    self.assertEqual(len(provider.calls), 2)
                    self.assertEqual(result['profile']['outcome'], 'sources_only')
                else:
                    self.assertEqual(model.calls, [])
                    self.assertEqual(provider.calls, [])
                    self.assertIsNone(result['profile'])

    async def test_hosted_model_uses_gateway_without_loading_local_model(self):
        import httpx

        response = httpx.Response(200, request=httpx.Request('POST', 'https://ai-gateway.vercel.sh/v1/chat/completions'),
                                  json={'choices': [{'message': {'content': 'It feels mellow and reflective.'}}]})
        client = AsyncMock()
        client.__aenter__.return_value.post.return_value = response
        with patch.dict('os.environ', {'AI_GATEWAY_API_KEY': 'test-key', 'RESEARCH_GATEWAY_MODEL': 'test-model'}), \
             patch('services.research.model.httpx.AsyncClient', return_value=client), \
             patch('services.research.model.generate_local', side_effect=AssertionError('Local inference is disabled')):
            summary = await LocalResearchModel().describe_vibe(SONG.model_dump(), [
                {'title': 'Review', 'text': 'A mellow and reflective recording.'},
            ], time.monotonic() + 5)
        self.assertEqual(summary, 'It feels mellow and reflective.')
        args = client.__aenter__.return_value.post.call_args.kwargs
        self.assertEqual(args['json']['model'], 'test-model')
        self.assertIn('A mellow and reflective recording.', args['json']['messages'][1]['content'])


    async def test_seed_context_wait_does_not_block_parallel_searches(self):
        future = asyncio.get_running_loop().create_future()
        model, provider = Model(), Provider()
        searched = asyncio.Event()
        def trace(**event):
            if event['action'] == 'evidence_ready':
                searched.set()
        task = asyncio.create_task(research_song(SONG, None, provider, model,
            time.monotonic()+3, trace, seed_profile=future))
        await asyncio.wait_for(searched.wait(), 1)
        self.assertEqual(model.calls, [])
        future.set_result({'song': SONG.model_dump(), 'vibe': 'Mellow and atmospheric.'})
        result = await task
        self.assertTrue(result['compares_to_seed'])
        self.assertEqual(model.calls[0]['reference']['vibe'], 'Mellow and atmospheric.')


    def test_version_and_artist_disambiguation(self):
        remix = Source.model_validate(source('https://example.com', 'Test Song Remix by Test Artist', 'Test Song Test Artist', 'written_excerpt'))
        self.assertFalse(identity_matches(SONG, remix))
        self.assertNotEqual(SONG.cache_key(), SONG.model_copy(update={'version': 'remix'}).cache_key())
        wrong = remix.model_copy(update={'title': 'Different song', 'text': 'Different artist'})
        self.assertFalse(identity_matches(SONG, wrong))

    def test_written_sources_never_fabricate_timestamps(self):
        self.assertIsNone(source('https://example.com/review', 'Review', 'Driving drums.', 'written_excerpt')['timestamp_seconds'])

    def test_different_excerpts_at_same_url_cannot_overwrite_provenance(self):
        first = source('https://example.com/review', 'Review', 'Driving drums.', 'written_excerpt')
        second = source('https://example.com/review', 'Review', 'Soft acoustic guitar.', 'written_excerpt')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['id'], source('https://example.com/review', 'Review', 'Driving drums.', 'written_excerpt')['id'])

    def test_comparison_skips_unknowns_and_preserves_refs(self):
        seed = {'profile': unknown_profile()}
        candidate = copy.deepcopy(seed)
        seed['profile']['musical_characteristics'][0].update(level='high', finding_ids=[0])
        candidate['profile']['musical_characteristics'][0].update(level='low', finding_ids=[1])
        comparison = comparisons(seed, candidate)
        self.assertEqual(len(comparison['differences']), 1)
        self.assertEqual(comparison['differences'][0]['seed_finding_ids'], [0])

    def test_job_admission_bound_preserves_base_flow(self):
        manager = JobManager()
        manager.jobs = {str(i): {'status': 'running', 'created_at': time.time()} for i in range(2)}
        self.assertIsNone(manager.start({}, []))

    def test_local_model_queue_obeys_deadline(self):
        _lock.acquire()
        try:
            with self.assertRaises(TimeoutError):
                with generation_lock(time.monotonic()+.01): pass
        finally:
            _lock.release()


if __name__ == '__main__':
    unittest.main()
