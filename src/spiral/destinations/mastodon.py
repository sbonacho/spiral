from ..errors import SpiralError
from ..i18n import _
from .base import Network, short_text


def preview(ctx):
    return f"[mastodon/{ctx.account}] {short_text(ctx.content)}\n\n{ctx.url}"


def login(ctx):
    from mastodon import Mastodon
    token = ctx.field("TOKEN")
    ctx.secrets.add(token)
    return Mastodon(access_token=token, api_base_url=ctx.field("URL"))


def publish(ctx):
    client = login(ctx)
    return client.status_post(f"{short_text(ctx.content)}\n\n{ctx.url}", language=ctx.cfg.language)["url"]


def unpublish(ctx, ref):
    status_id = str(ref).rstrip("/").rsplit("/", 1)[-1]   # la URL del estado acaba en su id
    if not status_id.isdigit():
        raise SpiralError(_("No puedo sacar el id del estado de {ref}: bórralo a mano.", ref=ref))
    login(ctx).status_delete(status_id)


NETWORK = Network("mastodon", "Mastodon", publish, preview, required=("URL", "TOKEN"), unpublish=unpublish)
