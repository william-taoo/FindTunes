from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.database import get_db
from ..db import crud
from ..sessions import current_user, require_owner
from services.genius import process_artist_songs, process_song
from services.sync_state import reserve, release, worker_lock

router = APIRouter()


def run_sync_job(user, artists, tracks):
    success = False
    try:
        with worker_lock:
            for artist in artists:
                process_artist_songs(artist)
            for title, artist in tracks:
                process_song(title, artist)
        success = True
    finally:
        release(user, success)


@router.post('/sync/{spotify_id}')
async def sync_songs_to_db(spotify_id: str, background_tasks: BackgroundTasks,
                           db: AsyncSession = Depends(get_db), user: str = Depends(current_user)):
    require_owner(spotify_id, user)
    profile = await crud.get_user_profile(db, spotify_id)
    if not profile or not profile['user']:
        raise HTTPException(404, 'User not found')
    # Copy primitive values before the request database session closes.
    artists = [item.artist_name for item in profile['top_artists']]
    tracks = [(item.track_name, item.artist_names[0]) for item in profile['top_tracks'] if item.artist_names]
    state = reserve(user)
    if state == 'queued':
        background_tasks.add_task(run_sync_job, user, artists, tracks)
    return {'status': state}
