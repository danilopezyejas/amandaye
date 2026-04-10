import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Home',
    // Componente placeholder o vista principal (ajustar luego al componente real)
    component: () => import('../App.vue'), 
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    // Componente placeholder para el Login interactivo
    component: () => import('../App.vue'), // Reemplazar por vistas reales ej: import('../views/Login.vue')
    meta: { guestOnly: true }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// Navigation Guard Global
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const isAuth = authStore.isAuthenticated

  // Si la ruta requiere estar autenticado y el usuario no lo está
  if (to.meta.requiresAuth && !isAuth) {
    next({ name: 'Login' })
  } 
  // Si la ruta es solo para invitados (ej: /login) y el usuario ya está conectado
  else if (to.meta.guestOnly && isAuth) {
    next({ name: 'Home' })
  } 
  // De lo contrario, permite la navegación normal
  else {
    next()
  }
})

export default router
