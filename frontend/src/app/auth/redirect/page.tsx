'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';

const AuthRedirectPage = () => {
    const router = useRouter();
    const searchParams = useSearchParams();
    const started = useRef(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Development Strict Mode replays effects; authorization codes are single-use.
        if (started.current) return;
        started.current = true;
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (!code || !state) {
            setError('Missing Spotify authorization details. Please start sign-in again.');
            return;
        }

        const fetchToken = async () => {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 45000);
            try {
                const res = await fetch(`${DOMAIN}/token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code }),
                    credentials: 'include',
                    signal: controller.signal,
                });

                const data = await res.json();

                if (!res.ok) {
                    throw new Error(typeof data.detail === 'string' ? data.detail : 'Sign-in failed. Please try again.');
                }

                if (typeof data.spotify_id !== 'string' || !data.spotify_id) {
                    throw new Error('The backend did not return a Spotify user ID.');
                }
                localStorage.setItem('spotify_id', data.spotify_id);
                sessionStorage.removeItem('alreadySynced');

                router.replace('/dashboard');
            } catch (err) {
                setError(controller.signal.aborted
                    ? 'Sign-in timed out. Check that your backend and PostgreSQL are running, then try again.'
                    : err instanceof Error ? err.message : 'Could not connect to the backend.');
            } finally {
                clearTimeout(timeout);
            }
        };

        fetchToken();
    }, [searchParams, router]);

    return error ? (
        <div className="p-6 space-y-3">
            <p role="alert">{error}</p>
            <a href="/api/auth" className="underline">Try Spotify sign-in again</a>
        </div>
    ) : <p>Signing you in...</p>;
};

export default AuthRedirectPage;
