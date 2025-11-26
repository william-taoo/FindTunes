import { useState, useEffect } from "react";
import axios from "axios";

const Recommend = ({ selectedTrack }: { selectedTrack?: { id: string, name: string, artist: string } }) => {
    const [songName, setSongName] = useState("");
    const [artistName, setArtistName] = useState("");
    const [loading, setLoading] = useState(false);
    const [recommendations, setRecommendations] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Auto populate from top track if provided
    useEffect(() => {
        if (selectedTrack) {
            setSongName(selectedTrack.name);
            setArtistName(selectedTrack.artist);
        }
    }, [selectedTrack]);

    const handleRecommend = async () => {
        if (!songName || !artistName) return;

        setLoading(true);
        setError(null);
        setRecommendations([]);

        try {
            const res = await axios.get(`http://localhost:8000/recommend`, {
                params: {
                    song_name: songName,
                    artist_name: artistName,
                },
            });
            console.log(res.data)
            setRecommendations(res.data || []);
        } catch (err: any) {
            console.error("Recommendation error:", err);
            setError(err.response.data.detail || "Something went wrong");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-4 border-2 border-[#1DB954] rounded-lg w-full max-w-2xl">
            <h2 className="text-xl font-bold mb-4">Song Recommendation</h2>

            <input
                type="text"
                className="w-full p-2 border rounded mb-2"
                placeholder="Song name"
                value={songName}
                onChange={(e) => setSongName(e.target.value)}
            />

            <input
                type="text"
                className="w-full p-2 border rounded mb-2"
                placeholder="Artist name"
                value={artistName}
                onChange={(e) => setArtistName(e.target.value)}
            />

            <button
                onClick={handleRecommend}
                disabled={loading}
                className="w-full p-2 bg-blue-600 text-white rounded disabled:opacity-50"
            >
                {loading ? "Loading..." : "Recommend"}
            </button>

            {error && <p className="text-red-500 mt-3">{error}</p>}

            {recommendations.length > 0 && (
                <div className="mt-4">
                    <h3 className="font-bold mb-2">Similar Tracks</h3>
                    <ul>
                        {recommendations.map((rec, i) => (
                            <li key={i} className="mb-2 flex justify-between items-center">
                                <div>
                                    <a
                                        href={rec.metadata.spotify_track_url || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-green-400 hover:underline"
                                    >
                                        <strong>{rec.metadata.title}</strong>
                                    </a>
                                    {" - "}
                                    {Array.isArray(rec.metadata.artist)
                                    ? rec.metadata.artist.join(", ")
                                    : rec.metadata.artist}
                                </div>

                                <div className="text-spotify-light">
                                    Lyrical Similarity: {(rec.score * 100).toFixed(2)}%
                                </div>
                            </li>
                            
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};


export default Recommend;