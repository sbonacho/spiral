"""Interfaz de terminal: selectores con flechas/espacio (questionary) y salida con color (rich).

Solo presenta y pregunta; la lógica vive en workspace, pipeline y destinations.
"""
import questionary
from rich.console import Console
from rich.markup import escape
from rich.table import Table

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
    console.print("\n[bold]Destinos[/]")
    if not dests:
        console.print("  [dim]ninguno configurado (ver .env.example)[/]")
    for d in dests:
        if d.configured:
            console.print(f"  [green]✔[/] {escape(d.id)}  [dim]{escape(d.label)}[/]", highlight=False)
        else:
            console.print(f"  [red]✘[/] {escape(d.id)}  [dim]falta: {escape(', '.join(d.missing))}[/]",
                          highlight=False)
    console.print()


def show_list(episodes):
    table = Table(show_header=True, header_style="bold")
    for col in ("Episodio", "Título", "Estado", "Publicado en"):
        table.add_column(col)
    for ep in episodes:
        icon, color, label = STAGE[ep.stage]
        table.add_row(escape(ep.name), escape(ep.title), f"[{color}]{icon} {label}[/]",
                      escape(", ".join(ep.done_destinations)) or "–")
    console.print(table if episodes else "[dim]No hay .mov ni episodios en este directorio.[/]")


def pick_action():
    return questionary.select(
        "¿Qué quieres hacer?", use_arrow_keys=True, use_jk_keys=False,
        choices=[questionary.Choice("list     ficheros y su estado", "list"),
                 questionary.Choice("process  procesar un fichero", "process"),
                 questionary.Choice("publish  publicar un episodio procesado", "publish"),
                 questionary.Choice("view     informe HTML", "view"),
                 questionary.Choice("salir", "quit")]).ask()


def pick_episode(episodes, message, usable):
    """`usable(ep)` devuelve None si se puede elegir o el motivo si no. Se filtra al escribir."""
    choices = []
    for ep in episodes:
        icon, _, label = STAGE[ep.stage]
        title = f"{icon} {ep.name}" + (f" — {ep.title}" if ep.title else "") + f"  ({label})"
        reason = usable(ep)
        choices.append(questionary.Choice(title, ep.name, disabled=reason))
    if not any(c.disabled is None for c in choices):
        return None
    return questionary.select(message + " (escribe para buscar)", choices=choices, use_search_filter=True,
                              use_jk_keys=False, use_arrow_keys=True).ask()


def pick_destinations(dests, done):
    """Casillas con espacio; los destinos sin configurar salen deshabilitados con su motivo."""
    choices = [questionary.Choice(
        d.label + ("  (ya publicado)" if d.id in done else ""), d.id,
        disabled=None if d.configured else f"falta: {', '.join(d.missing)}") for d in dests]
    return questionary.checkbox("¿Dónde publicar? (espacio marca, Enter confirma)", choices=choices).ask()


def pick_mode():
    return questionary.select("¿Cómo?", use_jk_keys=False, choices=[
        questionary.Choice("Publicar de verdad", "publish"),
        questionary.Choice("Simular (no publica nada)", "dry"),
        questionary.Choice("Cancelar", "cancel")]).ask()


def confirm(question, default=False):
    return bool(questionary.confirm(question, default=default).ask())


def show_results(results):
    colors = {"ok": "green", "skipped": "dim", "simulated": "cyan", "pending": "yellow",
              "failed": "red", "not-attempted": "yellow"}
    console.print("\n[bold]Resultado[/]")
    for r in results:
        console.print(f"  [{colors[r.status]}]{r.status:<13}[/] {escape(r.id)}  [dim]{escape(r.detail)}[/]",
                      highlight=False)
