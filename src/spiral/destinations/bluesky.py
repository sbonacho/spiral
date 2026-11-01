from .base import Network, fit, short_text


def preview(ctx):
    return f"[bluesky/{ctx.account}] {fit(short_text(ctx.content), 300 - len(ctx.url) - 1)} {ctx.url}"


def publish(ctx):
    from atproto import Client, client_utils
    client = Client()
    password = ctx.field("APP_PASSWORD")
    ctx.secrets.add(password)
    client.login(ctx.field("HANDLE"), password)
    room = 300 - len(ctx.url) - 1
    tb = client_utils.TextBuilder().text(fit(short_text(ctx.content), room) + " ").link(ctx.url, ctx.url)
    return client.send_post(tb).uri


NETWORK = Network("bluesky", "Bluesky", publish, preview, required=("HANDLE", "APP_PASSWORD"))
