## Context

Estado actual (ver `proposal.md`, «Why»): scripts sueltos (`spiral` menú, `engine.py`, `publish.py`, `social.py`, `library.py`) que viven en una carpeta del proyecto, leen `.env` de ahí, usan `SOURCE_DIR`/`ARCHIVE_DIR` y dejan los resultados en `SOURCE_DIR/out/<episodio>/`. El sitio (`site/`) forma parte del repositorio. Restricciones: solo macOS Apple Silicon (Whisper con MLX), un solo mantenedor, cero coste de servicios, repositorio público.

## Goals / Non-Goals

**Goals**
- Un paquete Python instalable con `uv tool`, con un único punto de entrada `spiral`.
- Estado derivado del sistema de ficheros del directorio actual, sin base de datos.
- Destinos (red + cuenta) extensibles añadiendo un módulo, sin tocar el flujo.
- Lógica separada de la interfaz para poder probarla sin terminal.

**Non-Goals**
- Windows y Linux; Mac Intel.
- Publicar en PyPI.
- Migrar datos del layout anterior.
- API de pago de X ni publicación automática en TikTok.
- Varios podcasts en un mismo directorio (un directorio = un podcast).

## Decisions

### D1. Paquete `src/spiral/` con una capa de lógica y otra de interfaz
```
src/spiral/
  cli.py            argparse + panel + selectores (questionary/rich); sin lógica de negocio
  config.py         capas de .env, validación de rutas, PODCAST_*, cuentas
  workspace.py      descubrimiento de episodios y estados (processed/ y published/)
  pipeline.py       concat, loudnorm, mp3, transcripción, clips (hoy engine.py)
  summary/          claude.py, gemini.py, ollama.py + validación común
  destinations/     site.py, youtube.py, bluesky.py, mastodon.py, instagram.py, manual.py
  report.py         informe HTML (hoy library.py)
```
**Por qué**: hoy la lógica está mezclada con `print`/`input`. Separar permite probar estado, configuración y destinos sin TTY. **Alternativa descartada**: mantener scripts sueltos y `install.sh` con alias; no cumple «software Python global estándar».

### D2. Empaquetado y distribución
`pyproject.toml` (backend `hatchling`) con `[project.scripts] spiral = "spiral.cli:main"`; todas las dependencias en `dependencies`. El proyecto se llama `spiral-cli` (el comando sigue siendo `spiral`). Instalación: `uv tool install git+https://github.com/sbonacho/spiral`. El instalador de una línea (`install.sh`, servido desde `raw.githubusercontent.com`) hace: comprobar macOS arm64 → instalar `uv` con su instalador oficial si falta → `uv tool install --force` → `uv tool update-shell` → crear `~/.config/spiral/.env` si no existe → avisar de `ffmpeg`. **Alternativas**: `pipx` (obliga a instalar pipx primero), PyPI (hay que reservar nombre y publicar versiones), alias en el rc (el binario ya está en el PATH; duplicaría el comando). El usuario eligió `uv tool` y PATH en lugar de alias.

### D3. Configuración en capas
`config.py` construye un diccionario inmutable: `os.environ` > `.env` local > `~/.config/spiral/.env`. Un valor vacío cuenta como no definido. Las cuentas se descubren por `<RED>_ACCOUNTS` y `<RED>_<CUENTA>_<CAMPO>`. **Por qué**: cumple «lo local sobrescribe a lo global variable a variable». Se asume (y debe confirmarse) que las variables de entorno reales tienen la máxima precedencia, como es habitual. **Alternativas**: `spiral.toml` o un directorio `.env/` (descartadas por el usuario).

### D4. El estado son carpetas, con marca de finalización
`processed/<nombre>/` se considera completa solo si contiene `done.json` (versión de esquema, fecha, proveedor, lista de ficheros), que se escribe lo último. El procesado construye en `processed/.<nombre>.tmp/`, lo renombra a `processed/<nombre>/` al terminar y entonces mueve el `.mov` original dentro. `published/<nombre>/` guarda `state.json` (por destino: hecho, fecha, id/URL, modo), `publish.log` y los textos generados. **Por qué**: el heurístico actual (¿existen estos 3 ficheros?) no detecta procesados a medias. **Riesgo asumido**: si el proceso muere entre el renombrado y el movimiento del original, quedan `a.mov` en la raíz y `processed/a/` completa; el requisito de conflicto lo detecta y lo explica, sin pérdida de datos.

### D5. Destinos como registro de módulos
Cada módulo de `destinations/` declara: `network`, campos obligatorios, `configured(account) -> list[missing]`, `preview(episode, account) -> str` y `publish(episode, account, ctx) -> Result`. El flujo de publicación itera sobre los destinos elegidos, aplica idempotencia (`state.json`), captura excepciones por destino, escribe el log (con un filtro que elimina secretos) y devuelve el resumen. `manual.py` implementa `x` y `tiktok`. **Por qué**: añadir una red nueva es añadir un fichero.

### D6. Tokens fuera del directorio de trabajo
`~/.config/spiral/tokens/<red>-<cuenta>.json`, permisos 600, creado con `os.open(..., 0o600)`. El resto de secretos viven en el `.env` (local o global); el `.env` local sigue estando junto a las grabaciones, así que `.gitignore` y la documentación lo deben avisar.

### D7. Interfaz con `questionary` y `rich`
- `questionary.select` (flechas), `questionary.checkbox` con `Choice(disabled=motivo)` (espacio, opciones no marcables) y `questionary.autocomplete`/`select` con `use_search_filter=True` para el selector de episodios.
- `rich` para panel de redes, tabla de `list`, spinners y barras de progreso; respeta `NO_COLOR`.
- Todo subcomando acepta argumentos explícitos (`--to`, `--dry-run`, `--yes`); sin TTY y con argumentos incompletos → error de uso (código 2). Esto permite pruebas automáticas sin pseudo-terminal en la mayoría de casos.

### D8. Un directorio = un podcast; el sitio en `site/`
Metadatos en `PODCAST_*` y `SITE_URL`, sitio en `$root/site/` (su propio repositorio git, opcional). Los clips para Instagram se copian a `site/media/` como hoy. `site/` se excluye del repositorio de la herramienta.

### D9. Proveedores de resumen
Interfaz común `summarize(transcript, language) -> dict` y validación única del esquema. `claude` ejecuta `claude -p`; `gemini` usa la API REST con `GEMINI_API_KEY`; `ollama` llama a `OLLAMA_URL/api/chat`. La transcripción se guarda antes de resumir para que un reintento no vuelva a transcribir.

### D10. Informe en `published/report.html`
Se escribe en la carpeta de publicados (ya gestionada por la herramienta) para no ensuciar el directorio de grabaciones, y se abre con `open`.

## Risks / Trade-offs

- **Instalación pesada** (`mlx-whisper` arrastra PyTorch, NumPy, SciPy; cientos de MB) → documentar el tamaño y el tiempo de la primera instalación; importar los módulos pesados de forma diferida para que `spiral --version` y el panel arranquen rápido.
- **`curl | sh`** → el script es corto, sin `sudo`, fijado a `main`; el README lo enlaza para que se lea antes de ejecutar.
- **Pruebas de selectores interactivos** → la lógica se prueba sin TTY; los selectores se verifican con una prueba de humo en pseudo-terminal y el aspecto visual lo revisa el usuario.
- **Secretos junto a las grabaciones** (`.env` local) → `.gitignore` por defecto, aviso en el README y permisos 600 en el instalador y en la plantilla.
- **APIs de terceros cambiantes** (cuota de YouTube, límites de Instagram, X de pago) → cada destino aislado; los límites se documentan como «verificar» en el README.
- **Sin migración** → aceptable porque no hay episodios reales procesados; se documenta como cambio incompatible.

## Migration Plan

1. Crear el paquete y mover la lógica existente módulo a módulo, con pruebas por capa.
2. Sustituir `install.sh` por el instalador nuevo y eliminar `engine.py`, `publish.py`, `social.py`, `library.py`, `menu`/`spiral` antiguos.
3. Retirar `site/` del repositorio y mover `DISENO.md` a `docs/`; `.claude/` y `openspec/` se versionan.
4. Reescribir README (en/es) y añadir `LICENSE`.
5. **Historial**: el repositorio público arranca de cero en `sbonacho/spiral` con un único commit inicial; no se reutiliza el historial de `callespiral`. **Rollback**: mientras no se borre, el repositorio antiguo conserva el layout actual.

## Open Questions

- ¿Se publica más adelante en PyPI con un nombre propio? No cambia los specs.
- ¿Conviene que `spiral view` pueda escribir el informe en una ruta indicada (`-o`)? Se puede añadir sin afectar a los requisitos.
