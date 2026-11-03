import json

import pytest

from conftest import make_cfg
from spiral import destinations
from spiral.destinations import Result, discover, site
from spiral.destinations.base import Network, Pending
from spiral.errors import SpiralError
from spiral.workspace import DONE, read_state

CONTENT = {"titulo": "Prueba", "resumen_corto": "corto", "resumen_largo": "l", "capitulos": [],
           "tags": ["radio"], "hilo_x": ["t"], "post_blog_md": "x", "clips": []}
SITE_ENV = {"SITE_URL": "https://e.github.io/p", "PODCAST_TITLE": "T", "PODCAST_DESCRIPTION": "d",
            "PODCAST_AUTHOR": "a", "PODCAST_EMAIL": "a@e.com", "PODCAST_CATEGORY": "Society & Culture",
            "IA_ACCESS_KEY": "k", "IA_SECRET_KEY": "s"}


@pytest.fixture(autouse=True)
def no_archive_lookup(monkeypatch):
    """Nada de red: por defecto Archive.org «no tiene» el mp3."""
    monkeypatch.setattr(site, "already_uploaded", lambda identifier, mp3: False)


def episode(work, name="a"):
    d = work / "processed" / name
    d.mkdir(parents=True)
    (d / "contenido.json").write_text(json.dumps(CONTENT))
    (d / DONE).write_text("{}")
    return d


def fake_network(calls, fail=(), key="bluesky"):
    def pub(ctx):
        calls.append(ctx.account)
        ctx.secrets.add("SECRETO-123456")
        if ctx.account in fail:
            raise RuntimeError("boom SECRETO-123456")
        return f"ref-{ctx.account}"
    return Network(key, "Fake", pub, lambda ctx: f"[{key}/{ctx.account}] texto", required=("HANDLE", "APP_PASSWORD"))


@pytest.fixture
def two_accounts(work, monkeypatch):
    calls = []
    monkeypatch.setattr(destinations, "NETWORKS", (fake_network(calls, fail=("malo",)),))
    values = dict(SITE_ENV, BLUESKY_ACCOUNTS="programa,personal,malo",
                  BLUESKY_PROGRAMA_HANDLE="h", BLUESKY_PROGRAMA_APP_PASSWORD="pass-programa",
                  BLUESKY_PERSONAL_HANDLE="h2", BLUESKY_PERSONAL_APP_PASSWORD="pass-personal",
                  BLUESKY_MALO_HANDLE="h3", BLUESKY_MALO_APP_PASSWORD="pass-malo")
    episode(work)
    return make_cfg(work, **values), calls


def test_two_accounts_are_distinct_destinations(two_accounts):
    cfg, _ = two_accounts
    ids = [d.id for d in discover(cfg)]
    assert "bluesky/programa" in ids and "bluesky/personal" in ids


def test_incomplete_account_names_missing_variable(work, monkeypatch):
    monkeypatch.setattr(destinations, "NETWORKS", (fake_network([]),))
    cfg = make_cfg(work, **SITE_ENV, BLUESKY_ACCOUNTS="programa", BLUESKY_PROGRAMA_HANDLE="h")
    d = next(d for d in discover(cfg) if d.id == "bluesky/programa")
    assert not d.configured and d.missing == ("BLUESKY_PROGRAMA_APP_PASSWORD",)


def test_account_only_in_local_env_is_offered(work, monkeypatch):
    monkeypatch.setattr(destinations, "NETWORKS", (fake_network([]),))
    cfg = make_cfg(work, **SITE_ENV, BLUESKY_ACCOUNTS="a,b", BLUESKY_A_HANDLE="1", BLUESKY_A_APP_PASSWORD="2",
                   BLUESKY_B_HANDLE="3", BLUESKY_B_APP_PASSWORD="4")
    assert {"bluesky/a", "bluesky/b"} <= {d.id for d in discover(cfg)}


def test_site_missing_names_variables(work):
    d = discover(make_cfg(work))[0]
    assert d.id == "site" and "SITE_URL" in d.missing


def test_unconfigured_or_unknown_destination_is_rejected(two_accounts):
    cfg, _ = two_accounts
    with pytest.raises(SpiralError, match="desconocido"):
        destinations.publish(cfg, "a", ["nada/x"])
    cfg2 = make_cfg(cfg.root, **{k: v for k, v in cfg.values.items() if k != "BLUESKY_PROGRAMA_APP_PASSWORD"})
    with pytest.raises(SpiralError, match="BLUESKY_PROGRAMA_APP_PASSWORD"):
        destinations.publish(cfg2, "a", ["bluesky/programa"])


def test_pending_episode_cannot_be_published(work):
    (work / "a.mov").write_bytes(b"x")
    with pytest.raises(SpiralError, match="no está procesado"):
        destinations.publish(make_cfg(work), "a", ["site"])


def test_partial_failure_is_isolated_and_recorded(two_accounts):
    cfg, calls = two_accounts
    res = destinations.publish(cfg, "a", ["bluesky/malo", "bluesky/programa"], log=lambda m: None)
    by = {r.id: r.status for r in res}
    assert by == {"bluesky/malo": "failed", "bluesky/programa": "ok"}
    state = read_state(cfg.root / "published" / "a")["destinations"]
    assert state["bluesky/programa"]["done"] and "bluesky/malo" not in state


def test_republishing_is_skipped(two_accounts):
    cfg, calls = two_accounts
    destinations.publish(cfg, "a", ["bluesky/programa"], log=lambda m: None)
    res = destinations.publish(cfg, "a", ["bluesky/programa"], log=lambda m: None)
    assert res[0].status == "skipped" and calls == ["programa"]


def test_dry_run_touches_nothing(two_accounts):
    cfg, calls = two_accounts
    out = []
    res = destinations.publish(cfg, "a", ["bluesky/programa"], dry=True, log=out.append)
    assert res[0].status == "simulated" and calls == [] and any("texto" in m for m in out)
    assert not (cfg.root / "published").exists()


def test_log_never_contains_secrets(two_accounts):
    cfg, _ = two_accounts
    shown = []
    destinations.publish(cfg, "a", ["bluesky/malo"], log=shown.append)
    text = (cfg.root / "published" / "a" / "publish.log").read_text()
    assert "failed" in text and "SECRETO-123456" not in text and "pass-malo" not in text
    assert all("SECRETO-123456" not in m for m in shown)


def test_manual_destination_only_recorded_if_confirmed(work, monkeypatch):
    def pub(ctx):
        if ctx.ask("manual", "¿hecho?"):
            return {"manual": True}
        raise Pending("sin confirmar")
    monkeypatch.setattr(destinations, "NETWORKS", (Network("x", "X", pub, lambda c: "", manual=True),))
    cfg = make_cfg(work, **SITE_ENV, X_ACCOUNTS="programa")
    episode(work)
    no = destinations.publish(cfg, "a", ["x/programa"], log=lambda m: None, ask=lambda k, q: False)
    assert no[0].status == "pending" and not (work / "published" / "a" / "state.json").exists()
    yes = destinations.publish(cfg, "a", ["x/programa"], log=lambda m: None, ask=lambda k, q: True)
    assert yes[0].status == "ok"
    assert read_state(work / "published" / "a")["destinations"]["x/programa"]["mode"] == "manual"


def test_site_failure_blocks_dependents(two_accounts, monkeypatch):
    cfg, calls = two_accounts
    monkeypatch.setattr(site, "publish", lambda ctx: (_ for _ in ()).throw(SpiralError("sin red")))
    res = destinations.publish(cfg, "a", ["bluesky/programa", "site"], log=lambda m: None)
    assert {r.id: r.status for r in res} == {"site": "failed", "bluesky/programa": "not-attempted"}
    assert calls == []


def test_checkpoint_keeps_partial_progress(work, monkeypatch):
    def pub(ctx):
        ctx.partial["video"] = "v1"
        ctx.checkpoint(ctx.partial)
        raise RuntimeError("se cayó")
    monkeypatch.setattr(destinations, "NETWORKS", (Network("bluesky", "B", pub, lambda c: ""),))
    cfg = make_cfg(work, **SITE_ENV, BLUESKY_ACCOUNTS="p")
    episode(work)
    destinations.publish(cfg, "a", ["bluesky/p"], log=lambda m: None)
    info = read_state(work / "published" / "a")["destinations"]["bluesky/p"]
    assert info == {"done": False, "partial": {"video": "v1"}}


def test_site_publish_creates_scaffold_post_feed_without_overwriting(work, monkeypatch):
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("hola\nmundo")
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: None)
    monkeypatch.setattr(site, "duration", lambda p: 61)
    (work / "site").mkdir()
    (work / "site" / "index.md").write_text("mío")
    cfg = make_cfg(work, **SITE_ENV)
    res = destinations.publish(cfg, "a", ["site"], log=lambda m: None)
    assert res[0].status == "ok"
    s = work / "site"
    assert (s / "index.md").read_text() == "mío" and (s / "_config.yml").exists()
    assert len(list((s / "_posts").glob("*.md"))) == 1
    feed = (s / "feed.xml").read_text()
    assert "<itunes:duration>0:01:01</itunes:duration>" in feed and "archive.org/download" in feed


def test_site_without_git_repo_does_not_push(work, monkeypatch):
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("x")
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: None)
    monkeypatch.setattr(site, "duration", lambda p: 1)
    pushed = []
    monkeypatch.setattr(site, "git_publish", lambda *a: pushed.append(1))
    logs = []
    destinations.publish(make_cfg(work, **SITE_ENV), "a", ["site"], log=logs.append, ask=lambda k, q: True)
    assert not pushed and any("no es un repositorio git" in m for m in logs)


def pod_of(work, **extra):
    return make_cfg(work, **SITE_ENV | extra)


def test_site_url_must_be_the_pages_address_not_the_repo(work):
    from spiral.errors import SpiralError
    for bad in ("https://github.com/u/r.git", "https://github.com/u/r"):
        with pytest.raises(SpiralError, match="GitHub Pages"):
            pod_of(work, SITE_URL=bad).podcast()


def test_cover_from_a_file_inside_site_gets_the_pages_url(work):
    (work / "site" / "img").mkdir(parents=True)
    (work / "site" / "img" / "logo.jpeg").write_bytes(b"x")
    cfg = pod_of(work, PODCAST_IMAGE="site/img/logo.jpeg")
    assert site.cover_url(cfg, cfg.podcast()) == "https://e.github.io/p/img/logo.jpeg"


def test_cover_from_a_file_outside_site_is_copied_into_it(work):
    (work / "logo.PNG").write_bytes(b"x")
    cfg = pod_of(work, PODCAST_IMAGE="logo.PNG")
    assert site.cover_url(cfg, cfg.podcast()) == "https://e.github.io/p/cover.png"
    assert (work / "site" / "cover.png").read_bytes() == b"x"


def test_cover_url_is_kept_and_a_missing_file_is_an_error(work):
    from spiral.errors import SpiralError
    cfg = pod_of(work, PODCAST_IMAGE="https://x.org/c.jpg")
    assert site.cover_url(cfg, cfg.podcast()) == "https://x.org/c.jpg"
    cfg = pod_of(work, PODCAST_IMAGE="nada.jpg")
    with pytest.raises(SpiralError, match="no existe"):
        site.cover_url(cfg, cfg.podcast())


def test_feed_has_managing_editor_and_owner_email(work):
    (work / "site").mkdir()
    (work / "site" / "episodes").mkdir()
    site.build_feed(work / "site", pod_of(work).podcast())
    feed = (work / "site" / "feed.xml").read_text()
    assert "<managingEditor>a@e.com (a)</managingEditor>" in feed and "<itunes:email>a@e.com</itunes:email>" in feed


def test_force_republishes_what_is_already_done(work, monkeypatch):
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("x")
    uploads = []
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: uploads.append(1))
    monkeypatch.setattr(site, "duration", lambda p: 1)
    cfg = make_cfg(work, **SITE_ENV)
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "ok"
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "skipped"
    assert destinations.publish(cfg, "a", ["site"], force=True, log=lambda m: None)[0].status == "ok"
    assert len(uploads) == 2


def published_site(work, monkeypatch):
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("x")
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: None)
    monkeypatch.setattr(site, "duration", lambda p: 1)
    cfg = make_cfg(work, **SITE_ENV)
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "ok"
    return cfg


def test_unpublish_site_removes_post_entry_and_feed_item(work, monkeypatch):
    cfg = published_site(work, monkeypatch)
    s = work / "site"
    assert list((s / "_posts").glob("*.md")) and "<item>" in (s / "feed.xml").read_text()
    res = destinations.unpublish(cfg, "a", ["site"], log=lambda m: None)
    assert res[0].status == "removed"
    assert not list((s / "_posts").glob("*.md")) and not list((s / "episodes").glob("*.json"))
    assert "<item>" not in (s / "feed.xml").read_text()
    assert not destinations.Workspace(cfg).episode("a").done_destinations      # se puede volver a publicar
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "ok"


def test_unpublish_dry_run_and_not_published_touch_nothing(work, monkeypatch):
    cfg = published_site(work, monkeypatch)
    assert destinations.unpublish(cfg, "a", ["site"], dry=True, log=lambda m: None)[0].status == "simulated"
    assert list((work / "site" / "_posts").glob("*.md")) and destinations.Workspace(cfg).episode("a").done_destinations
    destinations.unpublish(cfg, "a", ["site"], log=lambda m: None)
    assert destinations.unpublish(cfg, "a", ["site"], log=lambda m: None)[0].status == "skipped"


def test_unpublish_network_deletes_through_its_handler(work, monkeypatch):
    from dataclasses import replace
    from spiral.destinations import bluesky
    from spiral.workspace import write_state
    episode(work)
    cfg = make_cfg(work, **SITE_ENV, BLUESKY_ACCOUNTS="p", BLUESKY_P_HANDLE="h", BLUESKY_P_APP_PASSWORD="s3cret")
    write_state(work / "published" / "a", {"destinations": {"bluesky/p": {"done": True, "ref": "at://x/1"}}})
    deleted = []
    fake = replace(bluesky.NETWORK, unpublish=lambda ctx, ref: deleted.append(ref))
    monkeypatch.setattr(destinations, "NETWORKS", tuple(fake if n.key == "bluesky" else n for n in destinations.NETWORKS))
    res = destinations.unpublish(cfg, "a", ["bluesky/p"], log=lambda m: None)
    assert res[0].status == "removed" and deleted == ["at://x/1"]
    assert read_state(work / "published" / "a")["destinations"] == {}


def test_unpublish_manual_network_needs_confirmation_to_forget(work):
    from spiral.workspace import write_state
    episode(work)
    cfg = make_cfg(work, **SITE_ENV, X_ACCOUNTS="p")
    write_state(work / "published" / "a", {"destinations": {"x/p": {"done": True, "ref": {"manual": True}}}})
    assert destinations.unpublish(cfg, "a", ["x/p"], log=lambda m: None)[0].status == "manual"
    assert read_state(work / "published" / "a")["destinations"]["x/p"]["done"]
    res = destinations.unpublish(cfg, "a", ["x/p"], log=lambda m: None, ask=lambda k, q: k == "forget")
    assert res[0].status == "removed" and read_state(work / "published" / "a")["destinations"] == {}


def test_mastodon_url_is_reduced_to_the_instance_root():
    from spiral.destinations.mastodon import instance
    assert instance("https://mastodon.social/@lacalleespiral") == "https://mastodon.social"
    assert instance("mastodon.social/") == "https://mastodon.social"
    assert instance("https://mstdn.example:8443") == "https://mstdn.example:8443"


def test_youtube_rejects_a_web_oauth_client(work):
    from spiral.destinations import youtube
    secret = work / "cs.json"
    cfg = make_cfg(work, YOUTUBE_ACCOUNTS="c", YOUTUBE_C_CLIENT_SECRET=str(secret))
    secret.write_text(json.dumps({"web": {"client_id": "x"}}))
    assert "Aplicación de escritorio" in youtube.check(cfg, "c")[0]
    secret.write_text(json.dumps({"installed": {"client_id": "x"}}))
    assert youtube.check(cfg, "c") == []


def test_youtube_asks_again_when_the_stored_authorization_has_expired(work, monkeypatch):
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    import googleapiclient.discovery
    from spiral.destinations import base, youtube

    class Expired:
        valid, refresh_token = False, "r"

        def refresh(self, request):
            raise RefreshError("invalid_grant")

    class Fresh:
        valid = True

        def to_json(self):
            return "{}"

    class Flow:
        def run_local_server(self, port):
            return Fresh()

    token = base.token_path("youtube", "c")
    token.parent.mkdir(parents=True)
    token.write_text("{}")
    monkeypatch.setattr(Credentials, "from_authorized_user_file", classmethod(lambda cls, *a: Expired()))
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file", classmethod(lambda cls, *a: Flow()))
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *a, **k: "yt")
    logs = []
    ctx = base.Context(cfg=make_cfg(work, YOUTUBE_ACCOUNTS="c"), ep=None, content={}, key="youtube", account="c",
                       url=None, log=logs.append, ask=lambda k, q: True)
    assert youtube.service(ctx) == "yt"
    assert any("caducado" in m for m in logs)


def showcase_cfg(work, monkeypatch, **extra):
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("x")
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: None)
    monkeypatch.setattr(site, "duration", lambda p: 1)
    return make_cfg(work, **SITE_ENV | extra)


def test_site_publish_adds_the_publication_badges_to_post_and_listing(work, monkeypatch):
    from spiral.destinations import showcase
    from spiral.workspace import read_state, write_state
    cfg = showcase_cfg(work, monkeypatch, BLUESKY_ACCOUNTS="p", X_ACCOUNTS="p")
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "ok"
    post = next((work / "site" / "_posts").glob("*.md"))
    assert showcase.START + showcase.END in post.read_text()               # sin redes todavía: bloque vacío
    state = read_state(work / "published" / "a")
    state["destinations"] |= {"bluesky/p": {"done": True, "ref": "at://did:plc:abc/app.bsky.feed.post/3k"},
                              "x/p": {"done": True, "ref": {"manual": True}},
                              "youtube/c": {"done": True, "ref": {"video": "VID", "shorts": {}}}}
    write_state(work / "published" / "a", state)
    showcase.refresh(cfg, lambda m: None, lambda k, q: False)
    text = post.read_text()
    assert "https://bsky.app/profile/did:plc:abc/post/3k" in text and "watch?v=VID" in text
    assert 'class="sp-badge sp-nolink"' in text and "relative_url" in text      # X no tiene enlace
    assert text.index("<audio") < text.index(showcase.START) < text.index("## Capítulos")
    listing = (work / "site" / "index.md").read_text()
    assert "layout: default" in listing and "bsky.app" in listing and "feed.xml" in listing
    assert "<time>" in listing and "<h2><a href=" in listing
    assert (work / "site" / "img" / "redes" / "youtube.svg").read_text().startswith('<svg fill="#FF0000"')
    assert (work / "site" / "assets" / "main.scss").read_text().count("@import") == 2
    assert ".sp-badge" in (work / "site" / "_sass" / "spiral.scss").read_text()


def test_unpublishing_a_network_removes_its_badge(work, monkeypatch):
    from spiral.workspace import read_state, write_state
    cfg = showcase_cfg(work, monkeypatch, MASTODON_ACCOUNTS="p", MASTODON_P_URL="https://m.s", MASTODON_P_TOKEN="t")
    destinations.publish(cfg, "a", ["site"], log=lambda m: None)
    state = read_state(work / "published" / "a")
    state["destinations"]["mastodon/p"] = {"done": True, "ref": "https://m.s/@u/123"}
    write_state(work / "published" / "a", state)
    from spiral.destinations import showcase
    showcase.refresh(cfg, lambda m: None, lambda k, q: False)
    post = next((work / "site" / "_posts").glob("*.md"))
    assert "https://m.s/@u/123" in post.read_text()
    state = read_state(work / "published" / "a")
    del state["destinations"]["mastodon/p"]
    write_state(work / "published" / "a", state)
    showcase.refresh(cfg, lambda m: None, lambda k, q: False)
    assert "https://m.s/@u/123" not in post.read_text()


def test_logo_from_env_becomes_part_of_the_site_and_main_scss_is_not_overwritten(work, monkeypatch):
    from spiral.destinations import showcase
    (work / "site" / "img").mkdir(parents=True)
    (work / "site" / "img" / "logo.jpeg").write_bytes(b"x")
    (work / "site" / "assets").mkdir()
    (work / "site" / "assets" / "main.scss").write_text("mío")
    logs = []
    cfg = showcase_cfg(work, monkeypatch, PODCAST_IMAGE="site/img/logo.jpeg")
    destinations.publish(cfg, "a", ["site"], log=logs.append)
    css = (work / "site" / "_sass" / "spiral.scss").read_text()
    assert 'url("../img/logo.jpeg")' in css and ".site-title::before" in css
    assert (work / "site" / "assets" / "main.scss").read_text() == "mío"
    assert any("@import" in m for m in logs)
    cfg = make_cfg(work, **SITE_ENV)
    showcase.refresh(cfg, lambda m: None, lambda k, q: False)
    assert ".site-title::before" not in (work / "site" / "_sass" / "spiral.scss").read_text()


def test_ref_url_ignores_unknown_shapes():
    from spiral.destinations.showcase import ref_url
    assert ref_url("bluesky", "algo raro") is None and ref_url("youtube", "VID") is None
    assert ref_url("mastodon", {"x": 1}) is None and ref_url("instagram", {"reels": {}}) is None


def test_mp3_is_not_uploaded_again_when_archive_already_has_it_unchanged(work, monkeypatch):
    import hashlib
    import internetarchive
    d = episode(work)
    (d / "episodio.mp3").write_bytes(b"mp3")
    (d / "transcripcion.txt").write_text("x")
    uploads = []
    remote = {"md5": hashlib.md5(b"mp3").hexdigest()}

    class Item:
        def get_file(self, name):
            return type("F", (), remote)()
    monkeypatch.undo()                                   # quita el stub autouse para probar la función real
    monkeypatch.setattr(site, "upload_archive", lambda *a, **k: uploads.append(1))
    monkeypatch.setattr(site, "duration", lambda p: 1)
    monkeypatch.setattr(internetarchive, "get_item", lambda identifier: Item())
    cfg = make_cfg(work, **SITE_ENV)
    assert destinations.publish(cfg, "a", ["site"], log=lambda m: None)[0].status == "ok"
    assert uploads == []                                  # mismo MD5: no se sube
    remote["md5"] = "otro"
    assert destinations.publish(cfg, "a", ["site"], force=True, log=lambda m: None)[0].status == "ok"
    assert len(uploads) == 1                              # el mp3 cambió: se sube
    monkeypatch.setattr(internetarchive, "get_item", lambda identifier: (_ for _ in ()).throw(OSError("sin red")))
    assert site.already_uploaded("x", work / "processed" / "a" / "episodio.mp3") is False


def test_index_is_the_episode_list_and_a_custom_index_is_left_alone(work, monkeypatch):
    from spiral.destinations import showcase
    cfg = showcase_cfg(work, monkeypatch)
    (work / "site").mkdir()
    (work / "site" / "index.md").write_text("---\nlayout: home\n---\n")            # el de ensure_scaffold
    (work / "site" / "publicaciones.md").write_text("---\npermalink: /publicaciones.html\n---\n")
    destinations.publish(cfg, "a", ["site"], log=lambda m: None)
    index = (work / "site" / "index.md").read_text()
    assert showcase.INDEX_MARK in index and "<article" in index and "sp-lead" in index
    assert not (work / "site" / "publicaciones.md").exists()            # la página antigua de spiral se retira
    logs = []
    (work / "site" / "index.md").write_text("mi portada")
    showcase.refresh(cfg, logs.append, lambda k, q: False)
    assert (work / "site" / "index.md").read_text() == "mi portada" and any("index.md es tuyo" in m for m in logs)
