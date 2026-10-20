import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
    // Next's development server can normalize the request URL to localhost.
    // Keep the browser on the host that owns the OAuth state cookie.
    const origin = new URL(process.env.NEXT_SPOTIFY_REDIRECT_URI!).origin;
    // Extract query parameters
    const { searchParams } = new URL(req.url);
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    // console.log(code)
    // console.log(state)
    // console.log(error)

    if (error || !code || !state || state !== req.cookies.get('spotify_auth_state')?.value) {
        const errorType = error || 'invalid_state';
        return NextResponse.redirect(new URL(`/auth/error?${new URLSearchParams({error: errorType})}`, origin));
    }

    // Preserve the state cookie for the backend's token-exchange check.
    const response = NextResponse.redirect(new URL(`/auth/redirect?${new URLSearchParams({code, state})}`, origin));
    response.headers.set('Cache-Control', 'no-store');
    return response;
};
