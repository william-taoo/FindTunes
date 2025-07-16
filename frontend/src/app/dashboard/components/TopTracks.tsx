import { Track } from '../Dashboard';

interface TopTracksProps {
    top_tracks: Track[];
}

const TopTracks = ({ top_tracks }: TopTracksProps) => {
    return (
        <div className="bg-spotify-black p-6 rounded-lg">
            <h2 className="text-xl font-bold mb-4">Top Tracks</h2>
            <div className="space-y-3">
                {top_tracks?.map(track => (
                <div key={track.track_id} className="flex items-center gap-4 hover:bg-spotify-dark rounded p-2 transition">
                    <img 
                        src={track.images?.[2]} 
                        alt={track.track_name}
                        className="w-12 h-12 rounded"
                    />
                    <div className="flex-1 min-w-0">
                        <a 
                            href={track.track_url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium truncate text-green-400 hover:underline"
                        >
                            {track.track_name}
                        </a>
                        <p className="text-sm text-spotify-light truncate">
                            {track.artist_names?.map((name, i) => (
                                <span key={i}>
                                    <a
                                        href={track.artist_urls?.[name] || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:underline text-spotify-light"
                                    >
                                        {name}
                                    </a>
                                    {i < track.artist_names.length - 1 && ', '}
                                </span>
                            ))}
                        </p>
                    </div>
                </div>
                ))}
            </div>
        </div>
    );
};

export default TopTracks;
