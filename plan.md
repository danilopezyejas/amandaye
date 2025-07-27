# Plan de Desarrollo para la Aplicación Web del Club Amandayé Ipegua

Este documento describe el plan detallado para el desarrollo de una aplicación web moderna para el club de canotaje/kayak Amandayé Ipegua. La aplicación constará de un backend construido con Django y Django REST Framework, y un frontend construido con Vue 3, Vite y TailwindCSS.

## 1. Configuración del Backend (Django + DRF)

*   **Crear un nuevo proyecto Django:** Se utilizará el comando `django-admin startproject socios_amandaye_backend`.
*   **Configurar Django REST Framework:** Se instalará DRF y se configurará en `settings.py`.
*   **Crear aplicaciones Django:** Se crearán las siguientes aplicaciones Django:
    *   `alerta`: Para manejar las alertas meteorológicas.
    *   `brevet`: Para manejar las preguntas del examen de brevet.
    *   `schedule`: Para manejar los horarios de clases/actividades.
    *   `users`: Para manejar la autenticación de usuarios.
*   **Configurar CORS:** Se instalará `django-cors-headers` y se configurará en `settings.py` para permitir la comunicación con el frontend.
*   **Configurar variables de entorno (.env):** Se instalará `python-dotenv` y se configurará para cargar las variables de entorno desde un archivo `.env`.
*   **Implementar los endpoints de la API:** Se crearán las URLs y vistas correspondientes para los siguientes endpoints:
    *   `/api/alerta/`: Para consumir o simular alertas meteorológicas de INUMET.
    *   `/api/brevet/questions/`: Para servir preguntas para un examen de brevet.
    *   `/api/schedule/`: Para los horarios de clases/actividades.
*   **Implementar la autenticación de usuarios (Token o JWT):** Se utilizará Django REST Framework para implementar la autenticación de usuarios con Token o JWT. Se creará un sistema de login.
*   **Incluir un placeholder o enlace estático para el formulario de registro de membresía:** Se agregará un enlace a un formulario de registro de membresía que se implementará en el futuro.

## 2. Configuración del Frontend (Vue 3 + Vite + TailwindCSS)

*   **Crear un nuevo proyecto Vue 3 con Vite:** Se utilizará el comando `npm create vite@latest socios_amandaye_frontend --template vue`.
*   **Configurar TailwindCSS:** Se instalará TailwindCSS y se configurará en el proyecto Vue.
*   **Crear un layout responsive mobile-first:** Se creará un layout que se adapte a diferentes tamaños de pantalla, priorizando la experiencia en dispositivos móviles.
*   **Crear los componentes:** Se crearán los siguientes componentes:
    *   Página de inicio:
        *   Logo y club intro.
        *   Componente que muestra el estado del tiempo actual y la alerta INUMET activa.
        *   Enlaces visibles a: página de horarios, página de estudio de brevet y formulario de registro futuro.
    *   Página de estudio de brevet (sin contenido inicial).
    *   Página de horarios (sin contenido inicial).
*   **Configurar PWA:**
    *   Crear `manifest.webmanifest` con nombre de la aplicación, color e icono.
    *   Crear `service-worker.js` para caching e instalación.
*   **Preparar la funcionalidad de login:** Se preparará la funcionalidad de login para uso futuro (pero no requerida inicialmente).

## 3. Comunicación entre Frontend y Backend

*   **Configurar las llamadas a la API REST desde el frontend:** Se utilizará `axios` o `fetch` para realizar llamadas a la API REST del backend.
*   **Implementar la lógica para mostrar los datos recibidos de la API en los componentes del frontend:** Se utilizarán los datos recibidos de la API para mostrar la información correspondiente en los componentes del frontend.