'use client';
import { useState, useEffect } from 'react';
import ProfileCard from './components/ProfileCard';
import TopArtists from './components/TopArtists';
import TopTracks from './components/TopTracks';
import Playlists from './components/Playlists';

export interface Track {
  track_id: string;
  track_name: string;
  track_url?: string;
  artist_names: string[];
  artist_urls?: Record<string, string>;
  album_name: string;
  images?: string; 
}

export interface Artist {
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
  top_artists: Artist[];
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
        <div className="p-6 pb-12 space-y-6 flex flex-col lg:flex-row gap-6">
            <div className="w-full lg:w-1/2 space-y-6">
                <div className="flex justify-center">
                    <ProfileCard user={data.user} />
                </div>
                
                <div>
                    {/* Recommendation component will go here */}
                </div>
            </div>

            <div className="w-full lg:w-1/2 space-y-6">
                <div className="w-full  space-y-6 h-[calc(100vh-200px)]">
                    <div className="flex flex-col h-11/20">
                        <div className="overflow-y-auto pr-2 flex-1">
                            <TopArtists top_artists={data.top_artists} />
                        </div>
                    </div>

                    <div className="flex flex-col h-1/2">
                        <div className="overflow-y-auto pr-2 flex-1">
                            <TopTracks top_tracks={data.top_tracks} />
                        </div>
                    </div>

                    <div className="flex flex-col h-1/2">
                        <div className="overflow-y-auto pr-2 flex-1">
                            <Playlists playlists={data.playlists} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
