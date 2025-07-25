import pinecone
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('PINECONE_API_KEY')
host_url = os.getenv('PINECONE_HOST')

pc = pinecone.Pinecone(api_key=api_key)
index = pc.Index(host=host_url)

def upsert_vector(id: str, vector: list, metadata: dict) -> None:
    try:
        index.upsert(vectors=[{"id": id, "values": vector, "metadata": metadata}], namespace='findtunes')
        print(f"Upserted vector with ID: { id }")
    except Exception as e:
        print(f"Error during upsert for ID: { id }, { e }")

def fetch_vector(artist: str, song_name: str, genius_id: str) -> bool:
    try:
        id = f"{artist}_{song_name}_{genius_id}"
        response = index.fetch(ids=[id], namespace='findtunes')
        print(response)

        if id in response.vectors:
            print(f"Song already exists in database: { id }")
            return True
        else:
            print(f"Song not found in database: { id }")
    except Exception as e:
        print(f"Error during fetch for ID: { id }, { e }")
    
    return False
