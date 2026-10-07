import { useEffect, useState } from 'react';
import axios from 'axios';
const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';
export default function useSongArtwork(title: string, artist: string, trackId = '', knownImage?: string) {
    const [image, setImage] = useState<string>();
    useEffect(() => {
        setImage(knownImage);
        if (knownImage || !title.trim() || (!artist.trim() && !trackId)) return;
        const controller = new AbortController();
        const timer = setTimeout(() => {
            axios.get<{image_url: string | null}>(`${DOMAIN}/artwork`, {
                params: {song_name: title, artist_name: artist, spotify_track_id: trackId}, signal: controller.signal,
            }).then(response => setImage(response.data.image_url || undefined)).catch(() => {});
        }, 500);
        return () => { clearTimeout(timer); controller.abort(); };
    }, [title, artist, trackId, knownImage]);
    return image;
}
