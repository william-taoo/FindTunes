from fastapi import APIRouter, HTTPException, status
from ..db.database import get_db
from services.pinecone_utils import query_vector
import os
from dotenv import load_dotenv
from lyricsgenius import Genius

load_dotenv()
genius_client_id = os.getenv('GENIUS_CLIENT_ACCESS_TOKEN')
genius = Genius(genius_client_id, timeout=100)

router = APIRouter()

@router.get('/recommend')
async def recommend_songs(song_name: str, artist_name: str):
    # First lookup song in genius for genius id
    try:
        song = genius.search_song(title=song_name, artist=artist_name)
        if song is None:
            return
    except Exception as e:
        print("Song not found or no lyrics available.", e)
        return
    
    print(f"Looking up similar songs for: {song_name} by {artist_name}. Genius id: {song.id}")

    similar_songs = query_vector(song.id, song_name, artist_name)
    if similar_songs == -1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    print(similar_songs)
    return similar_songs
