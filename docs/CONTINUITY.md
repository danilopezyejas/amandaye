# Continuidad del proyecto

[Índice](README.md) · [Instrucciones de trabajo](../AGENTS.md) · [ECC](ECC_INTEGRATION.md)

Este registro conserva decisiones y próximos pasos entre sesiones. Comprobar siempre
`git status`, rama y commits: los estados del servidor y las fuentes externas deben
verificarse de nuevo cuando sean relevantes. Mantenerlo breve y sin datos personales,
secretos, volcados de conversaciones ni logs completos.

## Cierre de sesión — 2026-10-22

- El logout administrativo vuelve a la portada Vue: `http://localhost:5173/`
  en desarrollo y `/` en producción. Destino configurable con `FRONTEND_HOME_URL`.
  Antes, `/` en el puerto 8000 devolvía al login del backend.
- Tres pruebas satisfactorias: destino de desarrollo, raíz pública de producción,
  eliminación de sesión y conservación de la exigencia POST/CSRF.
- Cambio de configuración sin migraciones; guía de uso actualizada.

## Ayuda contextual — 2026-10-21

- Ayuda desplegable integrada en las pantallas Django y guías específicas para
  Gestión, Usuarios y Cobranzas; orientación general para otros módulos y acceso.
  La web pública incorpora guías en portada, inscripción y condiciones del río.
- Tooltips mediante botones de consulta junto a acciones y campos clave, incluidos
  los nombres del administrador tradicional. Funcionan con mouse, foco y toque;
  Escape cierra. No envían formularios ni cambian permisos o reglas del dominio.
- Catálogo Django en `apps/gestion/templatetags/ayuda.py`, interfaz en
  `templates/gestion/ayuda.html` y `static/ayuda/`; componente Vue `ContextHelp.vue`.
  Al agregar funciones, mantener guías y el catálogo de acciones/campos actualizado.
- Verificados 162 tests de Gestión/Usuarios/Cobranzas: 154 satisfactorios y 8
  omitidos por requerir MySQL. No se modificaron servicios financieros ni modelos;
  no se repitió concurrencia. Frontend: 28 tests, vue-tsc y build satisfactorios.
  El build del host requirió salir del aislamiento por acceso de esbuild.
- Chrome sintético: guía de acceso, panel y Pagos, ayuda en portada, inscripción y
  condiciones; tooltip con foco/toque y cierre Escape. Corregido el ocultamiento
  del tooltip durante el desplazamiento provocado por el foco del teclado.
- La guía de uso describe los controles. No hay nuevas dependencias ni migraciones.
- Instalado en desarrollo y comprobado el 22 de octubre: backend `9c68fb8ab600`
  y frontend `4a57c4afcb68`, reutilizando las dependencias de las imágenes previas.
  Django check satisfactorio y HTTP 200 en login con ayuda y script de tooltips.
  Los contenedores existentes y sus datos se conservaron; no se aplicaron migraciones.
  Las pruebas visuales se realizaron con datos sintéticos y sus servidores se cerraron.

## Cierre y documentación — 2026-10-21

- Hito 3 publicado en GitHub: `cdcedd8`, rama `codex/gestion-secretaria-tesoreria`.
  Los hitos 1–3 están implementados; P09–P12 permanecen pendientes.
- README actualizado con la rama de Gestión, acceso directo, módulo y resumen
  funcional. Arquitectura describe las consultas, el cobro y el evaluador compartido.
  Guía e índice actualizados; el plan distingue estado vigente y diseño original.
- Cambio exclusivamente documental: comprobar enlaces locales, anclas y diff;
  no requiere repetir suites ni reconstruir servicios. La evidencia de instalación
  y pruebas del 20 de octubre está debajo; no implica una nueva comprobación en vivo.
- Conservar las ediciones previas de configuración de Codex, AGENTS y ECC.

## Estado de referencia — 2026-10-02

- Rama de trabajo: `codex/gestion-secretaria-tesoreria`.
- Scraping provisional implementado en `4a00982`; documentación reorganizada en
  `f3f91a7`. Ambos commits se publicaron en esa rama.
- ECC y las instrucciones de proyecto se incorporaron en `22d4148`, también publicado.
- La página `/condiciones-del-rio` tiene acceso desde la portada. Combina observaciones
  locales con pronóstico independiente; no evalúa navegación ni muestra altura del río.
- `CONDITIONS_STATION_MODE=auto` usa API cuando hay credenciales completas para la
  estación y página pública cuando faltan. Una API configurada que falla no cambia
  automáticamente a scraping.
- Las lecturas en vivo y pruebas funcionales históricas están en
  [CONDITIONS_HANDOFF.md](CONDITIONS_HANDOFF.md). No interpretar sus fechas ni estados
  de estaciones como resultados actuales.

## Hito 3 — verificado e instalado, 2026-10-20

- P08 terminado en `codex/gestion-secretaria-tesoreria`: solicitudes, pagos con
  saldo, cargos vencidos y habilitaciones con filtros y paginación independiente
  de 25 registros. Los conteos respetan filtros y permisos; las acciones llevan
  a ficha, solicitud, cobro o aplicación de saldo según las capacidades del operador.
- Pagos distinguen anticipo, aplicación pendiente y legado sin clasificar.
  Deuda muestra saldo neto de aplicaciones activas, excluyendo anulaciones y
  vencimientos de hoy. No se compensan anticipos automáticamente.
- Política de habilitación compartida entre panel, ficha, administrador y recálculo:
  evaluador puro de estado/motivos con adaptador de lectura por lote. Conserva
  precedencia de revocación/suspensión y usa fecha local del club. Motivos sensibles
  requieren consulta de personas, socios y cuentas; las consultas no escriben estados.
- La lista filtra por estado registrado y distingue evaluación actual y último
  cálculo. Para revisar estados previamente habilitados usar Todos los estados.
  P09 (recálculo periódico y piloto) y P10–P12 siguen pendientes, fuera de este hito.
- Verificación con `amandaye-verification`: 266 pruebas SQLite (258 satisfactorias,
  8 de concurrencia omitidas) y **266 pruebas MySQL satisfactorias, sin omisiones**.
  Incluyen permisos, saldos activos/revertidos, paginación, filtros inválidos,
  ausencia de escrituras en GET, consultas acotadas y reglas de habilitación.
  `makemigrations --check --dry-run` sin cambios. Suite Vue omitida: no cambió Vue.
- Chrome con base sintética en memoria: panel, motivos, segunda página de pagos
  (4 de 29) y filtro combinado de socio/anticipos (14 resultados). Capturas revisadas
  en escritorio y ventana reducida. Pestaña y servidor sintético cerrados.
  MySQL desechable retirado; no se usaron datos del club para las pruebas.
- Imagen `7138ae2def3d` instalada en desarrollo; anterior `97cefc7bc097` conservada.
  Los cuatro servicios están activos, MySQL y Redis saludables. `manage.py check`
  y `migrate --check` satisfactorios. Login HTTP 200; Gestión redirige al login sin
  sesión y responde HTTP 200 final. No se aplicaron migraciones ni se cambiaron roles.
- Guía de Gestión y plan actualizados. Conservar fuera de este commit las ediciones
  previas de AGENTS, ECC, índice, docs/CODEX.md y .codex, incluida la sección de
  configuración de Codex de este registro. Siguiente paso: revisión del usuario y
  acordar P09 antes de implementarlo.

## Hito 2 — publicado e instalado, 2026-10-19

- Hito 1 publicado el 17 de octubre en `5770514`, rama
  `codex/gestion-secretaria-tesoreria`. Se preservaron fuera del commit los cambios
  ajenos de configuración de Codex, AGENTS, ECC e índice; conservarlos.
- Hito 2 implementa distribución editable sobre hasta 100 cargos pendientes,
  resumen previo y confirmación firmada por operador/cuenta/pago, con vigencia
  de 30 minutos. Los servicios revalidan permisos, saldos y versión bajo bloqueo;
  reintentos idénticos no duplican pagos ni aplicaciones.
- Aplicar saldo disponible desde ficha y panel no exige `add_pago` ni crea otro
  ingreso. Se conserva el comprobante original; un pago legado sin recibo obtiene
  uno marcado como reconstruido. La auditoría conserva la operación y aplicaciones.
- Propuestas calculadas con agregación SQL, sin consultas adicionales por cargo.
  Se aceptan distribuciones parciales y cargos posteriores al primero. Los importes
  excesivos, negativos, cargos ajenos, revisiones alteradas o vencidas se rechazan.
- El 17 de octubre pasaron 246 pruebas SQLite (238 satisfactorias y 8 omitidas
  de concurrencia) y las **246 pruebas MySQL sin omisiones** en imagen `43d1b16a3d13`.
  Incluyen tres carreras nuevas: doble confirmación del cobro, gasto simultáneo
  del mismo saldo y reenvío simultáneo de la misma aplicación. Entorno MySQL retirado.
- La revisión visual encontró la fecha inicial vacía por formato HTML. Se corrigió
  a ISO y fecha local del club; las 9 pruebas de pantalla posteriores pasan en
  SQLite. No cambian modelos: `makemigrations --check --dry-run` sin diferencias.
- Recorrido Chrome sintético completado el 19: editar distribución, volver a
  ajustar, confirmar y abrir PDF; luego aplicar el remanente del mismo pago y
  comprobar saldo cero, aplicaciones e historial. Servidor de prueba en memoria
  y pestaña cerrados. No se registraron cobros de prueba en la base del club.
- Guía de uso y estado del plan actualizados. No se ejecutó la suite Vue porque
  el cambio está en servicios y plantillas de Django.
- Publicado en GitHub: `0147aef` sobre `codex/gestion-secretaria-tesoreria`.
  Imagen final `97cefc7bc097`, con fecha corregida; sus 9 pruebas de pantalla
  también pasaron dentro del contenedor aislado sin red.
- Backend de desarrollo recreado con esa imagen. `manage.py check` sin problemas
  y `migrate --check` satisfactorio; no se aplicaron migraciones ni se cambiaron
  roles o datos reales. Imagen anterior conservada: `8e5b57dcb881`; respaldo local
  previo con restauración comprobada disponible. No se eliminaron volúmenes.
- Al retomar el cierre Docker Desktop estaba detenido; se volvió a iniciar y
  arrancaron los cuatro servicios existentes. MySQL y Redis saludables. Imagen
  activa confirmada: `97cefc7bc097`. Login HTTP 200; panel y nueva ruta de aplicación
  redirigen al login sin sesión y responden HTTP 200 final. Instalación comprobada.
- Hito 3 y P09–P12 permanecen pendientes, fuera del encargo actual.

## Hito 1 — instalado, 2026-10-16

- Encargo vigente: terminar la ficha unificada. Código local en
  `codex/gestion-secretaria-tesoreria`, base `0f78e5d`; conservar los cambios
  previos de Gestión, Personas, dependencias e instrucciones.
- Implementados búsqueda por familiares/nombres completos, permisos por sección,
  detección de titular ajeno al grupo, paginación independiente de cargos/pagos/
  aplicaciones/historial, totales separados y consultas sin crecimiento por fila.
- Nuevo `EventoSocio` con migración aditiva `usuarios.0010_eventosocio`: los servicios
  de transición escriben socio/actor/fecha/acción en su misma transacción, con ID
  automático. `socios_cambios` se conserva como legado; no se reconstruye por texto.
  El historial combina eventos vinculados, admin del socio y fuentes financieras.
- Verificado el 15 de octubre: 13 pruebas nuevas de ficha/transiciones pasan;
  suite SQLite completa: 227, con 223 satisfactorias y 4 omitidas de MySQL.
  `makemigrations --check --dry-run` sin cambios. Se añadió luego una prueba
  concurrente de auditoría pendiente de ejecución en MySQL.
- El 16 de octubre se corrigió una diferencia de colación de MySQL: algunos
  dígitos Unicode se comparaban como ASCII. La búsqueda ahora pide dígitos 0–9.
  Pruebas dirigidas SQLite posteriores: 13 pasan y una de MySQL se omite.
- **Suite MySQL final: 228 pruebas satisfactorias, sin omisiones**, incluida la
  auditoría concurrente y las consultas/paginación de la ficha. Se aplicó 0010
  sobre la base sintética; contenedor y red de pruebas retirados al terminar.
- Imagen verificada: `8e5b57dcb881`. Se construyó con el compilador integrado y
  copia temporal del Dockerfile sin directiva `syntax`, igual que la recuperación
  previa; el Dockerfile del repositorio no cambió. Imagen de vuelta: `718decad308b`.
- Revisión visual automática bloqueada: `computer-use` no pudo conectar su pipe
  nativo de Windows. Las pantallas sí se renderizaron y verificaron con fixtures.
- **Instalado:** respaldo nuevo cifrado con DPAPI, restaurado en MySQL temporal
  con comprobación de todas las tablas; el contenedor temporal fue eliminado.
  Se detuvo el backend durante la actualización. El plan de migración contenía
  únicamente `usuarios.0010_eventosocio` (crear `EventoSocio`), aplicada correctamente.
  Backend recreado con imagen `8e5b57dcb881`; `check` sin problemas y
  `migrate --check` sin migraciones pendientes. MySQL y Redis saludables.
- Admin y búsqueda responden HTTP 200 final después de redirigir al login sin
  sesión. No se hicieron cobros, altas ni cambios de socios como comprobaciones
  en la base del usuario. No se ejecutó `setup_roles`; no se eliminaron volúmenes.
- Guía, plan y enlaces locales actualizados; `git diff --check` sin errores.
  Cambios todavía locales y sin commit/publicación. Hito 1 disponible desde
  **Gestión diaria → Buscar socio**. El historial antiguo conserva las limitaciones
  documentadas; no promete reconstruir sucesos sin vínculo verificable.
- Próximo alcance pendiente, todavía no iniciado: completar hitos 2–3 (edición de
  aplicaciones, pantalla para saldo existente y motivos/filtros del panel). P09–P12
  siguen pendientes. La revisión visual automática queda sin completar por el
  componente de control de Windows no disponible; las pruebas de renderizado,
  permisos y paginación sí pasaron en SQLite y MySQL.

## Acceso visible a Gestión diaria — 2026-10-09

- El usuario no encontraba el acceso en la portada del administrador. Se agregó
  una tarjeta antes de los módulos con el botón **Abrir Gestión diaria** en
  `templates/admin/index.html`; se conserva también el enlace de la barra.
- La tarjeta usa los mismos permisos de acceso del panel. No se cambiaron roles,
  datos de socios, reglas financieras ni modelos; no requiere migraciones.
- Pasan 13 pruebas dirigidas de Gestión y Personas con SQLite sintético, incluidas
  tres nuevas que cubren los permisos admitidos, la ausencia de acceso sin ellos
  y la posición de la tarjeta para administradores. Las tres nuevas también pasan
  dentro de la imagen aislada, sin red. No se repitieron suites frontend ni MySQL
  porque el cambio afecta una plantilla del administrador.
- Se reconstruyó y recreó únicamente el backend de desarrollo; imagen activa
  `718decad308b`. Compose falló dos veces al iniciar el frontend externo del
  compilador (`frontend grpc server closed unexpectedly`). La construcción se
  completó con el compilador integrado usando una copia temporal del Dockerfile
  en `.local/gestion-admin.Dockerfile`, omitiendo solo su directiva `syntax`.
  El Dockerfile versionado no cambió; se conservaron los volúmenes y servicios.
- Verificación final: login HTTP 200; en la sesión del navegador integrado se
  confirmó la tarjeta visible en `/admin/` y se pulsó **Abrir Gestión diaria**,
  que abrió correctamente el panel. La primera navegación agotó la espera del
  control del navegador, pero la pestaña había navegado; la inspección posterior
  y el clic del botón sí se completaron.
- Se actualizó la guía de acceso en [GESTION.md](GESTION.md). Enlaces locales y
  `git diff --check` comprobados. Cambios locales sin commit ni publicación;
  conservar las modificaciones previas del árbol de trabajo. Próximo paso del
  usuario: entrar al administrador y usar la tarjeta; no queda activación pendiente.

## Incidente en Personas — cierre 2026-10-09

- El usuario informó un fallo en `/admin/usuarios/personas/`. Al retomar,
  Docker Desktop estaba detenido y la pestaña mostraba conexión rechazada.
- Se reprodujo con datos sintéticos un fallo adicional del listado:
  `estado_habilitacion_colorido` llamaba a `mark_safe` sin importar esa función.
  La suite anterior no cubría el renderizado de este listado con personas.
- Se eliminó la inyección duplicada de CSS dentro de cada fila; el estado conserva
  su color mediante `format_html` y los estilos de los formularios siguen en
  `custom_admin.css`, ya declarado en `PersonasAdmin.Media`.
- Se agregaron dos pruebas en `apps/usuarios/test_admin_personas.py`: listado con
  los cuatro estados y ficha con estilos/navegación. La primera reprodujo el
  NameError antes del cambio. Tras corregirlo pasan las 78 pruebas de Usuarios y
  Gestión con SQLite sintético; no cambian modelos, permisos ni reglas de cobro.
- Se confirmó el mismo NameError en los registros del backend anterior. Docker
  se recuperó tras detener únicamente `docker-desktop` y volver a iniciar Docker
  Desktop; no se detuvo OpenClawGateway ni se eliminaron volúmenes.
- **Instalado:** backend reconstruido y recreado con imagen `ae13712635ad`.
  Las dos pruebas nuevas también pasan dentro de esa imagen, sin red y con datos
  sintéticos. Se iniciaron los cuatro servicios existentes de desarrollo. No se
  aplicaron migraciones ni se modificaron datos de socios por esta corrección.
- El 9 de octubre MySQL y Redis figuran saludables. El login responde HTTP 200
  desde el contenedor y Windows. Personas y Gestión redirigen correctamente al
  login con respuesta final 200, y `custom_admin.css` también responde 200.
  La portada dejó de responder tras la reanudación; se reinició únicamente el
  frontend y se confirmó HTTP 200 en el puerto 5173.
- **Límite de verificación:** la herramienta del navegador integrado agotó la
  espera; no se verificó visualmente el listado con la sesión real. El listado
  con los cuatro estados y la ficha se comprobaron en las pruebas sintéticas.
  Próximo paso del usuario: recargar Personas e ingresar si se solicita.
- `git diff --check` sin errores; no se repitieron suites completas ni MySQL
  porque el cambio afecta el renderizado de una columna. Los cambios siguen
  locales, sin commit ni publicación. Conservar las modificaciones previas del
  árbol de trabajo; no publicar cambios ajenos.

## Activación local de Gestión — 2026-10-07

- El usuario informó que no veía Gestión al iniciar `socios-amandaye-devsecure`.
  Se confirmó que el backend ejecutaba una imagen sin `apps/gestion` ni la migración
  `cobranzas.0009`; iniciar un contenedor no reconstruye su imagen.
- Se corrigió `requirements.txt` mediante pip-compile: faltaba
  `charset-normalizer` (dependencia de ReportLab) y los hashes de Pillow para Linux.
  Se conservaron todas las versiones previamente fijadas. La imagen nueva
  `socios-amandaye-devsecure-backend`, identificador `a5e5cf63294d`, se construyó
  correctamente y pasó 10 pruebas de Gestión/cobros/PDF en SQLite sintético dentro
  de un contenedor sin red.
- El usuario autorizó explícitamente respaldar la base local, verificar su
  restauración y activar Gestión. El respaldo quedó cifrado con DPAPI de Windows
  bajo `.local/gestion-dev-activation/`, excluido de Git y del build. No imprimir
  ni versionar sus datos; requiere la misma cuenta de Windows para descifrarlo.
- Docker Desktop no estaba operativo al retomar; se recuperó iniciando su
  aplicación y los contenedores existentes de desarrollo, sin borrar volúmenes.
  El 7 de octubre se creó un respaldo nuevo, se restauró en MySQL 8.4 temporal sin
  red y se verificaron todas sus tablas mediante CHECK TABLE. El script local
  `.local/gestion-dev-activation/backup_restore.py` terminó correctamente y
  `backup-status.json` registra `restore_verified: true`. El contenedor temporal
  fue eliminado; el respaldo cifrado se conserva.
- Se revisó el plan y se aplicó explícitamente `cobranzas.0009`: crea únicamente
  las tres tablas previstas. El backend se recreó con Gestión; `showmigrations`
  confirma `[X] 0009`, Django no informa problemas y `pip check` pasa.
- La comprobación HTTP detectó que las vistas anónimas redirigían a
  `/accounts/login/`, una ruta inexistente. Se corrigió `LOGIN_URL` a `/login/`.
  Las pantallas de Gestión reciben ahora el contexto del administrador para
  conservar su barra de navegación. Tres pruebas nuevas cubren las cinco rutas
  sin sesión, el regreso al panel tras autenticarse y la navegación de las
  cuatro pantallas. Las ocho pruebas de vistas de Gestión pasan localmente.
- **Completado:** imagen final `f9d96e69c0ef` construida y activa en el backend.
  La suite completa dentro de esa imagen, sin red y con SQLite sintético, ejecutó
  209 pruebas: 205 satisfactorias y 4 de MySQL omitidas. Los cambios de esta
  activación no modifican reglas financieras ni concurrencia; no se repitió la
  suite MySQL. Las rutas de Gestión en 8000 y 5173 llegan a `/login/?next=...`
  con respuesta final HTTP 200; la portada también responde 200. Backend y
  frontend están iniciados; MySQL y Redis figuran saludables.
- La autenticación y el regreso al panel se verificaron con una cuenta sintética.
  No se ingresó con cuentas reales ni se registraron cobros de prueba en la base
  de desarrollo. Enlaces y anclas locales de las guías comprobados; el diff no
  presenta errores de espacios, solo avisos de finales de línea de Windows.
- El acceso es `http://localhost:8000/admin/gestion/`, o **Acceder** en
  la portada y luego **Gestión diaria** en la barra del administrador. La guía
  [Gestión](GESTION.md) explica la diferencia entre iniciar y actualizar Docker.
- Conservar los cambios locales previos en AGENTS, CODEX, ECC, índice y configuración
  de Codex. Esta activación no autoriza publicar esos cambios ajenos.
- Próximo paso: probar el panel con la cuenta administrativa habitual. No quedan
  migraciones ni reconstrucciones pendientes para esta entrega local. Las
  correcciones de dependencias, acceso y documentación de esta activación están
  en el árbol de trabajo, todavía sin commit ni publicación.

## Trabajo actual — primera entrega de Gestión

El usuario autorizó implementar la primera entrega del
[plan de Gestión](../plans/gestion-secretaria-tesoreria.md) en esta rama. El panel
está disponible en `/admin/gestion/` y usa Django con los permisos existentes.

Se implementó:

- panel de pendientes para solicitudes, pagos con saldo, deudas vencidas y
  habilitaciones;
- búsqueda de socios y ficha unificada con datos familiares, cuenta corriente,
  embarcaciones e historial administrativo según permisos;
- flujo de cobro en dos pasos, con propuesta por vencimiento/emisión/número,
  revisión de saldo restante, idempotencia, control de versión y comprobante PDF;
- registros aditivos de operación, intención del saldo y comprobante inmutable;
- configuración de `CLUB_NAME`, `CLUB_CURRENCY` y `CLUB_RECEIPT_DETAILS`.

La moneda elegida para esta entrega es `UYU` por defecto y los datos del club del
recibo se pueden cambiar por entorno. No se operó sobre datos reales.

Verificaciones realizadas el 2026-10-02:

- `manage.py check --settings=amandaye_backend.settings_test`;
- `manage.py makemigrations --check --dry-run`;
- 10 pruebas dirigidas de Gestión y cobros, incluyendo revisión/confirmación de la
  pantalla y generación del PDF;
- suite backend completa: 206 pruebas, con 4 omitidas ya existentes;
- `git diff --check` (solo informó conversiones de finales de línea de Windows).

La siguiente etapa todavía no está implementada: emisión de cuotas con vista previa,
tarifas con vigencia, seguimiento de cobranzas, conciliación bancaria, portal del
socio y tareas periódicas de habilitación. El plan conserva sus contratos y criterios
para retomarlos sin mezclar datos ni permisos.

La entrega previa de ECC 2.2.2 pasó su diagnóstico de caché, validación de skill y
comprobaciones de documentación el 30 de septiembre. Ver detalles y límites en
[ECC_INTEGRATION.md](ECC_INTEGRATION.md); la continuidad mediante estos archivos no
depende de autorizar hooks del plugin.

## Decisiones que deben conservarse

- Las reglas financieras viven en servicios transaccionales y verifican permisos.
  Las correcciones preservan auditoría; los importes se calculan con `Decimal`.
- El desarrollo, la producción y las pruebas MySQL usan archivos Compose separados.
  Las bases existentes no son entornos desechables para validar cambios.
- La verificación se selecciona por alcance. Las instrucciones genéricas de ECC se
  adaptan a los runners y dependencias existentes.
- Las claves de estaciones se configuran en el backend cuando las aporte el responsable.
  El modo `api` permite desactivar la lectura de páginas públicas.

## Pendientes e ideas

**Integración pendiente:** disponer de credenciales propias de Ecowitt y Weather
Underground y validar observaciones reales de sus API. La disponibilidad de las
estaciones debe comprobarse en ese momento.

**Gestión:** primera entrega implementada en la rama indicada. Portal del socio,
conciliación, perchas, reservas, préstamos y reportes quedan como evolución posterior.
Antes del despliegue se debe ejecutar el procedimiento de migración del proyecto y
configurar los datos reales del club mediante variables de entorno.

## Cómo actualizar este registro

Al cerrar una implementación sustancial o preparar un traspaso, reemplazar el estado
obsoleto y anotar fecha, objetivo, rama o commit conocido, cambios completados,
verificaciones realizadas y limitaciones. Dejar el próximo paso concreto y distinguir
lo autorizado de lo propuesto. No escribir el hash del propio commit antes de que exista.
