import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';

interface AuthState {
    accessToken: string | null;
    refreshToken: string | null;
    setTokens(access: string, refresh: string): void;
    clearAuth(): void;
}

interface ClientOptions {
    getAuth(): AuthState;
    getOrigin(): string;
    redirectToLogin(): void;
}

interface TokenResponse {
    access: string;
    refresh?: string;
}

export function createApiClients(options: ClientOptions) {
    const config = { baseURL: '/api/', timeout: 15000 };
    const api = axios.create(config);
    // Public requests and refresh must not enter the authenticated retry loop.
    const publicApi = axios.create(config);
    let refreshInFlight: Promise<string> | null = null;

    function enforceSameOrigin(request: InternalAxiosRequestConfig) {
        const url = new URL(axios.getUri(request), options.getOrigin());
        if (url.origin !== options.getOrigin() || !url.pathname.startsWith('/api/')) {
            throw new Error('La API solo admite solicitudes al mismo origen bajo /api/.');
        }
        return request;
    }

    publicApi.interceptors.request.use(enforceSameOrigin);
    api.interceptors.request.use((request) => {
        enforceSameOrigin(request);
        const auth = options.getAuth();
        if (auth.accessToken) {
            request.headers.Authorization = `Bearer ${auth.accessToken}`;
        }
        return request;
    });

    async function refreshAccessToken(): Promise<string> {
        const auth = options.getAuth();
        const refreshToken = auth.refreshToken;
        if (!refreshToken) throw new Error('La sesión expiró.');

        try {
            const response = await publicApi.post<TokenResponse>('token/refresh/', {
                refresh: refreshToken,
            });
            // A logout or another login must not be undone by an older response.
            if (auth.refreshToken !== refreshToken) throw new Error('La sesión cambió.');
            if (typeof response.data.access !== 'string' || !response.data.access) {
                throw new Error('Respuesta de autenticación inválida.');
            }
            auth.setTokens(response.data.access, response.data.refresh || refreshToken);
            return response.data.access;
        } catch (error) {
            if (auth.refreshToken === refreshToken) {
                auth.clearAuth();
                options.redirectToLogin();
            }
            throw error;
        }
    }

    api.interceptors.response.use((response) => response, async (error: AxiosError) => {
        const request = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
        if (error.response?.status !== 401 || !request || request._retry) {
            return Promise.reject(error);
        }
        const auth = options.getAuth();
        // A public 401 is not an authenticated session expiry.
        if (!auth.accessToken && !auth.refreshToken) return Promise.reject(error);
        if (!auth.refreshToken) {
            auth.clearAuth();
            options.redirectToLogin();
            return Promise.reject(error);
        }
        request._retry = true;

        // Another request may already have completed the token rotation.
        if (auth.accessToken && request.headers.Authorization !== `Bearer ${auth.accessToken}`) {
            request.headers.Authorization = `Bearer ${auth.accessToken}`;
            return api(request);
        }

        // Share one rotation across concurrent 401s so refresh tokens are not reused.
        if (!refreshInFlight) {
            refreshInFlight = refreshAccessToken().finally(() => { refreshInFlight = null; });
        }
        const accessToken = await refreshInFlight;
        request.headers.Authorization = `Bearer ${accessToken}`;
        return api(request);
    });

    return { api, publicApi };
}
