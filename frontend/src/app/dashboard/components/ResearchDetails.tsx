export interface Rating { label: string; level: 'low' | 'medium' | 'high' | 'unknown'; explanation: string; finding_ids: number[]; }
export interface ResearchProfile {
    mode?: 'quick' | 'deep';
    song: { title: string; artist: string; version: string };
    profile: Record<string, Rating[]>;
    findings: { claim: string; quote: string; source_id: string; category: string; support: string }[];
    sources: { id: string; url: string; title: string; text?: string; research_role?: string; kind: string; timestamp_seconds: number | null }[];
    errors: { code: string; message?: string }[];
    cached: boolean;
    analysis_status?: string;
}
export interface ResearchResult {
    lyric_overlap?: { shared_words: string[]; seed_lines_scanned: number; candidate_lines_scanned: number; seed_sections: string[]; candidate_sections: string[]; limitation: string } | null;
    status: string;
    profile: ResearchProfile | null;
    comparison: { similarities: {label: string; explanation: string}[]; differences: {label: string; explanation: string}[]; limitation: string } | null;
    explanation: {summary: string; shared_themes: string[]; difference: string} | null;
    sources: {seed: string; candidate: string} | null;
}
export interface ResearchJob {
    id: string; status: string; progress: string; seed: ResearchProfile | null;
    results: Record<string, ResearchResult>;
    trace: {agent: string; action: string; duration_ms?: number; status: string; decision?: {action: string; reason: string}}[];
}
const labels: Record<string, string> = {lyrical_emotions: 'Lyrical emotions', musical_characteristics: 'Musical characteristics', combined_vibe: 'Combined vibe'};

function Profile({ profile }: {profile: ResearchProfile}) {
    return <div className="ft-research-profile"><h4>{profile.song.title} · {profile.song.artist}</h4>
        <p className="ft-muted">{profile.song.version} · {profile.cached ? 'Cached research' : 'New research'}</p>
        {Object.entries(profile.profile).filter(([, rows]) => rows.some(row => row.level !== 'unknown')).map(([category, rows]) => <section key={category}>
            <h4>{labels[category] || category}</h4><div className="ft-rating-grid">{rows.filter(row => row.level !== 'unknown').map(row => <div key={row.label} className="ft-rating"><strong>{row.label}</strong><span>{row.level}</span><p>{row.explanation}</p></div>)}</div>
        </section>)}
        {!!profile.findings.length && <details><summary>Supporting observations and sources</summary>{profile.findings.map((finding, index) => {
            const source = profile.sources.find(value => value.id === finding.source_id);
            if (!source) return null;
            let link: URL;
            try { link = new URL(source.url); if(link.protocol !== 'https:') return null; } catch { return null; }
            return <div key={index} className="ft-observation"><p>{finding.claim}</p><small>{finding.support.replaceAll('_', ' ')} · {source.kind.replaceAll('_', ' ')}</small>
                {source.kind !== 'lyrics' && <blockquote>{finding.quote}</blockquote>}
                <a href={link.href} target="_blank" rel="noopener noreferrer">{source.title} ↗</a></div>;
        })}</details>}
        {profile.errors.length > 0 && <p className="ft-muted">{profile.errors.some(error => error.code.includes('Timeout')) ? 'Local AI did not finish within its budget. Retrieved excerpts remain available.' : 'Some AI analysis is unavailable. Only supported observations are shown.'}</p>}
    </div>;
}

function SourceExcerpts({ profile }: {profile?: ResearchProfile | null}) {
    const seen = new Set<string>();
    const written = (profile?.sources || []).filter(source => {
        if (source.kind !== 'written_excerpt' || seen.has(source.url)) return false;
        seen.add(source.url); return true;
    }).slice(0, 4);
    return <section><h4>Reviews and production context</h4>
        <p className="ft-muted">Matched search excerpts, not full articles or verified AI conclusions.</p>
        {written.length ? written.map(source => {
            let url: URL; try { url = new URL(source.url); if(url.protocol !== 'https:') return null; } catch { return null; }
            return <div className="ft-observation" key={source.id}><small>{source.research_role === 'context' ? 'Artist / production search' : 'Review search'}</small>
                <p>{source.text}</p><a href={url.href} target="_blank" rel="noopener noreferrer">{source.title} ↗</a></div>;
        }) : <p className="ft-muted">{profile?.analysis_status === 'running' ? 'Gathering sources…' : 'No matching written excerpts are available yet.'}</p>}
    </section>;
}

export default function ResearchDetails({ result, seed }: {result?: ResearchResult; seed?: ResearchProfile | null}) {
    const profile = result?.profile;
    const hasRatings = !!profile && Object.values(profile.profile).some(rows => rows.some(row => row.level !== 'unknown'));
    const hasObservations = !!profile?.findings.length;
    const comparison = result?.comparison;
    const hasComparison = !!comparison && (comparison.similarities.length > 0 || comparison.differences.length > 0);
    return <div className="ft-research-details"><h3>{hasRatings ? 'Lyrics, sound, and vibe' : 'Retrieved evidence'}</h3>
        {result?.lyric_overlap && <div className="ft-difference"><h4>Across the lyrics</h4>
            <p>Scanned {result.lyric_overlap.seed_lines_scanned} original lines and {result.lyric_overlap.candidate_lines_scanned} suggestion lines across all available lyric sections.</p>
            <p>{result.lyric_overlap.shared_words.length ? `Shared wording: ${result.lyric_overlap.shared_words.join(', ')}.` : 'No shared content words found.'}</p>
            <p>{result.lyric_overlap.limitation}</p></div>}
        <SourceExcerpts profile={profile}/>
        {hasComparison && <div className="ft-difference">
            {!!comparison.similarities.length && <><h4>Similarities</h4>{comparison.similarities.map(item => <p key={item.label}>{item.explanation}</p>)}</>}
            {!!comparison.differences.length && <><h4>Differences</h4>{comparison.differences.map(item => <p key={item.label}>{item.explanation}</p>)}</>}
        </div>}
        {hasRatings && <p className="ft-muted">Low, medium, and high describe prominence in the evidence, not measured audio. Combined vibe is an interpretation.</p>}
        {profile && (hasRatings || hasObservations) ? <Profile profile={profile}/> : <p className="ft-muted">{
            !result || result.status === 'running' || profile?.analysis_status === 'running' ? 'AI interpretation is still running; you can inspect the sources above now.' :
            profile?.mode === 'quick' ? 'AI profiles were not requested.' : 'No reliable AI profile was produced. This does not mean the songs lack these qualities; the available sources are shown above.'
        }</p>}
        {profile?.errors.some(error => error.code.includes('Timeout')) && !hasRatings && !hasObservations && <p className="ft-muted">Local AI reached its time budget.</p>}
        {seed && (seed.findings.length > 0 || Object.values(seed.profile).some(rows => rows.some(row => row.level !== 'unknown'))) && <details><summary>Compare with the original song</summary><Profile profile={seed}/></details>}
    </div>;
}
