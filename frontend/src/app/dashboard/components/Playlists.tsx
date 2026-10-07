import { useState } from 'react';
import type { Playlist } from '../Dashboard';

export default function Playlists({ playlists }: { playlists: Playlist[] }) {
    const [expanded, setExpanded] = useState(false);
    return <section>
        <div className="ft-section-heading"><div><h2>Your playlists</h2></div>{playlists.length > 4 && <button className="ft-text-button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : 'See all'}</button>}</div>
        <div className="ft-playlist-grid">{(expanded ? playlists : playlists.slice(0, 4)).map((playlist, i) => <a key={`${playlist.playlist_id}-${i}`} className="ft-playlist-card" href={playlist.playlist_url} target="_blank" rel="noopener noreferrer"><img src={playlist.playlist_image?.[0] || '/no-picture.png'} alt="" loading="lazy" /><div><strong>{playlist.playlist_name}</strong><span>Open playlist ↗</span></div></a>)}</div>
        {!playlists.length && <p className="ft-muted">Your Spotify playlists will appear here.</p>}
    </section>;
}
