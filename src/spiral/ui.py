"""Interfaz de terminal: selectores con flechas/espacio (questionary) y salida con color (rich).

Solo presenta y pregunta; la lógica vive en workspace, pipeline y destinations.
"""
import questionary
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import media
from .i18n import _

console = Console()

STAGE = {"pending": ("⏳", "yellow", "pendiente"), "processed": ("⚙️ ", "cyan", "procesado"),
         "published": ("📢", "green", "publicado")}


def error(msg):
    console.print(f"[bold red]✘[/] {escape(str(msg))}", highlight=False)


def info(msg):
    """Texto tal cual: los corchetes de los mensajes ([site], [bluesky/...]) no son marcado de rich."""
    console.print(msg, markup=False, highlight=False, soft_wrap=True)


def title(msg):
    console.print(f"\n[bold]{escape(msg)}[/]")


def show_destinations(dests):
    console.print(f"\n[bold]{_('Destinos')}[/]")
    if not dests:
        console.print(f"  [dim]{_('ninguno configurado (ver el README)')}[/]")
    for d in dests:
        if d.configured:
            console.print(f"  [green]✔[/] {escape(d.id)}  [dim]{escape(d.label)}[/]", highlight=False)
        else:
            console.print(f"  [red]✘[/] {escape(d.id)}  [dim]{_('falta')}: {escape(', '.join(d.missing))}[/]",
                          highlight=False)
    console.print()


def show_list(episodes):
    table = Table(show_header=True, header_style="bold")
    for col in (_("Episodio"), _("Título"), _("Duración"), _("Estado"), _("Publicado en")):
        table.add_column(col, justify="right" if col == _("Duración") else "left")
    for ep in episodes:
        icon, color, label = STAGE[ep.stage]
        table.add_row(escape(ep.name), escape(ep.title), media.clock(ep.duration), f"[{color}]{icon} {_(label)}[/]",
                      escape(", ".join(ep.done_destinations)) or "–")
    console.print(table if episodes else f"[dim]{_('No hay .mov ni episodios en este directorio.')}[/]")


def pick_action():
    def entry(key, text):
        return questionary.Choice(f"{key:<8} {text}", key)
    return questionary.select(
        _("¿Qué quieres hacer?"), use_arrow_keys=True, use_jk_keys=False,
        choices=[entry("list", _("ficheros y su estado")), entry("process", _("procesar uno o varios ficheros")),
                 entry("publish", _("publicar uno o varios episodios procesados")), entry("view", _("informe HTML")),
                 questionary.Choice(_("salir"), "quit")]).ask()


def pick_episodes(episodes, message, usable):
    """Casillas con espacio (Ctrl-A marca todos); `usable(ep)` da None si se puede elegir o el motivo si no."""
    choices = []
    for ep in episodes:
        icon, _color, label = STAGE[ep.stage]
        title = f"{icon} {ep.name}" + (f" — {ep.title}" if ep.title else "") + f"  ({_(label)}) · {media.clock(ep.duration)}"
        choices.append(questionary.Choice(title, ep.name, disabled=usable(ep)))
    if not any(c.disabled is None for c in choices):   # questionary falla si todas están deshabilitadas
        info(_("No hay ningún episodio que se pueda elegir para esta acción."))
        return []
    return questionary.checkbox(
        message, choices=choices, use_search_filter=True, use_jk_keys=False, use_arrow_keys=True,
        instruction=_("(espacio marca, Ctrl-A todos, escribe para buscar, Enter confirma)")).ask() or []


def pick_destinations(dests, done):
    """Casillas con espacio; los destinos sin configurar salen deshabilitados con su motivo."""
    choices = [questionary.Choice(
        d.label + ("  " + _("(ya publicado)") if d.id in done else ""), d.id,
        disabled=None if d.configured else f"{_('falta')}: {', '.join(d.missing)}") for d in dests]
    return questionary.checkbox(_("¿Dónde publicar?"), choices=choices,
                               instruction=_("(espacio marca, a todos, Enter confirma)")).ask()


def pick_mode():
    return questionary.select(_("¿Cómo?"), use_jk_keys=False, choices=[
        questionary.Choice(_("Publicar de verdad"), "publish"),
        questionary.Choice(_("Simular (no publica nada)"), "dry"),
        questionary.Choice(_("Cancelar"), "cancel")]).ask()


def confirm(question, default=False):
    return bool(questionary.confirm(question, default=default).ask())


def show_results(results):
    colors = {"ok": "green", "skipped": "dim", "simulated": "cyan", "pending": "yellow",
              "failed": "red", "not-attempted": "yellow"}
    console.print(f"\n[bold]{_('Resultado')}[/]")
    for r in results:
        console.print(f"  [{colors[r.status]}]{r.status:<13}[/] {escape(r.id)}  [dim]{escape(r.detail)}[/]",
                      highlight=False)
