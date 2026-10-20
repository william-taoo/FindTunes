"""Cheap discovery filters; passing these checks is not claim verification."""
import html
from html.parser import HTMLParser
import re


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_excerpt(value):
    parser = _Text()
    parser.feed(value or '')
    return re.sub(r'\s+', ' ', html.unescape(''.join(parser.parts))).strip()


def relevant_excerpt(song, source):
    """Keep song-specific musical commentary, not artist chart biographies.

    A song-focused page may use pronouns in subsequent sentences. General
    pages must name the song within the actual musical observation.
    """
    normalize = lambda text: ' '.join(re.findall(r'\w+', text.casefold()))
    title = clean_excerpt(source.title)
    song_title = normalize(song.title)
    focused = bool(re.search(r'\b' + re.escape(song_title) + r'\b', normalize(title)))
    musical = re.compile(r'\b(guitars?|drums?|bass|vocals?|melod\w*|harmon\w*|rhythm\w*|'
                         r'tempo|instrument\w*|production|produced|recording|mixing|'
                         r'texture|synth\w*|energetic|dreamy|brooding|upbeat|'
                         r'sound\w*|delivery|beat|beats)\b', re.I)
    biography = re.compile(r'\b(chart|peaked|top ten|top 10|billboard|guest appeared|'
                           r'won the|award|born|debuted at)\b', re.I)
    kept = []
    for line in source.text.splitlines():
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', clean_excerpt(line)):
            named = bool(re.search(r'\b' + re.escape(song_title) + r'\b', normalize(sentence)))
            if (focused or named) and musical.search(sentence) and not biography.search(sentence):
                if sentence not in kept:
                    kept.append(sentence)
    return '\n'.join(kept)[:6000]
