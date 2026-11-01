"""Difusión de un episodio ya procesado: YouTube (completo + Shorts), Bluesky, Mastodon, X (enlace).

Claves en .env (ver .env.example; fuera de git). Tokens y OAuth de YouTube en ~/.config/callespiral/:
  client_secret.json  OAuth de YouTube (Google Cloud, tipo "Aplicación de escritorio")
  youtube_token.json  lo crea el primer login
  instagram_token     token de larga duración de Instagram (se renueva solo en cada uso)
Lo publicado se anota en out/<episodio>/publicado.json para no duplicar al re-ejecutar.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_DIR = Path.home() / ".config" / "callespiral"
YT_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]
TARGETS = ("youtube", "bluesky", "mastodon", "x", "instagram")
IG_API = "https://graph.instagram.com/v26.0"


def load_env():
    """Carga .env del proyecto (y ~/.config/callespiral/env, si existe); lo ya exportado manda."""
    for f in (ROOT / ".env", CONFIG_DIR / "env"):
        if f.exists():
            for line in f.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    if v.strip():
                        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def need(*keys):
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Faltan {', '.join(missing)} en {ROOT / '.env'}")


def mmss(s):
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}" if s >= 3600 else f"{s // 60}:{s % 60:02}"


def youtube_description(c, url):
    """Capítulos de YouTube: el primero en 0:00, mínimo 3, y con el offset de la intro."""
    off = c.get("offset_intro", 0)
    lines = [f"{mmss(x['inicio'] + off)} {x['titulo']}" for x in c["capitulos"]]
    if off and c["capitulos"][0]["inicio"] + off > 0:
        lines.insert(0, "0:00 Intro")
    text = f"{c['resumen_largo']}\n\nCapítulos:\n" + "\n".join(lines) + f"\n\nTranscripción y más: {url}"
    return text.replace("<", "").replace(">", "")


def youtube_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    token = CONFIG_DIR / "youtube_token.json"
    creds = Credentials.from_authorized_user_file(token, YT_SCOPE) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret = CONFIG_DIR / "client_secret.json"
            if not secret.exists():
                raise SystemExit(f"Falta {secret} (OAuth de YouTube, ver DISENO.md)")
            creds = InstalledAppFlow.from_client_secrets_file(secret, YT_SCOPE).run_local_server(port=0)
        token.write_text(creds.to_json())
        token.chmod(0o600)
    return build("youtube", "v3", credentials=creds)


def youtube_upload(yt, path, title, description, tags):
    from googleapiclient.http import MediaFileUpload
    body = {"snippet": {"title": title[:100], "description": description, "tags": tags[:15],
                        "categoryId": "22", "defaultLanguage": "es"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"    subiendo {int(status.progress() * 100)}%")
    return resp["id"]


def fit(text, room):
    """Recorta en el límite de palabra, con puntos suspensivos."""
    if len(text) <= room:
        return text
    return text[:room - 1].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def bluesky_post(text, url):
    from atproto import Client, client_utils
    need("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    client = Client()
    client.login(os.environ["BLUESKY_HANDLE"], os.environ["BLUESKY_APP_PASSWORD"])
    room = 300 - len(url) - 1
    tb = client_utils.TextBuilder().text(fit(text, room) + " ").link(url, url)
    return client.send_post(tb).uri


def mastodon_post(text, url):
    from mastodon import Mastodon
    need("MASTODON_URL", "MASTODON_TOKEN")
    m = Mastodon(access_token=os.environ["MASTODON_TOKEN"], api_base_url=os.environ["MASTODON_URL"])
    return m.status_post(f"{text}\n\n{url}", language="es")["url"]


def x_intents(c, url):
    """Un enlace por tweet del hilo; el primero lleva la URL del episodio."""
    tweets = list(c["hilo_x"])
    tweets[0] = f"{tweets[0]} {url}"
    return ["https://x.com/intent/post?text=" + urllib.parse.quote(t) for t in tweets]


def ig_call(method, path, **params):
    data = urllib.parse.urlencode(params).encode() if method == "POST" else None
    query = "" if method == "POST" else "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{IG_API}/{path}{query}", data=data,
                                                           method=method), timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Instagram API {path}: {e.code} {e.read().decode()[:300]}")


def ig_token():
    """Token de larga duración (60 días); se renueva en cada uso y se guarda fuera del proyecto."""
    f = CONFIG_DIR / "instagram_token"
    token = f.read_text().strip() if f.exists() else os.environ.get("INSTAGRAM_TOKEN", "")
    if not token:
        raise SystemExit(f"Falta INSTAGRAM_TOKEN en {ROOT / '.env'}")
    try:
        with urllib.request.urlopen("https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
                {"grant_type": "ig_refresh_token", "access_token": token}), timeout=60) as r:
            token = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        # solo se puede renovar pasadas 24 h desde la emisión; si no, se usa el actual
        print(f"  (no se pudo renovar el token de Instagram: {e.code})")
    f.write_text(token)
    f.chmod(0o600)
    return token


def host_clips(out, slug, clips):
    """Los Reels deben estar en una URL pública: se alojan en site/media/ (GitHub Pages)."""
    from publish import SITE
    dest = SITE / "media" / slug
    dest.mkdir(parents=True, exist_ok=True)
    for n in clips:
        shutil.copy(out / "clips" / f"clip{n}.mp4", dest / f"clip{n}.mp4")
    git = ["git", "-C", str(SITE)]
    subprocess.run([*git, "add", "media"], check=True)
    subprocess.run([*git, "commit", "-m", f"Clips: {slug}"], check=True)
    subprocess.run([*git, "push"], check=True)


def wait_public(url, tries=30):
    """GitHub Pages tarda 1-2 min en publicar; Meta necesita un 200 con vídeo."""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200 and "video" in r.headers.get("Content-Type", ""):
                    return
        except urllib.error.URLError:
            pass
        time.sleep(15)
    raise SystemExit(f"{url} no está público tras {tries * 15} s")


def instagram_reel(token, user_id, video_url, caption):
    c = ig_call("POST", f"{user_id}/media", media_type="REELS", video_url=video_url,
                caption=caption, access_token=token)["id"]
    for _ in range(10):  # la doc pide consultar 1 vez por minuto, máx. 5 min; margen para vídeos largos
        time.sleep(30)
        status = ig_call("GET", c, fields="status_code", access_token=token)["status_code"]
        if status == "FINISHED":
            return ig_call("POST", f"{user_id}/media_publish", creation_id=c, access_token=token)["id"]
        if status in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram: el contenedor {c} terminó en {status}")
    raise SystemExit(f"Instagram: el contenedor {c} sigue procesándose; reintenta más tarde")


def hashtags(c, n=3):
    return " ".join("#" + "".join(w.capitalize() for w in t.split()) for t in c["tags"][:n])


def run(root, stem, url, only, dry):
    """url = URL pública de la entrada de blog del episodio."""
    load_env()
    out = Path(root) / "out" / stem
    c = json.loads((out / "contenido.json").read_text())
    state_f = out / "publicado.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {}
    short = f"{c['resumen_corto']} {hashtags(c)}"

    def save():
        if not dry:
            state_f.write_text(json.dumps(state, indent=1))

    if "youtube" in only:
        if dry:
            print(f"[youtube] {c['titulo'][:100]}\n{youtube_description(c, url)}")
            for n, clip in enumerate(c["clips"], 1):
                print(f"[youtube short {n}] {clip['titulo'][:90]} #Shorts")
        else:
            yt = youtube_service()
            if "youtube" not in state:
                state["youtube"] = youtube_upload(yt, out / "episodio.mov", c["titulo"],
                                                  youtube_description(c, url), c["tags"])
                save()
            shorts = state.setdefault("shorts", {})
            for n, clip in enumerate(c["clips"], 1):
                if str(n) not in shorts:
                    shorts[str(n)] = youtube_upload(
                        yt, out / "clips" / f"clip{n}.mp4", f"{clip['titulo'][:90]} #Shorts",
                        f"{clip['gancho']}\n\nEpisodio completo: {url}\n#Shorts", c["tags"])
                    save()
            print("  YouTube: subido en PRIVADO; publícalo en studio.youtube.com (o tras la auditoría)")
    if "bluesky" in only:
        if dry:
            print(f"[bluesky] {fit(short, 300 - len(url) - 1)} {url}")
        elif "bluesky" not in state:
            state["bluesky"] = bluesky_post(short, url)
            save()
    if "mastodon" in only:
        if dry:
            print(f"[mastodon] {short}\n\n{url}")
        elif "mastodon" not in state:
            state["mastodon"] = mastodon_post(short, url)
            save()
    if "instagram" in only:
        ready = [n for n in range(1, len(c["clips"]) + 1) if (out / "clips" / f"clip{n}.mp4").exists()
                 and str(n) not in state.get("instagram", {})]
        slug = url.rsplit("/", 1)[1].removesuffix(".html")
        base = url.rsplit("/episodios/", 1)[0] + f"/media/{slug}"
        captions = {n: f"{c['clips'][n - 1]['gancho']}\n\nEpisodio completo: enlace en la bio\n{hashtags(c, 5)}"
                    for n in ready}
        if dry:
            for n in ready:
                print(f"[instagram reel {n}] {base}/clip{n}.mp4\n{captions[n]}")
        elif ready:
            need("INSTAGRAM_USER_ID")
            token = ig_token()
            host_clips(out, slug, ready)
            done = state.setdefault("instagram", {})
            for n in ready:
                wait_public(f"{base}/clip{n}.mp4")
                done[str(n)] = instagram_reel(token, os.environ["INSTAGRAM_USER_ID"],
                                              f"{base}/clip{n}.mp4", captions[n])
                save()
    if "x" in only:
        print("[x] abre cada enlace y pulsa Publicar:")
        for link in x_intents(c, url):
            print("  " + link)
