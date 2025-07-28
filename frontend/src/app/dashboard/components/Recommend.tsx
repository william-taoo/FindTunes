import { useState } from "react";
import axios from "axios";

const Recommend = ({ selectedTrack }: { selectedTrack?: { id: string, name: string, artist: string } }) => {
    const [songName, setSongName] = useState("");
    const [artistName, setArtistName] = useState("");
    const [trackId, setTrackId] = useState("");
    const [loading, setLoading] = useState(false);
    const [recommendations, setRecommendations] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Auto populate from top track if provided
    useState(() => {
        if (selectedTrack) {
            setTrackId(selectedTrack.id);
            setSongName(selectedTrack.name);
            setArtistName(selectedTrack.artist);
        }
    });

    const handleRecommend = async () => {
        if (!trackId || !songName || !artistName) return;

        setLoading(true);
        setError(null);
        setRecommendations([]);

        try {
            const res = await axios.get(`/recommend/${ trackId }`, {
                params: {
                    song_name: songName,
                    artist_name: artistName,
                },
            });
            setRecommendations(res.data || []);
        } catch (err: any) {
            console.error("Recommendation error:", err);
            setError("Something went wrong. Try again.");
        } finally {
            setLoading(false);
        }
    };

    const isValid = trackId && songName && artistName;

    return (
        <>hi</>
    );
};


export default Recommend;