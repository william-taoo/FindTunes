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
