"""One song-vibe search and one short prose summary per song."""
import asyncio
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .schema import SongIdentity, Source, unknown_profile, identity_matches, ResearchOutcome
from .providers import tools_for, source
from .excerpts import relevant_excerpt


class State(TypedDict):
    song: dict
    deadline: float
    sources: list[dict]
    findings: list[dict]
    errors: list[dict]
    profile: dict
    outcome: ResearchOutcome
    outcome_reason: str | None
    vibe: str | None
    compares_to_seed: bool


async def timed(trace, agent, action, function, deadline, **details):
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(function(), timeout=max(.01, deadline - start))
        trace(agent=agent, action=action, duration_ms=round((time.monotonic()-start)*1000),
              status='ok', **details)
        return result
    except Exception as error:
        # Exception messages can contain provider credentials.
        trace(agent=agent, action=action, duration_ms=round((time.monotonic()-start)*1000),
              status='failed', error=type(error).__name__, **details)
        raise


def build_graph(provider, model, trace=lambda **event: None, mode='vibe', inference_gate=None, seed_profile=None):
    tools = tools_for(provider)

    async def research(state):
        song = SongIdentity.model_validate(state['song'])
        if not provider.capabilities().get('search_reviews'):
            return {'sources': [], 'outcome': 'search_failed', 'outcome_reason': 'provider_unavailable',
                    'errors': [{'agent': 'music', 'code': 'provider_unavailable',
                                              'message': 'Search provider is not configured.'}]}
        prefix = f'"{song.title}" "{song.artist}"'
        if song.version != 'original':
            prefix += f' "{song.version}"'
        query = prefix + ' song vibe mood atmosphere sound review -site:youtube.com -site:youtu.be'
        sources = {}
        try:
            values = await timed(trace, 'music', 'search_reviews',
                lambda: tools['search_reviews'].ainvoke({'query': query}), state['deadline'],
                arguments={'query': query})
            for value in values:
                parsed = Source.model_validate(value)
                excerpt = relevant_excerpt(song, parsed)
                if not identity_matches(song, parsed) or not excerpt:
                    trace(agent='music', action='reject_source', status='identity_mismatch', source_id=parsed.id)
                    continue
                item = source(str(parsed.url), parsed.title, excerpt, 'written_excerpt')
                item.update(research_role='music', identity_verified=False)
                sources[item['id']] = item
        except Exception as error:
            return {'sources': list(sources.values()), 'outcome': 'search_failed',
                'outcome_reason': 'timeout' if isinstance(error, TimeoutError) else 'search_error',
                'errors': [{'agent': 'music',
                'code': type(error).__name__, 'message': 'Musical search unavailable; no retry was made.'}]}
        if sources:
            trace(agent='music', action='evidence_ready', status='ok', sources=list(sources.values()))
        # Retrieval matches are not semantically verified findings. Never search again.
        return {'sources': list(sources.values()), 'errors': [], 'outcome_reason': None,
                'outcome': ('sources_only' if mode == 'quick' else 'analyzing') if sources else 'no_sources'}

    async def interpret(state):
        if mode == 'quick' or not state['sources'] or state['outcome'] == 'search_failed':
            return {'profile': unknown_profile(), 'findings': []}
        try:
            reference = None
            if seed_profile is not None:
                try:
                    seed = await asyncio.wait_for(asyncio.shield(seed_profile),
                        timeout=max(.01, state['deadline'] - time.monotonic()))
                    if seed and seed.get('vibe'):
                        reference = {'song': seed['song'], 'vibe': seed['vibe']}
                except Exception:
                    # Missing input-song context should not prevent a candidate description.
                    reference = None
            if inference_gate is None:
                return await interpret_work(state, reference)
            await asyncio.wait_for(inference_gate.acquire(), timeout=max(.01, state['deadline'] - time.monotonic()))
            try:
                return await interpret_work(state, reference)
            finally:
                inference_gate.release()
        except Exception as error:
            reason = ('timeout' if isinstance(error, TimeoutError) else
                      'invalid_output' if type(error).__name__ in ('ValidationError', 'OutputParserException') else
                      'call_limit' if type(error).__name__ == 'InferenceBudgetExceeded' else 'model_error')
            return {'profile': unknown_profile(), 'findings': [], 'outcome': 'analysis_failed',
                'outcome_reason': reason, 'errors': [*state['errors'],
                {'agent': 'music', 'code': type(error).__name__,
                 'message': 'Musical interpretation unavailable; retrieved excerpts retained.'}]}

    async def interpret_work(state, reference):
        vibe = await timed(trace, 'vibe', 'describe', lambda: model.describe_vibe(
            state['song'], state['sources'], state['deadline'], reference=reference), state['deadline'])
        return {'profile': unknown_profile(), 'findings': [], 'vibe': vibe,
                'compares_to_seed': bool(reference), 'outcome': 'vibe_ready', 'outcome_reason': None}

    graph = StateGraph(State)
    graph.add_node('music', research)
    graph.add_node('interpret', interpret)
    graph.add_edge(START, 'music')
    graph.add_edge('music', 'interpret')
    graph.add_edge('interpret', END)
    return graph.compile()


async def research_song(song, document, provider, model, deadline, trace, mode='vibe', inference_gate=None, seed_profile=None):
    # Lyrics remain in the existing retrieval/comparison path, outside musical research.
    result = await build_graph(provider, model, trace, mode=mode, inference_gate=inference_gate, seed_profile=seed_profile).ainvoke({
        'song': song.model_dump(), 'deadline': deadline, 'sources': [], 'findings': [],
        'errors': [], 'profile': unknown_profile(), 'outcome': 'searching',
        'outcome_reason': None, 'vibe': None, 'compares_to_seed': False}, config={'recursion_limit': 8})
    return {'mode': mode, 'analysis_status': 'complete' if result.get('vibe') or mode == 'quick' and not result['errors'] else 'partial',
        'song': song.model_dump(), 'profile': result['profile'], 'findings': result['findings'],
        'sources': result['sources'], 'errors': result['errors'], 'cached': False,
        'vibe': result.get('vibe'), 'compares_to_seed': result.get('compares_to_seed', False),
        'vibe_basis': 'search_excerpts',
        'outcome': result['outcome'], 'outcome_reason': result['outcome_reason'],
        'evidence_availability': {'lyrics': False, 'written_excerpt': bool(result['sources'])}}
