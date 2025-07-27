from lyricsgenius import Genius
import numpy as np
import unicodedata
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from .embeddings import clean_lyrics, split_lyrics, get_song_embedding
from .pinecone_utils import upsert_vector, fetch_vector

load_dotenv()
genius_client_id = os.getenv('GENIUS_CLIENT_ACCESS_TOKEN')
genius = Genius(genius_client_id, timeout=100)

spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret
))

def to_ascii_id(s: str) -> str:
    # Normalize to NFKD and encode to ASCII (removes fancy punctuation)
    ascii_str = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return ascii_str

def get_spotify_track_id(song_name: str, artist_name: str):
    query = f"track:{song_name} artist:{artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    
    items = results['tracks']['items']
    if items:
        track = items[0]
        info = {
            "name": track["name"],
            "artists": [song["name"] for song in track["artists"]],
            "url": track["external_urls"]["spotify"]
        }
        return info
    
    return None

def embed_and_store(song, artist_name: str):
    annotation, lyrics = split_lyrics(song.lyrics)
        
    # Clean both parts separately
    cleaned_annotation = clean_lyrics(annotation)
    cleaned_lyrics = clean_lyrics(lyrics)
    # print(cleaned_annotation)
    # print(cleaned_lyrics)

    # Embed the song lyrics and annotations using pretrained model
    annotation_embedding = get_song_embedding(cleaned_annotation)
    lyrics_embedding = get_song_embedding(cleaned_lyrics)

    if annotation_embedding is None and lyrics_embedding is None:
        print("There was a problem trying to get lyrics for ", song.title)
        return

    if annotation_embedding is None:
        combined_embedding = lyrics_embedding
    elif lyrics_embedding is None:
        combined_embedding = annotation_embedding
    else:
        combined_embedding = np.concatenate((annotation_embedding, lyrics_embedding))

    # Normalize the combined embedding
    norm = np.linalg.norm(combined_embedding)
    if norm == 0 or np.isnan(norm):
        print("Combined embedding norm is 0 or NaN")
        return

    combined_embedding = combined_embedding / norm
    # print(combined_embedding)

    # Clean up artist name or song title
    artist_name = to_ascii_id(artist_name)
    song_title = to_ascii_id(song.title)
    song_title_with_featured = to_ascii_id(song.title_with_featured)

    # Search for song's Spotify URL (if applicable)
    song_info = get_spotify_track_id(song_title, artist_name)

    # Store metadata
    id = f"{artist_name}_{song_title}_{song.id}" # song.id is the genius song ID
    metadata = {
        'artist': song_info['artists'] if song_info else artist_name,
        'title': song_info['name'] if song_info else song_title_with_featured,
        'genius_id': song.id,
        'spotify_url': song_info['url'] if song_info else "Couldn't find Spotify URL",
    }

    # Store in Pinecone 
    upsert_vector(id, combined_embedding.tolist(), metadata)

def process_artist_songs(artist):
    try:
        artist = genius.search_artist(artist, max_songs=1, sort="popularity")
    except Exception as e:
        print("Artist not found or no songs available.", e)
        return

    for song in artist.songs:
        # Look if the song is already in the database
        in_database = fetch_vector(artist.name, song.title, song.id)
        if in_database:
            continue

        embed_and_store(song, artist.name)
        print("next song\n")
    
def process_song(song_name: str, artist_name: str):
    try:
        song = genius.search_song(title=song_name, artist=artist_name)
    except Exception as e:
        print("Song not found or no lyrics available.", e)
        return
    
    # Look if the song is already in the database
    in_database = fetch_vector(song.primary_artist.name, song.title, song.id)
    if in_database:
        return
    
    embed_and_store(song, song.primary_artist.name)

# process_artist_songs("Lil Uzi Vert")
# process_song("The Way Life Goes (feat. Oh Wonder)", "Lil Uzi Vert")
