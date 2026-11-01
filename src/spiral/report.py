"""Informe HTML con todos los episodios, su estado y dónde están publicados."""
import html
from datetime import datetime

from .destinations import discover
from .i18n import _, language
from .workspace import Workspace

STAGES = {"pending": ("⏳", "pendiente"), "processed": ("⚙️", "procesado"), "published": ("📢", "publicado")}


def link_for(dest_id, info):
    ref = info.get("ref")
    if isinstance(ref, str) and ref.startswith("http"):
        return ref
    if isinstance(ref, dict):
        if dest_id.startswith("youtube/") and ref.get("video"):
            return f"https://youtu.be/{ref['video']}"
        if isinstance(ref.get("audio"), str):
            return ref["audio"]
    return None


def cell(ep, dest_id):
    if not ep.processed:
        return '<td class="na">–</td>'
    info = ep.destinations.get(dest_id, {})
    if not info.get("done"):
        return f'<td class="no" title="{_("no publicado")}">✘</td>'
    text = _("✔ a mano") if info.get("mode") == "manual" else "✔"
    link = link_for(dest_id, info)
    inner = f'<a href="{html.escape(link)}">{text}</a>' if link else text
    return f'<td class="si" title="{_("publicado")}">{inner}</td>'


def render(cfg, episodes):
    ids = [d.id for d in discover(cfg) if d.configured]
    for ep in episodes:
        ids += [i for i in ep.done_destinations if i not in ids]
    head = "".join(f'<th scope="col">{html.escape(i)}</th>' for i in ids)
    rows, totals = [], {i: 0 for i in ids}
    for ep in sorted(episodes, key=lambda e: e.name, reverse=True):
        icon, label = STAGES[ep.stage]
        cells = []
        for i in ids:
            totals[i] += bool(ep.destinations.get(i, {}).get("done"))
            cells.append(cell(ep, i))
        rows.append(f'<tr><th scope="row">{html.escape(ep.name)}<small>{html.escape(ep.title)}</small></th>'
                    f'<td><span role="img" aria-label="{_(label)}">{icon}</span> {_(label)}</td>{"".join(cells)}</tr>')
    n_proc = sum(e.processed for e in episodes)
    counts = {s: sum(e.stage == s for e in episodes) for s in STAGES}
    foot = "".join(f"<td>{totals[i]}/{n_proc}</td>" for i in ids)
    summary = _("{n} episodio(s): {pending} pendiente(s), {processed} procesado(s), {published} publicado(s) · generado el {date}",
                n=len(episodes), pending=counts["pending"], processed=counts["processed"],
                published=counts["published"], date=f"{datetime.now():%Y-%m-%d %H:%M}")
    return f"""<!doctype html>
<html lang="{language()}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_("Informe de episodios")}</title>
<style>
:root {{ --bg:#fff; --fg:#1b1b1f; --mut:#66666e; --line:#d9d9e0; --si:#1a7f37; --no:#b42318; --head:#f3f3f6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --mut:#9a9aa5; --line:#33333b; --si:#4ade80; --no:#f87171; --head:#202026; }} }}
body {{ font:15px/1.4 system-ui,sans-serif; background:var(--bg); color:var(--fg); margin:0; padding:16px; }}
.wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; }}
th,td {{ border:1px solid var(--line); padding:6px 10px; text-align:center; white-space:nowrap; }}
thead th,tfoot td {{ background:var(--head); }} tbody th {{ text-align:left; }}
small {{ display:block; color:var(--mut); font-weight:400; white-space:normal; max-width:36ch; }}
.si {{ color:var(--si); font-weight:600; }} .no {{ color:var(--no); }} .na {{ color:var(--mut); }} a {{ color:inherit; }}
</style></head><body>
<h1>{_("Informe de episodios")}</h1>
<p>{summary}</p>
<div class="wrap"><table>
<thead><tr><th scope="col">{_("Episodio")}</th><th scope="col">{_("Estado")}</th>{head}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
<tfoot><tr><td colspan="2">{_("Publicados (de los procesados)")}</td>{foot}</tr></tfoot>
</table></div>
<p><small>{_("✔ publicado · ✘ no publicado · – sin procesar · «a mano» = anotado manualmente (X y TikTok).")}</small></p>
</body></html>
"""


def write(cfg, path=None):
    episodes = Workspace(cfg).episodes()
    path = path or cfg.published_dir / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(cfg, episodes))
    return path, len(episodes)
