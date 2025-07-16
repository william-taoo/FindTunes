from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import httpx
import os
from dotenv import load_dotenv
from ..database import get_db
from .. import crud
from typing import Any
import base64

load_dotenv()
router = APIRouter()

# Function to get user data from Spotify
async def get_spotify_user_data(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://api.spotify.com/v1/me',
            headers={ 'Authorization': f'Bearer { access_token }' }
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch user data from Spotify"
            )

        return response.json()
    
# Endpoint to handle token exchange
@router.post('/token')
async def exchange_spotify_token(request: Request, db: AsyncSession = Depends(get_db)):
    # Get authorization request code from frontend
    code = (await request.json()).get('code')
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")
    
    auth_string = f"{os.getenv('SPOTIFY_CLIENT_ID')}:{os.getenv('SPOTIFY_CLIENT_SECRET')}"
    auth_bytes = auth_string.encode('utf-8')
    base64_auth = base64.b64encode(auth_bytes).decode('utf-8')

    # Token exchange
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            'https://accounts.spotify.com/api/token',
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f"Basic { base64_auth }"
            },
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': os.getenv('SPOTIFY_REDIRECT_URI'),
            }
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=token_response.status_code,
                detail="Failed to exchange token"
            )
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        # Get user profile data
        user_data = await get_spotify_user_data(access_token)

        if not user_data:
            raise HTTPException(status_code=400, detail="Failed to fetch user data from Spotify")
        
        # Check if user already exists in the database
        user = await crud.get_user_by_spotify_id(db, user_data['id']) # id is spotify_id
        if user:
            # Delete the user data including top songs/artists/playlists to get fresh data
            await crud.delete_user_data(db, user_data['id'])

        # Prepare user data for database
        user_dict = {
            'spotify_id': user_data['id'],
            'display_name': user_data.get('display_name', ''),
            'email': user_data.get('email'),
            'country': user_data.get('country', ''),
            'profile_image_url': user_data.get('images', [{}])[0].get('url'),
            'followers_count': user_data.get('followers', {}).get('total', 0),
            'product': user_data.get('product'),
            'spotify_profile_url': user_data.get('external_urls', {}).get('spotify'),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires_at': expires_at,
            'raw_data': str(user_data)  # Storing as string for reference
        }

        # Create new user
        user = await crud.create_user(db, user_dict)

        # Fetch user's top tracks, artists, and playlists
        headers = { 'Authorization': f'Bearer { access_token }' }

        # Get top tracks
        top_tracks_response = await client.get(
            'https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=50',
            headers=headers
        )
        top_tracks = top_tracks_response.json().get('items', []) if top_tracks_response.status_code == 200 else []

        # Get top artists
        top_artists_response = await client.get(
            'https://api.spotify.com/v1/me/top/artists?time_range=short_term&limit=10',
            headers=headers
        )
        top_artists = top_artists_response.json().get('items', []) if top_artists_response.status_code == 200 else []

        # Get playlists
        playlists_response = await client.get(
            'https://api.spotify.com/v1/me/playlists',
            headers=headers
        )
        playlists = playlists_response.json().get('items', []) if playlists_response.status_code == 200 else []

        user_top_tracks = await crud.get_user_top_tracks(db, user_data['id'])
        user_top_artists = await crud.get_user_top_artists(db, user_data['id'])
        user_playlists = await crud.get_user_playlists(db, user_data['id'])

        # Check if the top tracks and artists already exist in the database
        existing_track_ids = {track.track_id for track in user_top_tracks}
        existing_artist_ids = {artist.artist_id for artist in user_top_artists}
        existing_playlist_ids = {playlist.playlist_id for playlist in user_playlists}

        # Store this information in the database
        if top_tracks:
            tracks_to_store = []
            for track in top_tracks:
                if track['id'] in existing_track_ids:
                    # Don't include track in database
                    continue
                tracks_to_store.append({
                    'spotify_id': user_data['id'],
                    'track_id': track['id'],
                    'track_name': track['name'],
                    'track_url': track['external_urls']['spotify'],
                    'artist_names': [artist['name'] for artist in track['artists']],
                    'artist_urls': {artist['name']: artist['external_urls']['spotify'] for artist in track['artists']},
                    'album_name': track['album']['name'],
                    'images': [image['url'] for image in track['album']['images']] if track['album']['images'] else [],
                    'popularity': track['popularity'],
                    'time_range': 'short_term',
                })

            await crud.create_user_top_tracks(db, user_data['id'], tracks_to_store)

        # Store top artists
        if top_artists:
            artists_to_store = []
            for artist in top_artists:
                if artist['id'] in existing_artist_ids:
                    # Don't include artist in database
                    continue
                artists_to_store.append({
                    'spotify_id': user_data['id'],
                    'artist_id': artist['id'],
                    'artist_name': artist['name'],
                    'artist_url': artist['external_urls']['spotify'],
                    'genres': artist.get('genres', []),
                    'popularity': artist['popularity'],
                    'images': [image['url'] for image in artist['images']] if artist['images'] else []
                })

            await crud.create_user_top_artists(db, user_data['id'], artists_to_store)

        # Store playlists
        if playlists:
            playlists_to_store = []
            for playlist in playlists:
                if playlist['id'] in existing_playlist_ids:
                    # Don't include playlist in database
                    continue
                playlists_to_store.append({
                    'spotify_id': user_data['id'],
                    'playlist_id': playlist['id'],
                    'playlist_name': playlist['name'],
                    'playlist_image': [image['url'] for image in playlist['images']] if playlist['images'] else [],
                    'playlist_url': playlist['external_urls']['spotify'],
                })
            
            await crud.create_user_playlists(db, user_data['id'], playlists_to_store)

        # Set the cookie with the user's Spotify ID, and redirect to the dashboard
        response = JSONResponse(content={ 'spotify_id': user_data['id'] })

        return response
