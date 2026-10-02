# Documentación

[Volver al proyecto](../README.md)

## Guías vigentes

| Documento | Contenido |
| --- | --- |
| [Desarrollo](DEVELOPMENT.md) | Entorno local, pruebas, comandos habituales y resolución de problemas. |
| [Arquitectura](ARCHITECTURE.md) | Componentes, flujos de datos, autenticación y decisiones de diseño. |
| [API](API.md) | Rutas, métodos, permisos y convenciones de integración. |
| [Despliegue](DEPLOYMENT.md) | Instalación en producción, secretos, migración, verificaciones y mantenimiento. |
| [Condiciones del río](CONDITIONS.md) | Configuración, contrato ambiental, proveedores, caché y límites del scraping provisional. |
| [Gestión diaria](GESTION.md) | Panel de Secretaría/Tesorería, ficha de socio, cobros y comprobantes internos. |
| [Fuentes meteorológicas](CONDITIONS_SOURCES.md) | Contratos externos y referencias verificadas en las fechas indicadas. |
| [Contribución](../CONTRIBUTING.md) | Preparación y validación de cambios. |
| [Seguridad](../SECURITY.md) | Modelo de acceso, protección de datos y comunicación de incidentes. |
| [ECC y trabajo asistido](ECC_INTEGRATION.md) | Instalación del plugin y adaptación de sus procedimientos al proyecto. |
| [Continuidad](CONTINUITY.md) | Estado de referencia, decisiones y próximos pasos entre sesiones. |

## Por dónde empezar

- **Primera instalación:** [inicio rápido](../README.md#inicio-rápido), seguido de
  [puesta en marcha funcional](DEVELOPMENT.md#puesta-en-marcha-funcional).
- **Cambiar código:** arquitectura, desarrollo y la referencia del módulo afectado.
- **Administrar un servidor:** despliegue y seguridad; ensayar primero cualquier
  restauración o migración en un entorno separado.
- **Configurar las estaciones:** condiciones del río y fuentes meteorológicas.

## Planificación activa

- [Gestión de Secretaría y Tesorería](../plans/gestion-secretaria-tesoreria.md):
  plan por etapas para ficha unificada, cobro y pendientes; incluye tarifas,
  vista previa de cuotas y seguimiento.

## Notas históricas

Estas notas conservan decisiones y verificaciones de su momento; las instrucciones
de instalación y operación se mantienen en las guías anteriores.

- [Traspaso de condiciones del río](CONDITIONS_HANDOFF.md): contexto para continuar
  la implementación, pruebas realizadas y pendientes de integración.
- [Plan inicial](../plan.md): propuesta original, anterior a la arquitectura actual;
  incluye ideas que todavía no están implementadas.

## Mantener la documentación

Actualizar la guía correspondiente cuando cambien rutas, permisos, variables,
comandos o comportamiento. Usar datos sintéticos en ejemplos y distinguir las
funciones disponibles de las propuestas. Los contratos ejecutables están en el
código, las migraciones y los archivos de dependencias del repositorio.
