# Referencia de la API

[Índice](README.md) · [Arquitectura](ARCHITECTURE.md) · [Seguridad](../SECURITY.md)

Esta guía describe las rutas implementadas y sus reglas de acceso. Los campos de
entrada y sus validaciones se definen en los serializadores de
[usuarios](../amandaye_backend/apps/usuarios/serializers.py) y
[cobranzas](../amandaye_backend/apps/cobranzas/serializers.py).

## Convenciones

- Prefijo `/api/`, rutas con barra final y cuerpos JSON.
- API privada: `Authorization: Bearer <access_token>` y permiso Django específico
  de la operación. Autenticarse no concede acceso a todos los recursos.
- Las listas de los viewsets usan paginación por página, con 50 elementos y los
  campos `count`, `next`, `previous` y `results`. No aplicar esa forma a los
  reportes o a los endpoints ambientales.
- `400` indica entrada inválida; `401`/`403`, un problema de autenticación o permiso;
  `404`, recurso inexistente; `429`, límite de solicitudes o bloqueo de acceso.
- Los identificadores se obtienen de la API; no asumir que el identificador de una
  cuenta, un socio y una persona sea intercambiable.

## Autenticación

| Método y ruta | Entrada | Resultado |
| --- | --- | --- |
| `POST /api/token/` | `username`, `password` | Tokens `access` y `refresh` |
| `POST /api/token/refresh/` | `refresh` | Nuevo acceso y refresh rotado |
| `GET /api/me/` | Token de acceso | Perfil y grupos del usuario autenticado |

El acceso dura 10 minutos y el refresh un día según la configuración actual. El
refresh se rota y el anterior se incorpora a la lista de invalidación. El cliente
debe conservar el nuevo refresh tras cada renovación. Las claves de firma de JWT
y de sesiones Django son independientes.

El inicio de sesión del administrador en `/login/` o `/admin/` es un flujo distinto,
basado en cookies de sesión y CSRF.

## Endpoints públicos

| Método y ruta | Comportamiento |
| --- | --- |
| `POST /api/socios/solicitudes/` | Recibe una solicitud de inscripción; responde `202` con una confirmación mínima. |
| `GET /api/conditions/` | Observaciones consolidadas, fuentes, pronóstico y metadatos. |
| `GET /api/conditions/stations/` | Detalle de estaciones y metadatos, sin consultar el pronóstico. |

Ejemplo de lectura desde el entorno de desarrollo, en PowerShell:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:5173/api/conditions/' -Method Get
```

Una respuesta ambiental puede ser válida aunque una fuente esté caída. Revisar
`available`, antigüedad y errores de cada fuente. El
[contrato ambiental](CONDITIONS.md#endpoints-y-contrato) detalla métricas, estados y
diferencias entre observaciones y pronóstico.

## Socios

| Método y ruta | Permiso requerido |
| --- | --- |
| `GET /api/socios/` y `GET /api/socios/{id}/` | `usuarios.view_socios` |
| `POST /api/socios/{id}/aprobar/` | `usuarios.puede_aprobar_socio` |
| `POST /api/socios/{id}/dar-baja/` | `usuarios.puede_dar_baja_socio`; requiere `motivo` |

La API de socios permite lectura y acciones explícitas. Las rutas y los permisos
se mantienen en [api_views.py](../amandaye_backend/apps/usuarios/api_views.py).

## Cuentas y cobranzas

Todas las rutas de esta sección comienzan con `/api/cobranzas/`. Los permisos
indicados pertenecen a la aplicación Django `cobranzas`.

| Recurso o acción | Métodos | Permiso |
| --- | --- | --- |
| `conceptos-cobro/` y `conceptos-cobro/{id}/` | Lectura, creación, actualización y eliminación | `view_conceptocobro`, `add_conceptocobro`, `change_conceptocobro` o `delete_conceptocobro`, según operación |
| `cuentas/` y `cuentas/{id}/` | `GET` | `view_cuentacorriente` |
| `cuentas/{id}/estado-cuenta/` | `GET` | `view_cuentacorriente` |
| `cargos/` y `cargos/{id}/` | Lectura; `POST` en la colección | `view_cargo` o `add_cargo` |
| `cargos/{id}/anular/` | `POST` | `puede_anular_cargo` |
| `pagos/` y `pagos/{id}/` | Lectura; `POST` en la colección | `view_pago` o `add_pago` |
| `pagos/{id}/aplicar/` | `POST` | `puede_aplicar_pago` |
| `aplicaciones/` y `aplicaciones/{id}/` | `GET` | `view_aplicacionpago` |
| `aplicaciones/{id}/revertir/` | `POST` | `puede_revertir_aplicacion_pago` |
| `reportes/cuentas-con-deuda/` y `reportes/recaudacion/` | `GET` | `puede_ver_resumen_cobranzas` |

Aplicar un pago recibe `cargo_id` e `importe`; anular un cargo, `observaciones`;
revertir una aplicación, `motivo`. El reporte de recaudación admite los filtros
`desde` y `hasta`. Consultar los serializadores para tipos, obligatoriedad y límites.

La creación de una aplicación ocurre mediante la acción sobre el pago. Cargos,
pagos y aplicaciones no exponen `PUT`, `PATCH` ni `DELETE` genéricos. Los servicios
vuelven a comprobar autorización y reglas financieras antes de escribir.

## Límites de solicitudes

| Alcance | Configuración actual |
| --- | --- |
| Solicitudes públicas de socios | 5 por hora |
| Inicio de sesión JWT | 10 por minuto |
| Renovación JWT | 30 por minuto |
| Condiciones meteorológicas | 60 por minuto |

Estos límites se aplican mediante DRF; la identificación del cliente depende de la
autenticación y de la configuración de IP/proxy. El bloqueo por intentos fallidos
de autenticación es un control adicional. Al recibir `429`, respetar `Retry-After`
cuando esté presente. La configuración vigente se encuentra en
[settings.py](../amandaye_backend/amandaye_backend/settings.py).
