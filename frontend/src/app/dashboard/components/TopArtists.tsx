import { useState } from 'react';
import type { Artist } from '../Dashboard';

export default function TopArtists({ top_artists }: { top_artists: Artist[] }) {
    const [expanded, setExpanded] = useState(false);
    return <section>
        <div className="ft-section-heading"><div><p className="ft-eyebrow">THE VOICES YOU COME BACK TO</p><h2>Your artists</h2></div>{top_artists.length > 6 && <button className="ft-text-button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : 'See all'}</button>}</div>
        <div className="ft-artist-grid">{(expanded ? top_artists : top_artists.slice(0, 6)).map((artist, i) => <a key={`${artist.artist_id}-${i}`} className="ft-artist-card" href={artist.artist_url} target="_blank" rel="noopener noreferrer"><img src={artist.images?.[0] || '/no-picture.png'} alt="" loading="lazy" /><strong>{artist.artist_name}</strong><span>Artist</span></a>)}</div>
        {!top_artists.length && <p className="ft-muted">Your favorite artists will appear here.</p>}
    </section>;
}
