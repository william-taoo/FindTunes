# FindTunes

A Spotify-powered music recommendation platform that saves users’ top artists and tracks, 
embeds the lyrics using a Hugging Face sentence transformer model, 
and stores them in Pinecone, a vector database that can perform semantic search to find similar tracks.

Upon login, a user's top tracks and their top artists' catalogs are automatically processed and uploaded to the vector database.
Share this with friends so more tracks can be added to the database for greater and more diverse recommendations!  

# Requirements

This app uses the following technologies:
* `Next.js` – Frontend framework for building the UI
* `FastAPI` – Backend framework for handling API requests and server-side logic
* `PostgreSQL` – Database for storing user's listening history and profile data
* `Pinecone` – Vector database for storing song lyric embeddings and performing semantic search
* `Hugging Face` – The AI platform used to select the `all-mpnet-base-v2` model for lyric embeddings
* `PyTorch` – Machine Learning framework used to aid in embedding process
