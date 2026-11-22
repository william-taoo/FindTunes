import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import spotify, profile, sync, recommend

app = FastAPI()
app.include_router(spotify.router)
app.include_router(profile.router)
app.include_router(sync.router)
app.include_router(recommend.router)

frontend_origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
if frontend_origin := os.getenv('FRONTEND_ORIGIN'):
    frontend_origins.append(frontend_origin.rstrip('/'))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
