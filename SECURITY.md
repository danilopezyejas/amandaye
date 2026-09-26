# Seguridad

[Proyecto](README.md) · [Despliegue](docs/DEPLOYMENT.md) · [API](docs/API.md)

## Modelo de acceso

El administrador usa sesiones Django y protección CSRF. La API privada utiliza
JWT y permisos específicos para cada operación. La inscripción y la consulta
ambiental son públicas y tienen límites de solicitudes. Los intentos fallidos de
autenticación cuentan además con bloqueo temporal.

Las claves de sesiones y de JWT son independientes. Los tokens de renovación se
rotan y los anteriores quedan invalidados. Los servicios financieros comprueban al
operador y conservan auditoría de las correcciones.

## Roles y permisos

El comando `setup_roles` mantiene estos nombres exactos de grupos:

| Grupo | Responsabilidad principal |
| --- | --- |
| `Administrador` | Todos los permisos Django disponibles al ejecutar el comando. |
| `Comision Directiva` | Consulta, decisiones sobre socios y acceso a resúmenes de cobranzas. |
| `Secretaria` | Gestión de personas y socios dentro de sus permisos, registro y aplicación de pagos. |
| `Tesoreria` | Consulta financiera, gestión de conceptos y pagos, aplicación, reversión y anulación autorizadas. |

Esta tabla resume responsabilidades. La asignación exacta está en
[setup_roles.py](amandaye_backend/apps/usuarios/management/commands/setup_roles.py)
y cada operación añade sus controles de negocio. No todos los grupos tienen
permisos para crear, modificar o eliminar todos los recursos.

El comando **reemplaza los permisos** de esos grupos; no combina automáticamente
personalizaciones previas. El acceso al administrador también requiere un usuario
activo con `is_staff`. Reservar las cuentas de superusuario para tareas que lo
necesiten y asignar al personal los permisos de su función.

## Secretos y datos personales

- Generar secretos con `scripts/bootstrap_secrets.py` y usar conjuntos distintos
  para desarrollo y producción. El script conserva valores existentes y no rota
  las credenciales de una base ya inicializada.
- Mantener `.env`, secretos, copias de bases y datos personales fuera de commits,
  imágenes y ejemplos. Revisar lo preparado para commit antes de publicarlo.
- Los archivos montados como secretos de Compose requieren protección del host y
  de sus copias de seguridad; Compose no los cifra por sí mismo.
- Las claves de estaciones permanecen en el backend. La lectura provisional de
  páginas públicas no extrae ni reutiliza claves de terceros.
- La exclusión actual de un archivo no elimina versiones anteriores del historial.
  Ante una exposición, rotar el secreto afectado y coordinar la revisión de clones,
  artefactos e imágenes compartidas.

La [guía de despliegue](docs/DEPLOYMENT.md#secretos-y-límites-de-confianza) documenta
los archivos, permisos, límites del proxy y requisitos para bases externas.

## Operación

Publicar la aplicación con el gateway HTTPS; mantener MySQL y Redis en sus redes
privadas. Ejecutar `check --deploy`, comprobar permisos con cuentas de prueba y
verificar la restauración de respaldos antes de abrir tráfico. Los logs de seguridad
requieren acceso y retención controlados.

Programar el mantenimiento de tokens caducados y revisar dependencias e imágenes
como parte de la operación. El repositorio ofrece comandos de mantenimiento; su
ejecución periódica depende de la configuración del servidor.

## Comunicar una vulnerabilidad

Contactar de forma privada a quien mantiene el repositorio o administra el sistema
del club. Incluir componente afectado, versión o commit, impacto y pasos mínimos
con datos sintéticos. Acordar un canal privado antes de compartir registros sensibles.

No publicar claves, datos de socios ni detalles explotables en un issue público.
Si el hallazgo incluye un secreto expuesto, comunicarlo para coordinar su rotación
y la revisión del alcance antes de cerrar la incidencia.
