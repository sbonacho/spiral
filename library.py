"""Biblioteca de episodios: qué hay procesado, dónde se ha publicado, archivado e informe HTML.

Dos sitios: SOURCE_DIR (los .mov de OBS, con los resultados en SOURCE_DIR/out/<episodio>/) y
ARCHIVE_DIR (una carpeta por episodio con el .mov original y todo su resultado).
El estado de publicación de cada episodio vive en <resultados>/publicado.json.
"""
import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

REQUIRED_OUTPUTS = ("episodio.mov", "episodio.mp3", "contenido.json")
MANUAL = ("x", "tiktok")  # sin API: se marcan a mano
PLATFORMS = (("audio", "Audio / RSS"), ("youtube", "YouTube"), ("shorts", "Shorts"),
             ("bluesky", "Bluesky"), ("mastodon", "Mastodon"), ("instagram", "Instagram"),
             ("x", "X"), ("tiktok", "TikTok"))
LABELS = dict(PLATFORMS)


def env_dir(name):
    d = os.environ.get(name)
    if not d:
        raise SystemExit(f"Falta {name} en .env (ver .env.example)")
    return Path(d).expanduser()


def source_dir():
    p = env_dir("SOURCE_DIR")
    if not p.is_dir():
        raise SystemExit(f"SOURCE_DIR no existe: {p}")
    return p


def episodes(src):
    return sorted(p.stem for p in src.glob("*.mov") if p.stem not in ("intro", "outro"))


def has_results(out):
    return all((out / f).exists() for f in REQUIRED_OUTPUTS) and (out / "clips").is_dir()


def is_processed(src, stem):
    return has_results(src / "out" / stem)


def read_state(out):
    f = out / "publicado.json"
    return json.loads(f.read_text()) if f.exists() else {}


def done(state):
    """Plataformas con publicación registrada, en el orden de PLATFORMS."""
    return [k for k, _ in PLATFORMS if state.get(k)]


def set_manual(out, keys, value):
    """Marca (o quita la marca de) publicaciones hechas a mano (X, TikTok)."""
    state = read_state(out)
    for k in keys:
        if value:
            state[k] = "manual"
        else:
            state.pop(k, None)
    (out / "publicado.json").write_text(json.dumps(state, indent=1))


def collect(src, archive):
    """Todos los episodios: los de SOURCE_DIR (procesados o no) y los archivados."""
    rows = []
    for stem in episodes(src):
        out = src / "out" / stem
        rows.append({"stem": stem, "where": "origen", "dir": out, "processed": has_results(out)})
    if archive.is_dir():
        rows += [{"stem": d.name, "where": "archivo", "dir": d, "processed": True}
                 for d in sorted(archive.iterdir()) if d.is_dir() and has_results(d)]
    for r in rows:
        r["state"] = read_state(r["dir"])
        r["titulo"] = title(r["dir"]) if r["processed"] else ""
    return sorted(rows, key=lambda r: r["stem"], reverse=True)


def title(out):
    try:
        return json.loads((out / "contenido.json").read_text()).get("titulo", "")
    except (OSError, ValueError):
        return ""


def archive_all(src, archive):
    """Mueve cada episodio procesado a ARCHIVE_DIR/<episodio>/: el .mov original y todo su resultado.
    No pisa nada: si la carpeta de destino ya existe, ese episodio se omite."""
    if archive.resolve() in (src.resolve(), (src / "out").resolve()):
        raise SystemExit("ARCHIVE_DIR no puede ser SOURCE_DIR ni SOURCE_DIR/out")
    moved, skipped = [], []
    for stem in episodes(src):
        out = src / "out" / stem
        dest = archive / stem
        if not has_results(out):
            continue
        if dest.exists():
            skipped.append(stem)
            continue
        archive.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out), str(dest))
        shutil.move(str(src / f"{stem}.mov"), str(dest / f"{stem}.mov"))
        moved.append(stem)
    return moved, skipped


def cell(key, state):
    """(clase CSS, texto, enlace) de una plataforma para un episodio."""
    v = state.get(key)
    if not v:
        return "no", "✘", None
    if isinstance(v, dict):
        return "si", f"✔ {len(v)}", None
    if v == "manual":
        return "si", "✔ a mano", None
    if key == "youtube":
        return "si", "✔", f"https://youtu.be/{v}"
    if str(v).startswith("http"):
        return "si", "✔", v
    return "si", "✔", None


def render_report(rows):
    head = "".join(f"<th scope=\"col\">{html.escape(n)}</th>" for _, n in PLATFORMS)
    body, totals = [], {k: 0 for k, _ in PLATFORMS}
    for r in rows:
        cells = []
        for k, _ in PLATFORMS:
            if not r["processed"]:
                cells.append('<td class="na">–</td>')
                continue
            cls, text, link = cell(k, r["state"])
            totals[k] += cls == "si"
            inner = f'<a href="{html.escape(link)}">{text}</a>' if link else text
            cells.append(f'<td class="{cls}" title="{html.escape(LABELS[k])}: {"sí" if cls == "si" else "no"}">{inner}</td>')
        icon = '<span class="arch" title="Archivado" role="img" aria-label="archivado">📦</span> ' if r["where"] == "archivo" else ""
        proc = '<td class="si">✔</td>' if r["processed"] else '<td class="no">✘</td>'
        body.append(f"<tr><th scope=\"row\">{icon}{html.escape(r['stem'])}<small>{html.escape(r['titulo'])}</small></th>"
                    f"{proc}{''.join(cells)}</tr>")
    n_done = sum(r["processed"] for r in rows)
    n_arch = sum(r["where"] == "archivo" for r in rows)
    foot = "".join(f"<td>{totals[k]}/{n_done}</td>" for k, _ in PLATFORMS)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informe de episodios</title>
<style>
:root {{ --bg:#fff; --fg:#1b1b1f; --mut:#66666e; --line:#d9d9e0; --si:#1a7f37; --no:#b42318; --head:#f3f3f6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --mut:#9a9aa5; --line:#33333b; --si:#4ade80; --no:#f87171; --head:#202026; }} }}
body {{ font:15px/1.4 system-ui,sans-serif; background:var(--bg); color:var(--fg); margin:0; padding:16px; }}
.wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ border:1px solid var(--line); padding:6px 10px; text-align:center; white-space:nowrap; }}
thead th,tfoot td {{ background:var(--head); }}
tbody th {{ text-align:left; }}
small {{ display:block; color:var(--mut); font-weight:400; white-space:normal; max-width:36ch; }}
.si {{ color:var(--si); font-weight:600; }} .no {{ color:var(--no); }} .na {{ color:var(--mut); }}
a {{ color:inherit; }}
</style></head><body>
<h1>Informe de episodios</h1>
<p>{len(rows)} episodio(s): {n_done} procesado(s), {len(rows) - n_done} pendiente(s), {n_arch} archivado(s) 📦 · generado el {datetime.now():%Y-%m-%d %H:%M}</p>
<div class="wrap"><table>
<thead><tr><th scope="col">Episodio</th><th scope="col">Procesado</th>{head}</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
<tfoot><tr><td colspan="2">Subidos (de los procesados)</td>{foot}</tr></tfoot>
</table></div>
<p><small>✔ = publicado · ✘ = no publicado · – = sin procesar · 📦 = archivado · "a mano" = marcado manualmente (X y TikTok no tienen publicación automática).
Los números junto a Shorts e Instagram son los clips publicados.</small></p>
</body></html>
"""


def write_report(src, archive, dest):
    rows = collect(src, archive)
    dest.write_text(render_report(rows))
    return len(rows)
