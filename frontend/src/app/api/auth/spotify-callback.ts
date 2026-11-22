export function spotifyCallbackUrl() {
    const productionHost = process.env.VERCEL_PROJECT_PRODUCTION_URL;
    if (process.env.VERCEL_ENV === 'production' && productionHost) {
        return new URL('/api/auth/callback', `https://${productionHost}`);
    }
    return new URL(process.env.NEXT_SPOTIFY_REDIRECT_URI!);
}
