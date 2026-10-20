"""Pure state/budget checks: no event loop or network required."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.research.model import InferenceBudget
from services.research.jobs import publish_profile, has_analysis, budget
from services.research.schema import unknown_profile, SongIdentity, Source, identity_matches


class ResearchStateTests(unittest.TestCase):
    def test_job_budget_cannot_schedule_unlimited_inference(self):
        counter = InferenceBudget(2)
        counter.reserve()
        counter.reserve()
        with self.assertRaises(TimeoutError):
            counter.reserve()

    def test_retrieved_sources_can_publish_without_model_profile(self):
        job = {'seed': None, 'results': {'2': {'profile': None, 'status': 'running'}}}
        partial = {'sources': [{'id': 'review', 'text': 'Actual review excerpt'}],
                   'profile': unknown_profile(), 'findings': [], 'analysis_status': 'running'}
        publish_profile(job, '2', '1', partial)
        self.assertEqual(job['results']['2']['profile']['sources'][0]['text'], 'Actual review excerpt')
        job['results']['2']['status'] = 'unavailable'
        self.assertEqual(len(job['results']['2']['profile']['sources']), 1)

    def test_seed_progress_is_separate_from_candidates(self):
        job = {'seed': None, 'results': {}}
        publish_profile(job, '1', '1', {'sources': []})
        self.assertIsNotNone(job['seed'])
        self.assertEqual(job['results'], {})

    def test_unknown_grid_is_not_successful_analysis(self):
        self.assertFalse(has_analysis({'profile': unknown_profile(), 'findings': []}))
        self.assertTrue(has_analysis({'profile': unknown_profile(), 'findings': [{'claim': 'Supported observation'}]}))

    def test_old_large_environment_timeout_is_clamped(self):
        with patch.dict('os.environ', {'RESEARCH_JOB_SECONDS': '900'}):
            self.assertEqual(budget('RESEARCH_JOB_SECONDS', 120, 120), 120)

    def test_delivers_is_not_a_live_recording(self):
        song = SongIdentity(genius_id='1', title='7 Minute Drill', artist='J. Cole')
        item = Source(id='1', url='https://example.com/review', title='J. Cole delivers 7 Minute Drill',
                      text='A review of 7 Minute Drill by J. Cole.', kind='written_excerpt', retrieved_at=0)
        self.assertTrue(identity_matches(song, item))
        self.assertFalse(identity_matches(song, item.model_copy(update={'title': 'J. Cole 7 Minute Drill live review'})))


if __name__ == '__main__':
    unittest.main()
