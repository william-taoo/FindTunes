# FindTunes

FindTunes discovers songs with similar lyrical themes using Spotify listening
data, Genius lyrics, and semantic search in Pinecone. Its RAG pipeline retrieves
lyrics on demand and uses a local Qwen3-0.6B model to explain recommendations with
passage references and source links. LLM inference requires no API key.

## Requirements

- Python 3.10+ and Node.js 20+ with npm.
- PostgreSQL for user profiles and listening data.
- Spotify developer credentials, a Genius access token, and a Pinecone index.
- Next.js/React frontend; FastAPI/SQLAlchemy backend.
- PyTorch, Hugging Face Transformers (`all-mpnet-base-v2` embeddings and
  `Qwen3-0.6B` explanations), and LangChain for prompting.
- Enough RAM for both models; Qwen's CPU weights alone use roughly 2.4 GB.

Install backend dependencies from `backend/requirements.txt` and run `npm install`
in `frontend`. Configure `backend/.env` (see `backend/.env.example`) and
`frontend/.env.local`, then download the local LLM:

```powershell
python backend/scripts/download_local_model.py
```
