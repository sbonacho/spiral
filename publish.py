"""Publicación del audio: Archive.org (mp3) + sitio GitHub Pages (post de blog + feed.xml RSS).

El feed se reconstruye siempre entero desde site/episodes/*.json, así que es idempotente.
Alta única del RSS (site_url/feed.xml) en Spotify, Apple, iVoox, Amazon, Pocket Casts...
"""
import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import library

SITE = Path(__file__).parent / "site"
CONFIG = SITE / "podcast.json"
PLACEHOLDER = "TU_USUARIO"


def load_config():
    cfg = json.loads(CONFIG.read_text())
    if PLACEHOLDER in cfg["site_url"]:
        raise SystemExit(f"Edita {CONFIG}: site_url, autor y email todavía son de ejemplo")
    return cfg


def slugify(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def episode_url(cfg, contenido):
    return f"{cfg['site_url']}/episodios/{slugify(contenido['titulo'])}.html"


def episode_date(name, mtime):
    """OBS nombra los ficheros 'YYYY-MM-DD HH-MM-SS'; si no, usa la fecha del fichero."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})", name)
    if m:
        return datetime(*map(int, m.groups())).astimezone(timezone.utc)
    return datetime.fromtimestamp(mtime, timezone.utc)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return int(float(out.stdout))


def hms(s):
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}"


def upload_archive(identifier, mp3, title, description):
    import internetarchive
    # claves en .env; si faltan, internetarchive usa las de 'ia configure'
    keys = {"access_key": os.environ.get("IA_ACCESS_KEY"), "secret_key": os.environ.get("IA_SECRET_KEY")}
    res = internetarchive.upload(
        identifier, files=[str(mp3)], **(keys if all(keys.values()) else {}),
        metadata={"title": title, "description": description, "mediatype": "audio",
                  "language": "spa", "collection": "opensource_audio"})
    if not all(r.status_code == 200 for r in res):
        raise SystemExit("Fallo subiendo a Archive.org (¿IA_ACCESS_KEY/IA_SECRET_KEY en .env o 'ia configure'?)")


def write_post(cfg, ep):
    """Post Jekyll: reproductor, resumen, capítulos y transcripción completa (SEO)."""
    c = ep["contenido"]
    chapters = "\n".join(f"- {hms(int(x['inicio']))} {x['titulo']}" for x in c["capitulos"])
    transcript = ep["transcripcion"].replace("\n", "\n\n")
    body = (f"---\nlayout: post\ntitle: {json.dumps(ep['titulo'], ensure_ascii=False)}\n"
            f"date: {ep['fecha']}\npermalink: /episodios/{ep['slug']}.html\ntags: {json.dumps(c['tags'], ensure_ascii=False)}\n---\n\n"
            f"<audio controls preload=\"none\" src=\"{ep['audio_url']}\"></audio>\n\n"
            f"{c['post_blog_md']}\n\n## Capítulos\n\n{chapters}\n\n"
            f"<details><summary>Transcripción completa</summary>\n\n{transcript}\n\n</details>\n")
    (SITE / "_posts").mkdir(exist_ok=True)
    (SITE / "_posts" / f"{ep['fecha'][:10]}-{ep['slug']}.md").write_text(body)


def build_feed(cfg):
    items = []
    for f in sorted((SITE / "episodes").glob("*.json"), reverse=True):
        e = json.loads(f.read_text())
        pub = format_datetime(datetime.fromisoformat(e["fecha"]))
        items.append(f"""    <item>
      <title>{escape(e['titulo'])}</title>
      <description>{escape(e['resumen_corto'])}</description>
      <link>{cfg['site_url']}/episodios/{e['slug']}.html</link>
      <guid isPermaLink="false">{e['guid']}</guid>
      <pubDate>{pub}</pubDate>
      <enclosure url="{escape(e['audio_url'])}" length="{e['bytes']}" type="audio/mpeg"/>
      <itunes:duration>{hms(e['segundos'])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    image = f'\n    <itunes:image href="{cfg["imagen"]}"/>' if cfg.get("imagen") else ""
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(cfg['titulo'])}</title>
    <link>{cfg['site_url']}</link>
    <language>{cfg['idioma']}</language>
    <description>{escape(cfg['descripcion'])}</description>
    <itunes:author>{escape(cfg['autor'])}</itunes:author>
    <itunes:owner><itunes:name>{escape(cfg['autor'])}</itunes:name><itunes:email>{cfg['email']}</itunes:email></itunes:owner>
    <itunes:category text="{escape(cfg['categoria'])}"/>
    <itunes:explicit>false</itunes:explicit>{image}
{chr(10).join(items)}
  </channel>
</rss>
"""
    (SITE / "feed.xml").write_text(feed)


def publish(root, stem, push=False):
    """root = directorio de los .mov; stem = nombre del episodio (da la fecha si es de OBS)."""
    cfg = load_config()
    root = Path(root)
    outdir = root / "out" / stem
    contenido = json.loads((outdir / "contenido.json").read_text())
    mp3 = outdir / "episodio.mp3"
    fecha = episode_date(stem, (root / f"{stem}.mov").stat().st_mtime)
    slug = slugify(contenido["titulo"])
    identifier = f"{slugify(cfg['titulo'])}-{fecha:%Y%m%d}-{slug}"[:100]
    audio_url = f"https://archive.org/download/{identifier}/{mp3.name}"

    upload_archive(identifier, mp3, contenido["titulo"], contenido["resumen_corto"])

    ep = {"titulo": contenido["titulo"], "resumen_corto": contenido["resumen_corto"], "slug": slug,
          "fecha": fecha.isoformat(), "guid": identifier, "audio_url": audio_url,
          "bytes": mp3.stat().st_size, "segundos": duration(mp3), "contenido": contenido,
          "transcripcion": (outdir / "transcripcion.txt").read_text()}
    (SITE / "episodes").mkdir(exist_ok=True)
    meta = {k: v for k, v in ep.items() if k not in ("contenido", "transcripcion")}
    (SITE / "episodes" / f"{identifier}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    write_post(cfg, ep)
    build_feed(cfg)
    state = library.read_state(outdir)
    state["audio"] = audio_url
    (outdir / "publicado.json").write_text(json.dumps(state, indent=1))
    print(f"  audio en {audio_url}\n  feed: {cfg['site_url']}/feed.xml")

    if push:
        git = ["git", "-C", str(SITE)]
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-m", f"Episodio: {contenido['titulo']}"], check=True)
        subprocess.run([*git, "push"], check=True)
