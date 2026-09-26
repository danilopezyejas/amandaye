# Guía de contribución

[Proyecto](README.md) · [Desarrollo](docs/DEVELOPMENT.md) · [Arquitectura](docs/ARCHITECTURE.md)

## Preparar un cambio

1. Identificar el comportamiento esperado y el módulo que lo implementa.
2. Preparar el entorno de desarrollo y trabajar en una rama con un propósito claro.
3. Mantener el cambio acotado; separar refactorizaciones ajenas al problema.
4. Actualizar la documentación cuando cambien rutas, permisos, configuración o uso.

Las reglas de negocio de socios y cobranzas pertenecen a los servicios del backend.
Las vistas, los serializadores y el frontend deben utilizar esas reglas. Una
restricción en la interfaz nunca sustituye una comprobación de permisos del servidor.

## Criterios de implementación

- Conservar auditoría y consistencia de movimientos financieros. Usar los servicios
  transaccionales para escribir o corregir operaciones.
- Incluir migraciones explícitas cuando cambien los modelos y describir su impacto
  sobre una base existente.
- Usar datos sintéticos en pruebas, capturas y ejemplos. No añadir secretos,
  exportaciones de producción ni respuestas externas que contengan credenciales.
- Mantener las credenciales de proveedores en el backend; no incorporarlas a
  variables `VITE_*` ni al bundle público.
- Al cambiar dependencias, actualizar el archivo de bloqueo correspondiente y
  comprobar la instalación reproducible. Backend: `requirements.in` y
  `requirements.txt` con hashes. Frontend: `package.json` y `package-lock.json`.

## Validación según el cambio

| Cambio | Verificación pertinente |
| --- | --- |
| Backend | Suite Django con `settings_test`; comprobar migraciones pendientes. |
| Cobranzas o transacciones | Añadir la suite de concurrencia con MySQL desechable. |
| Frontend | Pruebas de Node, `vue-tsc` y build; revisar el flujo afectado en el navegador. |
| Integración meteorológica | Casos de unidades, fechas, datos ausentes, fallos y selección de fuente con respuestas simuladas. |
| Compose o despliegue | `docker compose … config --quiet` y verificación del entorno afectado. |
| Solo documentación | Comprobar enlaces, rutas, ejemplos, nombres de variables y consistencia con el código. |

Los comandos y las condiciones de aislamiento están en
[Desarrollo](docs/DEVELOPMENT.md#pruebas-locales-aisladas). Registrar las pruebas
ejecutadas y cualquier limitación real; no presentar una comprobación estática como
validación de un despliegue completo.

## Presentar el cambio

El commit y la solicitud de revisión deben explicar qué problema resuelve el cambio,
cuál es el comportamiento resultante y cómo se verificó. Incluir, cuando corresponda:

- Pasos para reproducir y comprobar la corrección.
- Capturas de cambios visibles con datos ficticios.
- Migraciones, nuevas variables y acciones operativas necesarias.
- Limitaciones conocidas y pasos pendientes.

Para vulnerabilidades o exposición de datos, seguir [Seguridad](SECURITY.md).
