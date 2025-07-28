from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.database import get_db
from services.pinecone_utils import query_vector

router = APIRouter()

@router.get('/recommend/{spotify_track_id}')
async def recommend_songs(spotify_track_id: str, song_name: str, artist_name: str):
    similar_songs = query_vector(spotify_track_id, song_name, artist_name)
    return similar_songs
