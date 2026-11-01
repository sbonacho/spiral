## 1. Paquete y configuración

- [x] 1.1 Crear `pyproject.toml` (hatchling, `name = "spiral-cli"`, `[project.scripts] spiral`, dependencias) y la estructura `src/spiral/`. Verificación: `uv tool install --force .` instala y `spiral --version` muestra la versión.
- [x] 1.2 Implementar `config.py`: capas entorno > `.env` local > `~/.config/spiral/.env`, valores vacíos ignorados. Verificación: pruebas unitarias de los 4 escenarios de precedencia de `workspace-config`.
- [x] 1.3 Validar `PROCESSED_DIR`/`PUBLISHED_DIR` (relativas, sin `..`). Verificación: prueba unitaria que rechaza `../x` y `/tmp/x` y acepta `listos`.
- [x] 1.4 Cargar `PODCAST_*`/`SITE_URL` y comprobar los obligatorios al publicar en el sitio. Verificación: prueba que el error nombra `SITE_URL` cuando falta.
- [x] 1.5 Localizar intro/outro (local, luego `~/.config/spiral/`, ausentes omitidas) y excluirlas de los episodios. Verificación: pruebas con directorios temporales y `HOME` simulado.

## 2. Ciclo de vida de los episodios

- [x] 2.1 Implementar `workspace.py`: estados pendiente/procesado/publicado desde las carpetas y marca `done.json`. Verificación: pruebas con árboles de ficheros de ejemplo, incluida una carpeta incompleta.
- [x] 2.2 Portar el pipeline (concat, loudnorm, mp3, transcripción, clips) a `pipeline.py` construyendo en `processed/.<nombre>.tmp/`, renombrando y moviendo el original solo al final. Verificación: prueba de integración con un `.mov` de unos segundos y transcripción simulada; un fallo forzado en el resumen deja `a.mov` en la raíz.
- [x] 2.3 Detectar conflictos (`a.mov` y `processed/a/`) sin sobrescribir. Verificación: prueba que no modifica nada y explica el conflicto.
- [x] 2.4 Implementar el reprocesado desde `processed/<nombre>/<nombre>.mov` con confirmación y conservando `published/<nombre>/`. Verificación: prueba que `published/` no cambia y se regeneran los ficheros.
- [x] 2.5 Eliminar toda referencia a archivar y a `ARCHIVE_DIR`. Verificación: `spiral --help` no lista `archive` y `grep -ri archive_dir` no devuelve nada en el código.
- [x] 2.6 Reescribir el informe HTML con los tres estados, columnas por destino configurado, icono de publicado y escape de títulos, escrito en `published/report.html`. Verificación: prueba con un título `<script>` y un episodio de cada estado.

## 3. Proveedores de resumen

- [x] 3.1 Definir la interfaz común y la validación del esquema; no escribir `contenido.json` si es inválido. Verificación: prueba con una respuesta sin `clips`.
- [x] 3.2 Implementar `claude` (CLI), `gemini` (API) y `ollama` (API local) con errores claros de configuración. Verificación: pruebas con respuestas simuladas por proveedor y mensaje de variable ausente.
- [x] 3.3 Guardar la transcripción antes de resumir y usar `PODCAST_LANGUAGE` en transcripción y prompt. Verificación: un reintento tras fallo no vuelve a transcribir; con `en` el prompt pide inglés.
- [x] 3.4 Mostrar el proveedor activo antes de enviar la transcripción. Verificación: la salida contiene el nombre del proveedor.

## 4. Destinos y publicación

- [x] 4.1 Implementar el descubrimiento de cuentas (`<RED>_ACCOUNTS`, `<RED>_<CUENTA>_<CAMPO>`) y el cálculo de campos que faltan. Verificación: pruebas de cuenta completa, incompleta y añadida solo en local.
- [x] 4.2 Definir la interfaz de destino y portar `site`, `youtube`, `bluesky`, `mastodon`, `instagram` y `manual` (x, tiktok). Verificación: cada módulo tiene prueba de `preview` y de `configured`; `bluesky` y `mastodon` con servidor HTTP simulado.
- [x] 4.3 Implementar el flujo de publicación: idempotencia por `state.json`, fallo aislado por destino, código de salida distinto de cero si alguno falla. Verificación: pruebas de «repetir» y de «publicación parcial».
- [x] 4.4 Implementar la simulación sin red ni cambios en `published/`. Verificación: prueba que no hay peticiones y `published/` queda intacto.
- [x] 4.5 Escribir `publish.log` filtrando secretos. Verificación: prueba que el valor de un token no aparece en el log.
- [x] 4.6 Guardar tokens en `~/.config/spiral/tokens/<red>-<cuenta>.json` con permisos 600. Verificación: prueba que comprueba la ruta y `stat` 0600, y que no hay tokens en el directorio de trabajo.
- [x] 4.7 Cortar la publicación de destinos dependientes si `site` falla en la misma ejecución, y gestionar `site/` sin repositorio git. Verificación: pruebas de ambos escenarios de `publishing`.

## 5. CLI interactivo

- [x] 5.1 Crear `cli.py` con subcomandos y argumentos explícitos (`process <n>`, `publish <n> --to … --dry-run --yes`, `list`, `view`, `--version`) y error de uso (código 2) sin TTY. Verificación: pruebas ejecutando el comando sin TTY con argumentos completos e incompletos.
- [x] 5.2 Panel inicial de redes con `rich` (símbolos además de color, `NO_COLOR`) y menú con flechas. Verificación: captura de la salida con `NO_COLOR=1` y revisión visual en un terminal real.
- [x] 5.3 Selector de episodios con búsqueda al escribir. Verificación: prueba de humo en pseudo-terminal que filtra y elige.
- [x] 5.4 Selector múltiple de destinos con espacio y opciones deshabilitadas con motivo. Verificación: prueba de humo en pseudo-terminal que marca dos destinos y no puede marcar uno no configurado.
- [x] 5.5 Indicadores de progreso en transcripción, codificación y subidas; Ctrl-C cancela sin modificar ficheros. Verificación: ejecución manual en un terminal real.

## 6. Instalación

- [x] 6.1 Escribir `install.sh` (macOS arm64, `uv`, `uv tool install --force`, PATH sin duplicar, `~/.config/spiral/.env` sin sobrescribir, aviso de `ffmpeg`, sin `sudo`). Verificación: ejecutarlo con `HOME` temporal dos veces, comprobar una sola línea de PATH y que un `.env` previo no cambia.
- [x] 6.2 Plantilla `.env` comentada para el global y `.env.example` para el local con todas las variables y el esquema de cuentas. Verificación: un `.env.example` copiado sin tocar no configura ninguna red.
- [x] 6.3 Probar la instalación de extremo a extremo desde GitHub en una cuenta de usuario limpia. Verificación: la línea del README deja `spiral --version` funcionando en una terminal nueva.

## 7. Documentación y repositorio público

- [x] 7.1 Escribir `README.md` en inglés con la instalación de una línea como primera sección, configuración en capas, ciclo de vida, alta de cada red y límites conocidos. Verificación: la primera sección tras el título contiene el comando.
- [x] 7.2 Traducir a `README.es.md` y enlazar ambos. Verificación: los enlaces cruzados funcionan.
- [x] 7.3 Añadir `LICENSE` (MIT) y actualizar `.gitignore` (`.env`, `processed/`, `published/`, `site/`, `informe.html`, `__pycache__/`). Verificación: `git status` no muestra ficheros de datos ni `.env`.
- [x] 7.4 Retirar del repositorio `site/`, `engine.py`, `publish.py`, `social.py`, `library.py`, `install.sh` antiguo y el `spiral` antiguo; mover `DISENO.md` a `docs/`. Verificación: `git ls-files` muestra solo el paquete, docs, README, LICENSE y OpenSpec.
- [x] 7.5 Revisión de datos personales y credenciales (historial y árbol). Resultado: sin claves ni tokens; el `.env` local nunca se commiteó; los commits `099fd86` y `4a45c9e` llevan el correo corporativo como autor/committer, por eso el historial se descarta.
- [x] 7.6 Crear el repositorio nuevo `sbonacho/spiral` con un único commit inicial hecho con `sbonacho@gmail.com`, sin reutilizar el historial anterior. Verificación: `git log --format='%an <%ae>'` muestra un solo commit con ese correo y `git remote -v` apunta a `sbonacho/spiral`.
- [x] 7.7 Borrar el repositorio antiguo `sbonacho/callespiral` en GitHub (acción manual del autor, que también elimina el historial publicado). Verificación: `https://github.com/sbonacho/callespiral` devuelve 404.
- [x] 7.8 Versionar `.claude/` y `openspec/`. Verificación: `git ls-files` los incluye y no contiene rutas personales.

## 8. Cierre

- [x] 8.1 Ejecutar todas las pruebas y `openspec validate workspace-cli --strict`. Verificación: ambas terminan sin errores.
- [x] 8.2 Recorrido manual completo en un directorio con un `.mov` real: `list` → `process` → `publish --dry-run` → `view`. Verificación: los ficheros aparecen en `processed/` y `published/` y el informe es correcto.

## 9. Idioma de la interfaz

- [x] 9.1 Crear `i18n.py` (español como origen, catálogo en inglés, idioma fijado desde `PODCAST_LANGUAGE`) y envolver todos los mensajes visibles. Verificación: prueba que cada mensaje de `_()` del código tiene traducción y los mismos marcadores `{}`.
- [x] 9.2 Traducir ayuda de argparse, panel, tabla, selectores, resultados, logs del procesado y de los destinos, errores e informe HTML (`lang`). Verificación: pruebas con `es`, `en`, `fr` y `es-MX` sobre `--help`, `list`, un error y el informe.
- [x] 9.3 Documentar la variable en los README y `.env.example`. Verificación: ambos README explican que `PODCAST_LANGUAGE` fija también el idioma de la interfaz.
- [x] 9.4 El instalador retira el alias antiguo de versiones previas (bloque `# >>> spiral >>>`) para que no tape el comando nuevo. Verificación: con un `HOME` temporal que contiene el bloque y otras líneas, tras instalar queda solo lo ajeno al bloque.
