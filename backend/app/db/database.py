from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import make_url
import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError('DATABASE_URL is required')

SQLALCHEMY_DATABASE_URL = make_url(database_url)
if SQLALCHEMY_DATABASE_URL.drivername in ('postgres', 'postgresql'):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.set(drivername='postgresql+asyncpg')

# Hosted PostgreSQL URLs can use libpq's sslmode parameter. asyncpg uses ssl.
if 'sslmode' in SQLALCHEMY_DATABASE_URL.query:
    ssl_mode = SQLALCHEMY_DATABASE_URL.query['sslmode']
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.difference_update_query(['sslmode'])
    if 'ssl' not in SQLALCHEMY_DATABASE_URL.query:
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.update_query_dict({'ssl': ssl_mode})

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
