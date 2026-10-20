import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

export async function GET(req: NextRequest) {
    // OAuth cookies belong to a hostname: localhost and 127.0.0.1 are different.
    const callback = new URL(process.env.NEXT_SPOTIFY_REDIRECT_URI!);
    const requestHost = req.headers.get('host') || new URL(req.url).host;
    if (requestHost !== callback.host) {
        return NextResponse.redirect(new URL('/api/auth', callback.origin));
    }
    const state = crypto.randomBytes(60).toString('hex').slice(0, 16);
    const scope = 'user-read-private user-read-email user-read-recently-played user-top-read playlist-read-private user-library-read';

    const params = new URLSearchParams({
        response_type: 'code',
        client_id: process.env.NEXT_SPOTIFY_CLIENT_ID!,
        scope: scope,
        redirect_uri: process.env.NEXT_SPOTIFY_REDIRECT_URI!,
        state: state,
        show_dialog: 'true',
    });

    const auth_url = `https://accounts.spotify.com/authorize?${params.toString()}`;

    const response = NextResponse.redirect(auth_url);
    response.headers.set('Cache-Control', 'no-store');
    response.cookies.set('spotify_auth_state', state, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 300,
        path: '/',
        sameSite: 'lax'
    });

    return response;
};
