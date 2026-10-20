from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import crud
from ..db.database import get_db
from ..db.schemas import ProfileResponse
from ..sessions import current_user, require_owner

router = APIRouter()

@router.get('/profile/{spotify_id}', response_model=ProfileResponse)
async def get_profile(spotify_id: str, response: Response, db: AsyncSession = Depends(get_db), user: str = Depends(current_user)):
    require_owner(spotify_id, user)
    response.headers['Cache-Control'] = 'no-store'
    print("Spotify ID from cookies:", spotify_id)

    if not spotify_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    profile_data = await crud.get_user_profile(db, spotify_id)

    if not profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return profile_data
