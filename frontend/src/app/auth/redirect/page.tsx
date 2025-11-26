'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';

const AuthRedirectPage = () => {
    const router = useRouter();
    const searchParams = useSearchParams();

    useEffect(() => {
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (!code || !state) {
            router.push('/auth/error?error=missing_params');
            return;
        }

        const fetchToken = async () => {
            try {
                const res = await fetch(`${DOMAIN}/token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code }),
                    credentials: 'include',
                });

                if (!res.ok) {
                    throw new Error("Failed to get token");
                }

                const data = await res.json();
                localStorage.setItem('spotify_id', data.spotify_id);
                console.log("Spotify ID stored in localStorage:", localStorage.getItem('spotify_id'));

                router.push('/dashboard');
            } catch (err) {
                console.error(err);
                router.push('/auth/error?error=backend_error');
            }
        };

        fetchToken();
    }, [searchParams, router]);

    return <p>Signing you in...</p>;
};

export default AuthRedirectPage;
