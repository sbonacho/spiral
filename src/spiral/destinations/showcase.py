"""Escaparate del sitio: tras publicar o retirar, cada episodio muestra dónde está publicado, con el logo de cada red."""
import html
import json
import re
import shutil
from pathlib import Path

from ..i18n import _
from ..workspace import Workspace
from . import site

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "redes"
ORDER = ("youtube", "bluesky", "mastodon", "instagram", "x", "tiktok")
LABELS = {"youtube": "YouTube", "bluesky": "Bluesky", "mastodon": "Mastodon", "instagram": "Instagram",
          "x": "X", "tiktok": "TikTok", "rss": "RSS"}
COLORS = {"youtube": "#FF0000", "bluesky": "#1185FE", "mastodon": "#6364FF", "instagram": "#FF0069",
          "x": "#000000", "tiktok": "#000000", "rss": "#FFA500", "spotify": "#1ED760",
          "applepodcasts": "#9933CC", "ivoox": "#F0762C", "amazonmusic": "#25D1DA", "youtubemusic": "#FF0000",
          "pocketcasts": "#F43E37", "podcastindex": "#F90000", "castbox": "#F55B23", "podcastaddict": "#F4842D",
          "deezer": "#A238FF", "generic": "#555555"}
# Dónde está el RSS dado de alta: PODCAST_LISTEN_<CLAVE>=<url del programa en esa plataforma>
LISTEN = (("SPOTIFY", "spotify", "Spotify"), ("APPLE", "applepodcasts", "Apple Podcasts"),
          ("IVOOX", "ivoox", "iVoox"), ("AMAZON", "amazonmusic", "Amazon Music"),
          ("YOUTUBEMUSIC", "youtubemusic", "YouTube Music"), ("POCKETCASTS", "pocketcasts", "Pocket Casts"),
          ("PODCASTINDEX", "podcastindex", "Podcast Index"), ("CASTBOX", "castbox", "Castbox"),
          ("PODCASTADDICT", "podcastaddict", "Podcast Addict"), ("DEEZER", "deezer", "Deezer"))
START, END = "<!-- spiral:donde -->", "<!-- /spiral:donde -->"
INDEX_MARK = "<!-- spiral:index -->"
DEFAULT_INDEX = "---\nlayout: home\n---"       # el que crea site.ensure_scaffold

STYLES = """// Generado por spiral en cada publicación: tus estilos van en assets/main.scss, después del @import.
.sp-donde { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; margin: 1.4rem 0; }
.sp-donde-title { width: 100%; font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; color: #828282; }
.sp-badge { display: inline-flex; align-items: center; gap: .5rem; padding: .4rem .95rem .4rem .7rem;
  border: 2px solid var(--c); border-radius: 999px; background: #fff; color: #222; font-weight: 600;
  line-height: 1.2; text-decoration: none; transition: transform .15s ease, box-shadow .15s ease; }
.sp-badge img { width: 1.35rem; height: 1.35rem; }
a.sp-badge:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0, 0, 0, .18); text-decoration: none; }
.sp-nolink { opacity: .85; }
.sp-card { margin: 0 0 2rem; padding-bottom: 1rem; border-bottom: 1px solid #e8e8e8; }
.sp-card h2 { margin-bottom: .2rem; }
.sp-card time { color: #828282; font-size: .9rem; }
.sp-card p { margin: .4rem 0 0; }
.sp-lead { font-size: 1.15rem; color: #555; }
"""
LOGO_STYLE = """.site-title { display: inline-flex; align-items: center; gap: .65rem; }
.site-title::before { content: ""; width: 2.4rem; height: 2.4rem; border-radius: 50%;
  background: url("{url}") center / cover no-repeat; }
"""


def ref_url(key, ref):
    """Enlace público de una publicación a partir de lo que guardó el destino; None si no se puede deducir."""
    if key == "youtube" and isinstance(ref, dict) and ref.get("video"):
        return f"https://www.youtube.com/watch?v={ref['video']}"
    if key == "bluesky" and isinstance(ref, str):
        m = re.fullmatch(r"at://([^/]+)/app\.bsky\.feed\.post/([^/]+)", ref)
        return f"https://bsky.app/profile/{m[1]}/post/{m[2]}" if m else None
    if key == "mastodon" and isinstance(ref, str) and ref.startswith("https://"):
        return ref
    return None


def badge(key, label, href=None, raw=False):
    icon = "{{ '/img/redes/" + key + ".svg' | relative_url }}"
    inner = f'<img src="{icon}" alt="" width="22" height="22"><span>{html.escape(label)}</span>'
    style = f'style="--c:{COLORS[key]}"'
    if not href:
        return f'<span class="sp-badge sp-nolink" {style}>{inner}</span>'
    href = href if raw else html.escape(href, quote=True)
    return f'<a class="sp-badge" href="{href}" target="_blank" rel="noopener" {style}>{inner}</a>'


def badges(cfg, ep):
    """Una insignia por destino externo publicado (el sitio no cuenta: ya estás en él)."""
    out = []
    known = sorted((d for d in ep.done_destinations if d.partition("/")[0] in ORDER),
                   key=lambda d: (ORDER.index(d.partition("/")[0]), d))
    for did in known:
        key, sep, account = did.partition("/")
        label = LABELS[key] + (f" · {account}" if len(cfg.accounts(key)) > 1 else "")
        out.append(badge(key, label, ref_url(key, ep.destinations[did].get("ref"))))
    return out


def donde(items):
    if not items:
        return ""
    return f'<div class="sp-donde"><span class="sp-donde-title">{_("Disponible también en")}</span>' \
           + "".join(items) + "</div>"


def set_block(text, content):
    block = f"{START}\n{content}\n{END}" if content else f"{START}{END}"
    if START in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: block, text, flags=re.S)
    return re.sub(r"(<audio[^\n]*</audio>\n)", lambda m: m.group(1) + "\n" + block + "\n", text, count=1)


def logo_style(pod):
    image, base = pod["image"], pod["site_url"] + "/"
    if not image:
        return ""
    return LOGO_STYLE.replace("{url}", "../" + image[len(base):] if image.startswith(base) else image)


def listen_badges(cfg, log):
    """Plataformas con el RSS dado de alta: las conocidas en el orden de LISTEN y después cualquier otra
    PODCAST_LISTEN_<NOMBRE> con el icono genérico (los _ del nombre pasan a espacios)."""
    known = {suffix: (key, label) for suffix, key, label in LISTEN}
    found = {k.removeprefix("PODCAST_LISTEN_"): v for k, v in cfg.values.items()
             if k.startswith("PODCAST_LISTEN_") and v}
    order = [s for s in known if s in found] + sorted(s for s in found if s not in known)
    out = []
    for suffix in order:
        url = found[suffix]
        if not url.startswith("https://"):
            log(_("  PODCAST_LISTEN_{name} no es una URL https: se ignora.", name=suffix))
            continue
        key, label = known.get(suffix, ("generic", suffix.replace("_", " ").title()))
        out.append(badge(key, label, url))
    return out


def write_index(cfg, site_dir, pod, cards, log):
    """La portada es el listado de episodios con sus insignias; solo se reescribe si es la de spiral."""
    old = site_dir / "publicaciones.md"          # página de una versión anterior: ahora el listado es la portada
    if old.is_file() and "permalink: /publicaciones.html" in old.read_text():
        old.unlink()
    index = site_dir / "index.md"
    current = index.read_text() if index.is_file() else DEFAULT_INDEX
    if INDEX_MARK not in current and current.strip() != DEFAULT_INDEX:
        log(_("  index.md es tuyo: spiral no lo toca y no genera el listado de episodios."))
        return
    rss = badge("rss", _("Suscríbete por RSS"), "{{ '/feed.xml' | relative_url }}", raw=True)
    body = "\n".join(
        f'<article class="sp-card"><h2><a href="{{{{ \'/episodios/{m["slug"]}.html\' | relative_url }}}}">'
        f'{html.escape(m["titulo"])}</a></h2><time>{m["fecha"][:10]}</time>'
        f'<p>{html.escape(m["resumen_corto"])}</p><div class="sp-donde">{"".join(items)}</div></article>'
        for m, items in cards)
    index.write_text(f"---\nlayout: default\n---\n{INDEX_MARK}\n"
                     f'<p class="sp-lead">{html.escape(pod["description"])}</p>\n'
                     f'<div class="sp-donde">{rss}{"".join(listen_badges(cfg, log))}</div>\n\n{body}\n')


def refresh(cfg, log, ask):
    """Reescribe los bloques de los posts, la página de publicaciones, los estilos y los logos; sube el cambio."""
    site_dir = cfg.site_dir
    if not (site_dir / "episodes").is_dir():
        return
    pod = cfg.podcast()
    pod["image"] = site.cover_url(cfg, pod)
    ws = Workspace(cfg)
    cards = []
    for name in ws.names():
        ep = ws.episode(name)
        info = ep.destinations.get("site", {})
        if not info.get("done") or "audio" not in (info.get("ref") or {}):
            continue
        meta_file = site_dir / "episodes" / f"{info['ref']['audio'].split('/download/')[1].split('/')[0]}.json"
        if not meta_file.is_file():
            continue
        meta, items = json.loads(meta_file.read_text()), badges(cfg, ep)
        post = site.post_path(site_dir, meta)
        if post.is_file():
            post.write_text(set_block(post.read_text(), donde(items)))
        cards.append((meta, items))
    cards.sort(key=lambda c: c[0]["fecha"], reverse=True)
    write_index(cfg, site_dir, pod, cards, log)
    (site_dir / "_sass").mkdir(exist_ok=True)
    (site_dir / "_sass" / "spiral.scss").write_text(STYLES + logo_style(pod))
    (site_dir / "assets").mkdir(exist_ok=True)
    main = site_dir / "assets" / "main.scss"
    if not main.exists():
        main.write_text('---\n---\n@import "minima";\n@import "spiral";\n')
    elif "spiral" not in main.read_text():
        log(_("  assets/main.scss no importa los estilos de spiral: añade @import \"spiral\"; al final."))
    (site_dir / "img" / "redes").mkdir(parents=True, exist_ok=True)
    for svg in ASSETS.glob("*.svg"):          # no se pisa un icono que hayas cambiado a mano
        if not (site_dir / "img" / "redes" / svg.name).exists():
            shutil.copyfile(svg, site_dir / "img" / "redes" / svg.name)
    if site.has_changes(site_dir):
        if not site.is_own_repo(site_dir):
            log(_("  site/ no es un repositorio git: sube su contenido tú (ver el README)."))
        elif ask("push", _("¿Subir site/ a GitHub con el listado de publicaciones?")):
            site.git_publish(site_dir, "Update publications")
        else:
            log(_("  site/ preparado, sin subir."))
