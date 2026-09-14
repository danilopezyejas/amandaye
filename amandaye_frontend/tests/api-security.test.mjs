import assert from 'node:assert/strict';
import test from 'node:test';
import axios, { AxiosError } from 'axios';
import { createApiClients } from '../src/api/client.ts';

function setup(authenticated = true) {
    let redirects = 0;
    const auth = {
        accessToken: authenticated ? 'old-access' : null,
        refreshToken: authenticated ? 'old-refresh' : null,
        setTokens(access, refresh) { this.accessToken = access; this.refreshToken = refresh; },
        clearAuth() { this.accessToken = null; this.refreshToken = null; },
    };
    return {
        auth,
        get redirects() { return redirects; },
        ...createApiClients({
            getAuth: () => auth,
            getOrigin: () => 'https://club.example',
            redirectToLogin: () => { redirects += 1; },
        }),
    };
}

function response(config, data, status = 200) {
    return { data, status, statusText: String(status), headers: {}, config };
}

function unauthorized(config) {
    return new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, {}, response(config, {}, 401));
}

test('rejects external destinations and paths outside /api before sending credentials', async () => {
    const { api, publicApi } = setup();
    let sent = 0;
    for (const client of [api, publicApi]) {
        client.defaults.adapter = async (config) => { sent += 1; return response(config, {}); };
        await assert.rejects(client.get('https://attacker.example/api/'), /mismo origen/);
        await assert.rejects(client.get('//attacker.example/api/'), /mismo origen/);
        await assert.rejects(client.get('https://club.example/login/'), /mismo origen/);
        await assert.rejects(client.get('../admin/'), /mismo origen/);
    }
    assert.equal(sent, 0);
});

test('registration uses the page origin and sends no saved bearer token', async () => {
    const { publicApi } = setup();
    publicApi.defaults.adapter = async (config) => {
        assert.equal(axios.getUri(config), '/api/socios/solicitudes/');
        assert.equal(config.headers.Authorization, undefined);
        return response(config, { detail: 'Recibida' }, 201);
    };
    assert.equal((await publicApi.post('socios/solicitudes/', {})).status, 201);
});

test('concurrent 401 responses share one refresh and retry with the rotated token', async () => {
    const state = setup();
    let refreshes = 0;
    let release;
    const refreshed = new Promise((resolve) => { release = resolve; });
    state.publicApi.defaults.adapter = async (config) => {
        refreshes += 1;
        assert.equal(axios.getUri(config), '/api/token/refresh/');
        assert.equal(config.headers.Authorization, undefined);
        await refreshed;
        return response(config, { access: 'new-access', refresh: 'new-refresh' });
    };
    state.api.defaults.adapter = async (config) => {
        if (config.headers.Authorization === 'Bearer old-access') throw unauthorized(config);
        assert.equal(config.headers.Authorization, 'Bearer new-access');
        return response(config, { ok: true });
    };
    const first = state.api.get('socios/');
    const second = state.api.get('cobranzas/cuentas/');
    await new Promise((resolve) => setImmediate(resolve));
    release();
    await Promise.all([first, second]);
    assert.equal(refreshes, 1);
    assert.equal(state.auth.refreshToken, 'new-refresh');
    assert.equal(state.redirects, 0);
});

test('a failed refresh clears tokens and redirects only once', async () => {
    const state = setup();
    state.api.defaults.adapter = async (config) => { throw unauthorized(config); };
    state.publicApi.defaults.adapter = async (config) => { throw unauthorized(config); };
    await assert.rejects(state.api.get('socios/'));
    assert.equal(state.auth.accessToken, null);
    assert.equal(state.auth.refreshToken, null);
    assert.equal(state.redirects, 1);
});

test('a refresh response cannot restore a logged-out session', async () => {
    const state = setup();
    state.api.defaults.adapter = async (config) => { throw unauthorized(config); };
    state.publicApi.defaults.adapter = async (config) => {
        state.auth.clearAuth();
        return response(config, { access: 'new-access', refresh: 'new-refresh' });
    };
    await assert.rejects(state.api.get('socios/'), /sesión cambió/);
    assert.equal(state.auth.accessToken, null);
    assert.equal(state.redirects, 0);
});

test('a retry cannot enter an infinite refresh loop', async () => {
    const state = setup();
    let refreshes = 0;
    state.api.defaults.adapter = async (config) => { throw unauthorized(config); };
    state.publicApi.defaults.adapter = async (config) => {
        refreshes += 1;
        return response(config, { access: 'new-access', refresh: 'new-refresh' });
    };
    await assert.rejects(state.api.get('socios/'));
    assert.equal(refreshes, 1);
});

test('unauthenticated 401 and transport errors do not trigger refresh', async () => {
    const state = setup(false);
    let refreshes = 0;
    state.publicApi.defaults.adapter = async (config) => { refreshes += 1; return response(config, {}); };
    state.api.defaults.adapter = async (config) => { throw unauthorized(config); };
    await assert.rejects(state.api.get('socios/'));
    state.api.defaults.adapter = async () => { throw new AxiosError('Network error'); };
    await assert.rejects(state.api.get('socios/'));
    assert.equal(refreshes, 0);
    assert.equal(state.redirects, 0);
});
