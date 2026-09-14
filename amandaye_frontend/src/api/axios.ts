import { createApiClients } from './client';
import { useAuthStore } from '../stores/auth';

// API, registration and token refresh inherit HTTPS from the page origin.
export const { api, publicApi } = createApiClients({
    getAuth: () => useAuthStore(),
    getOrigin: () => window.location.origin,
    redirectToLogin: () => window.location.assign('/login/'),
});
