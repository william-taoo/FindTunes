"""Read-only Pinecone + Genius + local LLM demo, independent of Spotify login."""
import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv

load_dotenv(BACKEND / '.env')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--genius-id', help='Use a specific song already indexed in Pinecone')
    parser.add_argument('--output', type=Path, default=BACKEND / 'live-rag-result.json')
    args = parser.parse_args()
    from services.pinecone_utils import index, NAMESPACE, TOP_K
    from services.lyric_retrieval import make_genius_client, fetch_song_document
    from services.rag import explain_match

    client = make_genius_client()
    ids = ([args.genius_id] if args.genius_id else
           [vector.id for vector in index.list_paginated(namespace=NAMESPACE, limit=5).vectors])
    seed = None
    for song_id in ids:
        if not index.fetch(ids=[str(song_id)], namespace=NAMESPACE).vectors:
            continue
        try:
            seed = fetch_song_document(client, song_id)
        except Exception:
            print(f'Could not fetch lyrics for indexed song {song_id}', file=sys.stderr)
        if seed:
            break
    if not seed:
        raise RuntimeError('No usable seed lyrics found. Try --genius-id with another indexed song.')

    print(f"Seed: {seed['title']} by {seed['artist']} (Genius ID {seed['song_id']})", flush=True)
    matches = index.query(id=seed['song_id'], namespace=NAMESPACE,
                          top_k=TOP_K + 1, include_metadata=True)
    results = []
    for match in [m for m in matches.matches if str(m.id) != seed['song_id']][:TOP_K]:
        print(f'Comparing candidate {match.id}...', flush=True)
        result = {'id': str(match.id), 'score': match.score, 'metadata': match.metadata,
                  'explanation_status': 'unavailable', 'explanation': None, 'sources': None}
        try:
            candidate = fetch_song_document(client, match.id)
            if candidate:
                result['sources'] = {'seed': seed['source_url'], 'candidate': candidate['source_url']}
                result['explanation'] = explain_match(seed, candidate)
                result['explanation_status'] = 'complete'
        except Exception as error:
            print(f'Candidate {match.id}: explanation unavailable ({type(error).__name__})', file=sys.stderr)
        results.append(result)
    payload = {'seed': {key: value for key, value in seed.items() if key != 'lines'},
               'recommendations': results}
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    completed = sum(result['explanation_status'] == 'complete' for result in results)
    print(f'{completed}/{len(results)} explanations completed. Saved to {args.output}')
    return 0 if completed else 1


if __name__ == '__main__':
    sys.exit(main())
