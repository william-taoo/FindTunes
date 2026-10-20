import logging
import asyncio
import os
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from services.pinecone_utils import query_vector
from services.lyric_retrieval import make_genius_client, song_to_document, fetch_song_document, song_id, song_artist, search_song_with_retry
from services.rag import is_configured, explain_match

router = APIRouter()
logger = logging.getLogger(__name__)


def retrieve_base(song_name, artist_name):
    song_name, artist_name = song_name.strip(), artist_name.strip()
    if not song_name:
        raise HTTPException(400, 'Enter a song title to get recommendations.')
    try:
        song = search_song_with_retry(make_genius_client(), song_name, artist_name)
    except Exception:
        raise HTTPException(502, 'Could not retrieve the input song')
    if song is None:
        raise HTTPException(404, 'Song not found; refine the title or artist.')
    resolved = {'id': song_id(song), 'title': song.title, 'artist': song_artist(song)}
    matches = query_vector(resolved['id'], resolved['title'], resolved['artist'])
    if matches == -1:
        raise HTTPException(502, 'Song similarity search failed')
    return song_to_document(song), [{**match, 'seed_song': resolved, 'explanation': None,
        'explanation_status': 'pending', 'sources': None} for match in matches]


@router.get('/recommend/stream')
async def recommend_stream(song_name: str = Query(min_length=1, max_length=200),
                           artist_name: str = Query(default='', max_length=200),
                           research_mode: Literal['quick', 'deep'] = 'quick'):
    """Return Pinecone candidates before inference/research; poll the attached job."""
    seed, matches = await asyncio.to_thread(retrieve_base, song_name, artist_name)
    job_id = None
    if seed and matches and os.getenv('RESEARCH_ENABLED', 'true').lower() not in ('false', '0', 'no'):
        try:
            from services.research.jobs import manager
            job_id = manager.start(seed, matches, mode=research_mode)
        except Exception:
            logger.exception('Research could not be started')
    return {'recommendations': matches, 'research_job_id': job_id,
            'research_status': 'queued' if job_id else 'unavailable'}


@router.get('/research/jobs/{job_id}')
async def research_status(job_id: str):
    from services.research.jobs import manager
    value = manager.snapshot(job_id)
    if value is None:
        raise HTTPException(404, 'Research job expired or the backend restarted.')
    return value


@router.get('/research/config')
def research_config():
    from services.research.providers import HTTPResearchProvider
    from services.local_llm import model_name
    from services.research.schema import SCHEMA_VERSION
    return {'providers': HTTPResearchProvider().capabilities(), 'model': model_name(),
            'searches_per_agent': 2, 'rounds_per_agent': 2,
            'default_mode': 'quick', 'quick_mode_model_calls': 0, 'audio_analysis': False,
            'research_revision': SCHEMA_VERSION, 'deep_job_seconds_max': 120, 'deep_model_attempts_max': 10}

@router.get('/recommend')
def recommend_songs(song_name: str = Query(min_length=1, max_length=200),
                    artist_name: str = Query(default='', max_length=200)):
    # Synchronous external libraries run in FastAPI's worker thread pool.
    song_name, artist_name = song_name.strip(), artist_name.strip()
    if not song_name:
        raise HTTPException(400, 'Enter a song title to get recommendations.')
    try:
        client = make_genius_client()
        song = search_song_with_retry(client, song_name, artist_name)
    except Exception:
        logger.exception('Input song retrieval failed')
        raise HTTPException(502, 'Could not retrieve the input song')
    if song is None:
        raise HTTPException(404, 'Genius could not resolve this song after two attempts. Check the title and artist, or try again shortly. Your Pinecone records have not been removed.')
    resolved = {'id': song_id(song), 'title': song.title, 'artist': song_artist(song)}
    # Ingestion must use the resolved identity when the user omits the artist.
    matches = query_vector(resolved['id'], resolved['title'], resolved['artist'])
    if matches == -1:
        raise HTTPException(502, 'Song similarity search failed')
    seed = song_to_document(song)
    results = []
    for match in matches:
        result = {**match, 'seed_song': resolved, 'explanation': None,
                  'explanation_status': 'unavailable', 'sources': None}
        if not is_configured():
            result['explanation_status'] = 'disabled'
        elif seed is not None:
            try:
                candidate = fetch_song_document(client, match['id'])
                if candidate is not None:
                    result['sources'] = {'seed': seed['source_url'],
                                         'candidate': candidate['source_url']}
                    result['explanation'] = explain_match(seed, candidate)
                    result['explanation_status'] = 'complete'
            except Exception:
                logger.exception('Explanation failed for song %s', match['id'])
        results.append(result)
    return results

@router.get('/artwork')
def artwork(song_name: str = Query(default='', max_length=200),
            artist_name: str = Query(default='', max_length=200),
            spotify_track_id: str = Query(default='', max_length=100)):
    from services.artwork import song_artwork
    try:
        return {'image_url': song_artwork(song_name.strip(), artist_name.strip(), spotify_track_id.strip())}
    except Exception:
        logger.warning('Cover artwork unavailable for %s', song_name)
        return {'image_url': None}
