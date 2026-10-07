import { useState } from 'react';
import type { Track } from '../Dashboard';

export default function TopTracks({ top_tracks, onSelect }: { top_tracks: Track[]; onSelect?: (track: Track) => void }) {
    const [expanded, setExpanded] = useState(false);
    const tracks = expanded ? top_tracks : top_tracks.slice(0, 6);
    return <section>
        <div className="ft-section-heading"><div><p className="ft-eyebrow">YOUR LISTENING DNA</p><h2>In your rotation</h2><p className="ft-muted">Pick a favorite as the starting point for something new.</p></div>{top_tracks.length > 6 && <button className="ft-text-button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : 'See all'}</button>}</div>
        <div className="ft-track-grid">{tracks.map((track, i) => <button className="ft-track-row" key={`${track.track_id}-${i}`} onClick={() => onSelect?.(track)} aria-label={`Find songs like ${track.track_name}`}>
            <span className="ft-track-number">{String(i + 1).padStart(2, '0')}</span><img src={track.images?.[0] || '/no-picture.png'} alt="" loading="lazy" /><span className="ft-track-copy"><strong>{track.track_name}</strong><span>{track.artist_names.join(', ')}</span></span><span className="ft-track-action" aria-hidden="true">↗</span>
        </button>)}</div>
        {!top_tracks.length && <p className="ft-muted">Your top tracks will appear here once Spotify has listening data.</p>}
    </section>;
}
