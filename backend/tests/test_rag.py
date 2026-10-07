"""Offline checks: no model calls, keys, database, or network required."""
import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.rag import SongExplanation, validate_and_enrich, explain_match
from services import rag, local_llm

with patch.dict(sys.modules, {'lyricsgenius': SimpleNamespace(Genius=Mock())}):
    retrieval = importlib.import_module('services.lyric_retrieval')
with patch.dict(sys.modules, {
    'services.pinecone_utils': SimpleNamespace(query_vector=Mock()),
    'services.lyric_retrieval': retrieval,
}):
    route = importlib.import_module('app.routers.recommend')


def song(song_id=1):
    return SimpleNamespace(id=song_id, title='Test',
                           primary_artist=SimpleNamespace(name='Artist'),
                           url='https://genius.com/test',
                           lyrics='2 ContributorsTest Lyrics\nRead More\n[Verse 1]\nA memory\n[Chorus]\nA return\n12Embed')


class RagTests(unittest.TestCase):
    def test_backend_builds_citations_from_plain_prose(self):
        document = retrieval.song_to_document(song())
        rag.get_explanation_chain.cache_clear()
        try:
            with patch.object(local_llm, 'generate_local', return_value='Both passages reflect on memories.'):
                result = rag.explain_match(document, document)
                self.assertEqual(result['summary'], 'Both passages reflect on memories.')
                self.assertTrue(result['evidence'][0]['candidate_line_ids'])
                self.assertTrue(result['evidence'][0]['seed_line_ids'])
                self.assertEqual(result['shared_themes'], [])
        finally:
            rag.get_explanation_chain.cache_clear()

    def test_passage_selection_preserves_ids(self):
        from services.passage_retrieval import select_passages
        doc = retrieval.song_to_document(song())
        left, right = select_passages(doc, doc)
        self.assertEqual([line['id'] for line in left], ['L1'])
        self.assertEqual(left, right)

    def test_local_enabled_without_provider_key(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertTrue(rag.is_configured())
            self.assertEqual(local_llm.model_name(), 'Qwen/Qwen3-0.6B')
        with patch.dict('os.environ', {'RAG_ENABLED': 'false'}):
            self.assertFalse(rag.is_configured())

    def test_local_chain_accepts_labels_and_rejects_empty_output(self):
        document = retrieval.song_to_document(song())
        rag.get_explanation_chain.cache_clear()
        try:
            with patch.object(local_llm, 'generate_local', return_value='Summary: Shared memories\nThemes: memory, nostalgia\nDifference: None clear') as generate:
                result = rag.explain_match(document, document)
                self.assertEqual(result['summary'], 'Shared memories')
                self.assertEqual(result['shared_themes'], ['memory', 'nostalgia'])
                self.assertIn('NOT JSON', generate.call_args[0][0].to_messages()[0].content)
            rag.get_explanation_chain.cache_clear()
            with patch.object(local_llm, 'generate_local', return_value=''):
                with self.assertRaises(rag.ExplanationUnavailableError):
                    rag.explain_match(document, document)
        finally:
            rag.get_explanation_chain.cache_clear()

    def test_local_generation_decodes_only_completion(self):
        tokenizer = Mock()
        inputs = {'input_ids': SimpleNamespace(shape=(1, 3))}
        tokenizer.return_value.to.return_value = inputs
        tokenizer.eos_token_id = 9
        tokenizer.decode.return_value = '{}'
        model = Mock(device='cpu')
        model.generate.return_value = [[1, 2, 3, 4]]
        prompt = Mock()
        prompt.to_messages.return_value = [SimpleNamespace(type='human', content='Compare')]
        torch = MagicMock()
        with patch.dict(sys.modules, {'torch': torch}), \
             patch.object(local_llm, 'load_model', return_value=(tokenizer, model)):
            self.assertEqual(local_llm.generate_local(prompt), '{}')
        tokenizer.decode.assert_called_once_with([4], skip_special_tokens=True)
        self.assertFalse(tokenizer.apply_chat_template.call_args.kwargs['enable_thinking'])
        self.assertEqual(model.generate.call_args.kwargs['max_new_tokens'], 512)

    def test_cleaning_and_sections(self):
        doc = retrieval.song_to_document(song())
        self.assertEqual([line['text'] for line in doc['lines']], ['A memory', 'A return'])
        self.assertEqual(doc['lines'][1]['section'], 'Chorus')
        self.assertEqual(doc['lines'][1]['id'], 'L2')

    def test_new_genius_metadata_format(self):
        modern = song()
        del modern.id
        modern.primary_artist = {'name': 'Artist'}
        modern.to_dict = lambda: {'id': 1}
        doc = retrieval.song_to_document(modern)
        self.assertEqual(doc['song_id'], '1')
        self.assertEqual(doc['artist'], 'Artist')

    def test_missing_or_wrong_song(self):
        client = Mock()
        client.search_song.return_value = None
        self.assertIsNone(retrieval.fetch_song_document(client, '1'))
        client.search_song.return_value = song(2)
        self.assertIsNone(retrieval.fetch_song_document(client, '1'))

    def test_title_search_retries_empty_response(self):
        client = Mock()
        client.search_song.side_effect = [None, song()]
        with patch.object(retrieval.time, 'sleep') as sleep:
            found = retrieval.search_song_with_retry(client, ' Test ', ' Artist ')
        self.assertEqual(found.title, 'Test')
        self.assertEqual(client.search_song.call_count, 2)
        client.search_song.assert_called_with(title='Test', artist='Artist')
        sleep.assert_called_once_with(0.5)
        client.search_song.side_effect = [None, None]
        with patch.object(retrieval.time, 'sleep'):
            self.assertIsNone(retrieval.search_song_with_retry(client, 'Test', 'Artist'))
    def test_validate_evidence(self):
        doc = retrieval.song_to_document(song())
        result = SongExplanation(summary='Shared memories', shared_themes=['memory'],
                                 difference='None clear', evidence=[{
                                     'seed_line_ids': ['L1'], 'candidate_line_ids': ['L2'],
                                     'reason': 'Related themes'}])
        enriched = validate_and_enrich(result, doc, doc)
        self.assertEqual(enriched['evidence'][0]['candidate_sections'], ['Chorus'])
        result.evidence[0].candidate_line_ids = ['L999']
        with self.assertRaises(ValueError):
            validate_and_enrich(result, doc, doc)

    def test_large_context_never_calls_model(self):
        with patch('services.rag.get_explanation_chain') as chain:
            with self.assertRaises(ValueError):
                explain_match({'text': 'a' * 25000}, {})
            chain.assert_not_called()

    def run_recommendation(self, configured=True, candidate=True, failure=False):
        client = Mock()
        client.search_song.return_value = song()
        match = {'id': '2', 'score': 0.7, 'metadata': {'title': 'Candidate'}}
        with patch.object(route, 'make_genius_client', return_value=client), \
             patch.object(route, 'query_vector', return_value=[match]), \
             patch.object(route, 'is_configured', return_value=configured), \
             patch.object(route, 'fetch_song_document', return_value=retrieval.song_to_document(song(2)) if candidate else None) as fetch, \
             patch.object(route, 'explain_match', side_effect=RuntimeError('Model down') if failure else None, return_value={'summary': 'Grounded comparison'}) as explain:
            if failure:
                with self.assertLogs(route.logger, level='ERROR'):
                    result = route.recommend_songs('Test', 'Artist')[0]
            else:
                result = route.recommend_songs('Test', 'Artist')[0]
            if not configured:
                fetch.assert_not_called()
                explain.assert_not_called()
            return result

    def test_success(self):
        result = self.run_recommendation()
        self.assertEqual(result['explanation_status'], 'complete')
        self.assertIn('candidate', result['sources'])

    def test_disabled(self):
        self.assertEqual(self.run_recommendation(configured=False)['explanation_status'], 'disabled')

    def test_missing_lyrics_and_model_failure_keep_matches(self):
        for options in ({'candidate': False}, {'failure': True}):
            result = self.run_recommendation(**options)
            self.assertEqual(result['id'], '2')
            self.assertIsNone(result['explanation'])
            self.assertEqual(result['explanation_status'], 'unavailable')

    def test_pinecone_excludes_seed_by_id_and_indexes_missing_seed(self):
        index = Mock()
        index.query.return_value = SimpleNamespace(matches=[
            SimpleNamespace(id='2', score=0.9, metadata={}),
            SimpleNamespace(id='1', score=0.8, metadata={}),
            SimpleNamespace(id='3', score=0.7, metadata={}),
        ])
        pc = Mock()
        pc.Index.return_value = index
        process = Mock(return_value='1')
        with patch.dict(sys.modules, {
            'pinecone': SimpleNamespace(Pinecone=Mock(return_value=pc)),
            'services.genius': SimpleNamespace(process_song=process),
        }):
            module = importlib.import_module('services.pinecone_utils')
            with patch.object(module, 'fetch_vector', side_effect=[False, True]):
                result = module.query_vector(1, 'Test', 'Artist')
            self.assertEqual([item['id'] for item in result], ['2', '3'])
            process.assert_called_once_with('Test', 'Artist')
            index.query.assert_called_once()
            with patch.object(module, 'fetch_vector', side_effect=[False, False, True]), \
                 patch.object(module.time, 'sleep') as sleep:
                self.assertTrue(module.wait_for_vector('1'))
                self.assertEqual(sleep.call_count, 2)
            with patch.object(module, 'fetch_vector', return_value=False), \
                 patch.object(module.time, 'sleep') as sleep:
                self.assertFalse(module.wait_for_vector('1'))
                self.assertEqual(sleep.call_count, 5)


if __name__ == '__main__':
    unittest.main()
