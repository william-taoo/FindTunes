'use client';
import { useState, useEffect } from 'react';

export interface Track {
  track_id: string;
  track_name: string;
  track_url?: string;
  artist_names: string[];
  artist_urls?: Record<string, string>;
  album_name: string;
  images?: string; 
}

export interface TopArtist {
  artist_id: string;
  artist_name: string;
  genres?: string[];
  popularity: number;
  images?: string; 
  artist_url?: string;
}

export interface Playlist {
  playlist_id: string;
  playlist_name: string;
  playlist_image?: string;
  playlist_url?: string;
}

export interface User {
  spotify_id: string;
  display_name: string;
  email: string;
  country: string;
  profile_image_url?: string;
  followers_count: number;
  product: string;
  spotify_profile_url?: string;
}

export interface SpotifyUser {
  user: User;
  top_tracks: Track[];
  top_artists: TopArtist[];
  playlists: Playlist[];
}

export default function Profile() {
    const [data, setData] = useState<SpotifyUser | null>(null);
    const [loading, setLoading] = useState(true); // Initialize as loading

    useEffect(() => {
        const fetchData = async () => {
            try {
                const spotify_id = localStorage.getItem('spotify_id');
                console.log("Fetching profile for Spotify ID:", spotify_id);
                if (!spotify_id) {
                    throw new Error('Spotify ID not found in localStorage');
                }

                const res = await fetch(`http://localhost:8000/profile?spotify_id=${ spotify_id }`, { credentials: 'include' });
                setData(await res.json() as SpotifyUser);
            } catch (error) {
                console.error('Fetch error:', error);
            } finally {
                setLoading(false); // Set loading to false after data is fetched
            }
        };

        fetchData();
    }, []);

    if (loading) return <div className="p-8">Loading profile...</div>;
    if (!data || !data.user) return <div className="p-8">Failed to load profile</div>;

    return (
        <div className="flex flex-col md:flex-row gap-8 p-6">
            {/* Profile Card */}
            <div className="bg-gradient-to-br from-spotify-dark to-spotify-darker p-6 rounded-lg shadow-lg w-full md:w-1/3">
                <div className="flex flex-col items-center">
                    <img 
                        src={data.user.profile_image_url || ''} 
                        alt={data.user.display_name}
                        className="w-32 h-32 rounded-full object-cover mb-4 border-4 border-white"
                    />
                    <h1 className="text-2xl font-bold text-white">{data.user.display_name}</h1>
                    <p className="text-spotify-light">{data.user.email}</p>
                    
                    <div className="mt-4 grid grid-cols-2 gap-4 w-full">
                        <div className="bg-spotify-black p-3 rounded-lg text-center">
                            <p className="text-sm text-spotify-light">Followers</p>
                            <p className="font-bold">{data.user.followers_count}</p>
                        </div>
                        <div className="bg-spotify-black p-3 rounded-lg text-center">
                            <p className="text-sm text-spotify-light">Subscription</p>
                            <p className="font-bold capitalize">{data.user.product}</p>
                        </div>
                    </div>

                    <a 
                        href={data.user.spotify_profile_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-6 px-4 py-2 bg-green-500 text-black rounded-full font-medium hover:bg-green-400 transition"
                    >
                        View on Spotify
                    </a>
                </div>
            </div>

            {/* Content Panel */}
            <div className="flex-1 space-y-6">
                {/* Top Artists */}
                <div className="bg-spotify-black p-6 rounded-lg">
                    <h2 className="text-xl font-bold mb-4">Top Artists</h2>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        {data.top_artists?.map(artist => (
                        <div key={artist.artist_id} className="text-center">
                            <img 
                                src={artist.images?.[1]} 
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

                {/* Top Tracks */}
                <div className="bg-spotify-black p-6 rounded-lg">
                    <h2 className="text-xl font-bold mb-4">Top Tracks</h2>
                    <div className="space-y-3">
                        {data.top_tracks?.map(track => (
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

                {/* Playlists */}
                <div className="bg-spotify-black p-6 rounded-lg">
                    <h2 className="text-xl font-bold mb-4">Your Playlists</h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {data.playlists?.map(playlist => (
                        <div key={playlist.playlist_id} className="bg-spotify-dark rounded overflow-hidden">
                            <img 
                                src={playlist.playlist_image?.[0]} 
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
            </div>
        </div>
    );
}