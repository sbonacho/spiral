"""X y TikTok no tienen publicación automática: se prepara el contenido y se confirma a mano."""
import subprocess
import urllib.parse

from ..i18n import _
from .base import Network, Pending


def x_links(ctx):
    tweets = list(ctx.content["hilo_x"])
    tweets[0] = f"{tweets[0]} {ctx.url}"
    return ["https://x.com/intent/post?text=" + urllib.parse.quote(t) for t in tweets]


def x_preview(ctx):
    return (_("[x/{account}] abre cada enlace y pulsa Publicar:", account=ctx.account) + "\n"
            + "\n".join(f"  {u}" for u in x_links(ctx)))


def x_publish(ctx):
    ctx.log(x_preview(ctx))
    if ctx.ask("manual", _("¿Ya has publicado el hilo en x/{account}? Se anotará como publicado", account=ctx.account)):
        return {"manual": True}
    raise Pending(_("sin confirmar"))


def tiktok_preview(ctx):
    return _("[tiktok/{account}] sube a mano los clips de {path}", account=ctx.account, path=ctx.ep.dir / "clips")


def tiktok_publish(ctx):
    ctx.log(tiktok_preview(ctx))
    subprocess.run(["open", str(ctx.ep.dir / "clips")])
    if ctx.ask("manual", _("¿Ya has subido los clips a tiktok/{account}? Se anotará como publicado", account=ctx.account)):
        return {"manual": True}
    raise Pending(_("sin confirmar"))


X = Network("x", "X (enlaces; publicas tú)", x_publish, x_preview, manual=True)
TIKTOK = Network("tiktok", "TikTok (subida a mano)", tiktok_publish, tiktok_preview, manual=True, needs_url=False)
