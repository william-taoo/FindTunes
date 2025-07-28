import pinecone
import os
from dotenv import load_dotenv

NAMESPACE = 'findtunes'
TOP_K = 3

load_dotenv()
api_key = os.getenv('PINECONE_API_KEY')
host_url = os.getenv('PINECONE_HOST')

pc = pinecone.Pinecone(api_key=api_key)
index = pc.Index(host=host_url)

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

def query_vector(spotify_track_id: str, song_name: str, artist_name: str):
    from .genius import process_song
    try:
        similar_songs = index.query(
            top_k = TOP_K,
            namespace=NAMESPACE,
            include_values=True,
            filter={ 'spotify_track_id': { '$eq': spotify_track_id } }
        )

        if not similar_songs.matches:
            # Need to embed that song and add it to the database
            print(f"Song not found in database: { spotify_track_id }")
            print("Embedding song...")
            process_song(song_name, artist_name)

            # Query for song again
            similar_songs = index.query(
                top_k = TOP_K,
                namespace=NAMESPACE,
                include_values=True,
                filter={ 'spotify_track_id': { '$eq': spotify_track_id } }
            )

    except Exception as e:
        print(f"Error during query for Spotify TrackID: { spotify_track_id }, { e }")
        return []

    return similar_songs.matches
