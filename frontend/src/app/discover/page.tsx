import Link from 'next/link';
import Recommend from '../dashboard/components/Recommend';

export default function DiscoverPage() {
    return <main className="ft-main mx-auto my-4 min-h-[calc(100vh-2rem)] w-[calc(100%-2rem)] max-w-6xl">
        <nav className="flex flex-wrap items-center justify-between gap-4 py-6" aria-label="Main navigation">
            <Link href="/" className="ft-landing-brand">FindTunes<b>.</b></Link>
            <a href="/api/auth" className="ft-landing-login">Connect Spotify <span>↗</span></a>
        </nav>
        <header className="mb-8">
            <h1 className="mb-2 text-3xl font-bold">Find songs by lyrical similarity</h1>
            <p className="ft-muted">Search the FindTunes catalog without signing in.</p>
        </header>
        <Recommend />
    </main>;
}
