from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from .database import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)

    spotify_id = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    country = Column(String, nullable=False)

    profile_image_url = Column(Text, nullable=True)
    followers_count = Column(Integer, nullable=False, default=0)
    product = Column(String, nullable=True)  # "premium" or "free"

    spotify_profile_url = Column(Text, nullable=True)

    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(TIMESTAMP, nullable=False)

    raw_data = Column(Text, nullable=True)

# Can change later
class UserTopTracks(Base):
    __tablename__ = "user_top_tracks"

    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, ForeignKey("users.spotify_id"), nullable=False, index=True)
    track_id = Column(String, nullable=False)
    track_name = Column(String, nullable=False)
    track_url = Column(Text, nullable=True)
    artist_names = Column(ARRAY(String), nullable=False)
    artist_urls = Column(JSON, nullable=True)
    album_name = Column(String)
    images = Column(ARRAY(String), nullable=True)
    popularity = Column(Integer)
    time_range = Column(String, nullable=False)
    retrieved_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

class UserTopArtists(Base):
    __tablename__ = "user_top_artists"

    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, ForeignKey("users.spotify_id"), nullable=False, index=True)
    artist_id = Column(String, nullable=False)
    artist_name = Column(String, nullable=False)
    artist_url = Column(Text, nullable=True)
    genres = Column(ARRAY(String), nullable=True)
    popularity = Column(Integer)
    images = Column(ARRAY(String), nullable=True)
    retrieved_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

class UserPlaylists(Base):
    __tablename__ = "user_playlists"

    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, ForeignKey("users.spotify_id"), nullable=False, index=True)
    playlist_id = Column(String, nullable=False)
    playlist_name = Column(String, nullable=False)
    playlist_image = Column(Text, nullable=True)
    playlist_url = Column(Text, nullable=True)
