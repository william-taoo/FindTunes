from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# A schema is a way to define the structure of data, and is used in APIs to validate data and show to the user
class Track(BaseModel):
    spotify_id: str
    track_id: str
    track_name: str
    track_url: Optional[str] = None
    artist_names: list[str]
    artist_urls: Optional[dict[str, str]] = None
    album_name: str
    images: Optional[list[str]] = None
    popularity: int
    time_range: str

class TopArtist(BaseModel):
    spotify_id: str
    artist_id: str
    artist_name: str
    artist_url: Optional[str] = None
    genres: Optional[list[str]] = None
    popularity: int
    images: Optional[list[str]] = None

class Playlist(BaseModel):
    spotify_id: str
    playlist_id: str
    playlist_name: str
    playlist_image: Optional[list[str]] = None
    playlist_url: Optional[str] = None

class UserResponse(BaseModel):
    spotify_id: str
    display_name: str
    email: str
    country: str
    profile_image_url: Optional[str] = None
    followers_count: int
    product: str
    spotify_profile_url: Optional[str] = None
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    raw_data: Optional[str] = None

class ProfileResponse(BaseModel):
    user: UserResponse
    top_tracks: list[Track]
    top_artists: list[TopArtist]
    playlists: list[Playlist]

    class Config:
        from_attributes = True
