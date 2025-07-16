import { Artist } from '../Dashboard';

interface TopArtistsProps {
    top_artists: Artist[];
}

const TopArtists = ({ top_artists }: TopArtistsProps) => {
    return (
        <div className="bg-spotify-black p-6 rounded-lg">
            <h2 className="text-xl font-bold mb-4">Top Artists</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {top_artists?.map(artist => (
                <div key={artist.artist_id} className="text-center">
                    <img 
                        src={artist.images?.[0]} 
                        alt={artist.artist_name}
                        className="w-full aspect-square rounded-full object-cover mb-2 mx-auto"
                    />
                    <a 
                        href={artist.artist_url || '#'} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="font-medium truncate text-green-400 hover:underline"
                    >
                        {artist.artist_name}
                    </a>
                </div>
                ))}
            </div>
        </div>
    );
};

export default TopArtists;
