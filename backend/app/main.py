from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import spotify, profile, sync, recommend

app = FastAPI()
app.include_router(spotify.router)
app.include_router(profile.router)
app.include_router(sync.router)
app.include_router(recommend.router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="localhost", port=8000, reload=True)
