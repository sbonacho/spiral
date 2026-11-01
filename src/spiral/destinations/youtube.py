"""YouTube: episodio completo y Shorts (siempre en privado hasta que publiques en Studio)."""
from pathlib import Path

from ..config import global_dir
from ..errors import SpiralError
from ..i18n import _
from .base import Network, read_token, write_token

SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]


def secret_path(cfg, account):
    custom = cfg.field("youtube", account, "CLIENT_SECRET")
    return Path(custom).expanduser() if custom else global_dir() / "client_secret.json"


def check(cfg, account):
    return [] if secret_path(cfg, account).is_file() else [f"client_secret.json ({secret_path(cfg, account)})"]


def mmss(s):
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}" if s >= 3600 else f"{s // 60}:{s % 60:02}"


def description(content, url):
    """Capítulos de YouTube: el primero en 0:00 y con el desplazamiento de la intro."""
    off = content.get("offset_intro", 0)
    lines = [f"{mmss(x['inicio'] + off)} {x['titulo']}" for x in content["capitulos"]]
    if off and content["capitulos"][0]["inicio"] + off > 0:
        lines.insert(0, "0:00 Intro")
    text = f"{content['resumen_largo']}\n\nChapters:\n" + "\n".join(lines) + f"\n\n{url}"
    return text.replace("<", "").replace(">", "")


def service(ctx):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from .base import token_path
    path = token_path("youtube", ctx.account)
    creds = Credentials.from_authorized_user_file(str(path), SCOPE) if path.is_file() else None
    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            creds.refresh(Request())
        else:
            ctx.log(_("  se abre el navegador para autorizar YouTube…"))
            creds = InstalledAppFlow.from_client_secrets_file(
                str(secret_path(ctx.cfg, ctx.account)), SCOPE).run_local_server(port=0)
        write_token("youtube", ctx.account, creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(ctx, yt, path, title, desc, tags):
    from googleapiclient.http import MediaFileUpload
    body = {"snippet": {"title": title[:100], "description": desc, "tags": tags[:15],
                        "categoryId": "22", "defaultLanguage": ctx.cfg.language},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            ctx.log(_("    subiendo {pct}%", pct=int(status.progress() * 100)))
    return resp["id"]


def preview(ctx):
    c = ctx.content
    shorts = "\n".join(f"[youtube short {n}] {clip['titulo'][:90]} #Shorts"
                       for n, clip in enumerate(c["clips"], 1))
    return f"[youtube/{ctx.account}] {c['titulo'][:100]}\n{description(c, ctx.url)}\n{shorts}"


def publish(ctx):
    c, ep = ctx.content, ctx.ep
    if not ctx.url:
        raise SpiralError(_("Falta SITE_URL."))
    yt = service(ctx)
    state = ctx.partial
    if "video" not in state:
        state["video"] = upload(ctx, yt, ep.dir / "episodio.mov", c["titulo"], description(c, ctx.url), c["tags"])
        ctx.checkpoint(state)
    shorts = state.setdefault("shorts", {})
    for n, clip in enumerate(c["clips"], 1):
        if str(n) not in shorts:
            shorts[str(n)] = upload(ctx, yt, ep.dir / "clips" / f"clip{n}.mp4", f"{clip['titulo'][:90]} #Shorts",
                                    f"{clip['gancho']}\n\n{ctx.url}\n#Shorts", c["tags"])
            ctx.checkpoint(state)
    ctx.log(_("  YouTube: subido en PRIVADO; publícalo en studio.youtube.com (o tras la auditoría de la API)"))
    return dict(state)


NETWORK = Network("youtube", "YouTube (episodio y Shorts)", publish, preview, check=check)
