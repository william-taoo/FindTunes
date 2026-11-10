"""Explicit, credential-aware research checks. Never prints keys or authorization headers."""
import argparse
import asyncio
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from services.research.providers import HTTPResearchProvider
from services.research.model import LocalResearchModel
from services.research.schema import SongIdentity
from services.research.providers import source


async def check(args):
    provider = HTTPResearchProvider()
    print('Configured capabilities:', provider.capabilities())
    if args.model:
        started = time.monotonic()
        try:
            value = await LocalResearchModel().describe_vibe(
                SongIdentity(genius_id='1', title='Test Song', artist='Test Artist').model_dump(),
                [source('https://example.com/review', 'Test Song review',
                        'Test Song by Test Artist has airy vocals, soft percussion, and a dreamy atmosphere.',
                        'written_excerpt')], started + 60)
            print('Local vibe description:', value)
        except Exception as error:
            print('Model check failed:', type(error).__name__)
            return 1
        print('Measured model-check seconds:', round(time.monotonic() - started, 2))
    if args.live:
        for name in ('search_reviews',):
            if not provider.capabilities().get(name):
                print('Skipped', name, '(credential unavailable)')
                continue
            start = time.monotonic()
            try:
                values = await getattr(provider, name)('"Bad Habit" "Steve Lacy" song vibe mood atmosphere sound review -site:youtube.com -site:youtu.be')
                print(name, 'returned', len(values), 'real source records; seconds:', round(time.monotonic()-start, 2))
            except Exception as error:
                print(name, 'failed:', type(error).__name__)
                return 1
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', action='store_true', help='Run one real local-model vibe description.')
    parser.add_argument('--live', action='store_true', help='Probe configured external search APIs.')
    raise SystemExit(asyncio.run(check(parser.parse_args())))
