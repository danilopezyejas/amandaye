# Documentación del Proyecto Web - Club Amandayé Ipeguá

Este proyecto es la plataforma oficial del Club Amandayé Ipeguá, diseñada con una arquitectura moderna, segura y estética premium.

---

## 1. Arquitectura General

El proyecto utiliza una arquitectura desacoplada con un backend robusto y un frontend dinámico.

### Frontend (Interfaz Web)

*   **Framework:** Vue 3 (Composition API)
*   **Lenguaje:** TypeScript
*   **Estado:** Pinia
*   **Herramientas:** Vite, TailwindCSS
*   **Estética:** Diseño Premium con Glassmorphism, fondos inmersivos y animaciones fluidas.
*   **Seguridad:** Autenticación JWT con rotación de tokens y Axios Interceptors para manejo de sesiones.
*   **Funcionalidad:**
    *   Landing page de alto impacto visual.
    *   Ficha de inscripción dinámica.
    *   Integración con Redes Sociales (WhatsApp, Instagram, Facebook).
    *   Acceso directo al panel administrativo para personal autorizado.
*   **Servidor en desarrollo:** `http://localhost:5173/`

### Backend (Lógica + Datos)

*   **Framework:** Django 4 + Django REST Framework (DRF)
*   **Autenticación:** SimpleJWT (JSON Web Tokens) e Historial de Modificaciones en el Admin.
*   **Base de Datos:** MySQL (soporta SQLite para desarrollo rápido).
*   **Funcionalidad:**
    *   API REST para gestión de usuarios, cobranzas y actividades.
    *   Panel de administración personalizado (branding, búsqueda avanzada, filtros optimizados).
    *   Sistema de rastreo de cambios ("From/To") en el Admin de Django.
*   **Servidor en desarrollo:** `http://localhost:8000/`

---

## 2. Estructura de Carpetas

```plaintext
amandaye/
├── amandaye_backend/          # Proyecto Django
│   ├── apps/
│   │   ├── usuarios/          # Autenticación JWT, Perfiles, Login
│   │   ├── cobranzas/         # Gestión de pagos y cuentas (Nuevo)
│   │   ├── alertas/           # Integración INUMET
│   │   ├── brevet/            # Material de estudio y exámenes
│   │   └── horarios/          # Gestión de clases y actividades
│   ├── amandaye_backend/      # Configuración central (settings, urls)
│   └── manage.py
│
└── amandaye_frontend/         # Proyecto Vue 3 + TypeScript
    ├── src/
    │   ├── api/               # Cliente Axios e Interceptores
    │   ├── stores/            # Pinia (auth, user state)
    │   ├── router/            # Navigation Guards y Rutas
    │   ├── components/        # Componentes UI reutilizables
    │   └── App.vue            # Componente raíz con diseño modernizado
```

---

## 3. Guía de Inicio

### Backend (Django):
1. Crear entorno virtual: `python -m venv venv`
2. Activar entorno: `.\venv\Scripts\activate` (Windows)
3. Instalar dependencias: `pip install -r requirements.txt`
4. Ejecutar: `python manage.py runserver`

### Frontend (Vue 3):
1. Instalar dependencias: `npm install`
2. Ejecutar: `npm run dev`

---

## 4. Accesos en Desarrollo

*   **Sitio Web:** `http://localhost:5173/` (Landing + Dashboard)
*   **Panel Administrativo:** `http://localhost:8000/admin/`

---

## 5. Seguridad y Personalización

*   **JWT:** El sistema refresca automáticamente los tokens para mantener la sesión segura.
*   **Admin Tracking:** Cada cambio realizado en el panel administrativo queda grabado con el valor anterior y el nuevo.
*   **Optimización de Búsqueda:** El admin permite búsquedas complejas cruzando tablas de socios y usuarios.

---

## 6. Próximos Pasos

*   [ ] Integración total del módulo de cobranzas en el frontend.
*   [ ] Notificaciones automáticas por correo/whatsapp.
*   [ ] Dashboard analítico para la directiva.
*   [ ] Consumo en tiempo real de la API de INUMET.

