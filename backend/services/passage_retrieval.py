"""Small, deterministic passage selection without another model download."""
import re

STOP_WORDS = set('a an the and or but i me my we us our you your he she it they them their is are was were be been to of in on at for with from this that these those as not do does did have has had can will would'.split())


def passages(document):
    groups = []
    current = []
    for line in document['lines']:
        if current and (len(current) == 6 or line['section'] != current[-1]['section']):
            groups.append(current)
            current = []
        current.append(line)
    if current:
        groups.append(current)
    return groups


def content_words(lines):
    return set(re.findall(r"[a-z]+", ' '.join(line['text'] for line in lines).lower())) - STOP_WORDS


def select_passages(seed, candidate):
    """Rank by word overlap; this is a locator, not proof of thematic similarity."""
    seed_groups, candidate_groups = passages(seed), passages(candidate)
    if not seed_groups or not candidate_groups:
        raise ValueError('Both songs need lyric lines')
    seed_words = [content_words(group) for group in seed_groups]
    candidate_words = [content_words(group) for group in candidate_groups]
    best = (-1, 0, 0)
    for i, left in enumerate(seed_words):
        for j, right in enumerate(candidate_words):
            union = left | right
            score = len(left & right) / len(union) if union else 0
            if score > best[0]:
                best = (score, i, j)
    return seed_groups[best[1]], candidate_groups[best[2]]


def representative_passages(document, max_passages=4, max_chars=2800):
    """Scan all sections, deduplicate repetitions, then sample informative passages across the song.

    This is bounded coverage, not a claim that the model read every line.
    """
    candidates, seen = [], set()
    for group in passages(document):
        signature = tuple(line['text'].casefold().strip() for line in group)
        if signature not in seen and len(content_words(group)) >= 2:
            candidates.append(group)
            seen.add(signature)
    if not candidates:
        candidates = passages(document)
    if len(candidates) <= 8 and sum(len(row['text']) + 1 for group in candidates for row in group) <= max_chars:
        return candidates
    chosen = []
    count = min(max_passages, len(candidates))
    for bucket in range(count):
        start, end = bucket * len(candidates) // count, (bucket + 1) * len(candidates) // count
        group = max(candidates[start:end], key=lambda rows: len(content_words(rows)))
        chosen.append(group)
    remaining, result = max_chars, []
    for i, group in enumerate(chosen):
        # Reserve room for later sections instead of consuming it all at the opening.
        allowance = remaining // (len(chosen) - i)
        rows = []
        for line in group:
            cost = len(line['text']) + 1
            if cost <= allowance:
                rows.append(line)
                allowance -= cost
                remaining -= cost
        if rows:
            result.append(rows)
    return result


def lyric_overlap(seed, candidate):
    """A transparent, non-generative comparison across all lyric sections."""
    left, right = content_words(seed['lines']), content_words(candidate['lines'])
    shared = sorted(left & right, key=lambda word: (-len(word), word))[:8]
    return {'shared_words': shared,
            'seed_lines_scanned': len(seed['lines']), 'candidate_lines_scanned': len(candidate['lines']),
            'seed_sections': list(dict.fromkeys(line.get('section', 'Lyrics') for line in seed['lines'])),
            'candidate_sections': list(dict.fromkeys(line.get('section', 'Lyrics') for line in candidate['lines'])),
            'limitation': 'Shared words are lexical overlap, not proof of a shared theme or musical feel.'}
