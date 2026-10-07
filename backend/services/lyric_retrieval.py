"""Request-scoped lyric documents; no lyrics are persisted."""
import os
import re
import time
from dotenv import load_dotenv
from lyricsgenius import Genius

load_dotenv()


def song_id(song):
    value = getattr(song, 'id', None)
    if value is None:
        value = song.to_dict().get('id')
    if value is None:
        raise ValueError('Genius song has no ID')
    return str(value)


def song_artist(song):
    artist = song.primary_artist
    return artist['name'] if isinstance(artist, dict) else artist.name


def make_genius_client():
    client = Genius(os.environ['GENIUS_CLIENT_ACCESS_TOKEN'], timeout=15, retries=1)
    if hasattr(client, 'verbose'):
        client.verbose = False
    return client


def search_song_with_retry(client, title, artist):
    """A single empty Genius search response is not proof a song is absent."""
    for attempt in range(2):
        song = client.search_song(title=title.strip(), artist=artist.strip())
        if song is not None:
            return song
        if attempt == 0:
            time.sleep(0.5)
    return None


def song_to_document(song):
    raw = song.lyrics or ''
    if 'Read More' in raw:
        raw = raw.split('Read More', 1)[1]
    raw = re.sub(r'\d*Embed\s*$', '', raw).strip()
    lines = []
    section = 'Lyrics'
    for text in raw.splitlines():
        text = text.strip()
        if not text:
            continue
        if text.startswith('[') and text.endswith(']'):
            section = text[1:-1]
            continue
        if not lines and (text.endswith(' Lyrics') or 'Contributors' in text):
            continue
        lines.append({'id': f'L{len(lines) + 1}', 'section': section, 'text': text})
    if not lines:
        return None
    return {'song_id': song_id(song), 'title': song.title,
            'artist': song_artist(song), 'source_url': song.url, 'lines': lines}


def fetch_song_document(client, genius_id):
    song = client.search_song(song_id=int(genius_id))
    if song is None or song_id(song) != str(genius_id):
        return None
    return song_to_document(song)
