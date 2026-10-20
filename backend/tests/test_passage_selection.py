"""Pure passage-selection checks; no sockets, model, credentials or database."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.passage_retrieval import representative_passages, lyric_overlap


def document(sections=12):
    return {'lines': [{'id': f'L{s*6+i+1}', 'section': f'Verse {s}',
                       'text': f'memory river journey section{s} detail{i}'}
                      for s in range(sections) for i in range(6)]}


class PassageSelectionTests(unittest.TestCase):
    def test_spans_opening_middle_and_ending(self):
        result = representative_passages(document())
        sections = [int(group[0]['section'].split()[-1]) for group in result]
        self.assertTrue(any(s < 3 for s in sections))
        self.assertTrue(any(3 <= s < 9 for s in sections))
        self.assertTrue(any(s >= 9 for s in sections))
        self.assertLessEqual(len(result), 4)

    def test_small_song_includes_all_lines(self):
        original = document(3)
        result = representative_passages(original)
        self.assertEqual([row['id'] for group in result for row in group], [row['id'] for row in original['lines']])

    def test_character_budget_reserves_space_for_end(self):
        result = representative_passages(document(), max_chars=500)
        self.assertLessEqual(sum(len(row['text'])+1 for group in result for row in group), 500)
        self.assertTrue(any(int(group[0]['section'].split()[-1]) >= 9 for group in result))

    def test_repeated_choruses_are_deduplicated(self):
        original = document(1)
        original['lines'] *= 4
        result = representative_passages(original)
        self.assertEqual(sum(len(group) for group in result), 6)

    def test_overlap_looks_beyond_first_twelve_lines(self):
        left, right = document(4), document(4)
        left['lines'][-1]['text'] = right['lines'][-1]['text'] = 'reconciliation'
        result = lyric_overlap(left, right)
        self.assertIn('reconciliation', result['shared_words'])
        self.assertEqual(result['seed_lines_scanned'], 24)
        self.assertEqual(len(result['seed_sections']), 4)

    def test_empty_documents_are_safe(self):
        self.assertEqual(representative_passages({'lines': []}), [])
        self.assertEqual(lyric_overlap({'lines': []}, {'lines': []})['shared_words'], [])


if __name__ == '__main__':
    unittest.main()
