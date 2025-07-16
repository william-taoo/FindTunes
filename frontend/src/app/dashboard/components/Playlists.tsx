import { Playlist } from '../Dashboard';

interface PlaylistsProps {
    playlists: Playlist[];
}

const Playlists = ({ playlists }: PlaylistsProps) => {
    return (
        <div className="bg-spotify-black p-6 rounded-lg">
            <h2 className="text-xl font-bold mb-4">Playlists</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {playlists?.map(playlist => (
                <div key={playlist.playlist_id} className="bg-spotify-dark rounded overflow-hidden">
                    <img 
                        src={playlist.playlist_image?.[0] ?? 'no-picture.png'} 
                        alt={playlist.playlist_name}
                        className="w-full aspect-square object-cover"
                    />
                    <div className="p-3">
                        <a 
                            href={playlist.playlist_url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium truncate text-green-400 hover:underline"
                        >
                            {playlist.playlist_name}
                        </a>
                    </div>
                </div>
                ))}
            </div>
        </div>
    );
};

export default Playlists;
