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

def get_spotify_track_info(song_name: str, artist_name: str):
    query = f"{song_name} {artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    
    items = results['tracks']['items']
    if items:
        track = items[0]
        info = {
            "name": track["name"],
            "artists": [song["name"] for song in track["artists"]],
            "spotify_track_id": track["id"],
            "spotify_track_url": track["external_urls"]["spotify"]
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

    dim = 768
    if annotation_embedding is None:
        annotation_embedding = np.zeros(dim)
    elif lyrics_embedding is None:
        lyrics_embedding = np.zeros(dim)
    
    combined_embedding = np.concatenate((annotation_embedding, lyrics_embedding))

    # Normalize the combined embedding
    norm = np.linalg.norm(combined_embedding)
    if norm == 0 or np.isnan(norm):
        print("Combined embedding norm is 0 or NaN")
        return

    combined_embedding = combined_embedding / norm
    # print(combined_embedding)

    # Clean up song title
    song_title = to_ascii_id(song.title)
    song_title_with_featured = to_ascii_id(song.title_with_featured)

    # Search for song's Spotify URL (if applicable)
    song_info = get_spotify_track_info(song_title, artist_name)

    # Store metadata
    id = str(song.id) # Genius ID
    metadata = {
        'artist': song_info['artists'] if song_info else artist_name,
        'title': song_info['name'] if song_info else song_title_with_featured,
        'spotify_track_id': song_info['spotify_track_id'] if song_info else "Couldn't find Spotify ID",
        'spotify_track_url': song_info['spotify_track_url'] if song_info else "Couldn't find Spotify URL",
    }

    # Store in Pinecone 
    upsert_vector(id, combined_embedding.tolist(), metadata)

def process_artist_songs(artist):
    try:
        artist = genius.search_artist(artist, max_songs=5, sort="popularity")
        if artist is None:
            print(f"Artist not found or no songs available.", artist)
            return
    except Exception as e:
        print(f"Error during genius artist search: ${ artist }", e)
        return

    for song in artist.songs:
        # Look if the song is already in the database
        artist_name = to_ascii_id(artist.name)
        song_title = to_ascii_id(song.title)
        in_database = fetch_vector(song.id)
        if in_database:
            continue

        embed_and_store(song, artist_name)
        print("next song\n")
    
def process_song(song_name: str, artist_name: str):
    try:
        song = genius.search_song(title=song_name, artist=artist_name)
        if song is None:
            return
    except Exception as e:
        print("Song not found or no lyrics available.", e)
        return
    
    # Look if the song is already in the database
    in_database = fetch_vector(song.id)
    if in_database:
        return
    
    artist_name = to_ascii_id(song.primary_artist.name)
    embed_and_store(song, artist_name)

    return song.id
