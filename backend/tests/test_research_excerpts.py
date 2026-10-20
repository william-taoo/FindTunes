import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.research.excerpts import clean_excerpt, relevant_excerpt
from services.research.schema import SongIdentity, Source


class ExcerptTests(unittest.TestCase):
    def setUp(self):
        self.song = SongIdentity(genius_id='1', title='XO Tour Llif3', artist='Lil Uzi Vert')

    def excerpt(self, title, text):
        return relevant_excerpt(self.song, Source(id='1', url='https://example.com',
            title=title, text=text, kind='written_excerpt', retrieved_at=0))

    def test_search_html_is_plain_text(self):
        self.assertEqual(clean_excerpt('<strong>Lil</strong> Uzi&#x27;s &quot;song&quot;'), 'Lil Uzi\'s "song"')

    def test_biography_is_not_musical_evidence(self):
        self.assertEqual(self.excerpt('Lil Uzi Vert', 'After releasing an additional mixtape and EP, Lil Uzi Vert guest appeared on Migos\' single. They secured their first top ten single with XO Tour Llif3, which won the MTV Video Music Award.'), '')

    def test_song_page_keeps_musical_sentences_and_removes_chart_info(self):
        self.assertEqual(self.excerpt('XO Tour Llif3 review', 'It peaked atop the chart. The vocals are brooding over distorted bass.'),
                         'The vocals are brooding over distorted bass.')

    def test_general_page_needs_song_in_musical_sentence(self):
        self.assertEqual(self.excerpt('Lil Uzi Vert biography', 'XO Tour Llif3 was released in 2017. Another song features acoustic guitars.'), '')

    def test_song_observation_on_album_page_is_kept(self):
        self.assertTrue(self.excerpt('Album review', 'XO Tour Llif3 features brooding vocals.'))

    def test_duplicate_snippets_are_removed(self):
        self.assertEqual(self.excerpt('XO Tour Llif3 review', 'The guitar sounds dreamy.\nThe guitar sounds dreamy.'), 'The guitar sounds dreamy.')


if __name__ == '__main__':
    unittest.main()
