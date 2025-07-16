import Image from "next/image";
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#121212]">
      <h1 className="text-3xl font-bold mb-8">Song Recommender</h1>
      <Link
        href="/api/auth"
        className="px-6 py-3 bg-green-500 text-white rounded-full hover:bg-green-600 transition"
      >
        Login with Spotify
      </Link>
    </div>
  );
}
