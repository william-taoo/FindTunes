from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud
from app.database import get_db
from app.schemas import ProfileResponse

router = APIRouter()

@router.get('/profile', response_model=ProfileResponse)
async def get_profile(request: Request, spotify_id: str, db: AsyncSession = Depends(get_db)):
    print("Spotify ID from cookies:", spotify_id)

    if not spotify_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    profile_data = await crud.get_user_profile(db, spotify_id)

    if not profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return profile_data
