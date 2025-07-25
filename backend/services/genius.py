from lyricsgenius import Genius
import numpy as np
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from embeddings import clean_lyrics, split_lyrics, get_song_embedding
from pinecone_utils import upsert_vector, fetch_vector

load_dotenv()
genius_client_id = os.getenv('GENIUS_CLIENT_ACCESS_TOKEN')
genius = Genius(genius_client_id, timeout=100)

spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret
))

def get_spotify_track_id(song_name: str, artist_name: str):
    query = f"track:{song_name} artist:{artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    
    items = results['tracks']['items']
    if items:
        track = items[0]
        info = {
            "id": track["id"],
            "name": track["name"],
            "url": track["external_urls"]["spotify"],
            "artists": [song["name"] for song in track["artists"]]
        }

        return info
    return None

def process_songs(artist):
    try:
        artist = genius.search_artist(artist, max_songs=3, sort="popularity")
    except Exception as e:
        print("Artist not found or no songs available.", e)
        return

    for song in artist.songs:
        # Look if the song is already in the database
        in_database = fetch_vector(artist.name, song.title, song.id)
        if in_database:
            continue

        annotation, lyrics = split_lyrics(song.lyrics)
        
        # Clean both parts separately
        cleaned_annotation = clean_lyrics(annotation)
        cleaned_lyrics = clean_lyrics(lyrics)
        # print(cleaned_annotation)
        # print(cleaned_lyrics)

        # Embed the song lyrics and annotations using pretrained model
        annotation_embedding = get_song_embedding(cleaned_annotation)
        lyrics_embedding = get_song_embedding(cleaned_lyrics)
        combined_embedding = np.concatenate((annotation_embedding, lyrics_embedding))

        # Normalize the combined embedding
        combined_embedding = combined_embedding / np.linalg.norm(combined_embedding)
        # print(combined_embedding)

        # Search for song's Spotify URL (if applicable)
        song_info = get_spotify_track_id(song.title_with_featured, artist.name)

        # Store metadata
        id = f"{artist.name}_{song.title}_{song.id}" # song.id is the genius song ID
        metadata = {
            'artist': song_info['artists'] if song_info else artist.name,
            'title': song_info['name'] if song_info else song.title_with_featured,
            'genius_id': song.id,
            'spotify_id': song_info['id'] if song_info else None,
            'spotify_url': song_info['url'] if song_info else None,
        }

        # Store in Pinecone 
        upsert_vector(id, combined_embedding.tolist(), metadata)
        print("next song\n")
    
process_songs("Lil Uzi Vert")
