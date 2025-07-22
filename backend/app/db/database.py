from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Async connection
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Create the async engine
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, future=True)

# Configure session maker
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Base class for declarative models
Base = declarative_base()

# Dependency for FastAPI
async def get_db():
    async with SessionLocal() as session:
        yield session
        