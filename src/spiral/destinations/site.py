"""Destino `site`: mp3 en Archive.org, entrada de blog y feed.xml en site/ (GitHub Pages)."""
import json
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from ..errors import SpiralError
from ..i18n import _

ID = "site"
LABEL = "Audio + blog + RSS"


def slugify(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def episode_url(cfg, content):
    return f"{cfg.get('SITE_URL').rstrip('/')}/episodios/{slugify(content['titulo'])}.html"


def episode_date(name, fallback_ts):
    """OBS nombra los ficheros 'YYYY-MM-DD HH-MM-SS'; si no, usa la fecha del fichero."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})", name)
    if m:
        return datetime(*map(int, m.groups())).astimezone(timezone.utc)
    return datetime.fromtimestamp(fallback_ts, timezone.utc)


def hms(s):
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return int(float(out.stdout))


def missing(cfg):
    out = cfg.missing_podcast()
    from ..config import global_dir
    from pathlib import Path
    ia = (cfg.get("IA_ACCESS_KEY") and cfg.get("IA_SECRET_KEY")) or any(
        p.exists() for p in (Path.home() / ".config/internetarchive/ia.ini", Path.home() / ".ia"))
    if not ia:
        out.append("IA_ACCESS_KEY/IA_SECRET_KEY")
    return out


def upload_archive(cfg, identifier, mp3, title, description, language):
    import internetarchive
    keys = {"access_key": cfg.get("IA_ACCESS_KEY"), "secret_key": cfg.get("IA_SECRET_KEY")}
    res = internetarchive.upload(
        identifier, files=[str(mp3)], **(keys if all(keys.values()) else {}),
        metadata={"title": title, "description": description, "mediatype": "audio",
                  "language": language, "collection": "opensource_audio"})
    if not all(r.status_code == 200 for r in res):
        raise SpiralError(_("Falló la subida a Archive.org (¿IA_ACCESS_KEY/IA_SECRET_KEY en el .env o 'ia configure'?)"))


def write_post(site_dir, ep, content, transcript, audio_url, slug, fecha):
    """Post Jekyll: reproductor, resumen, capítulos y transcripción completa (SEO)."""
    chapters = "\n".join(f"- {hms(int(x['inicio']))} {x['titulo']}" for x in content["capitulos"])
    body = (f"---\nlayout: post\ntitle: {json.dumps(content['titulo'], ensure_ascii=False)}\n"
            f"date: {fecha.isoformat()}\npermalink: /episodios/{slug}.html\n"
            f"tags: {json.dumps(content['tags'], ensure_ascii=False)}\n---\n\n"
            f"<audio controls preload=\"none\" src=\"{audio_url}\"></audio>\n\n"
            f"{content['post_blog_md']}\n\n## Capítulos\n\n{chapters}\n\n"
            f"<details><summary>Transcripción completa</summary>\n\n{transcript.replace(chr(10), chr(10) * 2)}\n\n"
            f"</details>\n")
    (site_dir / "_posts").mkdir(parents=True, exist_ok=True)
    (site_dir / "_posts" / f"{fecha:%Y-%m-%d}-{slug}.md").write_text(body)


def ensure_scaffold(site_dir, pod):
    """Jekyll mínimo para GitHub Pages; solo crea lo que falta, nunca pisa tus ficheros."""
    site_dir.mkdir(parents=True, exist_ok=True)
    files = {"_config.yml": f"title: {json.dumps(pod['title'])}\ntheme: minima\nlang: {pod['language']}\n"
                            "exclude: [episodes]\n",
             "index.md": "---\nlayout: home\n---\n",
             ".gitignore": ".DS_Store\n"}
    for name, text in files.items():
        if not (site_dir / name).exists():
            (site_dir / name).write_text(text)


def cover_url(cfg, pod):
    """PODCAST_IMAGE puede ser una URL o un fichero local; un fichero se sirve desde site/ (se copia si hace falta)."""
    image = pod["image"]
    if not image or image.startswith(("http://", "https://")):
        return image
    src = Path(image).expanduser()
    src = src if src.is_absolute() else cfg.root / src
    if not src.is_file():
        raise SpiralError(_("PODCAST_IMAGE={image}: no existe ese fichero.", image=image))
    cfg.site_dir.mkdir(parents=True, exist_ok=True)
    site_dir = cfg.site_dir.resolve()
    if site_dir not in src.resolve().parents:
        shutil.copyfile(src, site_dir / f"cover{src.suffix.lower()}")
        src = site_dir / f"cover{src.suffix.lower()}"
    return f"{pod['site_url']}/{src.resolve().relative_to(site_dir).as_posix()}"


def build_feed(site_dir, pod):
    items = []
    for f in sorted((site_dir / "episodes").glob("*.json"), reverse=True):
        e = json.loads(f.read_text())
        items.append(f"""    <item>
      <title>{escape(e['titulo'])}</title>
      <description>{escape(e['resumen_corto'])}</description>
      <link>{pod['site_url']}/episodios/{e['slug']}.html</link>
      <guid isPermaLink="false">{escape(e['guid'])}</guid>
      <pubDate>{format_datetime(datetime.fromisoformat(e['fecha']))}</pubDate>
      <enclosure url="{escape(e['audio_url'])}" length="{e['bytes']}" type="audio/mpeg"/>
      <itunes:duration>{hms(e['segundos'])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    image = f'\n    <itunes:image href="{escape(pod["image"])}"/>' if pod["image"] else ""
    (site_dir / "feed.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(pod['title'])}</title>
    <link>{pod['site_url']}</link>
    <language>{pod['language']}</language>
    <description>{escape(pod['description'])}</description>
    <itunes:author>{escape(pod['author'])}</itunes:author>
    <managingEditor>{escape(pod['email'])} ({escape(pod['author'])})</managingEditor>
    <itunes:owner><itunes:name>{escape(pod['author'])}</itunes:name><itunes:email>{escape(pod['email'])}</itunes:email></itunes:owner>
    <itunes:category text="{escape(pod['category'])}"/>
    <itunes:explicit>false</itunes:explicit>{image}
{chr(10).join(items)}
  </channel>
</rss>
""")


def is_own_repo(site_dir):
    """True si site/ es la raíz de su propio repositorio git (no el de un directorio superior)."""
    r = subprocess.run(["git", "-C", str(site_dir), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return r.returncode == 0 and os.path.realpath(r.stdout.strip()) == os.path.realpath(site_dir)


def git_publish(site_dir, message):
    git = ["git", "-C", str(site_dir)]
    subprocess.run([*git, "add", "-A"], check=True)
    if subprocess.run([*git, "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run([*git, "commit", "-m", message], check=True)
    subprocess.run([*git, "push"], check=True)


def unpublish(ctx, ref):
    """Quita el episodio del feed y del blog (los .json de episodes/ y el post) y sube el cambio."""
    cfg = ctx.cfg
    identifier = ref["audio"].split("/download/")[1].split("/")[0]
    site_dir, meta_file = cfg.site_dir, cfg.site_dir / "episodes" / f"{identifier}.json"
    if meta_file.is_file():
        meta = json.loads(meta_file.read_text())
        post = site_dir / "_posts" / f"{datetime.fromisoformat(meta['fecha']):%Y-%m-%d}-{meta['slug']}.md"
        post.unlink(missing_ok=True)
        meta_file.unlink()
    pod = cfg.podcast()
    pod["image"] = cover_url(cfg, pod)
    build_feed(site_dir, pod)
    if not is_own_repo(site_dir):
        ctx.log(_("  site/ no es un repositorio git: sube su contenido tú (ver el README)."))
    elif ctx.ask("push", _("¿Subir site/ a GitHub para que el feed deje de incluirlo?")):
        git_publish(site_dir, f"Remove episode: {identifier}")
    else:
        ctx.log(_("  site/ preparado, sin subir."))
    ctx.log(_("  El mp3 sigue en Archive.org ({url}): bórralo allí si quieres.", url=ref["audio"]))


def preview(ctx):
    mp3 = ctx.ep.dir / "episodio.mp3"
    return _("[site] subir {mp3} a Archive.org, crear la entrada «{title}» y regenerar feed.xml",
             mp3=mp3.name, title=ctx.content["titulo"]) + f"\n  {ctx.url}"


def publish(ctx):
    cfg, ep, content = ctx.cfg, ctx.ep, ctx.content
    pod = cfg.podcast()
    pod["image"] = cover_url(cfg, pod)          # antes de subir nada: si falla, no queda a medias
    mp3 = ep.dir / "episodio.mp3"
    fecha = episode_date(ep.name, mp3.stat().st_mtime)
    slug = slugify(content["titulo"])
    identifier = f"{slugify(pod['title'])}-{fecha:%Y%m%d}-{slug}"[:100]
    audio_url = f"https://archive.org/download/{identifier}/{mp3.name}"

    ctx.log(_("  subiendo el mp3 a Archive.org…"))
    upload_archive(cfg, identifier, mp3, content["titulo"], content["resumen_corto"], pod["language"])
    site_dir = cfg.site_dir
    ensure_scaffold(site_dir, pod)
    (site_dir / "episodes").mkdir(parents=True, exist_ok=True)
    meta = {"titulo": content["titulo"], "resumen_corto": content["resumen_corto"], "slug": slug,
            "fecha": fecha.isoformat(), "guid": identifier, "audio_url": audio_url,
            "bytes": mp3.stat().st_size, "segundos": duration(mp3)}
    (site_dir / "episodes" / f"{identifier}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    write_post(site_dir, ep, content, (ep.dir / "transcripcion.txt").read_text(), audio_url, slug, fecha)
    build_feed(site_dir, pod)
    ctx.log(f"  audio: {audio_url}\n  feed: {pod['site_url']}/feed.xml")

    if not is_own_repo(site_dir):
        ctx.log(_("  site/ no es un repositorio git: sube su contenido tú (ver el README)."))
    elif ctx.ask("push", _("¿Subir site/ a GitHub (necesario para que el RSS se actualice)?")):
        git_publish(site_dir, f"Episode: {content['titulo']}")
    else:
        ctx.log(_("  site/ preparado, sin subir."))
    return {"audio": audio_url}
