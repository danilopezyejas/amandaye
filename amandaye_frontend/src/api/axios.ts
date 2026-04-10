import axios, { type AxiosInstance, type InternalAxiosRequestConfig, AxiosError } from 'axios';
import { useAuthStore } from '../stores/auth';
import router from '../router';

// Configuración base de la instancia
export const api: AxiosInstance = axios.create({
    baseURL: 'http://localhost:8000/api/', // Cambiar según ambiente de producción
    headers: {
        'Content-Type': 'application/json'
    }
});

// Interceptor de Request: inyecta el token de acceso
api.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const authStore = useAuthStore();
        if (authStore.accessToken) {
            config.headers.Authorization = `Bearer ${authStore.accessToken}`;
        }
        return config;
    },
    (error: any) => Promise.reject(error)
);

// Interceptor de Response: Maneja errores Globales y refresca tokens (401)
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // Si el error es 401, hay token guardado y no se ha reintentado previamente
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            
            const authStore = useAuthStore();

            if (!authStore.refreshToken) {
                // Si no hay refresh token, no podemos hacer mucho. Expulsar al usuario.
                authStore.clearAuth();
                router.push('/login');
                return Promise.reject(error);
            }

            try {
                // Intenta refrescar el token con el endpoint nativo de Simple JWT
                const response = await axios.post('http://localhost:8000/api/token/refresh/', {
                    refresh: authStore.refreshToken
                });

                // Si tiene éxito, renueva ambos tokens
                const newAccessToken = response.data.access;
                const newRefreshToken = response.data.refresh; // Si ROTATE_REFRESH_TOKENS es True, llega uno nuevo
                
                authStore.setTokens(newAccessToken, newRefreshToken || authStore.refreshToken);

                // Modifica el request original con el nuevo access token y lo reintenta
                if (originalRequest.headers) {
                    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                }
                return api(originalRequest);
                
            } catch (refreshError) {
                // Si falla el refresco (token inválido o expirado también), expulsa al usuario
                authStore.clearAuth();
                router.push('/login');
                return Promise.reject(refreshError);
            }
        }

        // Para cualquier otro error (400, 403, 500, etc), propagarlo hacia el componente
        return Promise.reject(error);
    }
);
