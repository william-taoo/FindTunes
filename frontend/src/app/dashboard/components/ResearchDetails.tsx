export interface Rating { label: string; level: 'low' | 'medium' | 'high' | 'unknown'; explanation: string; finding_ids: number[]; }
export type ResearchOutcome = 'searching' | 'analyzing' | 'sources_only' | 'vibe_ready' |
    'no_sources' | 'analysis_failed' | 'search_failed' | 'unavailable';
export interface ResearchProfile {
    mode?: 'quick' | 'vibe' | 'deep';
    song: { title: string; artist: string; version: string };
    profile: Record<string, Rating[]>;
    findings: { claim: string; quote: string; source_id: string; category: string; support: string }[];
    sources: { id: string; url: string; title: string; text?: string; research_role?: string; kind: string; timestamp_seconds: number | null }[];
    errors: { code: string; message?: string }[];
    cached: boolean;
    analysis_status?: string;
    outcome?: ResearchOutcome;
    outcome_reason?: string | null;
    vibe?: string | null;
    compares_to_seed?: boolean;
}
export interface ResearchResult {
    lyric_overlap?: { shared_words: string[]; seed_lines_scanned: number; candidate_lines_scanned: number; seed_sections: string[]; candidate_sections: string[]; limitation: string } | null;
    status: string;
    vibe_description?: string | null;
    profile: ResearchProfile | null;
    comparison: { similarities: {label: string; explanation: string}[]; differences: {label: string; explanation: string}[]; limitation: string } | null;
    explanation: {summary: string; shared_themes: string[]; difference: string} | null;
    sources: {seed: string | null; candidate: string | null} | null;
}
export interface ResearchJob {
    id: string; status: string; progress: string; seed: ResearchProfile | null; mode?: 'quick' | 'vibe' | 'deep' | 'lyrics_links';
    results: Record<string, ResearchResult>;
    trace: {agent: string; action: string; duration_ms?: number; status: string; decision?: {action: string; reason: string}}[];
}
export function musicalOutcome(result?: ResearchResult): {code: ResearchOutcome; label: string; message: string} {
    const profile = result?.profile;
    const code: ResearchOutcome = profile?.vibe || result?.vibe_description ? 'vibe_ready' :
        profile?.outcome === 'searching' || profile?.outcome === 'analyzing' || profile?.outcome === 'sources_only' ||
        profile?.outcome === 'no_sources' || profile?.outcome === 'analysis_failed' || profile?.outcome === 'search_failed' ? profile.outcome :
        profile?.analysis_status === 'running' ? (profile.sources.length ? 'analyzing' : 'searching') :
        profile?.mode === 'quick' ? 'sources_only' : profile?.errors.length ? 'analysis_failed' :
        profile ? 'no_sources' : result?.status === 'running' ? 'searching' : 'unavailable';
    const outcomes: Record<ResearchOutcome, {label: string; message: string}> = {
        searching: {label: 'Finding the vibe…', message: 'Looking up the song’s mood and sound.'},
        analyzing: {label: 'Writing the vibe description…', message: 'Putting the song’s overall feel into words.'},
        sources_only: {label: 'Sources only', message: 'AI vibe descriptions are off. You can read the source excerpts below.'},
        vibe_ready: {label: profile?.compares_to_seed ? 'Vibe compared with your song' : 'Song vibe',
            message: 'An AI interpretation of written descriptions.'},
        no_sources: {label: 'Vibe description unavailable', message: 'This search did not find enough song-specific context to describe the vibe.'},
        analysis_failed: {label: 'Vibe description unavailable', message: profile?.outcome_reason === 'timeout' ?
            'The vibe description ran out of time. Any retrieved sources are still available below.' :
            'The vibe description could not be completed. Any retrieved sources are still available below.'},
        search_failed: {label: 'Vibe lookup unavailable', message: 'The song lookup could not complete. Your lyric-based recommendation is still available.'},
        unavailable: {label: 'Vibe lookup unavailable', message: 'A vibe description is not available for this recommendation yet.'},
    };
    return {code, ...outcomes[code]};
}

export function musicalStatus(result?: ResearchResult) {
    return musicalOutcome(result).label;
}

export function vibeDescription(result?: ResearchResult) {
    return result?.vibe_description || result?.profile?.vibe || null;
}

function SourceExcerpts({ profile }: {profile?: ResearchProfile | null}) {
    const seen = new Set<string>();
    const sources = (profile?.sources || []).filter(source => {
        if (source.kind !== 'written_excerpt' || seen.has(source.url)) return false;
        seen.add(source.url); return true;
    }).slice(0, 4);
    if (!sources.length) return null;
    return <details open><summary>{profile?.mode === 'quick' ? 'Written excerpts' : 'Sources behind the vibe'}</summary>
        {sources.map(source => {
            let url: URL;
            try { url = new URL(source.url); if (url.protocol !== 'https:') return null; } catch { return null; }
            return <div className="ft-observation" key={source.id}><p>{source.text}</p>
                <a href={url.href} target="_blank" rel="noopener noreferrer">{source.title} ↗</a></div>;
        })}
    </details>;
}

export default function ResearchDetails({ result, seed }: {result?: ResearchResult; seed?: ResearchProfile | null}) {
    if (!result?.profile && !result?.vibe_description && !seed && !result?.lyric_overlap) return null;
    const outcome = musicalOutcome(result);
    const description = vibeDescription(result);
    const writtenOnly = result?.profile?.mode === 'quick' || seed?.mode === 'quick' || outcome.code === 'sources_only';
    const showVibe = !writtenOnly && Boolean(result?.profile || description || seed?.vibe);
    return <div className="ft-research-details">
        {showVibe && <section className="ft-ai-observation" aria-label="Song vibe">
            <h3>The vibe</h3>
            {description ? <><p>{description}</p><p className="ft-muted">{outcome.message}</p></> :
                <><p className="ft-muted" role="status">{outcome.label}</p><p>{outcome.message}</p></>}
            {seed?.vibe && <div className="ft-difference"><h4>Your song · {seed.song.title}</h4><p>{seed.vibe}</p></div>}
        </section>}
        {writtenOnly && <section className="ft-ai-observation" aria-label="Written sources">
            <h3>Written sources</h3>
            <p className="ft-muted" role="status">{outcome.code === 'sources_only' ? 'Sources only' :
                outcome.code === 'searching' || result?.status === 'running' ? 'Looking up written sources…' :
                'No written excerpts available for this track.'}</p>
        </section>}
        <SourceExcerpts profile={result?.profile}/>
        {seed?.sources.length ? <details open><summary>Sources for your song</summary><SourceExcerpts profile={seed}/></details> : null}
        {(seed?.sources.length || result?.profile?.sources.length) ? <p className="ft-muted">Web search by <a href="https://brave.com/search/api/" target="_blank" rel="noopener noreferrer">Brave</a></p> : null}
        {result?.lyric_overlap && <details open><summary>Lyric wording comparison</summary>
            <p>Scanned {result.lyric_overlap.seed_lines_scanned} original lines and {result.lyric_overlap.candidate_lines_scanned} suggestion lines across all available lyric sections.</p>
            <p>{result.lyric_overlap.shared_words.length ? `Shared wording: ${result.lyric_overlap.shared_words.join(', ')}.` : 'No shared content words found.'}</p>
            <p>{result.lyric_overlap.limitation}</p></details>}
    </div>;
}
