from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models, schemas
from typing import Optional

# CRUD (Create, Read, Update, Delete) operations for User model
async def get_user_by_spotify_id(db: AsyncSession, spotify_id: str) -> schemas.UserResponse:
    result = await db.execute(
        select(models.User).where(models.User.spotify_id == spotify_id)
    )

    return result.scalars().first()

async def create_user(db: AsyncSession, user_data: dict) -> schemas.UserResponse:
    db_user = models.User(
        spotify_id=user_data["spotify_id"],
        display_name=user_data["display_name"],
        email=user_data["email"],
        country=user_data["country"],
        profile_image_url=user_data.get("profile_image_url"),
        followers_count=user_data.get("followers_count", 0),
        product=user_data.get("product"),
        spotify_profile_url=user_data.get("spotify_profile_url"),
        access_token=user_data["access_token"],
        refresh_token=user_data["refresh_token"],
        token_expires_at=user_data["token_expires_at"],
        raw_data=user_data.get("raw_data")
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_user_top_tracks(db: AsyncSession, spotify_id: str, limit: Optional[int] = None) -> list[schemas.Track]:
    query = select(models.UserTopTracks).where(
        models.UserTopTracks.spotify_id == spotify_id
    ).order_by(
        models.UserTopTracks.retrieved_at.desc()
    )

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def create_user_top_tracks(db: AsyncSession, spotify_id: str, tracks: list[dict]) -> list[schemas.Track]:
    db_tracks = []
    for track in tracks:
        db_track = models.UserTopTracks(
            spotify_id=spotify_id,
            track_id=track["track_id"],
            track_name=track["track_name"],
            track_url=track.get("track_url", {}),
            artist_names=track["artist_names"],
            artist_urls=track.get("artist_urls", {}),
            album_name=track.get("album_name"),
            images=track.get("images"),
            popularity=track.get("popularity"),
            time_range=track["time_range"],
        )
        db.add(db_track)
        db_tracks.append(db_track)

    await db.commit()
    return db_tracks

# Top Artists CRUD Operations
async def get_user_top_artists(db: AsyncSession, spotify_id: str, limit: Optional[int] = None) -> list[schemas.TopArtist]:
    query = select(models.UserTopArtists).where(
        models.UserTopArtists.spotify_id == spotify_id
    ).order_by(
        models.UserTopArtists.retrieved_at.desc()
    )

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def create_user_top_artists(db: AsyncSession, spotify_id: str, artists: list[dict]) -> list[schemas.TopArtist]:
    db_artists = []
    for artist in artists:
        db_artist = models.UserTopArtists(
            spotify_id=spotify_id,
            artist_id=artist["artist_id"],
            artist_name=artist["artist_name"],
            artist_url=artist.get("artist_url", {}),
            genres=artist.get("genres"),
            popularity=artist["popularity"],
            images=artist.get("images", [])
        )
        db.add(db_artist)
        db_artists.append(db_artist)

    await db.commit()
    return db_artists

# Playlists CRUD Operations
async def get_user_playlists(db: AsyncSession, spotify_id: str, limit: Optional[int] = None) -> list[schemas.Playlist]:
    query = select(models.UserPlaylists).where(
        models.UserPlaylists.spotify_id == spotify_id
    ).order_by(
        models.UserPlaylists.retrieved_at.desc()
    )

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def create_user_playlists(db: AsyncSession, spotify_id: str, playlists: list[dict]) -> list[schemas.Playlist]:
    db_playlists = []
    for playlist in playlists:
        db_playlist = models.UserPlaylists(
            spotify_id=spotify_id,
            playlist_id=playlist["playlist_id"],
            playlist_name=playlist["playlist_name"],
            playlist_image=playlist.get("playlist_image"),
            playlist_url=playlist["playlist_url"]
        )
        db.add(db_playlist)
        db_playlists.append(db_playlist)
        
    await db.commit()
    return db_playlists

# Combined Operations
# Gets all data for a user
async def get_user_profile(db: AsyncSession, spotify_id: str) -> schemas.ProfileResponse:
    user = await get_user_by_spotify_id(db, spotify_id)
    top_tracks = await get_user_top_tracks(db, spotify_id)
    top_artists = await get_user_top_artists(db, spotify_id)
    playlists = await get_user_playlists(db, spotify_id)
    
    return {
        "user": user,
        "top_tracks": top_tracks,
        "top_artists": top_artists,
        "playlists": playlists
    }

# Delete user profile and listening data
async def delete_user_data(db: AsyncSession, spotify_id: str) -> None:
    await db.execute(
        delete(models.UserTopTracks).where(models.UserTopTracks.spotify_id == spotify_id)
    )
    await db.execute(
        delete(models.UserTopArtists).where(models.UserTopArtists.spotify_id == spotify_id)
    )
    await db.execute(
        delete(models.UserPlaylists).where(models.UserPlaylists.spotify_id == spotify_id)
    )
    await db.execute(
        delete(models.User).where(models.User.spotify_id == spotify_id)
    )

    await db.commit()
