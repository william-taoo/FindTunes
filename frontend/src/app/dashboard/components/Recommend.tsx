import { useState, useEffect } from "react";
import axios from "axios";

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';

interface Evidence {
    seed_line_ids: string[];
    candidate_line_ids: string[];
    seed_sections: string[];
    candidate_sections: string[];
    reason: string;
}

interface Recommendation {
    id: string;
    score: number;
    metadata: { title: string; artist: string | string[]; spotify_track_url?: string };
    explanation_status: 'complete' | 'unavailable' | 'disabled';
    explanation: { summary: string; shared_themes: string[]; difference: string; evidence: Evidence[] } | null;
    sources: { seed: string; candidate: string } | null;
}

function safeLink(url?: string): string | undefined {
    if (!url) return undefined;
    try {
        const parsed = new URL(url);
        return parsed.protocol === 'https:' ? parsed.href : undefined;
    } catch { return undefined; }
}

const Recommend = ({ selectedTrack }: { selectedTrack?: { id: string, name: string, artist: string } }) => {
    const [songName, setSongName] = useState("");
    const [artistName, setArtistName] = useState("");
    const [loading, setLoading] = useState(false);
    const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
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
            const res = await axios.get<Recommendation[]>(`${DOMAIN}/recommend`, {
                params: {
                    song_name: songName,
                    artist_name: artistName,
                },
            });
            setRecommendations(res.data || []);
        } catch (err: unknown) {
            console.error("Recommendation error:", err);
            const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
            setError(typeof detail === 'string' ? detail : "Could not load recommendations. Please try again.");
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
                {loading ? "Finding songs and comparing lyrics..." : "Recommend"}
            </button>

            {error && <p className="text-red-500 mt-3">{error}</p>}

            {recommendations.length > 0 && (
                <div className="mt-4">
                    <h3 className="font-bold mb-2">Similar Tracks</h3>
                    <ul>
                        {recommendations.map((rec) => (
                            <li key={rec.id} className="mb-4 border-t pt-3">
                                <div>
                                    <a
                                        href={safeLink(rec.metadata.spotify_track_url)}
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
                                    Retrieval score: {rec.score.toFixed(3)}
                                </div>
                                {rec.explanation ? (
                                    <div className="mt-2 space-y-2">
                                        <p>{rec.explanation.summary}</p>
                                        {rec.explanation.shared_themes.length > 0 && (
                                            <p className="text-sm">Shared themes: {rec.explanation.shared_themes.join(', ')}</p>
                                        )}
                                        <p className="text-sm">{rec.explanation.difference}</p>
                                        <details className="text-sm">
                                            <summary className="cursor-pointer">Passages used for this explanation</summary>
                                            {rec.explanation.evidence.length === 0 && <p>No strong lyrical evidence found.</p>}
                                            {rec.explanation.evidence.map((item, index) => (
                                                <div key={index} className="mt-2">
                                                    <p>{item.reason}</p>
                                                    <p>Input: {item.seed_sections.join(', ')} ({item.seed_line_ids.join(', ')})</p>
                                                    <p>Suggestion: {item.candidate_sections.join(', ')} ({item.candidate_line_ids.join(', ')})</p>
                                                </div>
                                            ))}
                                            {rec.sources && (
                                                <div className="mt-2 flex gap-4">
                                                    <a className="text-green-400 underline" href={safeLink(rec.sources.seed)} target="_blank" rel="noopener noreferrer">Input lyrics on Genius</a>
                                                    <a className="text-green-400 underline" href={safeLink(rec.sources.candidate)} target="_blank" rel="noopener noreferrer">Suggested lyrics on Genius</a>
                                                </div>
                                            )}
                                        </details>
                                    </div>
                                ) : (
                                    <p className="mt-2 text-sm text-gray-400">
                                        {rec.explanation_status === 'disabled' ? 'Lyric explanations are not enabled yet.' : 'Lyric explanation unavailable for this song.'}
                                    </p>
                                )}
                            </li>
                            
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};


export default Recommend;
