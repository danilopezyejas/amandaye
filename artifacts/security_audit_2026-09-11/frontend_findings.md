# Auditoría del frontend — 11 de septiembre de 2026

Alcance: código Vue/TypeScript, cliente Axios, estado de autenticación, rutas, configuración de Vite, dependencias declaradas y bloqueadas, y publicación del frontend en Docker Compose. Revisión estática; no se ejecutaron ataques ni se modificó la aplicación. Se contrastaron versiones con avisos publicados por los mantenedores antes de la fecha de auditoría.

## F-FE-01 — Lectura de archivos mediante Vite vulnerable expuesto a la red

**1. Vulnerabilidad y categoría OWASP.** Severidad alta; **A03:2025 — Software Supply Chain Failures**. La publicación del servidor de desarrollo contribuye como **A02:2025 — Security Misconfiguration**. El hallazgo reúne una dependencia vulnerable y una configuración que satisface sus condiciones de exposición; no representa dos problemas independientes.

**2. Ubicación exacta.**

- [package.json:21](C:/Users/Danilo/socios_amandaye/amandaye_frontend/package.json:21): rango de Vite `^7.0.4`.
- [package-lock.json:3523](C:/Users/Danilo/socios_amandaye/amandaye_frontend/package-lock.json:3523): entrada `node_modules/vite`; la línea 3524 fija **7.0.6**.
- [vite.config.js:15](C:/Users/Danilo/socios_amandaye/amandaye_frontend/vite.config.js:15): `host: true`; no desactiva WebSocket.
- [docker-compose.yml:29](C:/Users/Danilo/socios_amandaye/docker-compose.yml:29): `npm install && npm run dev -- --host 0.0.0.0 --port 5173`; la línea 31 publica `5173:5173` sin restringir la interfaz del host.

El paquete instalado localmente también declara **Vite 7.0.6**, según `amandaye_frontend/node_modules/vite/package.json`. Se inspeccionó su implementación: acepta conexiones WebSocket sin encabezado `Origin` y expone `fetchModule`.

**3. Riesgo y escenario de explotación.** Un atacante que pueda alcanzar el puerto 5173 puede solicitar archivos accesibles al proceso de Vite mediante su canal WebSocket. El fallo evita las restricciones de archivos aplicadas por la ruta HTTP. El aviso **CVE-2026-39363 / GHSA-p9ff-h696-f583**, publicado el **6 de abril de 2026**, incluye Vite 7.0.6 y establece **7.3.2** como primera corrección de la rama 7. [Aviso oficial de Vite](https://github.com/vitejs/vite/security/advisories/GHSA-p9ff-h696-f583).

La condición de red está configurada; no se verificó el firewall ni que exista una instancia accesible actualmente. En ejecución nativa, el alcance depende de los permisos del usuario que inicia Vite. En Docker, depende del sistema de archivos y los volúmenes del contenedor: el frontend monta su propia carpeta, no la carpeta del backend. No corresponde afirmar acceso automático a la base de datos o al equipo anfitrión completo.

**4. Código corregido y remediación.** Actualizar al menos a **Vite 7.3.5**, cuya publicación oficial es del **1 de junio de 2026**. Además de superar la corrección anterior, esta versión corrige otra vía de lectura de archivos específica de Windows. [Versión 7.3.5](https://github.com/vitejs/vite/releases/tag/v7.3.5), [aviso oficial sobre rutas de Windows](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff).

Fragmento de `package.json`; conservar las demás dependencias:

```json
{
  "devDependencies": {
    "vite": "^7.3.5"
  }
}
```

Actualizar también el lockfile mediante la instalación explícita, revisar el cambio y verificar el árbol resuelto:

```powershell
# Ejecutar dentro de amandaye_frontend al implementar la corrección.
npm install --save-dev "vite@^7.3.5"
npm ls vite
npm audit
npm run build
```

El rango de `package.json` permite actualizaciones, pero no prueba que estén instaladas. `npm install` normalmente conserva las versiones del lockfile que satisfacen el manifiesto. Sustituirlo por `npm ci` mejora la reproducibilidad, pero **no corrige un lockfile vulnerable**. La actualización del lockfile debe preceder al cambio de instalación. [Comportamiento oficial de npm install](https://docs.npmjs.com/cli/v11/commands/npm-install/), [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/).

Para desarrollo nativo, sustituir el bloque `server` por:

```javascript
server: {
  host: '127.0.0.1',
  port: 5173,
  strictPort: true,
  watch: {
    usePolling: true,
    interval: 1000,
  },
},
```

Para desarrollo en Docker, reemplazar estos campos del servicio `frontend`; el proceso debe escuchar dentro del contenedor, mientras el puerto publicado se restringe al equipo local:

```yaml
frontend:
  profiles: ["dev"]
  command: sh -c "npm ci && npm run dev -- --host 0.0.0.0 --port 5173"
  ports:
    - "127.0.0.1:5173:5173"
```

Es un fragmento de reemplazo, no un segundo bloque que se deba concatenar a `ports`: el mapeo previo `5173:5173` debe desaparecer. Activar expresamente el perfil de desarrollo cuando se necesite. La restricción de interfaz reduce exposición y debe acompañar la actualización.

Para producción, generar el artefacto en una etapa de construcción y publicar únicamente `dist` con el servidor web HTTPS del despliegue:

```dockerfile
# Etapa de construcción del frontend; no es el contenedor de publicación.
FROM node:24-alpine AS frontend_build
WORKDIR /build
COPY amandaye_frontend/package.json amandaye_frontend/package-lock.json ./
RUN npm ci
COPY amandaye_frontend/ ./
RUN npm run build
# Copiar /build/dist a la raíz estática del servidor HTTPS de producción.
```

Excluir `node_modules`, `dist` y archivos de entorno privados del contexto de construcción. El servidor de producción debe servir archivos estáticos; Vite documenta `vite preview` como comprobación local del resultado, no como servidor de producción. [Despliegue estático oficial](https://vite.dev/guide/static-deploy.html).

La verificación pendiente tras implementar consiste en comprobar la versión realmente resuelta, la compilación y la inaccesibilidad del puerto de desarrollo desde otras máquinas. Estas correcciones propuestas no se ejecutaron durante la auditoría.

## Observaciones que no constituyen vulnerabilidades explotables demostradas

- **Tokens persistentes:** [auth.ts:13](C:/Users/Danilo/socios_amandaye/amandaye_frontend/src/stores/auth.ts:13) y las líneas 30–34 leen/escriben access y refresh tokens en `localStorage`. Una futura XSS podría extraerlos. Sin embargo, no hay un flujo de login Vue implementado y `setTokens` solamente se llama al refrescar una sesión previamente existente; no se encontró una fuente de XSS. Antes de habilitar el login Vue, diseñar refresh/sesión con cookie `HttpOnly`, `Secure`, `SameSite`, controles CSRF en el backend y acceso de corta duración en memoria. No introducir cookies de autenticación sin protección CSRF.
- **URLs de desarrollo:** [axios.ts:7](C:/Users/Danilo/socios_amandaye/amandaye_frontend/src/api/axios.ts:7), línea 46, y [App.vue:31](C:/Users/Danilo/socios_amandaye/amandaye_frontend/src/App.vue:31) usan `http://localhost:8000`. En un despliegue remoto apuntarían al equipo del visitante. No demuestran envío de credenciales en claro por Internet porque son destinos loopback. Preparar `/api/`, `/api/token/refresh/` y `/login/` bajo un mismo origen HTTPS mediante el proxy de producción.
- **Autorización del navegador:** `isAuthenticated` comprueba sólo que exista un token y `jwtDecode` no verifica su firma. No se usan para conceder privilegios en el código actual; la seguridad efectiva debe seguir en el servidor. No se reporta un bypass de autorización por estas líneas.
- **XSS/CSRF:** el formulario usa interpolaciones de Vue para nombres y errores; no se observaron `v-html`, `innerHTML`, `eval`, plantillas compiladas desde entradas externas ni URLs aportadas por usuarios. El único envío de datos del frontend usa JSON y la API pública de solicitudes; no se identificó una mutación autenticada con cookies que permita demostrar CSRF desde este frontend.
- **Avisos sin ruta de explotación identificada:** Axios 1.15.0 figura en avisos que requieren contaminación previa de prototipos o su adaptador HTTP de Node; este cliente se ejecuta en navegador y no se encontró esa contaminación. Rollup 4.46.2 tiene un aviso que requiere controlar nombres de salida o configuración de construcción; aquí son internos. Los avisos sobre el servidor SSR de Vue y el servidor propio de esbuild no prueban afectación de esta SPA. Actualizar y auditar dependencias sigue siendo recomendable, pero no se presentan como ataques remotos adicionales confirmados. [Axios: precondición de contaminación de prototipos](https://github.com/axios/axios/security/advisories/GHSA-pf86-5x62-jrwf), [Rollup: nombres de salida manipulables](https://github.com/rollup/rollup/security/advisories/GHSA-mw96-cpmx-2vgc), [Vue: alcance SSR](https://github.com/vuejs/core/security/advisories/GHSA-g2v6-rqmx-r4w6).
