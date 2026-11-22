import pinecone
import os
import time
from dotenv import load_dotenv

NAMESPACE = 'findtunes'
TOP_K = 3

load_dotenv()
api_key = os.getenv('PINECONE_API_KEY')
host_url = os.getenv('PINECONE_HOST')

pc = pinecone.Pinecone(api_key=api_key)
index = pc.Index(host=host_url)


def ingestion_enabled():
    return os.getenv('CATALOG_INGESTION_ENABLED', 'true').lower() not in ('false', '0', 'no')

def catalog_song_for_spotify_track(track_id):
    try:
        records = index.fetch_by_metadata(filter={'spotify_track_id': {'$eq': track_id}},
                                          namespace=NAMESPACE, limit=2).vectors
    except Exception as error:
        print(f'Spotify catalog lookup failed ({type(error).__name__})')
        return None
    if len(records) != 1:
        return None

    record = next(iter(records.values()))
    metadata = record.metadata or {}
    artist = metadata.get('artist')
    if isinstance(artist, list):
        artist = artist[0] if artist else None
    if not metadata.get('title') or not artist:
        return None
    return {'id': record.id, 'title': metadata['title'], 'artist': artist}


def upsert_vector(id: int, vector: list, metadata: dict) -> None:
    try:
        index.upsert(vectors=[{"id": id, "values": vector, "metadata": metadata}], namespace=NAMESPACE)
        print(f"Upserted vector with ID: { id }")
    except Exception as e:
        print(f"Error during upsert for ID: { id }, { e }")

def fetch_vector(genius_id: str) -> bool:
    try:
        id = str(genius_id)
        response = index.fetch(ids=[id], namespace=NAMESPACE)

        if id in response.vectors:
            print(f"Song already exists in database: { id }")
            return True
        # else:
        #     print(f"Song not found in database: { id }")
    except Exception as e:
        print(f"Error during fetch for ID: { id }, { e }")
    
    return False


def wait_for_vector(genius_id):
    # Acknowledged writes can take a few seconds to become visible to reads.
    for delay in (0, 0.25, 0.5, 1, 2, 4):
        if delay:
            time.sleep(delay)
        if fetch_vector(str(genius_id)):
            return True
    return False

def query_vector(genius_id: int, song_name: str, artist_name: str):
    try:
        if not fetch_vector(str(genius_id)):
            if not ingestion_enabled():
                return None
            from .genius import process_song
            indexed_id = process_song(song_name, artist_name)
            if indexed_id is not None and str(indexed_id) != str(genius_id):
                raise ValueError('Ingestion resolved a different Genius song ID')
            if not wait_for_vector(genius_id):
                raise ValueError('Input song is not visible in Pinecone yet; please retry shortly')
        similar_songs = index.query(
            id=str(genius_id),
            top_k = TOP_K + 1,
            namespace=NAMESPACE,
            include_metadata=True,
            include_values=False,
        )

    except Exception as e:
        print(f"Error during query for: { song_name } by { artist_name }, { e }")
        return -1

    return [
        {
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata,
        }
        for match in similar_songs.matches
        if str(match.id) != str(genius_id)
    ][:TOP_K]
