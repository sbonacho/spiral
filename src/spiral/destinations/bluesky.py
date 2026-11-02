from .base import Network, fit, short_text


def preview(ctx):
    return f"[bluesky/{ctx.account}] {fit(short_text(ctx.content), 300 - len(ctx.url) - 1)} {ctx.url}"


def login(ctx):
    from atproto import Client
    client = Client()
    password = ctx.field("APP_PASSWORD")
    ctx.secrets.add(password)
    client.login(ctx.field("HANDLE"), password)
    return client


def publish(ctx):
    from atproto import client_utils
    client = login(ctx)
    room = 300 - len(ctx.url) - 1
    tb = client_utils.TextBuilder().text(fit(short_text(ctx.content), room) + " ").link(ctx.url, ctx.url)
    return client.send_post(tb).uri


def unpublish(ctx, ref):
    login(ctx).delete_post(ref)


NETWORK = Network("bluesky", "Bluesky", publish, preview, required=("HANDLE", "APP_PASSWORD"), unpublish=unpublish)
