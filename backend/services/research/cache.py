"""Persistent PostgreSQL profiles; no full lyrics or secrets are stored."""
import time
from sqlalchemy import MetaData, Table, Column, String, Float, JSON, select
from sqlalchemy.dialects.postgresql import insert

metadata = MetaData()
profiles = Table('song_research_cache', metadata,
    Column('key', String(64), primary_key=True), Column('expires_at', Float, nullable=False),
    Column('payload', JSON, nullable=False))


class PostgresCache:
    async def get(self, key):
        from app.db.database import engine
        async with engine.connect() as connection:
            row = (await connection.execute(select(profiles.c.payload).where(
                profiles.c.key == key, profiles.c.expires_at > time.time()))).first()
            return row[0] if row else None

    async def put(self, key, payload):
        from app.db.database import engine
        # Incomplete/unavailable profiles expire quickly so new credentials can be used.
        has_written = any(s['kind'] == 'written_excerpt' for s in payload.get('sources', []))
        ttl = 86400 * 7 if payload.get('findings') else 86400 if payload.get('mode') == 'quick' and has_written else 300
        async with engine.begin() as connection:
            statement = insert(profiles).values(key=key, payload=payload, expires_at=time.time() + ttl)
            await connection.execute(statement.on_conflict_do_update(index_elements=['key'],
                set_={'payload': payload, 'expires_at': time.time() + ttl}))


class MemoryCache:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def put(self, key, payload):
        self.values[key] = payload
