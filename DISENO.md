# Diseño: automatización del podcast/programa "callespiral"

Fecha: 2026-10-31 · Objetivo de coste: 0 € · Plataforma de proceso: Mac Apple Silicon (local)

---

## 1. Recomendación final (resumen)

1. **Un solo script Python (CLI `spiral`) + ffmpeg**, sin orquestadores (n8n/Postiz no compensan para 1 episodio/semana).
2. ffmpeg: intro/outro **pre-convertidos una vez** al perfil de OBS → concat sin recodificar vídeo; audio con **loudnorm 2 pasadas (-16 LUFS)**.
3. Transcripción local con **mlx-whisper + large-v3-turbo** (0 €, ~minutos por hora de audio, buen español). Fallback: whisper.cpp.
4. Contenido (resumen, hilo, post, momentos para reels con timestamps): **`claude -p` (Claude Code headless, ya pagado)** o **Gemini Flash free tier**; Ollama (gemma4/qwen) como alternativa 100 % offline.
5. Feed RSS propio en **GitHub Pages** (mismo repo = blog Hugo/Jekyll) + MP3 en **Archive.org**. Ese RSS se da de alta una vez en Spotify, Apple, iVoox, Amazon, YouTube (RSS), Pocket Casts, Podcast Index, etc.
6. Vídeo completo y Shorts: **YouTube Data API** (sube en privado si el proyecto no está auditado → 1 clic para publicar, o solicitar auditoría gratuita).
7. Bluesky y Mastodon: API gratis, 100 % automático. **X: semiautomático** (enlace `x.com/intent/post` precargado; la API ya es de pago por uso).
8. Instagram Reels: Graph API con cuenta profesional propia (sin App Review para tu propia cuenta) → automatizable en fase 3. **TikTok: manual** (API sin auditoría = solo privado).
9. Coste: **0 €/mes**. Opcional: X API ≈ 0,25 $/episodio.
10. MVP primero (ffmpeg + mp3 + whisper + resumen) en 1-2 tardes; publicación por fases.

---

## 2. Arquitectura / pipeline

```
 episodios/2026-11-05/                    assets/ (una vez)
   ├─ parte1.mov ... (OBS)                  ├─ intro.mov ─┐ normalizados 1 vez al
   └─ meta.yaml (título, nº, invitados)     └─ outro.mov ─┘ perfil OBS (cache)
            │
            ▼
 [1] PROBE      ffprobe: códec, resolución, fps, sample rate, canales
            │   ¿coinciden con intro/outro cacheados? sí → copy / no → reencode
            ▼
 [2] CONCAT     ffmpeg concat demuxer (-c:v copy)  |  fallback: concat filter + h264_videotoolbox
            ▼
 [3] LOUDNORM   2 pasadas loudnorm I=-16 TP=-1.5 LRA=11 (sólo audio se recodifica)
            ▼                                     → out/episodio.mov
 [4] MP3        libmp3lame 128k CBR (o 96k mono) + ID3 + carátula → out/episodio.mp3
            ▼
 [5] TRANSCRIBE mlx-whisper large-v3-turbo (lang=es) → .srt .vtt .json (word timestamps) .txt
            ▼
 [6] LLM        transcript + prompt plantilla → JSON validado:
            │   {titulo, resumen_corto, resumen_largo, capitulos[ts], tags,
            │    hilo_x[], post_blog_md, post_bluesky, clips[{inicio,fin,gancho,titulo}]}
            ▼
 [7] CLIPS      por clip: ffmpeg recorte 9:16 (crop centro o fondo desenfocado)
            │   + subtítulos quemados (SRT del tramo) + título → out/clips/*.mp4 (≤60-90 s)
            ▼
 [8] REVISIÓN   (humano, 5 min) editar out/contenido.json / descartar clips  ← puerta manual
            ▼
 [9] PUBLICAR   ├─ archive.org (ia CLI): mp3 (+ mov opcional)
                ├─ repo GitHub Pages: post blog + item en feed.xml (+ transcripción) → git push
                │      └─ Spotify / Apple / iVoox / Amazon / YT Music / Pocket Casts... leen el RSS
                ├─ YouTube API: vídeo completo (+capítulos) + Shorts  [privado→público]
                ├─ Bluesky + Mastodon API: post con enlace
                ├─ Instagram Graph API: reels (fase 3)
                └─ X / TikTok: se genera enlace intent / se deja carpeta lista para subir
            ▼
 [10] ESTADO    out/state.json (paso hecho/pendiente → re-ejecución idempotente)
```

Comandos previstos: `spiral process <dir>` (1-7), `spiral publish <dir> [--only youtube,rss,...]` (9).

---

## 3. Decisiones A-F

| # | Decisión | Elegida | Alternativa(s) | Pros / contras clave | Coste |
|---|---|---|---|---|---|
| A | Vídeo/audio | ffmpeg: intro/outro **re-codificados 1 vez** al perfil OBS (mismo códec, resolución, fps, timebase, AAC 48 kHz) → **concat demuxer `-c:v copy`**; audio con **loudnorm 2 pasadas** (-16 LUFS, TP -1.5) | Concat filter recodificando todo (h264_videotoolbox) | Copy: rápido y sin pérdida, pero exige parámetros idénticos (si no, saltos/desincronía). Recodificar: robusto pero lento. Se hace check con ffprobe y fallback automático. Loudnorm obliga a recodificar sólo el audio (barato). | 0 € |
| B | Transcripción | **mlx-whisper + large-v3-turbo** local (WER español ~5-10 % en Common Voice; ~2x más rápido que whisper.cpp en Apple Silicon según benchmark 2026) | whisper.cpp (sin Python, Metal/CoreML); faster-whisper (no usa GPU Apple, más lento); API OpenAI gpt-4o-mini-transcribe (~0,18 $/h aprox.); Groq Whisper (tier gratis con límites) | Local = 0 €, privado, sin cuotas. Modelo `large-v3` completo sólo si turbo falla con nombres propios. Pasar `initial_prompt` con nombres del programa. | 0 € |
| C | Resumen y contenido | **`claude -p` (Claude Code headless)** si ya hay suscripción → coste marginal 0; si no, **Gemini Flash free tier** (≈250-1500 req/día, de sobra) | Ollama local: gemma4:26b / qwen3.6:35b (32 GB RAM) o gemma4:12b / gpt-oss:20b (16 GB); API de pago (Gemini Flash / Claude Haiku) | Calidad: Claude/Gemini > local en español y en elegir buenos ganchos. Gemini free: los datos pueden usarse para entrenar. Local: offline, más lento, peor criterio para clips. El script abstrae proveedor (`--llm claude|gemini|ollama`). | Tokens/episodio (1 h): ~15-20k entrada + ~3-4k salida. De pago ≈ 0,01-0,05 €. Free/suscripción: 0 € |
| D | Publicación | Script propio por plataforma (ver tabla 4): YouTube API, Bluesky/Mastodon API, RSS propio, IG Graph API (fase 3); X y TikTok semimanuales | Postiz/Mixpost self-hosted; Buffer free | Los schedulers necesitan igualmente tus apps OAuth (mismas auditorías) y añaden Docker+DB. Script = menos piezas. | 0 € (X API opcional ~0,25 $/ep) |
| E | Hosting RSS | **GitHub Pages (feed.xml + blog) + MP3 en Archive.org** | Spotify for Creators (gratis, sin API de subida, soporta vídeo en Spotify); iVoox (gratis, RSS propio limitado a 20 últimos episodios salvo PRO); Cloudflare R2 (10 GB gratis, sin coste de salida, pide tarjeta) | Propio = 100 % automatizable y portable; contras: hay que generar RSS válido (iTunes tags) y Archive.org puede ir lento. Spotify for Creators = cero mantenimiento pero subida manual y lock-in. | 0 € |
| F | Herramientas | **Script Python** (typer + subprocess ffmpeg + mlx-whisper + google-api-python-client + atproto + Mastodon.py + internetarchive) | n8n self-hosted; Postiz; Auto-Editor (quitar silencios, opcional); OpusClip y similares (de pago) | El LLM ya devuelve timestamps de clips → no hace falta clon de OpusClip. Auto-Editor sólo si quieres recortar silencios en los clips. | 0 € |

---

## 4. Plataformas

| Plataforma | Formato | Modo | Cómo | Límite / requisito | Coste |
|---|---|---|---|---|---|
| RSS propio (GitHub Pages + Archive.org) | MP3 + notas | **Automático** | `ia upload` + generar feed.xml + `git push` | GitHub Pages: sitio ≤1 GB, 100 GB/mes de ancho de banda (los MP3 van a Archive.org) | 0 € |
| Spotify | Audio | **Automático vía RSS** (alta única en Spotify for Creators) | Lee el RSS | Vídeo en Spotify sólo si se aloja en Spotify for Creators (subida manual) | 0 € |
| Apple Podcasts, Amazon Music/Audible, Pocket Casts, Podcast Index (→ Podverse, Fountain, etc.), Overcast, Castbox, Podcast Addict, Deezer, Podchaser, Goodpods | Audio | **Automático vía RSS** (alta única) | Lee el RSS | Apple requiere Apple ID; Deezer: disponibilidad de alta variable | 0 € |
| iVoox | Audio | **Automático vía RSS** (importación "¿Ya tienes un programa?") | Lee el RSS | Sin API pública de subida | 0 € |
| YouTube (episodio completo) | Vídeo .mov | **Semiautomático** → automático tras auditoría | Data API v3 `videos.insert` (resumible) + capítulos en descripción + miniatura | 10.000 unidades/día por proyecto; coste de insert discrepante en fuentes (100-1.600 u.) → suficiente para varias subidas/día. Proyecto no auditado: **vídeos forzados a privado** → publicar a mano (1 clic) o pedir auditoría (gratis, semanas). App OAuth en modo *Testing* caduca refresh token a los 7 días → pasar a *In production* (sin verificar, sólo tú) | 0 € |
| YouTube Music / Podcasts (RSS) | Audio | Automático vía RSS (opcional) | Studio → importar RSS | Sólo en países soportados; duplica el canal si ya subes vídeo → elegir uno de los dos | 0 € |
| YouTube Shorts | Vertical ≤60 s (hasta 3 min permitido) | Semiautomático | Misma API, `#Shorts` | Igual que arriba (privado sin auditoría) | 0 € |
| Instagram Reels | Vertical | **Automático (fase 3)** | Graph API (Instagram Login), contenedor → publish; el vídeo debe estar en URL pública (Archive.org/GitHub) | Cuenta profesional (creador/empresa). Para tu propia cuenta basta acceso estándar (app en desarrollo, sin App Review). Límite de publicaciones API por 24 h (verificar cifra vigente en docs) | 0 € |
| TikTok | Vertical | **Manual** (o borrador vía API) | App/web; carpeta `out/clips` lista | Content Posting API sin auditar: sólo privado, máx. 5 usuarios/24 h; auditoría 1-2+ semanas, requiere web y política de privacidad | 0 € |
| X (Twitter) | Hilo + enlace | **Semiautomático** | Script abre `https://x.com/intent/post?text=…` precargado; tú pulsas Publicar (hilo: un intent por tweet o pegar) | API ya sin tier gratis (desde feb-2026, pago por uso): ~0,015 $/post, **0,20 $ si lleva enlace** | 0 € (API: ~0,25 $/ep) |
| Bluesky | Post + enlace + clip | **Automático** | AT Protocol (`atproto`), app password | Sin coste; límites de rate generosos | 0 € |
| Mastodon | Post + enlace | **Automático** | API REST (`Mastodon.py`) | Depende de la instancia | 0 € |
| Blog | Post MD + transcripción + reproductor | **Automático** | Mismo repo GitHub Pages (Hugo/Jekyll) | Transcripción completa en la web = SEO gratis | 0 € |
| Threads / LinkedIn / Facebook Page (opcional) | Post | Automatizable con apps propias (Meta / "Share on LinkedIn") | Fase 4, sólo si hay audiencia | Mismas fricciones OAuth | 0 € |
| Newsletter (opcional) | Resumen | Semiautomático | Buttondown/Substack free: pegar el resumen | — | 0 € |

---

## 5. Costes

| Concepto | Por episodio | Mensual (4 ep.) |
|---|---|---|
| ffmpeg, mlx-whisper, script, GitHub Pages, Archive.org, YouTube/Bluesky/Mastodon/IG APIs | 0 € | 0 € |
| LLM vía `claude -p` (suscripción existente) o Gemini free | 0 € | 0 € |
| LLM API de pago (si se quiere, ~20k in / 4k out) | 0,01-0,05 € | ≤0,20 € |
| X API pay-per-use (hilo 4 tweets, 1 con enlace) — opcional | ~0,25 $ | ~1 $ |
| Electricidad del Mac (~15-30 min de cómputo) | despreciable | despreciable |
| **Total recomendado** | **0 €** | **0 €** |

Tiempo humano estimado tras fase 3: ~10 min/episodio (revisar JSON, publicar YouTube privado→público, X y TikTok).

---

## 6. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| YouTube: proyecto no auditado → privado; token 7 días en modo Testing; cuota y coste de `videos.insert` han cambiado en 2025-2026 | Publicación no 100 % automática / fallos de auth | App en *In production*; publicar a mano o pedir auditoría; reintentos con subida resumible; consultar coste real en Cloud Console |
| X cambia precios de nuevo (ya pasó: free → pay-per-use, recargo por enlaces) | Coste inesperado | Por defecto sin API (intent URL); módulo X desacoplado |
| Meta (IG): cambios de permisos/scopes (renombrados en 2025), requisito de cuenta profesional, límites de duración en Reels vía API | Fallo de publicación | Fase 3 aislada; fallback manual con carpeta preparada |
| TikTok: auditoría obligatoria para público | No automatizable | Manual asumido |
| Archive.org lento/caído o cambie políticas | Episodios no descargables | URL de enclosure configurable; migrar a R2 cambiando 1 variable y regenerando feed |
| Gemini free tier: límites recortados sin aviso (ya ocurrió dic-2025) y uso de datos para entrenamiento | Paso LLM falla | Proveedor intercambiable (claude/gemini/ollama) |
| Whisper: alucinaciones en silencios / música de intro | Transcripción con basura | Transcribir sólo el programa (sin intro/outro) y desplazar timestamps; VAD; `initial_prompt` |
| Timestamps de clips del LLM imprecisos | Cortes a mitad de frase | Ajustar inicio/fin al límite de segmento whisper más cercano |
| Concat `-c copy` con parámetros distintos (OBS cambia perfil) | Vídeo roto/desincronizado | Validación ffprobe + fallback a recodificar |
| Tokens/secretos en disco | Fuga de credenciales | Keychain de macOS o `.env` fuera del repo, `.gitignore` |

---

## 7. Plan de implementación por fases

| Fase | Alcance | Se programa | Se reutiliza | Esfuerzo |
|---|---|---|---|---|
| **0. Preparación** | Normalizar intro/outro al perfil OBS; definir `meta.yaml` y estructura `episodios/`, `out/` | Comando `spiral prepare-assets` | ffmpeg | 1 h |
| **1. MVP proceso** | Pasos 1-6: concat + loudnorm + MP3 + transcripción + `contenido.json` | `probe.py`, `media.py` (concat/loudnorm/mp3), `transcribe.py`, `llm.py` (prompt + validación JSON con pydantic), `state.json` | ffmpeg, mlx-whisper, `claude -p` / google-genai / ollama | 1-2 tardes |
| **2. Clips + RSS + blog** | Paso 7 (reels 9:16 con subtítulos) y publicación de audio: Archive.org + feed.xml + post en GitHub Pages; alta única del RSS en Spotify, Apple, iVoox, Amazon, Pocket Casts, Podcast Index... | `clips.py`, `rss.py` (feedgen o plantilla Jinja con tags iTunes/podcast:), `blog.py` | ffmpeg (subtitles/crop), `internetarchive`, Hugo/Jekyll, GitHub Pages | 2 tardes |
| **3. Vídeo y redes** | YouTube (completo + Shorts, privado→público), Bluesky, Mastodon, X intent, Instagram Reels | `publish/youtube.py`, `bluesky.py`, `mastodon.py`, `x_intent.py`, `instagram.py` | google-api-python-client, atproto, Mastodon.py, requests (Graph API) | 2-3 tardes |
| **4. Opcional** | Auditoría YouTube/TikTok; X API de pago; Threads/LinkedIn; Auto-Editor para silencios; Postiz si se suman colaboradores | Según necesidad | Postiz, Auto-Editor | — |

Criterio de "hecho" del MVP: `spiral process episodios/X` produce `episodio.mov`, `episodio.mp3`, `transcripcion.srt/.txt` y `contenido.json` válido sin intervención, y es re-ejecutable sin rehacer pasos completados.

---

### Fuentes consultadas (oct-2026)
- YouTube `videos.insert` (privado sin auditoría, cuota): https://developers.google.com/youtube/v3/docs/videos/insert · https://www.activepieces.com/blog/youtube-api-quota-exceeded-how-to-fix-and-avoid-it
- YouTube RSS ingestion: https://support.google.com/youtube/answer/13525207
- X API pay-per-use 2026: https://postproxy.dev/blog/x-api-pricing-2026 · https://opentweet.io/answers/is-the-x-api-free-in-2026
- TikTok Content Posting API: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- Instagram Content Publishing: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing
- iVoox RSS: https://www.ivoox.com/blog/como-publicar-tu-podcast-en-ivoox/
- Spotify for Creators RSS: https://support.spotify.com/us/creators/article/your-rss-feed/
- Gemini free tier: https://yingtu.ai/en/blog/google-gemini-api-free-tier-limits-2026
- mlx-whisper vs whisper.cpp: https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html
- Modelos Ollama 2026: https://www.morphllm.com/best-ollama-models
- Postiz: https://dupple.com/tools/postiz

Cifras marcadas como discrepantes (coste de `videos.insert`, límites Gemini free, límite diario IG) deben verificarse en la consola/documentación oficial al implementar.
