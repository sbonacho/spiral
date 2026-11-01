# Calle Spiral: automatización del programa de radio

Toma las grabaciones `.mov` de OBS y, por cada programa, genera el vídeo final con intro y outro, el mp3, la transcripción, un resumen y clips verticales. Después publica en todas partes. Coste objetivo: 0 €.

El diseño y las alternativas descartadas están en [DISENO.md](DISENO.md).

> **Estado:** el procesado (ffmpeg, mp3, transcripción, resumen, clips) está probado con clips de muestra. La parte de publicación (Archive.org, GitHub Pages, YouTube, Bluesky, Mastodon, Instagram) está escrita pero **no se ha probado contra las cuentas reales**: la primera vez, usa siempre `--dry-run` y revisa el resultado. Las instrucciones de las consolas de terceros (Google, Meta, etc.) pueden cambiar; si un menú no coincide, manda la documentación oficial de cada plataforma.

---

## 1. Qué hay en el proyecto

| Fichero | Para qué sirve |
|---|---|
| `spiral` | **El comando que usas**: menú guiado y subcomandos `list`, `process`, `publish`, `archive`, `view`. |
| `install.sh` | Instala `spiral` (alias en el rc de tu shell) y crea `.env`. |
| `engine.py` | Motor que ejecuta `spiral`: comandos `process`, `publish`, `social`, `archive` y `report`. |
| `library.py` | Qué episodios hay, dónde se han publicado, archivado e informe HTML. |
| `publish.py` | Sube el mp3 a Archive.org y genera el post de blog y `feed.xml`. |
| `social.py` | YouTube, Bluesky, Mastodon, X e Instagram. |
| `site/` | El sitio web (GitHub Pages): blog, `feed.xml` del podcast y clips para Instagram. Es **un repositorio git aparte**. |
| `site/podcast.json` | Datos del podcast (título, autor, URL pública...). |
| `.env` | Tus claves y la carpeta de grabaciones (`SOURCE_DIR`). Se crea desde `.env.example`; está en `.gitignore`, nunca se sube a git. |
| `~/.config/callespiral/` | OAuth y tokens que genera el propio script (YouTube, Instagram). Fuera del proyecto. |

## 2. Requisitos del Mac

- macOS con Apple Silicon (la transcripción usa mlx-whisper).
- `ffmpeg` y `ffprobe`. Ya los tienes (los trae miniconda).
- [`uv`](https://docs.astral.sh/uv/). Ya lo tienes. Instala solo las dependencias de Python la primera vez.
- Claude Code (`claude`) iniciado con tu cuenta: el resumen se genera con `claude -p`. Usa tu suscripción, sin coste extra. **La transcripción completa se envía a Anthropic** para resumirla.
- `git` y una cuenta de GitHub (para el sitio y el RSS).

La primera ejecución de `process` descarga el modelo de Whisper (~1,5 GB) y varios paquetes. Tarda más; las siguientes no.

## 3. Instalación y uso diario

### 3.0 Instalar el comando `spiral`

Una línea, desde la carpeta del proyecto:

```bash
~/callespiral/install.sh
```

Añade un alias `spiral` a tu `~/.zshrc` (o `~/.bash_profile` si usas bash) entre las marcas `# >>> spiral >>>` y `# <<< spiral <<<`, crea `.env` a partir de `.env.example` si no existe y comprueba que tienes `python3`, `ffmpeg`, `uv`, `claude` y `git`. Repetirlo no duplica nada. Abre una terminal nueva (o `source ~/.zshrc`) y ya puedes escribir `spiral` en cualquier carpeta. Para quitarlo: `~/callespiral/install.sh --uninstall`.

En otro Mac, con el repositorio ya subido a GitHub, sería una sola línea (no la he probado desde cero):

```bash
git clone https://github.com/sbonacho/callespiral ~/callespiral && ~/callespiral/install.sh
```

Después edita `.env` (`SOURCE_DIR`, `ARCHIVE_DIR` y las claves de las redes; ver 4.8). Si ejecutas `spiral` sin `.env`, te ofrece crearlo.

### 3.1 El comando `spiral`

Sin argumentos abre el menú guiado. Primero muestra **qué redes tienes configuradas y cuáles no**, y qué te falta en cada una:

```
Redes
  ✘ Audio + blog + RSS — falta: claves de Archive.org (README 4.2)
  ✘ YouTube (episodio y Shorts) — falta: client_secret.json (README 4.4)
  ✔ Bluesky
  ✘ Mastodon — falta: MASTODON_* en .env (README 4.6)
  ✘ Instagram (Reels) — falta: INSTAGRAM_* en .env (README 4.7)
  ✔ X (te dejo los enlaces, publicas tú)
  ✔ TikTok (subida a mano)
```

Cada acción también se puede lanzar directamente (`spiral publish`):

| Acción | Qué hace |
|---|---|
| `list` | Los `.mov` de `SOURCE_DIR` con `[x]` los ya procesados, su título y dónde se han publicado. |
| `process` | Muestra todos los ficheros; eliges uno por número o escribes texto para buscar (por nombre o título; `*` vuelve a mostrar todos). Se procesa generando todos los ficheros de salida. Si ya estaba procesado, pide confirmación para rehacerlo: borra la transcripción, `contenido.json` (también tus ediciones) y los clips, y conserva el registro de lo ya publicado. |
| `publish` | Igual, eliges un fichero procesado. Después sale la lista de redes: **solo se pueden marcar las configuradas**. Elige `publicar` o `simular` (no publica nada). Con X y TikTok, que no tienen publicación automática, te da los enlaces o abre la carpeta de clips y te pregunta si lo has publicado para anotarlo. |
| `archive` | Mueve **todos los procesados** a `ARCHIVE_DIR/<episodio>/`: una carpeta por `.mov`, con el original y todo su resultado. Muestra la lista y avisa de los que no se han publicado en ningún sitio. No pisa nada: si ya existe la carpeta de un episodio, lo omite. Desde el archivo ya no se puede publicar con `spiral publish`. |
| `view` | Genera `informe.html` (no se sube a git) y lo abre en el navegador. |
| `config` | Vuelve a mostrar qué redes están configuradas. |

Informe (`view`): una fila por fichero, **procesado o no** (los pendientes salen con ✘ y sin datos), y las filas de los **archivados** llevan el icono 📦. Columnas: Procesado, Audio/RSS, YouTube, Shorts, Bluesky, Mastodon, Instagram, X y TikTok, con ✔ si se subió y ✘ si no, y los totales abajo. YouTube y el audio enlazan al contenido; Shorts e Instagram muestran cuántos clips se publicaron.

Publicar con `spiral publish` pregunta antes de subir `site/` a GitHub, necesario para que el RSS y Instagram vean el contenido. Lo ya publicado se anota en `out/<episodio>/publicado.json` y no se duplica al repetir.

### Referencia: comandos del motor (`engine.py`)

Es lo que `spiral` ejecuta por debajo; puedes usarlo directamente. Cada `.mov` que no sea intro/outro es **un episodio distinto**; intro y outro, si las tienes, van en la misma carpeta con los nombres `intro.mov` y `outro.mov` (o con `--intro`/`--outro`). `process DIRECTORIO` procesa **todos** los `.mov` de la carpeta; limítalo con `--episodio NOMBRE` (repetible) y rehaz con `--rehacer`.

### 3.2 Procesar

```bash
~/callespiral/engine.py process ~/Movies
```

Deja en `~/Movies/out/<episodio>/`:

| Fichero | Contenido |
|---|---|
| `episodio.mov` | Intro + programa + outro (solo las piezas que existan), con el volumen normalizado a -16 LUFS. |
| `episodio.mp3` | Solo audio, 128 kbps. |
| `transcripcion.txt` / `.srt` / `.json` | Transcripción (Whisper local, gratis). |
| `contenido.json` | Título, resúmenes, capítulos, etiquetas, hilo de X, post de blog y clips. **Revísalo y edítalo antes de publicar.** |
| `clips/clip1.mp4`... | Clips verticales 9:16 con título y subtítulos. Borra los que no quieras publicar. |

Si los formatos de intro, programa y outro coinciden, el vídeo no se recodifica; si no, el script recodifica al formato del programa (más lento). Es re-ejecutable: salta lo que ya está hecho. Para rehacer un paso, borra su fichero.

Los tiempos de `contenido.json` son del programa sin intro; `offset_intro` es la duración de la intro, que ya se suma en los capítulos de YouTube.

### 3.3 Publicar el audio y el blog

```bash
~/callespiral/engine.py publish ~/Movies NOMBRE_DEL_MOV [--push]
```

`NOMBRE_DEL_MOV` es el nombre del fichero sin `.mov`, por ejemplo `2026-10-30 20-10-42` (si es de OBS, la fecha del episodio sale de ahí). Hace tres cosas:

1. Sube el mp3 a Archive.org.
2. Crea el post de blog en `site/_posts/` (reproductor, resumen, capítulos, transcripción).
3. Reconstruye `site/feed.xml`.

Con `--push` hace además `git commit` y `git push` de `site/`. Sin él, solo prepara los ficheros.

### 3.4 Difundir en redes

```bash
~/callespiral/engine.py social ~/Movies NOMBRE_DEL_MOV --dry-run
~/callespiral/engine.py social ~/Movies NOMBRE_DEL_MOV [--only youtube,bluesky,mastodon,x,instagram]
```

`--dry-run` muestra los textos sin publicar nada. **Ejecuta antes `publish`**, porque los textos enlazan a la entrada del blog. Lo ya publicado se anota en `out/<episodio>/publicado.json`, así que repetir el comando no duplica nada.

| Plataforma | Qué hace el script |
|---|---|
| YouTube | Sube el episodio completo y los clips como Shorts, en **privado**. Tú los haces públicos. |
| Bluesky, Mastodon | Publican resumen + enlace + hasta 3 hashtags. |
| X | Imprime un enlace por tweet del hilo; tú pulsas Publicar. |
| Instagram | Copia los clips a `site/media/`, hace push, espera a que sean públicos y publica Reels. |
| TikTok | No automatizado: sube a mano los clips de `out/<episodio>/clips/`. |
| Spotify, Apple, iVoox, Amazon... | Leen tu `feed.xml` solas (alta única, ver abajo). |

---

## 4. Configuración inicial (una sola vez)

Orden recomendado: **4.1 → 4.2 → 4.3**, y después las redes que quieras.

### 4.1 GitHub Pages: sitio, blog y feed RSS

1. En GitHub, crea un repositorio **público** (por ejemplo `callespiral`).
2. Convierte `site/` en ese repositorio:
   ```bash
   cd ~/callespiral/site
   git init -b main
   git add -A && git commit -m "Sitio inicial"
   git remote add origin git@github.com:TU_USUARIO/callespiral.git
   git push -u origin main
   ```
3. En GitHub: *Settings → Pages → Build and deployment → Deploy from a branch → `main` / `(root)`*. En un minuto o dos queda en `https://TU_USUARIO.github.io/callespiral/`.
4. Edita `site/podcast.json`:
   - `site_url`: la URL de arriba, sin barra final.
   - `autor` y `email`.
   - `descripcion` y `categoria` (nombre de categoría de Apple Podcasts).
   - `imagen`: URL de la portada, un cuadrado JPG o PNG de entre 1400 y 3000 píxeles. Sube el fichero a `site/` (por ejemplo `site/portada.jpg`) y pon `https://TU_USUARIO.github.io/callespiral/portada.jpg`. Apple y Spotify la piden.

Mientras `podcast.json` contenga `TU_USUARIO`, `publish` y `social` se niegan a ejecutarse.

### 4.2 Archive.org (aloja los mp3)

1. Crea una cuenta gratuita en [archive.org](https://archive.org).
2. Consigue tus claves en [archive.org/account/s3.php](https://archive.org/account/s3.php) y ponlas en `.env` como `IA_ACCESS_KEY` e `IA_SECRET_KEY`. Alternativa: déjalas vacías y ejecuta una vez `uv run --with internetarchive ia configure` (guarda las claves en `~/.config/internetarchive/`).

### 4.3 Dar de alta el RSS en las plataformas de podcast

Se hace una sola vez, **después de publicar el primer episodio** (el feed necesita al menos uno). El RSS es `https://TU_USUARIO.github.io/callespiral/feed.xml`. Comprueba antes que es válido con un validador de podcast (por ejemplo el de Podbase o Podcast Index). A partir de ahí, cada `publish --push` actualiza todas las plataformas sin más trabajo (algunas tardan horas en refrescar).

| Plataforma | Cómo dar de alta el RSS |
|---|---|
| **Spotify** | En *Spotify for Creators* (creators.spotify.com): *Add a podcast / Ya tengo un podcast* → pegar la URL del RSS → verificar con el código que llega al correo del feed. |
| **Apple Podcasts** | En *Apple Podcasts Connect* (podcastsconnect.apple.com) con tu Apple ID: añadir un programa con RSS. Revisión de unos días. |
| **iVoox** | En ivoox.com: *Subir → ¿Ya tienes un programa? / Importar desde RSS*. iVoox no tiene API de subida; solo importa el feed. |
| **Amazon Music / Audible** | En *Amazon Music for Podcasters* (podcasters.amazon.com): añadir programa con RSS. |
| **Podcast Index** | En podcastindex.org: *Add a feed*. Desde ahí lo recogen Pocket Casts, Podverse, Fountain y otras aplicaciones; Apple Podcasts lo incluye también por su lado. |
| **YouTube Music (opcional)** | En YouTube Studio: *Contenido → Podcasts → Enviar un feed RSS*. Solo en algunos países, y duplica el contenido si ya subes el vídeo a YouTube. Elige una de las dos opciones. |

### 4.4 YouTube

Sube el episodio y los Shorts por la API oficial. Es gratis, pero con una limitación: **un proyecto de Google sin auditar fuerza los vídeos a "privado"**, así que los publicas tú desde Studio (un clic) o solicitas la auditoría gratuita de la API (tarda semanas).

1. Entra en [console.cloud.google.com](https://console.cloud.google.com) y crea un proyecto.
2. *APIs y servicios → Biblioteca*: busca **YouTube Data API v3** y actívala.
3. *APIs y servicios → Pantalla de consentimiento de OAuth*: tipo **Externo**, rellena los datos básicos y añade tu cuenta como usuario de prueba. Después **publica la aplicación ("En producción")**. Si la dejas en modo "Prueba", la autorización caduca cada 7 días. Aparecerá el aviso de "app no verificada" al autorizar: es normal, es tu propia app.
4. *Credenciales → Crear credenciales → ID de cliente de OAuth → Aplicación de escritorio*. Descarga el JSON.
5. Guárdalo como `~/.config/callespiral/client_secret.json`.
6. La primera vez que uses `social` con YouTube se abre el navegador para autorizar. Elige la cuenta del canal y acepta. El token se guarda en `~/.config/callespiral/youtube_token.json`.

Cuota diaria de la API: 10.000 unidades. Una subida de vídeo cuesta entre 100 y 1.600 según la fuente; comprueba el dato real en la consola de Google Cloud. Con un episodio y tres clips por semana no hay problema.

### 4.5 Bluesky

1. Crea la cuenta en bsky.app si no la tienes.
2. *Ajustes → Privacidad y seguridad → Contraseñas de aplicación → Añadir*. Copia la contraseña que te da (no uses la de tu cuenta).
3. Guarda `BLUESKY_HANDLE` y `BLUESKY_APP_PASSWORD` en `.env` (ver 4.8).

### 4.6 Mastodon

1. Cuenta en la instancia que prefieras (por ejemplo mastodon.social).
2. *Preferencias → Desarrollo → Nueva aplicación*. Pon un nombre y marca solo el permiso `write:statuses`.
3. Abre la aplicación creada y copia **"Tu token de acceso"**.
4. Guarda `MASTODON_URL` (por ejemplo `https://mastodon.social`) y `MASTODON_TOKEN` en `.env`.

### 4.7 Instagram (Reels)

Es la más trabajosa. Requisitos y pasos:

1. La cuenta de Instagram debe ser **profesional** (creador o empresa): *Ajustes → Tipo de cuenta y herramientas → Cambiar a cuenta profesional*.
2. En [developers.facebook.com](https://developers.facebook.com) crea una app de Meta (te pedirá una cuenta de desarrollador) y añade el producto **Instagram** con el flujo **"Instagram Login"** (acceso a la API de Instagram con inicio de sesión de Instagram).
3. Permisos necesarios: `instagram_business_basic` e `instagram_business_content_publish`.
4. Para publicar en **tu propia cuenta** basta con tener la app en modo desarrollo y tu cuenta añadida como rol de la app (probador). No hace falta revisión de Meta.
5. En el panel del producto Instagram, genera un **token de acceso** para tu cuenta, y cámbialo por uno de larga duración (60 días) siguiendo las instrucciones del panel. Anota también el **ID de tu cuenta de Instagram**.
6. Guarda `INSTAGRAM_USER_ID` e `INSTAGRAM_TOKEN` en `.env`.

Cómo funciona después:

- El script renueva el token en cada ejecución y lo guarda en `~/.config/callespiral/instagram_token`. Si pasas más de 60 días sin ejecutarlo, caduca y tendrás que generar otro.
- Instagram necesita que el vídeo esté en una URL pública. El script copia los clips a `site/media/<episodio>/`, hace `git commit` y `git push` y espera a que GitHub Pages los sirva (1-2 min). Eso significa que **`site/` debe estar configurado como en 4.1** antes de usar Instagram.
- Cada clip ocupa unos 10-20 MB en el repositorio para siempre (el límite orientativo de GitHub Pages es de 1 GB).
- No he comprobado que Meta acepte los vídeos servidos desde GitHub Pages. Si falla, el mensaje de error de la API indicará el motivo.

### 4.8 Fichero de credenciales (.env)

```bash
cp .env.example .env
chmod 600 .env
```

Rellena `SOURCE_DIR` y solo las redes que vayas a usar (las claves vacías se ignoran). `.env.example` lista todas las variables:

| Variable | Para qué |
|---|---|
| `SOURCE_DIR` | Carpeta con los `.mov` de OBS. |
| `ARCHIVE_DIR` | Carpeta donde "Archivar" deja una carpeta por episodio. |
| `IA_ACCESS_KEY`, `IA_SECRET_KEY` | Archive.org (opcionales si hiciste `ia configure`). |
| `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Bluesky. |
| `MASTODON_URL`, `MASTODON_TOKEN` | Mastodon. |
| `INSTAGRAM_USER_ID`, `INSTAGRAM_TOKEN` | Instagram. |

YouTube no usa variables: su OAuth va en `~/.config/callespiral/client_secret.json` (4.4). Si prefieres no tener un `.env` en el proyecto, el script también lee `~/.config/callespiral/env` con el mismo formato.

`.env` está en `.gitignore`, así que no entra en ningún commit. No lo pegues en chats ni en issues.

### 4.9 X (Twitter) y TikTok

- **X:** no hay nada que configurar. El script imprime enlaces `x.com/intent/post?text=...`, uno por tweet del hilo. Los abres con tu sesión iniciada y pulsas Publicar. Los tweets se publican sueltos, no encadenados: responde a mano al primero si quieres un hilo. La API de X ya no tiene plan gratuito (pago por uso, unos 0,015 $ por post y 0,20 $ si lleva enlace), por eso va semiautomático.
- **TikTok:** manual. Su API solo publica en privado hasta pasar una auditoría de varias semanas. Sube a mano los clips de `out/<episodio>/clips/`.

---

## 5. Flujo de trabajo de cada programa

1. Grabar con OBS; el `.mov` queda en `SOURCE_DIR` (con `intro.mov` y `outro.mov` si los tienes).
2. `spiral process` y elegir el fichero.
3. Revisar y editar `out/<episodio>/contenido.json` y borrar los clips que no sirvan.
4. `spiral publish`, elegir el fichero y las redes; mejor simular primero.
5. En YouTube Studio, hacer públicos el episodio y los Shorts; subir los clips a TikTok y publicar en X (el comando te lo guía y anota que lo has hecho).
6. Cuando hayas terminado con el episodio, `spiral archive`; `spiral view` para ver el informe.

Tiempo estimado de trabajo manual una vez todo está configurado: unos 10 minutos por programa.

## 6. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `Edita .../podcast.json: ... de ejemplo` | Falta rellenar `site/podcast.json` (4.1). |
| `Fallo subiendo a Archive.org` | Faltan `IA_ACCESS_KEY`/`IA_SECRET_KEY` en `.env` o no has hecho `ia configure` (4.2) o la cuenta no está verificada por correo. |
| `Faltan X en .../.env` | Falta esa variable en `.env`. `spiral config` te dice cuáles. |
| YouTube pide autorizar cada semana | La app de Google está en modo "Prueba": publícala en producción (4.4). |
| Los vídeos de YouTube salen en privado | Es lo esperado sin auditoría: hazlos públicos en Studio. |
| Instagram: `no está público tras 450 s` | GitHub Pages no desplegó. Revisa *Actions* y *Pages* en el repositorio. |
| Instagram: error de token | El token caducó (más de 60 días sin usarlo). Genera uno nuevo y bórralo de `~/.config/callespiral/instagram_token`. |
| Vídeo final con saltos o desincronizado | Intro/outro con parámetros distintos al programa. El script ya recodifica en ese caso; si persiste, graba intro y outro con el mismo perfil de OBS. |
| La transcripción escribe cosas sin sentido en silencios | Whisper alucina con silencios o música. Por eso se transcribe solo el programa, sin intro ni outro; si pasa, edita `transcripcion.json` y borra `contenido.json` para regenerarlo. |

## 7. Qué no está hecho

- Prueba real con una grabación de OBS larga y con intro/outro reales.
- Prueba real de todas las publicaciones (YouTube, Bluesky, Mastodon, Instagram, Archive.org, git push).
- TikTok y X por API (decisión de coste y de auditoría, ver [DISENO.md](DISENO.md)).
- Threads, LinkedIn, Facebook y newsletter (fase 4 del diseño, solo si hay audiencia).
