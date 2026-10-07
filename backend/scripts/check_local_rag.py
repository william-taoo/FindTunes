"""Smoke-test real local generation using original, synthetic lyric-like text."""
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from services.rag import explain_match, ExplanationUnavailableError


def document(song_id, title, texts):
    return {'song_id': song_id, 'title': title, 'artist': 'Synthetic example',
            'source_url': '', 'lines': [
                {'id': f'L{i + 1}', 'section': 'Verse', 'text': text}
                for i, text in enumerate(texts)]}


if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    seed = document('1', 'Empty room', [
        'I miss our conversations in this empty room.',
        'I keep your letters because I cannot let go.',
    ])
    candidate = document('2', 'Old messages', [
        'I read your old messages and wish you were here.',
        'Tomorrow I will move on, but tonight I remember.',
    ])
    start = perf_counter()
    try:
        result = explain_match(seed, candidate)
    except ExplanationUnavailableError as error:
        print(f'Local comparison unavailable: {error}', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))
    print(f'Local comparison completed in {perf_counter() - start:.1f}s')
