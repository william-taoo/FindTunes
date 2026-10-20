"""Two tool-using research agents + lyric branch, with fan-out/fan-in validation."""
import asyncio
import operator
import time
import re
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from .schema import (SongIdentity, Source, Decision, SupportCheck,
                     ProfileDraft, GROUPS, unknown_profile, identity_matches, ObservationSelection, Finding)
from .providers import tools_for, source
from .excerpts import relevant_excerpt


class State(TypedDict):
    song: dict
    document: dict | None
    deadline: float
    sources: Annotated[list[dict], operator.add]
    findings: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    profile: dict


async def timed(trace, agent, action, function, deadline, **details):
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(function(), timeout=max(.01, deadline - start))
        trace(agent=agent, action=action, duration_ms=round((time.monotonic()-start)*1000),
              status='ok', **details)
        return result
    except Exception as error:
        # Error classes are safe; HTTP exception strings can contain API keys.
        trace(agent=agent, action=action, duration_ms=round((time.monotonic()-start)*1000),
              status='failed', error=type(error).__name__, **details)
        raise


async def supported_findings(model, sources, song, instruction, deadline, trace, agent):
    if not sources:
        return []
    excerpts = [{'source_index': i, 'title': item['title'], 'sentences':
        [sentence.strip()[:500] for sentence in re.split(r'(?<=[.!?])\s+|\n', item['text']) if sentence.strip()][:20]}
        for i, item in enumerate(sources[:8])]
    selected = await timed(trace, agent, 'extract', lambda: model.ask(ObservationSelection,
        instruction + ' Choose source_index and sentence_index supporting each claim. '
        'Do not generate quotes, IDs, URLs or timestamps; Python attaches the real source excerpt. '
        'At most two short claims. Omit observations if evidence does not support them.',
        {'song': song.model_dump(), 'excerpts': excerpts}, deadline), deadline)
    accepted = []
    for choice in selected.observations[:1]:
        if choice.source_index >= len(excerpts) or choice.sentence_index >= len(excerpts[choice.source_index]['sentences']):
            trace(agent=agent, action='reject_finding', status='invalid_excerpt_index')
            continue
        original = sources[choice.source_index]
        quote = excerpts[choice.source_index]['sentences'][choice.sentence_index]
        if not original['identity_verified'] or quote not in original['text']:
            trace(agent=agent, action='reject_finding', status='invalid_reference_or_quote')
            continue
        finding = Finding(claim=choice.claim, source_id=original['id'], quote=quote,
            category='lyrical_emotions' if agent == 'lyrics' else 'musical_characteristics',
            support='lyrical_interpretation' if agent == 'lyrics' else 'sourced_observation')
        check = await timed(trace, agent, 'validate_claim', lambda: model.ask(SupportCheck,
            'Independently test whether the quoted TEXT supports the claim and concerns this exact song/version. '
            'Title/topic similarity is not support. A lyric cannot establish sound. '
            'An album-wide description does not establish a claim about a particular song. '
            'The quoted passage must explicitly concern this song; attribute criticism and interviews to their sources. '
            'Original means no version qualifier: absence of the word original is not a contradiction. '
            'Lyrics sources are attached to the canonical Genius song ID; reject conflicting versions. '
            'Reject if uncertain or contradicted.',
            {'song': song.model_dump(), 'finding': finding.model_dump(), 'source': original}, deadline), deadline)
        # Lyric identity is already authoritative: fetched and checked by canonical Genius ID.
        # External observations still require the independent song/version check.
        if check.supported and (agent == 'lyrics' or check.exact_song_version):
            accepted.append(finding.model_dump())
        else:
            trace(agent=agent, action='reject_finding', status='unsupported', reason=check.reason,
                  claim_supported=check.supported, exact_song_version=check.exact_song_version)
    return accepted


def build_graph(provider, model, trace=lambda **event: None, mode='deep'):
    tools = tools_for(provider)

    async def research(state, agent):
        song = SongIdentity.model_validate(state['song'])
        deadline = state['deadline']
        sources, errors = [], []
        capabilities = provider.capabilities()
        prefix = f'"{song.title}" "{song.artist}"'
        if song.version != 'original':
            prefix += f' "{song.version}"'
        if agent == 'reviews':
            queries = [prefix + ' song review music criticism -site:youtube.com -site:youtu.be',
                       prefix + ' track review vocals instrumentation mood -site:youtube.com -site:youtu.be',
                       prefix + ' single review production energy -site:youtube.com -site:youtu.be']
            tool_name = 'search_reviews'
            role = ('Find published music criticism about this exact song. Prioritize critic observations '
                    'about mood, vocals, instrumentation, energy, and texture; attribute subjective opinions.')
        else:
            queries = [prefix + ' written artist interview song meaning production -site:youtube.com -site:youtu.be',
                       prefix + ' producer interview recording instrumentation -site:youtube.com -site:youtu.be',
                       prefix + ' artist commentary making of song production -site:youtube.com -site:youtu.be']
            tool_name = 'search_context'
            role = ('Find written artist/producer interviews and production breakdowns about this exact song. '
                    'Prioritize first-hand intent and recording context. Intent alone does not prove audible sound.')
        searches = 0
        if mode == 'quick':
            # Fast evidence retrieval is a fixed workflow, not an LLM-controlled agent.
            for query in queries[:2]:
                if not capabilities.get(tool_name):
                    errors.append({'agent': agent, 'code': 'provider_unavailable', 'message': 'Search provider is not configured.'})
                    break
                try:
                    values = await timed(trace, agent, tool_name,
                        lambda: tools[tool_name].ainvoke({'query': query}), deadline)
                    for value in values:
                        parsed = Source.model_validate(value)
                        excerpt = relevant_excerpt(song, parsed)
                        if identity_matches(song, parsed) and excerpt:
                            parsed = Source.model_validate(source(str(parsed.url), parsed.title, excerpt, 'written_excerpt'))
                            item = parsed.model_dump(mode='json')
                            item['research_role'] = agent
                            # Retrieval matches are not semantically verified findings.
                            item['identity_verified'] = False
                            sources.append(item)
                    if sources:
                        break
                except Exception as error:
                    errors.append({'agent': agent, 'code': type(error).__name__, 'message': 'Search unavailable.'})
            return {'sources': sources, 'findings': [], 'errors': errors}
        findings = []
        try:
            for round_number in range(2):
                if not capabilities.get(tool_name):
                    errors.append({'agent': agent, 'code': 'provider_unavailable', 'message': 'Search provider is not configured.'})
                    break
                option = 0
                # The initial search is mandatory; only a follow-up needs an agent decision.
                if round_number:
                    decision = await timed(trace, agent, 'decide', lambda: model.ask(Decision,
                        f'You are the {agent} research agent. ' + role +
                        ' The first search did not produce a supported observation. Choose search to try '
                        'another query, or finish. Select option 1 or 2; do not repeat option 0.',
                        {'song': song.model_dump(), 'available': ['search', 'finish'], 'queries': queries,
                         'sources': sources[:3], 'errors': errors, 'round': round_number}, deadline), deadline)
                    trace(agent=agent, action='decision', status='ok', decision=decision.model_dump())
                    if decision.action == 'finish':
                        break
                    option = decision.option or 1
                args = {'query': queries[option]}
                try:
                    values = await timed(trace, agent, tool_name,
                        lambda: tools[tool_name].ainvoke(args), deadline, arguments=args)
                except Exception as error:
                    errors.append({'agent': agent, 'code': type(error).__name__, 'message': 'Search failed.'})
                    continue
                for item in values:
                    parsed = Source.model_validate(item)
                    matches = identity_matches(song, parsed)
                    excerpt = relevant_excerpt(song, parsed)
                    if matches and excerpt:
                        parsed = Source.model_validate(source(str(parsed.url), parsed.title, excerpt, 'written_excerpt'))
                    parsed.identity_verified = bool(matches and excerpt)
                    if parsed.identity_verified and parsed.id not in {s['id'] for s in sources}:
                        value = parsed.model_dump(mode='json')
                        value['research_role'] = agent
                        sources.append(value)
                    elif not parsed.identity_verified:
                        trace(agent=agent, action='reject_source', status='identity_mismatch', source_id=parsed.id)
                # This publishes retrieval matches, never verified findings, before inference.
                if sources:
                    trace(agent=agent, action='evidence_ready', status='ok', sources=sources)
                    findings = await supported_findings(model, sources, song,
                        role + ' Extract at most ONE musical observation explicitly supported by the written excerpt. '
                        'Reject album-wide claims without song-specific evidence. Do not infer sound from intent alone.',
                        deadline, trace, agent)
                    if findings:
                        break
        except Exception as error:
            findings = []
            errors.append({'agent': agent, 'code': type(error).__name__, 'message': 'Research unavailable or output rejected.'})
        return {'sources': sources, 'findings': findings, 'errors': errors}

    async def reviews(state):
        return await research(state, 'reviews')

    async def context(state):
        return await research(state, 'context')

    async def lyrics(state):
        document = state.get('document')
        if not document:
            return {'errors': [{'agent': 'lyrics', 'code': 'lyrics_unavailable', 'message': 'No lyric document.'}]}
        song = SongIdentity.model_validate(state['song'])
        from services.passage_retrieval import representative_passages
        groups = representative_passages(document)
        items = []
        for group in groups:
            item = source(document['source_url'], f'{song.title} — {song.artist}',
                          '\n'.join(line['text'] for line in group), 'lyrics')
            item.update(identity_verified=True, line_ids=[line['id'] for line in group])
            items.append(item)
        trace(agent='lyrics', action='passage_selection', status='ok',
              total_lines=len(document['lines']), selected_lines=sum(len(group) for group in groups),
              sections=list(dict.fromkeys(line.get('section', 'Lyrics') for group in groups for line in group)))
        if mode == 'quick':
            return {'sources': items, 'findings': []}
        try:
            findings = await supported_findings(model, items, song,
                'Interpret lyrical emotions from ONLY supplied excerpts; use lyrical_emotions / lyrical_interpretation. '
                'No musical or combined vibe claims.', state['deadline'], trace, 'lyrics')
            return {'sources': items, 'findings': findings}
        except Exception as error:
            return {'sources': items, 'errors': [{'agent': 'lyrics', 'code': type(error).__name__, 'message': 'Lyric interpretation unavailable.'}]}

    async def synthesize(state):
        profile = unknown_profile()
        if not state['findings']:
            return {'profile': profile}
        try:
            draft = await timed(trace, 'synthesis', 'profile', lambda: model.ask(ProfileDraft,
                'Apply low/medium/high to strength/prominence, NOT probabilities. Low=weak/subtle, '
                'medium=clear/mixed, high=dominant/explicit. Unknown=insufficient evidence. '
                'Multiple emotions can coexist. Use exact permitted labels. Each explanation must cite finding INDEXES. '
                'Musical characteristics require musical observations. Combined vibe requires BOTH lyric and musical findings. '
                'Do not infer tempo, sound, or instruments from lyrics.',
                {'findings': state['findings'], 'labels': GROUPS}, state['deadline']), state['deadline'])
            remaining_ratings = 1
            for group, ratings in draft.model_dump().items():
                for rating in ratings:
                    if not remaining_ratings:
                        break
                    refs = rating['finding_ids']
                    if rating['label'] not in GROUPS[group] or not refs or any(i < 0 or i >= len(state['findings']) for i in refs):
                        continue
                    categories = {state['findings'][i]['category'] for i in refs}
                    required = {'lyrical_emotions', 'musical_characteristics'} if group == 'combined_vibe' else {group}
                    if not required.issubset(categories):
                        continue
                    remaining_ratings -= 1
                    check = await timed(trace, 'synthesis', 'validate_rating', lambda: model.ask(SupportCheck,
                        'Does the evidence actually support this rating LEVEL and explanation? Reject speculative sound claims '
                        'or unsupported intensity. Combined vibe is interpretation, not measured audio.',
                        {'song': state['song'], 'rating': rating, 'evidence': [state['findings'][i] for i in refs]}, state['deadline']), state['deadline'])
                    if check.supported and check.exact_song_version:
                        profile[group] = [rating if row['label'] == rating['label'] else row for row in profile[group]]
        except Exception as error:
            return {'profile': profile, 'errors': [{'agent': 'synthesis', 'code': type(error).__name__, 'message': 'Partial profile; unsupported ratings stay unknown.'}]}
        return {'profile': profile}

    graph = StateGraph(State)
    for name, function in [('reviews', reviews), ('context', context), ('lyrics', lyrics), ('synthesis', synthesize)]:
        graph.add_node(name, function)
    for name in ('reviews', 'context', 'lyrics'):
        graph.add_edge(START, name)
    graph.add_edge(['reviews', 'context', 'lyrics'], 'synthesis')
    graph.add_edge('synthesis', END)
    return graph.compile()


async def research_song(song, document, provider, model, cache, deadline, trace, mode='deep'):
    import hashlib
    import json
    import os
    # Capability/model changes invalidate cached unavailable profiles.
    config_key = hashlib.sha256(json.dumps([mode, provider.capabilities(), os.getenv('LOCAL_LLM_MODEL', 'Qwen/Qwen3-0.6B')], sort_keys=True).encode()).hexdigest()[:10]
    key = hashlib.sha256((song.cache_key() + config_key).encode()).hexdigest()
    cache_error = []
    try:
        cached = await asyncio.wait_for(cache.get(key), timeout=max(.1, min(3, deadline - time.monotonic())))
        if cached:
            trace(agent='cache', action='hit', status='ok', song_id=song.genius_id)
            return {**cached, 'cached': True}
    except Exception:
        cache_error = [{'agent': 'cache', 'code': 'cache_unavailable', 'message': 'Run the research cache migration; research can still proceed.'}]
    result = await build_graph(provider, model, trace, mode=mode).ainvoke({'song': song.model_dump(),
        'document': document, 'deadline': deadline, 'sources': [], 'findings': [], 'errors': cache_error},
        config={'recursion_limit': 8})
    # Deduplicate provenance and omit lyric source text from persisted/output profiles.
    sources = {s['id']: {**s, 'text': '' if s['kind'] == 'lyrics' else s['text']} for s in result['sources']}
    has_ratings = any(row['level'] != 'unknown' for rows in result['profile'].values() for row in rows)
    payload = {'mode': mode, 'analysis_status': 'complete' if (result['findings'] or has_ratings) and not result['errors'] else 'partial',
        'song': song.model_dump(), 'profile': result['profile'], 'findings': result['findings'],
        'sources': list(sources.values()), 'errors': result['errors'], 'cached': False,
        'evidence_availability': {kind: any(s['kind'] == kind for s in sources.values())
            for kind in ('lyrics', 'written_excerpt')}}
    try:
        await asyncio.wait_for(cache.put(key, payload), timeout=3)
    except Exception:
        payload['errors'].append({'agent': 'cache', 'code': 'cache_write_failed', 'message': 'Profile not persisted.'})
    return payload
