import { useState, useEffect, useRef, useId } from 'react';
import axios from 'axios';
import useSongArtwork from './useSongArtwork';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';

export interface Recommendation {
    id: string;
    score: number;
    seed_song?: { id: string; title: string; artist: string };
    metadata: { title: string; artist: string | string[]; spotify_track_url?: string; image_url?: string; spotify_track_id?: string };
    explanation_status: 'complete' | 'unavailable' | 'disabled';
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

function Details({ rec, index, image, onClose }: { rec: Recommendation; index: number; image?: string; onClose: () => void }) {
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
                <h3>Why this song?</h3>
                <p>{rec.explanation?.summary || 'We found this song through lyrical similarity. An explanation isn’t available right now.'}</p>
                {!!rec.explanation?.shared_themes.length && <div className="ft-tags">{rec.explanation.shared_themes.map((theme, i) => <span key={i}>{theme}</span>)}</div>}
                {rec.explanation?.difference && <div className="ft-difference"><h4>A different perspective</h4><p>{rec.explanation.difference}</p></div>}
                <p className="ft-score">Lyrical retrieval score <strong>{rec.score.toFixed(3)}</strong></p>
                {rec.sources && <div className="ft-source-links">
                    {safeLink(rec.sources.seed) && <a href={safeLink(rec.sources.seed)} target="_blank" rel="noopener noreferrer">Original lyrics on Genius ↗</a>}
                    {safeLink(rec.sources.candidate) && <a href={safeLink(rec.sources.candidate)} target="_blank" rel="noopener noreferrer">Suggested lyrics on Genius ↗</a>}
                </div>}
                {spotify && <a className="ft-primary ft-spotify-link" href={spotify} target="_blank" rel="noopener noreferrer">Open in Spotify ↗</a>}
            </div>
        </div>
    </dialog>;
}

export default function Recommend({ selectedTrack, artworkById = {}, initialRecommendations = [], onSongChange }: {
    selectedTrack?: { id: string; name: string; artist: string };
    artworkById?: Record<string, string>;
    initialRecommendations?: Recommendation[];
    onSongChange?: (song: {name: string; artist: string}) => void;
}) {
    const [songName, setSongName] = useState('Bad Habit');
    const [artistName, setArtistName] = useState('Steve Lacy');
    const [loading, setLoading] = useState(false);
    const [recommendations, setRecommendations] = useState<Recommendation[]>(initialRecommendations);
    const [error, setError] = useState<string | null>(null);
    const [hasSearched, setHasSearched] = useState(initialRecommendations.length > 0);
    const [selected, setSelected] = useState<number | null>(null);
    const results = useRef<HTMLDivElement>(null);
    const songInput = useRef<HTMLInputElement>(null);
    useEffect(() => { onSongChange?.({name: songName, artist: artistName}); }, [songName, artistName, onSongChange]);
    const canRecommend = !!songName.trim() && !loading;
    useEffect(() => {
        if (selectedTrack) { setSongName(selectedTrack.name); setArtistName(selectedTrack.artist); songInput.current?.focus(); }
    }, [selectedTrack]);
    useEffect(() => { if (hasSearched) results.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' }); }, [hasSearched]);

    const handleRecommend = async () => {
        if (!canRecommend) return;
        setLoading(true); setError(null); setRecommendations([]); setHasSearched(false); setSelected(null);
        try {
            const response = await axios.get<Recommendation[]>(`${DOMAIN}/recommend`, {
                params: { song_name: songName.trim(), artist_name: artistName.trim() },
            });
            setRecommendations(response.data || []); setHasSearched(true);
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
        </form>
        {error && <div className="ft-error" role="alert">{error}</div>}
        <div ref={results} className="ft-results" aria-live="polite" aria-busy={loading}>
            {loading ? <>
                <div className="ft-section-heading"><div><h2>Finding your next favorites</h2><p className="ft-muted">Comparing lyrics and putting the connections into words. This can take a moment.</p></div></div>
                <div className="ft-card-grid">{[0, 1, 2].map(i => <div className="ft-skeleton-card" key={i}><div /><span /><span /></div>)}</div>
            </> : recommendations.length ? <>
                <div className="ft-section-heading"><div><p className="ft-eyebrow">LYRICAL CONNECTIONS</p><h2>Your next discoveries</h2></div><span className="ft-muted">{recommendations.length} tracks · Click to explore</span></div>
                {recommendations[0].seed_song && <p className="ft-match-note">Inspired by <strong>{recommendations[0].seed_song.title}</strong> · {recommendations[0].seed_song.artist}. Wrong song? Refine the artist above.</p>}
                <div className="ft-card-grid">{recommendations.map((rec, index) => <button key={rec.id} className="ft-song-card" onClick={() => setSelected(index)} aria-label={`Explore ${rec.metadata.title} by ${artist(rec)}`}>
                    <div className="ft-card-art"><Cover title={rec.metadata.title} artistName={artist(rec)} trackId={rec.metadata.spotify_track_id} image={imageFor(rec)} index={index} /><span className="ft-card-arrow">↗</span></div>
                    <p className="ft-card-kicker">DISCOVERY {String(index + 1).padStart(2, '0')}</p>
                    <h3>{rec.metadata.title}</h3><p className="ft-card-artist">{artist(rec)}</p>
                    <p className="ft-card-summary">{rec.explanation?.summary || 'A new connection through the lyrics. Tap to explore this track.'}</p>
                    <div className="ft-card-bottom"><span>{rec.explanation?.shared_themes[0] || 'Lyrical connection'}</span><span>Explore →</span></div>
                </button>)}</div>
            </> : <div className="ft-empty-state"><span className="ft-empty-record" aria-hidden="true">♪</span><h3>{hasSearched ? 'No discoveries just yet' : 'A song you love. A song you haven’t met.'}</h3><p>{hasSearched ? 'Try another song to find a new connection.' : 'Enter a title above, or pick a track from your rotation below.'}</p></div>}
        </div>
        {selected !== null && recommendations[selected] && <Details rec={recommendations[selected]} index={selected} image={imageFor(recommendations[selected])} onClose={() => setSelected(null)} />}
    </section>;
}
