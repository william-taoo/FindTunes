from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.database import get_db
from ..db import crud
from services.genius import process_artist_songs, process_song

router = APIRouter()

def run_sync_job(top_artists, top_tracks):
    print("Starting background sync job...")

    for artist in top_artists:
        print(f"Processing artist: {artist.artist_name}")
        process_artist_songs(artist.artist_name)
    
    for track in top_tracks:
        print(f"Processing track: {track.track_name}")
        process_song(track.track_name, track.artist_names[0])

    print("Background sync job completed.")

@router.post('/sync/{spotify_id}')
async def sync_songs_to_db(spotify_id: str,
                           background_tasks: BackgroundTasks,
                           db: AsyncSession = Depends(get_db)):
    # Gather songs from user's top artists songs and then store them in Pinecone
    print("Spotify ID from cookies:", spotify_id)

    if not spotify_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    profile_data = await crud.get_user_profile(db, spotify_id)

    if not profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    top_artists = profile_data['top_artists']
    top_tracks = profile_data['top_tracks']

    # Schedule background job
    background_tasks.add_task(run_sync_job, top_artists, top_tracks)
