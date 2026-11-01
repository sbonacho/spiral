"""Instagram Reels vía Graph API. Los vídeos deben estar en una URL pública: se alojan en site/media/."""
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

from ..errors import SpiralError
from ..i18n import _
from .base import Network, hashtags, read_token, token_path, write_token
from .site import git_publish, is_own_repo

API = "https://graph.instagram.com/v26.0"


def check(cfg, account):
    if cfg.field("instagram", account, "TOKEN") or token_path("instagram", account).is_file():
        return []
    return [f"INSTAGRAM_{account.upper()}_TOKEN"]


def call(method, path, **params):
    data = urllib.parse.urlencode(params).encode() if method == "POST" else None
    query = "" if method == "POST" else "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(f"{API}/{path}{query}", data=data, method=method)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SpiralError(_("Instagram API {path}: {code} {body}", path=path, code=e.code, body=e.read().decode()[:300])) from e


def token(ctx):
    """Token de larga duración (60 días): se renueva en cada uso y se guarda en ~/.config/spiral/tokens/."""
    saved = read_token("instagram", ctx.account)
    tok = saved["access_token"] if saved else ctx.field("TOKEN")
    ctx.secrets.add(tok)
    try:
        url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
            {"grant_type": "ig_refresh_token", "access_token": tok})
        with urllib.request.urlopen(url, timeout=60) as r:
            tok = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        ctx.log(_("  (no se pudo renovar el token de Instagram: {code})", code=e.code))  # solo se renueva pasadas 24 h
    ctx.secrets.add(tok)
    write_token("instagram", ctx.account, {"access_token": tok})
    return tok


def wait_public(url, tries=30):
    """GitHub Pages tarda 1-2 min en publicar; Meta necesita un 200 con vídeo."""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200 and "video" in r.headers.get("Content-Type", ""):
                    return
        except urllib.error.URLError:
            pass
        time.sleep(15)
    raise SpiralError(_("{url} no está público tras {seconds} s", url=url, seconds=tries * 15))


def reel(tok, user_id, video_url, caption):
    cid = call("POST", f"{user_id}/media", media_type="REELS", video_url=video_url,
               caption=caption, access_token=tok)["id"]
    for _ in range(10):
        time.sleep(30)
        status = call("GET", cid, fields="status_code", access_token=tok)["status_code"]
        if status == "FINISHED":
            return call("POST", f"{user_id}/media_publish", creation_id=cid, access_token=tok)["id"]
        if status in ("ERROR", "EXPIRED"):
            raise SpiralError(_("Instagram: el contenedor {cid} terminó en {status}", cid=cid, status=status))
    raise SpiralError(_("Instagram: el contenedor {cid} sigue procesándose; reintenta más tarde", cid=cid))


def base_url(ctx):
    slug = ctx.url.rsplit("/", 1)[1].removesuffix(".html")
    return slug, f"{ctx.url.rsplit('/episodios/', 1)[0]}/media/{slug}"


def captions(ctx):
    c = ctx.content
    return {n: f"{clip['gancho']}\n\n{hashtags(c, 5)}" for n, clip in enumerate(c["clips"], 1)
            if (ctx.ep.dir / "clips" / f"clip{n}.mp4").exists()}


def preview(ctx):
    _, base = base_url(ctx)
    return "\n".join(f"[instagram/{ctx.account} reel {n}] {base}/clip{n}.mp4\n{cap}"
                     for n, cap in captions(ctx).items())


def publish(ctx):
    slug, base = base_url(ctx)
    done = ctx.partial.setdefault("clips", {})
    todo = {n: cap for n, cap in captions(ctx).items() if str(n) not in done}
    if not todo:
        return dict(ctx.partial)
    site_dir = ctx.cfg.site_dir
    if not is_own_repo(site_dir):
        raise SpiralError(_("Instagram necesita que site/ sea un repositorio git publicado (GitHub Pages)."))
    tok = token(ctx)
    dest = site_dir / "media" / slug
    dest.mkdir(parents=True, exist_ok=True)
    for n in todo:
        shutil.copy(ctx.ep.dir / "clips" / f"clip{n}.mp4", dest / f"clip{n}.mp4")
    ctx.log(_("  subiendo los clips a site/ para que Meta pueda descargarlos…"))
    git_publish(site_dir, f"Clips: {slug}")
    for n, cap in todo.items():
        wait_public(f"{base}/clip{n}.mp4")
        done[str(n)] = reel(tok, ctx.field("USER_ID"), f"{base}/clip{n}.mp4", cap)
        ctx.checkpoint(ctx.partial)
    return dict(ctx.partial)


NETWORK = Network("instagram", "Instagram (Reels)", publish, preview, required=("USER_ID",), check=check)
