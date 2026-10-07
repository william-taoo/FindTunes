import logging
from fastapi import APIRouter, HTTPException, Query
from services.pinecone_utils import query_vector
from services.lyric_retrieval import make_genius_client, song_to_document, fetch_song_document, song_id, search_song_with_retry
from services.rag import is_configured, explain_match

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get('/recommend')
def recommend_songs(song_name: str = Query(min_length=1, max_length=200),
                    artist_name: str = Query(min_length=1, max_length=200)):
    # Synchronous external libraries run in FastAPI's worker thread pool.
    try:
        client = make_genius_client()
        song = search_song_with_retry(client, song_name, artist_name)
    except Exception:
        logger.exception('Input song retrieval failed')
        raise HTTPException(502, 'Could not retrieve the input song')
    if song is None:
        raise HTTPException(404, 'Genius could not resolve this song after two attempts. Check the title and artist, or try again shortly. Your Pinecone records have not been removed.')
    matches = query_vector(song_id(song), song_name, artist_name)
    if matches == -1:
        raise HTTPException(502, 'Song similarity search failed')
    seed = song_to_document(song)
    results = []
    for match in matches:
        result = {**match, 'explanation': None,
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
