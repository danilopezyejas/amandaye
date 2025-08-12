# Documentación del Proyecto Web - Club Amandayé Ipegua

Este proyecto corresponde al desarrollo del sitio web oficial del Club Amandayé Ipegua, pensado para ser moderno, modular, accesible desde el celular y escalable.

---

## 1. Arquitectura General

El proyecto está dividido en dos partes principales:

### Frontend (Interfaz Web)

* **Framework:** Vue 3
* **Herramientas:** Vite, TailwindCSS
* **Funcionalidad:**

  * Sitio informativo accesible sin iniciar sesión
  * Consulta de horarios, alertas de INUMET, pronóstico del clima
  * Sección para estudio del brevet
  * Ficha de afiliación (link disponible para futura integración)
  * Aplicación PWA con iconos y manifest
* **Servidor en desarrollo:** `http://localhost:5173/`

### Backend (Lógica + Datos)

* **Framework:** Django 4 + Django REST Framework
* **Base de Datos:** MySQL (XAMPP en desarrollo)
* **Funcionalidad:**

  * API REST que provee datos al frontend
  * Panel de administración de Django accesible en `/admin`
* **Servidor en desarrollo:** `http://localhost:8000/admin/`

---

## 2. Estructura de Carpetas

```plaintext
amandaye/
├── amandaye_backend/          # Proyecto Django
│   ├── apps/
│   │   ├── usuarios/          # autenticación, login
│   │   ├── alertas/           # INUMET
│   │   ├── brevet/            # preguntas de examen
│   │   ├── horarios/          # clases y actividades
│   │   └── afiliaciones/      # ficha de socios (futuro)
│   ├── amandaye_backend/      # config Django (settings, urls)
│   ├── manage.py
│   └── static/                # archivos estáticos (si se usan)
│
└── amandaye_frontend/         # Proyecto Vue 3
    ├── index.html
    ├── package.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── public/
    │   ├── manifest.webmanifest
    │   └── icons/
    └── src/
        ├── main.js
        ├── assets/
        │   └── tailwind.css
        ├── components/
        ├── pages/
        ├── router/
        ├── api/
        └── store/
```

---

## 3. Levantamiento de Servidores

### Backend (Django):

```bash
cd amandaye_backend
python manage.py runserver
```

### Frontend (Vue 3 + Vite):

```bash
cd amandaye_frontend
npm install     # solo la primera vez
npm run dev
```

---

## 4. Accesos en desarrollo

* Sitio web: `http://localhost:5173/`
* Admin de Django: `http://localhost:8000/admin/`

---

## 5. Consideraciones de Seguridad (Producción)

* El admin Django debe estar protegido por HTTPS, autenticación fuerte y/o firewall.
* El frontend debe compilarse con `npm run build` y puede servirse con Nginx o desde Django.
* El panel de administración se mantendrá accesible desde `www.amandaye.org.uy/admin`.

---

## 6. Futuras mejoras

* CRUD de socios y fichas
* Integración de login
* Buscador de actividades
* Formularios dinámicos para el panel
* Consumo real de la API de INUMET
