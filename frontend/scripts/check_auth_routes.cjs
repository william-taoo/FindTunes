const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const {NextRequest} = require('next/server');
function load(relative) {
    const exports = {};
    const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', relative), 'utf8'), {
        compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true},
    }).outputText;
    const requireFromRoute = name => name.startsWith('.')
        ? load(path.join(path.dirname(relative), `${name}.ts`))
        : require(name);
    vm.runInNewContext(code, {exports, require: requireFromRoute, process, URL, URLSearchParams});
    return exports;
}
(async () => {
    process.env.NEXT_SPOTIFY_CLIENT_ID = 'test-client';
    process.env.NEXT_SPOTIFY_REDIRECT_URI = 'http://localhost:3000/api/auth/callback';
    const login = await load('src/app/api/auth/route.ts').GET(new NextRequest('http://localhost:3000/api/auth'));
    const auth = new URL(login.headers.get('location'));
    assert.equal(auth.searchParams.get('show_dialog'), 'true');
    assert.ok(login.cookies.get('spotify_auth_state').value);
    const canonical = await load('src/app/api/auth/route.ts').GET(new NextRequest('http://127.0.0.1:3000/api/auth', {headers: {host: '127.0.0.1:3000'}}));
    assert.equal(canonical.headers.get('location'), 'http://localhost:3000/api/auth');
    const {GET} = load('src/app/api/auth/callback/route.ts');
    const invalid = await GET(new NextRequest('http://localhost:3000/api/auth/callback?code=test&state=wrong', {
        headers: {cookie: 'spotify_auth_state=expected'},
    }));
    assert.equal(new URL(invalid.headers.get('location')).pathname, '/auth/error');
    const valid = await GET(new NextRequest('http://localhost:3000/api/auth/callback?code=test&state=expected', {
        headers: {cookie: 'spotify_auth_state=expected'},
    }));
    assert.equal(new URL(valid.headers.get('location')).pathname, '/auth/redirect');
    // Next's development request URL can say localhost even when the browser
    // and its host-only OAuth cookie use the configured loopback IP.
    process.env.NEXT_SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:3000/api/auth/callback';
    const loopback = await GET(new NextRequest('http://localhost:3000/api/auth/callback?code=test&state=expected', {
        headers: {host: '127.0.0.1:3000', cookie: 'spotify_auth_state=expected'},
    }));
    assert.equal(new URL(loopback.headers.get('location')).origin, 'http://127.0.0.1:3000');
    process.env.VERCEL_ENV = 'production';
    process.env.VERCEL_PROJECT_PRODUCTION_URL = 'findtunes.vercel.app';
    const production = await load('src/app/api/auth/route.ts').GET(new NextRequest('https://findtunes.vercel.app/api/auth'));
    assert.equal(new URL(production.headers.get('location')).searchParams.get('redirect_uri'),
        'https://findtunes.vercel.app/api/auth/callback');
    console.log('Auth route checks passed: fresh dialog, state cookie, reject mismatch, accept matching state.');
})().catch(error => {console.error(error); process.exitCode = 1;});
