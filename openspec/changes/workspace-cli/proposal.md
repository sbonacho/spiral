## Why

Hoy `spiral` está atado a una instalación concreta: carpetas fijas en `.env`, un `site/` dentro del proyecto, una sola cuenta por red y un instalador que solo crea un alias. Para publicarlo como herramienta abierta, tiene que instalarse con una línea, trabajar sobre cualquier directorio de grabaciones y permitir varias redes y varias cuentas por programa.

## What Changes

- El comando `spiral` trabaja siempre sobre el **directorio actual**: sus `.mov`, su `.env` local y sus carpetas de resultados. Desaparece `SOURCE_DIR`.
- Configuración en capas: `.env` global (`~/.config/spiral/.env`) y `.env` local del directorio; lo local gana variable a variable.
- Nuevo ciclo de vida de cada episodio, deducido de las carpetas: **pendiente** (`.mov` en el directorio), **procesado** (`processed/<nombre>/`, con el original movido dentro) y **publicado** (`published/<nombre>/`, con estado, logs e intermedios).
- Un episodio procesado se publica en N destinos; cada red admite N cuentas, todo configurado en el `.env`.
- Los metadatos del podcast (hoy `site/podcast.json`) pasan al `.env`; el sitio (blog, RSS, clips) vive en `site/` dentro del directorio de trabajo.
- El resumen admite tres proveedores: Claude Code, Gemini y Ollama.
- CLI interactivo moderno (flechas, espacio para marcar, búsqueda al escribir, colores) con `questionary` y `rich`.
- Instalación con una línea con `uv tool` desde GitHub (paquete `spiral-cli`, repositorio nuevo `sbonacho/spiral`); `spiral` queda en el PATH y el rc de la shell se ajusta solo si falta.
- README público en inglés (con `README.es.md`) y licencia MIT.
- **BREAKING**: se elimina el comando y la opción de **archivar** (`ARCHIVE_DIR`).
- **BREAKING**: `SOURCE_DIR`, `out/<episodio>/` y `site/podcast.json` dejan de existir; el layout nuevo no migra datos antiguos (no hay episodios reales procesados todavía).
- **BREAKING**: los tokens pasan de `~/.config/callespiral/` a `~/.config/spiral/tokens/`.

## Capabilities

### New Capabilities

- `workspace-config`: directorio de trabajo = directorio actual, capas de `.env`, carpetas configurables, metadatos del podcast, intro y outro.
- `episode-lifecycle`: estados pendiente/procesado/publicado, listado, procesado y reprocesado, informe HTML.
- `publishing`: destinos (red + cuenta), selección, estado por destino, simulación, logs, tokens, destinos manuales y sitio.
- `summary-providers`: proveedores de resumen y de transcripción en el idioma del programa.
- `interactive-cli`: selectores con flechas y espacio, panel de redes, uso no interactivo.
- `installation`: instalador de una línea, actualización, requisitos y documentación pública.

### Modified Capabilities

(ninguna: el proyecto aún no tiene specs en `openspec/specs/`)

## Impact

- **Código**: se reorganiza `engine.py`, `publish.py`, `social.py`, `library.py` y `spiral` en un paquete Python instalable (`pyproject.toml`); se reutiliza la lógica existente de ffmpeg, Whisper, clips, RSS y APIs.
- **Dependencias**: `questionary`, `rich`, y las ya usadas (`mlx-whisper`, `internetarchive`, `atproto`, `Mastodon.py`, librerías de Google). Solo macOS con Apple Silicon (por `mlx-whisper`).
- **Repositorio**: se añaden `pyproject.toml`, `LICENSE` (MIT), `README.md` y `README.es.md`; `site/` deja de formar parte del repositorio (pasa a ser dato del usuario) y `.claude/` (comandos y skills de OpenSpec) se versiona; `DISENO.md` pasa a `docs/`.
- **Usuarios actuales**: solo el autor; no hay migración.
