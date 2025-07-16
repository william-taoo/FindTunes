import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

export async function GET(req: NextRequest) {
    const state = crypto.randomBytes(60).toString('hex').slice(0, 16);
    const scope = 'user-read-private user-read-email user-read-recently-played user-top-read playlist-read-private user-library-read';

    const params = new URLSearchParams({
        response_type: 'code',
        client_id: process.env.NEXT_SPOTIFY_CLIENT_ID!,
        scope: scope,
        redirect_uri: process.env.NEXT_SPOTIFY_REDIRECT_URI!,
        state: state,
    });

    const auth_url = `https://accounts.spotify.com/authorize?${params.toString()}`;

    const response = NextResponse.redirect(auth_url);
    response.cookies.set('spotify_auth_state', state, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 300,
        path: '/',
        sameSite: 'lax'
    });

    return response;
}