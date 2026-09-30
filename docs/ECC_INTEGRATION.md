# ECC y trabajo asistido

[Índice](README.md) · [AGENTS.md](../AGENTS.md) · [Continuidad](CONTINUITY.md)

## Instalación de referencia

El 30 de septiembre de 2026 se instaló el plugin nativo **ECC 2.2.2** en el perfil
local de Codex de Danilo, con Codex CLI 0.153.4. El marketplace quedó fijado a la
revisión `c70874fae9eb0e5ad0365beb7e2955899fd1d30f` del
[repositorio oficial](https://github.com/affaan-m/ECC/tree/c70874fae9eb0e5ad0365beb7e2955899fd1d30f).
Codex informa `ecc@ecc` como instalado y habilitado. El diagnóstico de caché pasó
y las skills de ECC aparecen en el catálogo de la sesión.

El plugin se instala en el perfil del usuario, fuera de este repositorio. Clonar
Amandayé no instala ECC automáticamente. Las instrucciones, la skill específica
y el registro de continuidad sí están versionados con el proyecto.

## Incorporación al proyecto

| Pieza | Uso |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Mapa de trabajo, reglas de cobranzas, selección de pruebas y cuidado de los entornos existentes. |
| [amandaye-verification](../.agents/skills/amandaye-verification/SKILL.md) | Comprobar cambios con Django, Vue y MySQL desechable, según el alcance. |
| [CONTINUITY.md](CONTINUITY.md) | Conservar decisiones, evidencias fechadas, limitaciones y próximo paso entre sesiones. |

La instalación nativa incluye el catálogo de ECC. Para este proyecto, la selección
inicial de referencias es:

- `django-patterns`: diseño de modelos, servicios, vistas y consultas.
- `django-security`: permisos, formularios y configuración de Django.
- `database-migrations`: planificación de cambios de esquema y recuperación.
- `verification-loop`: estructura de verificación; ejecutar los comandos concretos
  de `amandaye-verification` y de la guía de desarrollo.

Las instrucciones específicas de Amandayé se mantienen aquí, sin modificar el caché
del plugin. Cargar una referencia cuando aporte al cambio solicitado. Las herramientas
genéricas de ECC, como pytest o comandos de lint, no sustituyen a los runners del
proyecto ni justifican incorporar dependencias por sí solas.

La skill local se descubre desde `.agents/skills/` y admite selección automática.
También puede invocarse explícitamente:

```text
Usá $amandaye-verification para comprobar los cambios de cobranzas.
```

Las skills nuevas estarán disponibles en el próximo turno; si la interfaz conserva
un catálogo anterior, iniciar una sesión nueva o reiniciar Codex. Ver la
[documentación de skills](https://learn.chatgpt.com/docs/build-skills).

## Continuidad entre sesiones

Al retomar trabajo, el agente lee el registro y contrasta rama, commits y cambios
locales. Al cerrar una implementación sustancial o preparar un traspaso, actualiza
los resultados y el próximo paso. El archivo conserva contexto curado; no es una
copia automática del chat ni almacena información personal de socios.

El hook de inicio de sesión incluido en ECC tiene su propio mecanismo de confianza
en Codex. Instalar el plugin no equivale a autorizar ese hook. Esta integración usa
`AGENTS.md` y el registro versionado para la continuidad, sin depender de su ejecución.
La confianza del hook se revisa desde `/hooks` en una sesión nueva si se decide usarlo,
según la [guía nativa de ECC](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/.codex-plugin/README.md).

El manifiesto también incluye el conector `chrome-devtools`, con versión fijada por
ECC. Su presencia no sustituye la elección de la herramienta de navegador disponible
para una tarea ni implica que se haya abierto o conectado a una sesión de Chrome.

## Reproducir la instalación

Requiere una versión de Codex CLI que disponga de `plugin add` y Git. Desde una
terminal del usuario que ejecuta Codex:

```powershell
codex plugin marketplace add affaan-m/ECC --ref c70874fae9eb0e5ad0365beb7e2955899fd1d30f --json
codex plugin add ecc@ecc --json
codex plugin list --marketplace ecc --json
```

Usar la instalación nativa como único canal de ECC para ese perfil. El procedimiento
antiguo `sync-ecc-to-codex.sh` copia otra capa de configuración y no forma parte de
esta instalación. Para actualizar, revisar una nueva revisión de ECC y cambiar
explícitamente la referencia del marketplace; la referencia fijada no sigue `main`.

La comprobación de caché incluida en ECC se ejecuta con Node, indicando la ruta
`installedPath` que devuelve la instalación:

```powershell
$eccPluginPath = 'C:/Users/Danilo/.codex/plugins/cache/ecc/ecc/2.2.2'
node "$eccPluginPath/scripts/codex/check-plugin-cache.js" --plugin-dir "$eccPluginPath"
```

En otro equipo, sustituir la ruta por su `installedPath`. Esta comprobación verifica
referencias a archivos; una prueba funcional de una skill requiere una tarea real.

Para retirar el plugin de ese perfil, cuando se solicite expresamente:

```powershell
codex plugin remove ecc@ecc
```

Las instrucciones de Amandayé y la skill local siguen funcionando sin ECC. El plugin
se utiliza durante el desarrollo; no es una dependencia del backend, frontend o
contenedores del club.

## Fuentes

- [ECC: manifiesto instalado](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/.codex-plugin/plugin.json).
- [ECC: licencia MIT](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/LICENSE).
- [OpenAI: plugins y marketplaces](https://developers.openai.com/plugins/build/plugins).
- [OpenAI: creación y descubrimiento de skills](https://learn.chatgpt.com/docs/build-skills).
