## 1. Paquete y configuración

- [ ] 1.1 Crear `pyproject.toml` (hatchling, `name = "spiral-cli"`, `[project.scripts] spiral`, dependencias) y la estructura `src/spiral/`. Verificación: `uv tool install --force .` instala y `spiral --version` muestra la versión.
- [ ] 1.2 Implementar `config.py`: capas entorno > `.env` local > `~/.config/spiral/.env`, valores vacíos ignorados. Verificación: pruebas unitarias de los 4 escenarios de precedencia de `workspace-config`.
- [ ] 1.3 Validar `PROCESSED_DIR`/`PUBLISHED_DIR` (relativas, sin `..`). Verificación: prueba unitaria que rechaza `../x` y `/tmp/x` y acepta `listos`.
- [ ] 1.4 Cargar `PODCAST_*`/`SITE_URL` y comprobar los obligatorios al publicar en el sitio. Verificación: prueba que el error nombra `SITE_URL` cuando falta.
- [ ] 1.5 Localizar intro/outro (local, luego `~/.config/spiral/`, ausentes omitidas) y excluirlas de los episodios. Verificación: pruebas con directorios temporales y `HOME` simulado.

## 2. Ciclo de vida de los episodios

- [ ] 2.1 Implementar `workspace.py`: estados pendiente/procesado/publicado desde las carpetas y marca `done.json`. Verificación: pruebas con árboles de ficheros de ejemplo, incluida una carpeta incompleta.
- [ ] 2.2 Portar el pipeline (concat, loudnorm, mp3, transcripción, clips) a `pipeline.py` construyendo en `processed/.<nombre>.tmp/`, renombrando y moviendo el original solo al final. Verificación: prueba de integración con un `.mov` de unos segundos y transcripción simulada; un fallo forzado en el resumen deja `a.mov` en la raíz.
- [ ] 2.3 Detectar conflictos (`a.mov` y `processed/a/`) sin sobrescribir. Verificación: prueba que no modifica nada y explica el conflicto.
- [ ] 2.4 Implementar el reprocesado desde `processed/<nombre>/<nombre>.mov` con confirmación y conservando `published/<nombre>/`. Verificación: prueba que `published/` no cambia y se regeneran los ficheros.
- [ ] 2.5 Eliminar toda referencia a archivar y a `ARCHIVE_DIR`. Verificación: `spiral --help` no lista `archive` y `grep -ri archive_dir` no devuelve nada en el código.
- [ ] 2.6 Reescribir el informe HTML con los tres estados, columnas por destino configurado, icono de publicado y escape de títulos, escrito en `published/report.html`. Verificación: prueba con un título `<script>` y un episodio de cada estado.

## 3. Proveedores de resumen

- [ ] 3.1 Definir la interfaz común y la validación del esquema; no escribir `contenido.json` si es inválido. Verificación: prueba con una respuesta sin `clips`.
- [ ] 3.2 Implementar `claude` (CLI), `gemini` (API) y `ollama` (API local) con errores claros de configuración. Verificación: pruebas con respuestas simuladas por proveedor y mensaje de variable ausente.
- [ ] 3.3 Guardar la transcripción antes de resumir y usar `PODCAST_LANGUAGE` en transcripción y prompt. Verificación: un reintento tras fallo no vuelve a transcribir; con `en` el prompt pide inglés.
- [ ] 3.4 Mostrar el proveedor activo antes de enviar la transcripción. Verificación: la salida contiene el nombre del proveedor.

## 4. Destinos y publicación

- [ ] 4.1 Implementar el descubrimiento de cuentas (`<RED>_ACCOUNTS`, `<RED>_<CUENTA>_<CAMPO>`) y el cálculo de campos que faltan. Verificación: pruebas de cuenta completa, incompleta y añadida solo en local.
- [ ] 4.2 Definir la interfaz de destino y portar `site`, `youtube`, `bluesky`, `mastodon`, `instagram` y `manual` (x, tiktok). Verificación: cada módulo tiene prueba de `preview` y de `configured`; `bluesky` y `mastodon` con servidor HTTP simulado.
- [ ] 4.3 Implementar el flujo de publicación: idempotencia por `state.json`, fallo aislado por destino, código de salida distinto de cero si alguno falla. Verificación: pruebas de «repetir» y de «publicación parcial».
- [ ] 4.4 Implementar la simulación sin red ni cambios en `published/`. Verificación: prueba que no hay peticiones y `published/` queda intacto.
- [ ] 4.5 Escribir `publish.log` filtrando secretos. Verificación: prueba que el valor de un token no aparece en el log.
- [ ] 4.6 Guardar tokens en `~/.config/spiral/tokens/<red>-<cuenta>.json` con permisos 600. Verificación: prueba que comprueba la ruta y `stat` 0600, y que no hay tokens en el directorio de trabajo.
- [ ] 4.7 Cortar la publicación de destinos dependientes si `site` falla en la misma ejecución, y gestionar `site/` sin repositorio git. Verificación: pruebas de ambos escenarios de `publishing`.

## 5. CLI interactivo

- [ ] 5.1 Crear `cli.py` con subcomandos y argumentos explícitos (`process <n>`, `publish <n> --to … --dry-run --yes`, `list`, `view`, `--version`) y error de uso (código 2) sin TTY. Verificación: pruebas ejecutando el comando sin TTY con argumentos completos e incompletos.
- [ ] 5.2 Panel inicial de redes con `rich` (símbolos además de color, `NO_COLOR`) y menú con flechas. Verificación: captura de la salida con `NO_COLOR=1` y revisión visual en un terminal real.
- [ ] 5.3 Selector de episodios con búsqueda al escribir. Verificación: prueba de humo en pseudo-terminal que filtra y elige.
- [ ] 5.4 Selector múltiple de destinos con espacio y opciones deshabilitadas con motivo. Verificación: prueba de humo en pseudo-terminal que marca dos destinos y no puede marcar uno no configurado.
- [ ] 5.5 Indicadores de progreso en transcripción, codificación y subidas; Ctrl-C cancela sin modificar ficheros. Verificación: ejecución manual en un terminal real.

## 6. Instalación

- [ ] 6.1 Escribir `install.sh` (macOS arm64, `uv`, `uv tool install --force`, PATH sin duplicar, `~/.config/spiral/.env` sin sobrescribir, aviso de `ffmpeg`, sin `sudo`). Verificación: ejecutarlo con `HOME` temporal dos veces, comprobar una sola línea de PATH y que un `.env` previo no cambia.
- [ ] 6.2 Plantilla `.env` comentada para el global y `.env.example` para el local con todas las variables y el esquema de cuentas. Verificación: un `.env.example` copiado sin tocar no configura ninguna red.
- [ ] 6.3 Probar la instalación de extremo a extremo desde GitHub en una cuenta de usuario limpia. Verificación: la línea del README deja `spiral --version` funcionando en una terminal nueva.

## 7. Documentación y repositorio público

- [ ] 7.1 Escribir `README.md` en inglés con la instalación de una línea como primera sección, configuración en capas, ciclo de vida, alta de cada red y límites conocidos. Verificación: la primera sección tras el título contiene el comando.
- [ ] 7.2 Traducir a `README.es.md` y enlazar ambos. Verificación: los enlaces cruzados funcionan.
- [ ] 7.3 Añadir `LICENSE` (MIT) y actualizar `.gitignore` (`.env`, `processed/`, `published/`, `site/`, `informe.html`, `__pycache__/`). Verificación: `git status` no muestra ficheros de datos ni `.env`.
- [ ] 7.4 Retirar del repositorio `site/`, `engine.py`, `publish.py`, `social.py`, `library.py`, `install.sh` antiguo y el `spiral` antiguo; mover `DISENO.md` a `docs/`. Verificación: `git ls-files` muestra solo el paquete, docs, README, LICENSE y OpenSpec.
- [x] 7.5 Revisión de datos personales y credenciales (historial y árbol). Resultado: sin claves ni tokens; el `.env` local nunca se commiteó; los commits `099fd86` y `4a45c9e` llevan el correo corporativo como autor/committer, por eso el historial se descarta.
- [ ] 7.6 Crear el repositorio nuevo `sbonacho/spiral` con un único commit inicial hecho con `sbonacho@gmail.com`, sin reutilizar el historial anterior. Verificación: `git log --format='%an <%ae>'` muestra un solo commit con ese correo y `git remote -v` apunta a `sbonacho/spiral`.
- [ ] 7.7 Borrar el repositorio antiguo `sbonacho/callespiral` en GitHub (acción manual del autor, que también elimina el historial publicado). Verificación: `https://github.com/sbonacho/callespiral` devuelve 404.
- [ ] 7.8 Versionar `.claude/` y `openspec/`. Verificación: `git ls-files` los incluye y no contiene rutas personales.

## 8. Cierre

- [ ] 8.1 Ejecutar todas las pruebas y `openspec validate workspace-cli --strict`. Verificación: ambas terminan sin errores.
- [ ] 8.2 Recorrido manual completo en un directorio con un `.mov` real: `list` → `process` → `publish --dry-run` → `view`. Verificación: los ficheros aparecen en `processed/` y `published/` y el informe es correcto.
