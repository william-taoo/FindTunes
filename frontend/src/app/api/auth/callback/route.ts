import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
    // Extract query parameters
    const { searchParams } = new URL(req.url);
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    // console.log(code)
    // console.log(state)
    // console.log(error)

    if (error || !code || !state) {
        const errorType = error || 'missing_params';
        return NextResponse.redirect(new URL(`/auth/error?error=${errorType}`, req.url));
    }

    // Redirect to middleman to handle token exchange and set localStorage
    return NextResponse.redirect(new URL(`/auth/redirect?code=${ code }&state=${ state }`, req.url));
};
