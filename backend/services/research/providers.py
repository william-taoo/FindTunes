"""Written review and artist/production research via bounded search excerpts."""
import asyncio
import hashlib
import os
import time
from typing import Protocol
import httpx
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from .schema import Source
from .excerpts import clean_excerpt


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class ResearchProvider(Protocol):
    def capabilities(self) -> dict[str, bool]: ...
    async def search_reviews(self, query: str) -> list[dict]: ...
    async def search_context(self, query: str) -> list[dict]: ...


def source(url, title, text, kind, timestamp=None):
    if kind == 'written_excerpt':
        title = clean_excerpt(title)
        text = '\n'.join(dict.fromkeys(clean_excerpt(line) for line in text.splitlines() if clean_excerpt(line)))
    # Immutable excerpt identity prevents concurrent agents overwriting each other's evidence.
    return Source(id=hashlib.sha256(f'{url}|{timestamp}|{kind}|{text[:6000]}'.encode()).hexdigest()[:16],
        url=url, title=title, text=text[:6000], kind=kind,
        timestamp_seconds=timestamp, retrieved_at=time.time()).model_dump(mode='json')


class HTTPResearchProvider:
    def capabilities(self):
        enabled = bool(os.getenv('BRAVE_SEARCH_API_KEY'))
        return {'search_reviews': enabled, 'search_context': enabled}

    async def _get(self, url, **kwargs):
        # Only fixed provider endpoints are reachable; keys never appear in traces.
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            for attempt in range(2):
                try:
                    response = await client.get(url, **kwargs)
                    if response.status_code >= 500 and attempt == 0:
                        await asyncio.sleep(.2)
                        continue
                    response.raise_for_status()
                    return response
                except httpx.TransportError:
                    if attempt:
                        raise
        raise RuntimeError('Provider request unavailable')

    async def search_written(self, query):
        key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise RuntimeError('BRAVE_SEARCH_API_KEY unavailable')
        data = (await self._get('https://api.search.brave.com/res/v1/web/search',
            headers={'X-Subscription-Token': key},
            params={'q': query, 'count': 5, 'extra_snippets': 'true'})).json()
        return [source(item['url'], item.get('title', ''),
                       '\n'.join([item.get('description', ''), *item.get('extra_snippets', [])]),
                       'written_excerpt')
                for item in data.get('web', {}).get('results', [])[:5]
                if item.get('url', '').startswith('https://')
                and 'youtube.com/' not in item['url'] and 'youtu.be/' not in item['url']]

    async def search_reviews(self, query):
        return await self.search_written(query)

    async def search_context(self, query):
        return await self.search_written(query)


def tools_for(provider: ResearchProvider):
    return {name: StructuredTool.from_function(name=name, description=description,
        args_schema=SearchArgs, coroutine=getattr(provider, name))
        for name, description in (
            ('search_reviews', 'Find published song reviews and criticism with attributable musical observations.'),
            ('search_context', 'Find written artist/producer interviews and production commentary about this exact song.'))}
