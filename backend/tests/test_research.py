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
from services.research.schema import ObservationSelection, ObservationChoice
from services.research.providers import source
from services.research.providers import HTTPResearchProvider
from services.research.graph import build_graph, research_song
from services.research.cache import MemoryCache
from services.research.jobs import comparisons, JobManager
from services.local_llm import generation_lock, _lock
from services.research.model import LocalResearchModel

SONG = SongIdentity(genius_id='123', title='Test Song', artist='Test Artist')


class Provider:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.started = 0
        self.both_started = asyncio.Event()

    def capabilities(self):
        return {'search_reviews': True, 'search_context': True}

    async def search(self, name):
        self.calls.append(name)
        self.started += 1
        if self.started >= 2:
            self.both_started.set()
        await asyncio.wait_for(self.both_started.wait(), 1)
        if self.fail and name == 'context':
            raise RuntimeError('Provider failed')
        return [source(f'https://example.com/{name}',
            'Test Song by Test Artist review', 'Test Song by Test Artist has driving drums.',
            'written_excerpt')]

    async def search_reviews(self, query):
        return await self.search('reviews')

    async def search_context(self, query):
        return await self.search('context')



class Model:
    def __init__(self, forged=False, unsupported=False):
        self.forged = forged
        self.unsupported = unsupported

    async def ask(self, schema, instruction, context, deadline):
        if schema is Decision:
            action = 'search' if context['round'] == 0 else 'finish'
            return Decision(action=action, option=0, reason='Need relevant written evidence')
        if schema is ObservationSelection:
            if 'lyrical_emotions / lyrical_interpretation' in instruction:
                return ObservationSelection(observations=[ObservationChoice(claim='The narrator longs for someone.', source_index=0, sentence_index=0)])
            return ObservationSelection(observations=[ObservationChoice(claim='The reviewer describes driving drums.',
                source_index=0, sentence_index=19 if self.forged else 0)])
        if schema is SupportCheck:
            return SupportCheck(supported=not self.unsupported, exact_song_version=True, reason='Evidence check')
        if schema is ProfileDraft:
            musical = [i for i, finding in enumerate(context['findings']) if finding['category'] == 'musical_characteristics']
            return ProfileDraft(musical_characteristics=[Rating(label='energy', level='high',
                explanation='Reviewers describe driving drums.', finding_ids=musical)])
        raise AssertionError(schema)


class ResearchTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, provider=None, model=None, document=None):
        self.trace = []
        return await build_graph(provider or Provider(), model or Model(), lambda **event: self.trace.append(event)).ainvoke(
            {'song': SONG.model_dump(), 'document': document, 'deadline': time.monotonic()+5,
             'sources': [], 'findings': [], 'errors': []})

    async def test_parallel_external_io_and_agent_tool_choice(self):
        provider = Provider()
        result = await self.run_graph(provider)
        self.assertTrue(provider.both_started.is_set())
        self.assertEqual(provider.calls.count('context'), 1)
        self.assertEqual(provider.calls.count('reviews'), 1)
        self.assertTrue(all(item['kind'] == 'written_excerpt' for item in result['sources']))
        self.assertEqual(len([event for event in self.trace if event['action'] == 'decision']), 0)
        self.assertEqual(len([event for event in self.trace if event['action'] == 'evidence_ready']), 2)
        self.assertEqual(result['profile']['musical_characteristics'][0]['level'], 'high')

    async def test_partial_failure_preserves_other_agent(self):
        result = await self.run_graph(Provider(fail=True))
        self.assertTrue(result['findings'])
        self.assertTrue(any(error['agent'] == 'context' for error in result['errors']))

    async def test_inference_timeout_does_not_discard_retrieved_sources(self):
        class TimeoutModel(Model):
            async def ask(self, schema, instruction, context, deadline):
                if schema is ObservationSelection:
                    raise TimeoutError('Simulated model queue timeout')
                return await super().ask(schema, instruction, context, deadline)
        result = await self.run_graph(model=TimeoutModel())
        self.assertEqual(len(result['sources']), 2)
        self.assertEqual(result['findings'], [])
        self.assertTrue(any(error['code'] == 'TimeoutError' for error in result['errors']))
        self.assertEqual(len([event for event in self.trace if event['action'] == 'evidence_ready']), 2)

    async def test_quick_graph_never_calls_model_and_exposes_excerpts(self):
        class NoModel:
            async def ask(self, *args): raise AssertionError('Quick mode must not invoke inference')
        provider = Provider()
        result = await build_graph(provider, NoModel(), mode='quick').ainvoke({
            'song': SONG.model_dump(), 'document': None, 'deadline': time.monotonic()+5,
            'sources': [], 'findings': [], 'errors': []})
        self.assertEqual(sorted(provider.calls), ['context', 'reviews'])
        self.assertEqual(result['findings'], [])
        self.assertTrue(all(not item['identity_verified'] for item in result['sources']))
        self.assertEqual({item['research_role'] for item in result['sources']}, {'reviews', 'context'})

    async def test_quick_and_deep_caches_are_separate(self):
        cache, provider = MemoryCache(), Provider()
        quick = await research_song(SONG, None, provider, Model(), cache, time.monotonic()+5, lambda **event: None, mode='quick')
        count = len(provider.calls)
        deep = await research_song(SONG, None, provider, Model(), cache, time.monotonic()+5, lambda **event: None, mode='deep')
        self.assertFalse(deep['cached'])
        self.assertGreater(len(provider.calls), count)
        self.assertEqual(quick['mode'], 'quick')

    async def test_agent_can_retry_a_different_query_after_search_failure(self):
        class FirstReviewFails(Provider):
            async def search_reviews(self, query):
                self.review_attempts = getattr(self, 'review_attempts', 0) + 1
                values = await self.search('reviews')
                if self.review_attempts == 1:
                    raise RuntimeError('Search temporarily unavailable')
                return values
        class Retry(Model):
            async def ask(self, schema, instruction, context, deadline):
                if schema is Decision and 'You are the reviews' in instruction and context['round'] == 1:
                    self.assert_errors = context['errors']
                    return Decision(action='search', option=1, reason='Try a different review query')
                return await super().ask(schema, instruction, context, deadline)
        model = Retry()
        provider = FirstReviewFails()
        result = await self.run_graph(provider, model)
        self.assertTrue(model.assert_errors)
        self.assertEqual(provider.calls.count('reviews'), 2)
        self.assertTrue(result['findings'])

    async def test_roles_use_distinct_queries_and_scoped_tools(self):
        class Capture(Model):
            def __init__(self):
                super().__init__()
                self.roles = {}
            async def ask(self, schema, instruction, context, deadline):
                if schema is SupportCheck:
                    return SupportCheck(supported=False, exact_song_version=True, reason='Need a more specific excerpt')
                if schema is Decision:
                    role = 'reviews' if 'You are the reviews' in instruction else 'context'
                    self.roles[role] = context
                return await super().ask(schema, instruction, context, deadline)
        model = Capture()
        await self.run_graph(model=model)
        self.assertNotEqual(model.roles['reviews']['queries'], model.roles['context']['queries'])
        self.assertIn('search', model.roles['reviews']['available'])
        self.assertNotIn('search_context', model.roles['reviews']['available'])
        self.assertIn('search', model.roles['context']['available'])
        self.assertTrue(all('interview' in query or 'commentary' in query for query in model.roles['context']['queries']))

    async def test_rejects_album_only_claims_and_wrong_song_evidence(self):
        class AlbumOnly(Model):
            async def ask(self, schema, instruction, context, deadline):
                if schema is SupportCheck:
                    return SupportCheck(supported=False, exact_song_version=False,
                        reason='Album-wide evidence does not establish this track claim')
                return await super().ask(schema, instruction, context, deadline)
        result = await self.run_graph(model=AlbumOnly())
        self.assertEqual(result['findings'], [])

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

    async def test_forged_quote_is_rejected(self):
        result = await self.run_graph(model=Model(forged=True))
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['profile'], unknown_profile())

    async def test_real_reference_does_not_prove_support(self):
        result = await self.run_graph(model=Model(unsupported=True))
        self.assertEqual(result['findings'], [])

    async def test_cache_reuses_research_without_io(self):
        cache = MemoryCache()
        provider = Provider()
        first = await research_song(SONG, None, provider, Model(), cache, time.monotonic()+5, lambda **event: None)
        count = len(provider.calls)
        second = await research_song(SONG, None, provider, Model(), cache, time.monotonic()+5, lambda **event: None)
        self.assertTrue(second['cached'])
        self.assertEqual(count, len(provider.calls))
        self.assertEqual(first['profile'], second['profile'])

    async def test_cache_failure_is_nonfatal(self):
        class Broken:
            async def get(self, key): raise RuntimeError()
            async def put(self, key, payload): raise RuntimeError()
        result = await research_song(SONG, None, Provider(), Model(), Broken(), time.monotonic()+5, lambda **event: None)
        self.assertTrue(result['findings'])
        self.assertTrue(any(error['code'] == 'cache_write_failed' for error in result['errors']))

    async def test_missing_provider_has_explicit_availability(self):
        provider = Provider()
        provider.capabilities = lambda: {}
        result = await self.run_graph(provider)
        self.assertEqual(provider.calls, [])
        self.assertTrue(any(error['code'] == 'provider_unavailable' for error in result['errors']))

    async def test_lyrics_never_establish_sound(self):
        document = {'source_url': 'https://genius.com/test', 'lines': [{'id': 'L1', 'section': 'Chorus', 'text': 'I wait for you every night'}]}
        result = await self.run_graph(model=Model(forged=True), document=document)
        self.assertTrue(any(f['category'] == 'lyrical_emotions' for f in result['findings']))
        self.assertTrue(all(row['level'] == 'unknown' for row in result['profile']['musical_characteristics']))

    async def test_invalid_tool_choice_is_bounded(self):
        class Bad(Model):
            async def ask(self, schema, instruction, context, deadline):
                if schema is ObservationSelection: return ObservationSelection(observations=[])
                if schema is Decision: return Decision(action='search', option=9, reason='Bad index')
                return await super().ask(schema, instruction, context, deadline)
        provider = Provider()
        result = await self.run_graph(provider, Bad())
        self.assertEqual(sorted(provider.calls), ['context', 'reviews'])
        self.assertEqual(result['findings'], [])

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

    async def test_background_job_keeps_success_when_one_candidate_fails(self):
        import services.research.jobs as jobs
        document = {'song_id': '123', 'title': 'Test Song', 'artist': 'Test Artist',
                    'source_url': 'https://genius.com/test', 'lines': [{'id': 'L1', 'section': 'Chorus', 'text': 'I wait for you'}]}
        payload = {'profile': unknown_profile(), 'findings': [], 'sources': [], 'errors': []}
        async def profile(*args, **kwargs): return copy.deepcopy(payload)
        def fetch(client, song_id):
            if song_id == '2': raise ValueError('Missing song')
            return document
        manager = JobManager()
        with patch.object(jobs, 'research_song', side_effect=profile), \
             patch.object(jobs, 'LocalResearchModel', return_value=Model()), \
             patch.object(jobs, 'PostgresCache', return_value=MemoryCache()), \
             patch('services.lyric_retrieval.make_genius_client', return_value=Mock()), \
             patch('services.lyric_retrieval.fetch_song_document', side_effect=fetch), \
             patch('services.rag.explain_match', return_value={'summary': 'Shared longing'}), \
             patch.object(jobs, 'TRACE_DIR', Path(__file__).resolve().parents[1] / '.research-traces'):
            job_id = manager.start(document, [{'id': '1'}, {'id': '2'}], mode='deep')
            await asyncio.gather(*manager.tasks)
        job = manager.snapshot(job_id)
        self.assertEqual(job['status'], 'partial')
        self.assertEqual(job['results']['1']['explanation']['summary'], 'Shared longing')
        self.assertEqual(job['results']['2']['status'], 'unavailable')

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
