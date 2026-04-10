import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'

interface UserTokenPayload {
    user_id: number;
    exp: number;
    [key: string]: any;
}

export const useAuthStore = defineStore('auth', () => {
    // State
    const accessToken = ref<string | null>(localStorage.getItem('access_token'))
    const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
    
    // Getters
    const isAuthenticated = computed(() => !!accessToken.value)
    
    const user = computed(() => {
        if (!accessToken.value) return null
        try {
            return jwtDecode<UserTokenPayload>(accessToken.value)
        } catch (error) {
            console.error('Invalid token', error)
            return null
        }
    })

    // Actions
    function setTokens(access: string, refresh: string) {
        accessToken.value = access
        refreshToken.value = refresh
        localStorage.setItem('access_token', access)
        localStorage.setItem('refresh_token', refresh)
    }

    function clearAuth() {
        accessToken.value = null
        refreshToken.value = null
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
    }

    return {
        accessToken,
        refreshToken,
        isAuthenticated,
        user,
        setTokens,
        clearAuth
    }
})
