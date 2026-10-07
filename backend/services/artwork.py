from functools import lru_cache
import os
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

@lru_cache(maxsize=1)
def client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')),
        requests_timeout=5, retries=0, status_retries=0)

@lru_cache(maxsize=256)
def song_artwork(title, artist, track_id=''):
    if re.fullmatch(r'[A-Za-z0-9]{22}', track_id):
        track = client().track(track_id)
    elif title and artist:
        items = client().search(q=f'track:{title} artist:{artist}', type='track', limit=1)['tracks']['items']
        track = items[0] if items else None
    else:
        track = None
    images = (track or {}).get('album', {}).get('images', [])
    return images[0]['url'] if images else None
