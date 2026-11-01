from .base import Network, short_text


def preview(ctx):
    return f"[mastodon/{ctx.account}] {short_text(ctx.content)}\n\n{ctx.url}"


def publish(ctx):
    from mastodon import Mastodon
    token = ctx.field("TOKEN")
    ctx.secrets.add(token)
    client = Mastodon(access_token=token, api_base_url=ctx.field("URL"))
    return client.status_post(f"{short_text(ctx.content)}\n\n{ctx.url}", language=ctx.cfg.language)["url"]


NETWORK = Network("mastodon", "Mastodon", publish, preview, required=("URL", "TOKEN"))
