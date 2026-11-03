# spiral

Convierte las grabaciones de tu programa de radio en un podcast y en publicaciones para redes, desde la terminal: añade intro y outro, genera el mp3, transcribe, resume, corta clips verticales y publica en plataformas de podcast y redes sociales, con varias cuentas por red.

[English](README.md)

## Instalación

```bash
curl -LsSf https://raw.githubusercontent.com/sbonacho/spiral/main/install.sh | bash
```

Solo macOS con Apple Silicon (la transcripción se ejecuta en local con MLX). El script instala [uv](https://docs.astral.sh/uv/) si no lo tienes, instala `spiral` como herramienta global, se asegura de que la carpeta de herramientas esté en el `PATH` y crea `~/.config/spiral/.env` para tu configuración global. No usa `sudo` y nunca sobrescribe tu configuración (solo retira el bloque de alias `# >>> spiral >>>` que añadían las primeras versiones a `~/.zshrc`, `~/.bash_profile` o `~/.bashrc`, porque taparía el comando nuevo). Vuelve a ejecutarlo para actualizar; es [lo bastante corto para leerlo antes](install.sh). Para quitarlo: `uv tool uninstall spiral-cli`.

Necesitas también `ffmpeg` (`brew install ffmpeg`) y un proveedor de resúmenes (ver [Resúmenes](#resúmenes)).

> **Estado: beta.** El procesado, la gestión del estado y la interfaz tienen pruebas automáticas. Los destinos de red (YouTube, Bluesky, Mastodon, Instagram, Archive.org) solo se han probado con APIs simuladas: haz tu primera publicación con `--dry-run` y luego con un solo destino.

## Qué hace

Por cada `.mov` grabado con OBS (o cualquier otra herramienta):

1. Añade tu `intro.mov` y `outro.mov` si los tienes y normaliza el volumen.
2. Exporta un mp3.
3. Lo transcribe en local con Whisper (gratis y privado).
4. Escribe título, resúmenes, capítulos, un hilo para X, una entrada de blog y propuestas de clips con el proveedor de IA que elijas.
5. Corta clips verticales 9:16 con subtítulos incrustados.
6. Publica en cualquier combinación de: audio + blog + feed RSS (Archive.org y GitHub Pages), YouTube (episodio y Shorts), Bluesky, Mastodon, Instagram Reels, X y TikTok (estos dos, asistidos a mano).

Todo es gratis salvo lo que tú decidas pagar (una API de LLM, si eliges una).

## Inicio rápido

`spiral` trabaja siempre sobre el **directorio actual**: tus grabaciones, tu configuración y tus resultados viven juntos, así que un directorio es un programa.

```bash
cd ~/Movies/mi-programa
curl -o .env https://raw.githubusercontent.com/sbonacho/spiral/main/src/spiral/env.example   # y edítalo
spiral
```

El menú muestra qué destinos están configurados y cuáles no (y qué le falta a cada uno), y te deja elegir una acción con las flechas. Cada acción también funciona sin menú:

| Comando | Qué hace |
|---|---|
| `spiral list` | Ficheros del directorio con su estado: pendiente, procesado, publicado (y dónde). |
| `spiral process [nombre...] [--redo]` | Procesa uno o varios ficheros. Se marcan en una lista (espacio marca, Ctrl-A todos, escribe para filtrar). |
| `spiral publish [nombre...] [--to a,b] [--dry-run] [--force] [--yes]` | Marcas uno o varios episodios procesados y los destinos (espacio marca, `a` todos; solo los configurados) y publicas o simulas. Los destinos ya publicados se omiten; `--force` (o responder sí en el menú) los publica otra vez. |
| `spiral unpublish [nombre...] [--from a,b] [--dry-run] [--yes]` | Retira publicaciones hechas por error. Borra el post en Bluesky y Mastodon y saca el episodio del sitio y del feed; YouTube, Instagram, X y TikTok hay que borrarlos a mano (spiral te pregunta y los olvida). El mp3 se queda en Archive.org. Siempre pregunta antes. |
| `spiral view [--no-open]` | Informe HTML de todos los ficheros, su estado y dónde están publicados. |
| `spiral --version` | Versión. |

Ejemplo para scripts (sin terminal): `spiral publish 2026-11-01_programa --to site,bluesky/programa --yes`. Sin terminal y sin los argumentos necesarios, spiral termina con código 2 y un mensaje de uso.

## Cómo funciona

El estado se deduce de las carpetas, sin base de datos:

```
mi-programa/
├── 2026-11-01_programa.mov    pendiente: una grabación a la espera de procesarse
├── intro.mov  outro.mov       opcionales, se añaden a cada episodio
├── .env                       configuración local
├── processed/<nombre>/        procesado: episodio.mov, episodio.mp3, transcripcion.{txt,srt,json},
│                              contenido.json (resumen y textos), clips/ y el .mov original
├── published/<nombre>/        publicado: state.json (por destino), publish.log, report.html
└── site/                      blog, feed.xml y clips, los crea el destino `site`
```

- El procesado lo construye todo en una carpeta temporal y, solo cuando está completo, la mueve a `processed/<nombre>/` y mueve tu `.mov` original dentro. Si algo falla, el original se queda donde estaba y un reintento reutiliza lo ya hecho (no transcribe dos veces).
- `contenido.json` puedes editarlo antes de publicar. Reprocesar un episodio (`--redo`) lo pregunta antes porque regenera ese fichero; lo ya publicado se conserva.
- Los nombres de carpeta se cambian con `PROCESSED_DIR` y `PUBLISHED_DIR` (solo rutas relativas dentro del directorio).

### Capas de configuración

Los ajustes se leen, variable a variable, de (de mayor a menor prioridad): el entorno del proceso, el `.env` del directorio actual y `~/.config/spiral/.env`. Los valores vacíos se ignoran. Pon en el global lo que compartes entre programas (Archive.org, proveedor de resúmenes) y en el local lo propio de cada programa. `intro.mov` y `outro.mov` siguen la misma regla: gana el fichero local y, si no, el de `~/.config/spiral/`.

### Destinos: redes y cuentas

Cada red puede tener varias cuentas. Se declaran con `<RED>_ACCOUNTS` y cada una lleva sus variables, por ejemplo:

```
BLUESKY_ACCOUNTS=programa,personal
BLUESKY_PROGRAMA_HANDLE=miprograma.bsky.social
BLUESKY_PROGRAMA_APP_PASSWORD=...
BLUESKY_PERSONAL_HANDLE=yo.bsky.social
BLUESKY_PERSONAL_APP_PASSWORD=...
```

Los destinos se escriben `red/cuenta` (`bluesky/programa`). El de audio, blog y RSS es simplemente `site` (uno por programa). Un destino está configurado solo si tiene todas sus variables; si no, sale deshabilitado con lo que le falta. Publicar es idempotente: un destino ya publicado se omite, el fallo de uno no detiene a los demás y el progreso parcial (por ejemplo, Shorts ya subidos) se recuerda. `--dry-run` muestra lo que se enviaría sin contactar con nada ni escribir estado.

Los tokens que genera spiral (autorización de YouTube, token renovado de Instagram) se guardan en `~/.config/spiral/tokens/` con permisos `600`, nunca junto a tus grabaciones. Los logs no contienen secretos.

## Configurar cada destino

Haz la configuración una sola vez y rellena `.env` (todas las variables están en [`env.example`](src/spiral/env.example)).

### Audio, blog y RSS (`site`)

1. Crea un repositorio público en GitHub para el programa y activa *Settings → Pages → Deploy from a branch → `main` / root*. Define `SITE_URL=https://<usuario>.github.io/<repo>` y las variables `PODCAST_*`.
2. Haz que `site/` sea ese repositorio (spiral crea los ficheros; tú lo conectas): `mkdir site && cd site && git init -b main && git remote add origin git@github.com:<usuario>/<repo>.git`.
3. Consigue tus claves de Archive.org en <https://archive.org/account/s3.php> y ponlas en `IA_ACCESS_KEY` e `IA_SECRET_KEY` (o ejecuta `uv tool run --from internetarchive ia configure`).
4. Publica tu primer episodio y **da de alta `SITE_URL/feed.xml` una sola vez** en los directorios que quieras: Spotify for Creators («ya tengo un podcast»), Apple Podcasts Connect, iVoox («importar desde RSS»), Amazon Music for Podcasters, Podcast Index (que leen Pocket Casts y otras) y, opcionalmente, YouTube Music. Desde entonces, cada publicación en `site` los actualiza todos. Portada (`PODCAST_IMAGE`): JPG o PNG cuadrado de 1400–3000 px.

Tras cada publicación o retirada, spiral también actualiza el sitio: la página de cada episodio muestra insignias con el logo de cada red en la que se ha publicado (con enlace cuando se conoce: YouTube, Bluesky, Mastodon), y la portada (`index.md`) pasa a ser el listado de episodios con las mismas insignias (solo si sigue siendo la de por defecto; un `index.md` personalizado no se toca). Si defines `PODCAST_IMAGE`, también se usa como logo en la cabecera del sitio. Dónde tienes dado de alta el RSS se configura en el `.env` con `PODCAST_LISTEN_<NOMBRE>=<URL https del programa en esa plataforma>`: salen como insignias junto al enlace RSS de la portada, y el cambio se ve en la siguiente publicación o con `--force`. Nombres conocidos, con su logo: `SPOTIFY`, `APPLE`, `IVOOX`, `AMAZON`, `YOUTUBEMUSIC`, `POCKETCASTS`, `PODCASTINDEX`, `CASTBOX`, `PODCASTADDICT`, `DEEZER`; cualquier otro nombre (p. ej. `PODCAST_LISTEN_MI_WEB`) también vale, con un icono genérico y el nombre como etiqueta (los guiones bajos pasan a espacios). `.env.example` los lista todos. iVoox no tiene icono en el conjunto de iconos, así que lleva uno genérico de auriculares: sustituye `img/redes/ivoox.svg` en el sitio para usar el real (spiral nunca pisa un icono que ya existe). Los estilos generados están en `_sass/spiral.scss`; los tuyos van después del `@import` en `assets/main.scss`. Los enlaces de YouTube solo funcionan para los visitantes cuando publiques el vídeo en Studio.

Si `site/` es su propio repositorio git, spiral ofrece hacer commit y push tras generar los ficheros; si no, solo los genera.

### YouTube

Sube el episodio y cada clip como Short, **en privado**: un proyecto de Google sin auditar no puede publicar vídeos públicos por la API, así que los haces públicos en YouTube Studio (un clic) o solicitas la auditoría gratuita de la API.

1. En [Google Cloud Console](https://console.cloud.google.com) crea un proyecto y activa **YouTube Data API v3**.
2. Configura la pantalla de consentimiento de OAuth (Externo), añádete como usuario de prueba y **publica la aplicación («En producción»)**; si no, la autorización caduca cada 7 días.
3. Crea un **ID de cliente de OAuth** de tipo *Aplicación de escritorio* y descarga su JSON a `~/.config/spiral/client_secret.json` (o define `YOUTUBE_<CUENTA>_CLIENT_SECRET`).
4. Añade `YOUTUBE_ACCOUNTS=canal`. La primera publicación abre el navegador para autorizar.

La cuota diaria de la API (10.000 unidades) da para varias subidas al día; el coste exacto por subida varía según la fuente, compruébalo en la consola de Cloud.

### Bluesky

*Ajustes → Privacidad y seguridad → Contraseñas de aplicación → Añadir*. Usa `BLUESKY_<CUENTA>_HANDLE` y `BLUESKY_<CUENTA>_APP_PASSWORD` (nunca la contraseña de tu cuenta).

### Mastodon

*Preferencias → Desarrollo → Nueva aplicación*, permiso `write:statuses`, y copia el token de acceso. Usa `MASTODON_<CUENTA>_URL` (tu instancia, p. ej. `https://mastodon.social`; si pones la URL de un perfil se reduce a la instancia) y `MASTODON_<CUENTA>_TOKEN`.

### Instagram Reels

Necesita una cuenta profesional (creador o empresa) y una app de Meta con el producto **Instagram Login** y el permiso `instagram_business_content_publish`. Para tu propia cuenta la app puede quedarse en modo desarrollo, sin revisión de Meta. Genera un token de larga duración y el ID de tu cuenta de Instagram, y define `INSTAGRAM_<CUENTA>_USER_ID` e `INSTAGRAM_<CUENTA>_TOKEN`; spiral renueva el token en cada uso (caduca a los 60 días sin usarlo).

Instagram solo acepta vídeos desde una URL pública, así que spiral copia los clips a `site/media/`, sube el sitio y espera a que GitHub Pages los sirva. Por eso `site/` debe ser un repositorio git publicado con Pages.

### X y TikTok

Ninguno tiene publicación automática gratuita. En X, spiral muestra los enlaces de publicación ya rellenados para el hilo; en TikTok abre la carpeta de clips. En ambos casos pregunta si ya lo has hecho y, solo si confirmas, lo anota como publicado (aparece como «a mano» en el informe).

## Resúmenes

Define `LLM_PROVIDER`:

| Proveedor | Necesita | Notas |
|---|---|---|
| `claude` (por defecto) | La [CLI `claude`](https://claude.com/claude-code) con sesión iniciada | Usa tu plan de Claude; `CLAUDE_MODEL` para cambiar el modelo (por defecto `claude-sonnet-5-5`). |
| `gemini` | `GEMINI_API_KEY` (opcional `GEMINI_MODEL`) | Hay plan gratuito; revisa las condiciones de Google sobre el uso de datos. |
| `ollama` | `OLLAMA_MODEL` y un Ollama local (`OLLAMA_URL` opcional) | Totalmente offline, nada sale de tu máquina. |

**Idioma:** `PODCAST_LANGUAGE` (por defecto `es`) fija el idioma de la transcripción y de los textos generados, y también el de los mensajes, preguntas, ayuda e informe de spiral: español para `es` (y `es-MX`...), inglés para `en` y para cualquier otro idioma.

**Privacidad:** con `claude` y `gemini` la transcripción completa se envía a ese proveedor; spiral indica cuál antes de enviarla. El resumen y los textos se escriben en `PODCAST_LANGUAGE` (por defecto `es`), que es también el idioma de la transcripción.

## Límites conocidos

- Solo macOS con Apple Silicon. La primera instalación es grande (Whisper arrastra PyTorch) y la primera transcripción descarga un modelo de ~1,5 GB.
- El destino `site` depende de que GitHub Pages sirva `feed.xml` como fichero estático junto al tema de Jekyll; comprueba que `SITE_URL/feed.xml` carga tras la primera publicación.
- Las APIs de terceros cambian (cuotas de YouTube, permisos de Instagram, precios de X). Cada destino está aislado, así que un cambio solo rompe ese.
- Los ficheros `.env` pueden guardar secretos junto a tus grabaciones: mantenlos fuera de git (el `.gitignore` incluido lo hace).

## Desarrollo

```bash
git clone https://github.com/sbonacho/spiral && cd spiral
uv run --with-editable . --with pytest --with pexpect pytest
```

El diseño y los requisitos están en [`openspec/`](openspec/) (cambio `workspace-cli`); [`docs/design.md`](docs/design.md) conserva la investigación original (en español). Las contribuciones son bienvenidas; abre antes un issue para cambios grandes.

## Licencia

[MIT](LICENSE)
