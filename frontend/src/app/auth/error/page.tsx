export default function AuthError() {
    return <main className="ft-loading-screen"><h1>Spotify sign-in wasn’t completed.</h1>
        <p>Please try again. If Spotify denies access, check that your account is allowed to use this app.</p>
        <a className="ft-primary" href="/api/auth">Try signing in again</a><a href="/">Back to home</a></main>;
}
