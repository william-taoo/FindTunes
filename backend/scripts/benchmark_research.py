"""Repeatable local inference probe; --live adds four Brave searches (uses quota).

Synthetic cases measure grounding, not real-world music knowledge. No model downloads.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    import torch
    from services.local_llm import load_model
    report = {'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(),
              'device': os.getenv('LOCAL_LLM_DEVICE', 'cpu'), 'cases': [], 'searches': []}
    started = time.perf_counter()
    tokenizer, model = load_model()
    report['load_seconds'] = round(time.perf_counter() - started, 3)
    cases = [
        ('supported', 'The review of Paper Moon by Test Artist describes its brisk drums and energetic bass.', True),
        ('unsupported', 'Paper Moon by Test Artist was released on Friday. The article lists its release date.', False),
        ('wrong_song', 'The review describes Other Song by Another Artist as energetic. Paper Moon by Test Artist is mentioned only in a release list.', False),
    ]
    for name, evidence, expected in cases:
        messages = [{'role': 'system', 'content': 'Use only the supplied text. Return only JSON with supported (boolean) and reason (under 15 words). Decide whether the text supports high musical energy for Paper Moon by Test Artist. A different song is not evidence.'},
                    {'role': 'user', 'content': evidence}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(text, return_tensors='pt').to(model.device)
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=80, max_time=30, do_sample=False,
                                    pad_token_id=tokenizer.eos_token_id)
        if model.device.type == 'cuda':
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        tokens = output.shape[-1] - inputs.input_ids.shape[-1]
        answer = tokenizer.decode(output[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True)
        try:
            parsed = json.loads(answer)
            passed = parsed.get('supported') is expected
            semantic_passed = parsed.get('supported', parsed.get('high_musical_energy')) is expected
        except ValueError:
            passed = False
            semantic_passed = False
        report['cases'].append({'case': name, 'seconds': round(elapsed, 3), 'tokens': tokens,
                                'tokens_per_second': round(tokens / elapsed, 2), 'schema_and_answer_passed': passed,
                                'semantic_answer_passed': semantic_passed, 'answer': answer})
        print(json.dumps(report['cases'][-1]), flush=True)
    if args.live:
        import httpx
        key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise RuntimeError('BRAVE_SEARCH_API_KEY missing')
        for song, artist in [('Bad Habit', 'Steve Lacy'), ('7 Minute Drill', 'J. Cole')]:
            for role, suffix in [('reviews', 'song review sound production'), ('context', 'producer interview production')]:
                started = time.perf_counter()
                try:
                    response = httpx.get('https://api.search.brave.com/res/v1/web/search',
                        headers={'X-Subscription-Token': key}, params={'q': f'"{song}" "{artist}" {suffix} -site:youtube.com',
                        'count': 5, 'extra_snippets': 'true'}, timeout=10)
                    response.raise_for_status()
                    results = [{k: item.get(k) for k in ('title', 'url', 'description', 'extra_snippets')}
                               for item in response.json().get('web', {}).get('results', [])[:5]]
                    entry = {'song': song, 'role': role, 'seconds': round(time.perf_counter()-started, 3), 'results': results}
                except Exception as error:
                    # Never print request headers or credentials.
                    entry = {'song': song, 'role': role, 'error': type(error).__name__}
                report['searches'].append(entry)
                print(json.dumps({k: v for k, v in entry.items() if k != 'results'}), flush=True)
    target = Path(__file__).resolve().parents[1] / '.research-traces' / 'benchmark-latest.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(str(target), flush=True)


if __name__ == '__main__':
    main()
