'use client';
import { useState, useEffect, useRef, useId } from 'react';
import axios from 'axios';
import useSongArtwork from './useSongArtwork';
import ResearchDetails, {type ResearchResult, type ResearchProfile, type ResearchJob} from './ResearchDetails';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';

export interface Recommendation {
    id: string;
    score: number;
    seed_song?: { id: string; title: string; artist: string };
    metadata: { title: string; artist: string | string[]; spotify_track_url?: string; image_url?: string; spotify_track_id?: string };
    explanation_status: 'complete' | 'unavailable' | 'disabled' | 'pending';
    research?: ResearchResult;
    explanation: { summary: string; shared_themes: string[]; difference: string } | null;
    sources: { seed: string; candidate: string } | null;
}

function safeLink(url?: string) {
    try { const parsed = new URL(url || ''); return parsed.protocol === 'https:' ? parsed.href : undefined; }
    catch { return undefined; }
}

function artist(rec: Recommendation) {
    return Array.isArray(rec.metadata.artist) ? rec.metadata.artist.join(', ') : rec.metadata.artist;
}

function Cover({ title, image: knownImage, artistName = '', trackId = '', index = 0 }: { title: string; image?: string; artistName?: string; trackId?: string; index?: number }) {
    const image = useSongArtwork(title, artistName, trackId, knownImage);
    const [failed, setFailed] = useState(false);
    return <div className={`ft-cover ft-cover-${index % 3}`} aria-hidden="true">
        {safeLink(image) && !failed ? <img src={image} alt="" onError={() => setFailed(true)} /> : <>
            <span className="ft-cover-label">FINDTUNES / DISCOVERY</span>
            <span className="ft-vinyl"><span /></span>
            <span className="ft-cover-title">{title}</span>
        </>}
    </div>;
}

function Details({ rec, index, image, seed, onClose }: { rec: Recommendation; index: number; image?: string; seed?: ResearchProfile | null; onClose: () => void }) {
    const dialog = useRef<HTMLDialogElement>(null);
    const titleId = useId();
    useEffect(() => {
        const element = dialog.current;
        const oldOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        element?.showModal();
        return () => { element?.close(); document.body.style.overflow = oldOverflow; };
    }, []);
    const spotify = safeLink(rec.metadata.spotify_track_url);
    return <dialog ref={dialog} className="ft-dialog" aria-labelledby={titleId} onCancel={onClose}
        onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
        <div className="ft-detail-panel">
            <button className="ft-close" onClick={onClose} aria-label="Close song details" autoFocus>×</button>
            <div className="ft-detail-heading">
                <Cover title={rec.metadata.title} artistName={artist(rec)} trackId={rec.metadata.spotify_track_id} image={image} index={index} />
                <div><p className="ft-eyebrow">YOUR DISCOVERY</p><h2 id={titleId}>{rec.metadata.title}</h2><p className="ft-muted">{artist(rec)}</p></div>
            </div>
            <div className="ft-detail-body">
                <h3>{rec.research?.profile?.mode === 'quick' ? 'Lyrical match' : 'Why this song?'}</h3>
                <p>{rec.explanation?.summary || (rec.research?.profile?.mode === 'quick' ? 'Retrieved through lyrical similarity. See the source excerpts and full-song wording comparison below.' : 'We found this song through lyrical similarity. An explanation isn’t available right now.')}</p>
                {!!rec.explanation?.shared_themes.length && <div className="ft-tags">{rec.explanation.shared_themes.map((theme, i) => <span key={i}>{theme}</span>)}</div>}
                {rec.explanation?.difference && <div className="ft-difference"><h4>A different perspective</h4><p>{rec.explanation.difference}</p></div>}
                <p className="ft-score">Lyrical retrieval score <strong>{rec.score.toFixed(3)}</strong></p>
                {rec.sources && <div className="ft-source-links">
                    {safeLink(rec.sources.seed) && <a href={safeLink(rec.sources.seed)} target="_blank" rel="noopener noreferrer">Original lyrics on Genius ↗</a>}
                    {safeLink(rec.sources.candidate) && <a href={safeLink(rec.sources.candidate)} target="_blank" rel="noopener noreferrer">Suggested lyrics on Genius ↗</a>}
                </div>}
                {spotify && <a className="ft-primary ft-spotify-link" href={spotify} target="_blank" rel="noopener noreferrer">Open in Spotify ↗</a>}
                <ResearchDetails result={rec.research} seed={seed}/>
            </div>
        </div>
    </dialog>;
}

export default function Recommend({ selectedTrack, artworkById = {}, initialRecommendations = [], initialResearchJobId = null, onSongChange }: {
    selectedTrack?: { id: string; name: string; artist: string };
    artworkById?: Record<string, string>;
    initialRecommendations?: Recommendation[];
    initialResearchJobId?: string | null;
    onSongChange?: (song: {name: string; artist: string}) => void;
}) {
    const [songName, setSongName] = useState('Bad Habit');
    const [artistName, setArtistName] = useState('Steve Lacy');
    const [loading, setLoading] = useState(false);
    const [deepResearch, setDeepResearch] = useState(false);
    const [recommendations, setRecommendations] = useState<Recommendation[]>(initialRecommendations);
    const [error, setError] = useState<string | null>(null);
    const [hasSearched, setHasSearched] = useState(initialRecommendations.length > 0);
    const [selected, setSelected] = useState<number | null>(null);
    const [jobId, setJobId] = useState<string | null>(initialResearchJobId);
    const [researchJob, setResearchJob] = useState<ResearchJob | null>(null);
    const [researchProgress, setResearchProgress] = useState('');
    const results = useRef<HTMLDivElement>(null);
    const songInput = useRef<HTMLInputElement>(null);
    useEffect(() => { onSongChange?.({name: songName, artist: artistName}); }, [songName, artistName, onSongChange]);
    const canRecommend = !!songName.trim() && !loading;
    useEffect(() => {
        if (selectedTrack) { setSongName(selectedTrack.name); setArtistName(selectedTrack.artist); songInput.current?.focus(); }
    }, [selectedTrack]);
    useEffect(() => { if (hasSearched) results.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' }); }, [hasSearched]);
    useEffect(() => {
        if (!jobId) return;
        let disposed = false;
        let failures = 0;
        let timer: ReturnType<typeof setTimeout>;
        const controller = new AbortController();
        const started = Date.now();
        const poll = async () => {
            try {
                const {data} = await axios.get<ResearchJob>(`${DOMAIN}/research/jobs/${jobId}`, {signal: controller.signal, timeout: 15000});
                if (disposed) return;
                failures = 0;
                setResearchJob(data); setResearchProgress(data.progress);
                setRecommendations(previous => previous.map(rec => {
                    const result = data.results[rec.id];
                    return result ? {...rec, research: result, explanation: result.explanation || rec.explanation,
                        sources: result.sources || rec.sources, explanation_status: result.explanation ? 'complete' : ['complete', 'unavailable', 'evidence_only'].includes(result.status) ? 'unavailable' : rec.explanation_status} : rec;
                }));
                if (!['queued', 'running'].includes(data.status)) return;
            } catch {
                if (disposed) return;
                if (++failures >= 3) { setResearchProgress('Research connection unavailable; your songs remain available.'); return; }
            }
            if (Date.now() - started > 1800000) { setResearchProgress('Research polling ended; your songs remain available.'); return; }
            timer = setTimeout(poll, 2000);
        };
        void poll();
        return () => { disposed = true; clearTimeout(timer); controller.abort(); };
    }, [jobId]);

    const handleRecommend = async () => {
        if (!canRecommend) return;
        setLoading(true); setError(null); setRecommendations([]); setHasSearched(false); setSelected(null);
        setJobId(null); setResearchJob(null); setResearchProgress('');
        try {
            const response = await axios.get<{recommendations: Recommendation[]; research_job_id: string | null}>(`${DOMAIN}/recommend/stream`, {
                params: { song_name: songName.trim(), artist_name: artistName.trim(), research_mode: deepResearch ? 'deep' : 'quick' },
            });
            setRecommendations(response.data.recommendations || []); setHasSearched(true);
            setJobId(response.data.research_job_id);
            setResearchProgress(response.data.research_job_id ? deepResearch ? 'Songs found. Generating AI explanations and profiles…' : 'Songs found. Gathering source excerpts and lyric overlap…' : 'Research unavailable; your songs remain available.');
        } catch (err: unknown) {
            const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
            setError(typeof detail === 'string' ? detail : 'Could not load recommendations. Please try again.');
        } finally { setLoading(false); }
    };
    const imageFor = (rec: Recommendation) => rec.metadata.image_url || artworkById[rec.metadata.spotify_track_id || ''];
    return <section className="ft-discovery" id="discover" aria-label="Discover similar songs">
        <form className="ft-search-panel" onSubmit={event => { event.preventDefault(); void handleRecommend(); }}>
            <div className="ft-section-heading"><h2>Start with a song</h2><span className="ft-pill">LYRICS → DISCOVERY</span></div>
            <div className="ft-search-fields">
                <div><label htmlFor="recommend-song">Song title <span>Required</span></label><input ref={songInput} id="recommend-song" placeholder="What’s on repeat?" required maxLength={200} value={songName} onChange={e => setSongName(e.target.value)} aria-describedby="recommend-help" disabled={loading} /></div>
                <div><label htmlFor="recommend-artist">Artist <span>Optional</span></label><input id="recommend-artist" placeholder="e.g. Steve Lacy" maxLength={200} value={artistName} onChange={e => setArtistName(e.target.value)} aria-describedby="recommend-help" disabled={loading} /></div>
                <button type="submit" className="ft-primary" disabled={!canRecommend}>{loading ? <><span className="ft-spinner" /> Finding songs</> : <>Recommend some new songs <span>↗</span></>}</button>
            </div>
            <p id="recommend-help" className="ft-input-help">An artist helps with shared song titles. For collaborations, the main artist is enough. Title-only searches use the first match.</p>
            <label className="ft-research-option"><input type="checkbox" checked={deepResearch} onChange={event => setDeepResearch(event.target.checked)} disabled={loading}/>Generate AI explanations and vibe profiles (slower)</label>
            <p className="ft-input-help">By default, show source excerpts and lyric overlap without waiting for local AI inference.</p>
        </form>
        {error && <div className="ft-error" role="alert">{error}</div>}
        <div ref={results} className="ft-results" aria-live="polite" aria-busy={loading}>
            {loading ? <>
                <div className="ft-section-heading"><div><h2>Finding your next favorites</h2><p className="ft-muted">Searching for lyrical connections.</p></div></div>
                <div className="ft-card-grid">{[0, 1, 2].map(i => <div className="ft-skeleton-card" key={i}><div /><span /><span /></div>)}</div>
            </> : recommendations.length ? <>
                <div className="ft-section-heading"><div><p className="ft-eyebrow">LYRICAL CONNECTIONS</p><h2>Your next discoveries</h2></div><span className="ft-muted">{recommendations.length} tracks · Click to explore</span></div>
                {recommendations[0].seed_song && <p className="ft-match-note">Inspired by <strong>{recommendations[0].seed_song.title}</strong> · {recommendations[0].seed_song.artist}. Wrong song? Refine the artist above.</p>}
                {researchProgress && <p className="ft-muted" role="status">{researchProgress}</p>}
                <div className="ft-card-grid">{recommendations.map((rec, index) => <button key={rec.id} className="ft-song-card" onClick={() => setSelected(index)} aria-label={`Explore ${rec.metadata.title} by ${artist(rec)}`}>
                    <div className="ft-card-art"><Cover title={rec.metadata.title} artistName={artist(rec)} trackId={rec.metadata.spotify_track_id} image={imageFor(rec)} index={index} /><span className="ft-card-arrow">↗</span></div>
                    <p className="ft-card-kicker">DISCOVERY {String(index + 1).padStart(2, '0')}</p>
                    <h3>{rec.metadata.title}</h3><p className="ft-card-artist">{artist(rec)}</p>
                    <p className="ft-card-summary">{rec.explanation?.summary || 'A new connection through the lyrics. Tap to explore this track.'}</p>
                    <div className="ft-card-bottom"><span>{rec.explanation?.shared_themes[0] || 'Lyrical connection'}</span><span>Explore →</span></div>
                </button>)}</div>
                {!!researchJob?.trace.length && <details className="ft-research-trace"><summary>Research activity</summary>{researchJob.trace.map((event, i) => <p key={i}>{event.agent} · {event.action} · {event.status}{event.duration_ms !== undefined && ` · ${(event.duration_ms / 1000).toFixed(1)}s`}{event.decision && ` · ${event.decision.action}: ${event.decision.reason}`}</p>)}</details>}
            </> : <div className="ft-empty-state"><span className="ft-empty-record" aria-hidden="true">♪</span><h3>{hasSearched ? 'No discoveries just yet' : 'A song you love. A song you haven’t met.'}</h3><p>{hasSearched ? 'Try another song to find a new connection.' : 'Enter a title above, or pick a track from your rotation below.'}</p></div>}
        </div>
        {selected !== null && recommendations[selected] && <Details rec={recommendations[selected]} index={selected} image={imageFor(recommendations[selected])} seed={researchJob?.seed} onClose={() => setSelected(null)} />}
    </section>;
}
