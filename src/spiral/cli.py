"""Punto de entrada `spiral`: menú guiado y subcomandos list, process, publish y view."""
import argparse
import subprocess
import sys

from . import __version__, report, ui
from .config import Config
from .destinations import discover
from .destinations import publish as publish_episode
from .errors import SpiralError
from .i18n import _, set_language
from .pipeline import process_episode
from .workspace import Workspace


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


class UsageError(SpiralError):
    """Faltan argumentos y no hay terminal para preguntarlos (código de salida 2)."""


def parser():
    ap = argparse.ArgumentParser(prog="spiral", description=_("Procesa y publica los episodios del directorio actual."))
    ap.add_argument("--version", action="version", version=f"spiral {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help=_("ficheros del directorio y su estado"))
    p = sub.add_parser("process", help=_("procesar un fichero"))
    p.add_argument("name", nargs="?", help=_("nombre del .mov sin extensión"))
    p.add_argument("--redo", action="store_true", help=_("rehacer un episodio ya procesado (sin preguntar)"))
    p = sub.add_parser("publish", help=_("publicar un episodio procesado"))
    p.add_argument("name", nargs="?")
    p.add_argument("--to", help=_("destinos separados por comas, p. ej. site,bluesky/programa"))
    p.add_argument("--dry-run", action="store_true", help=_("muestra el contenido sin publicar nada"))
    p.add_argument("--yes", action="store_true", help=_("no preguntar"))
    p = sub.add_parser("view", help=_("informe HTML de todos los ficheros"))
    p.add_argument("--no-open", action="store_true", help=_("solo generarlo"))
    return ap


def cmd_list(cfg, args):
    ui.show_list(Workspace(cfg).episodes())


def cmd_process(cfg, args):
    ws = Workspace(cfg)
    name = args.name
    if not name:
        if not interactive():
            raise UsageError(_("Falta el nombre: spiral process <nombre>"))
        name = ui.pick_episode(ws.episodes(), _("¿Qué fichero procesas?"),
                               lambda ep: None if ep.original else _("no se encuentra el .mov"))
        if not name:
            return
    ep = ws.episode(name)
    redo = False
    if ep.processed:
        if args.redo:
            redo = True
        elif not interactive():
            raise SpiralError(_("«{name}» ya está procesado; usa --redo para rehacerlo.", name=name))
        elif ui.confirm(_("«{name}» ya está procesado. Rehacerlo borra la transcripción, contenido.json "
                          "(también tus ediciones) y los clips; lo ya publicado se conserva. ¿Rehacerlo?",
                          name=name)):
            redo = True
        else:
            return
    with ui.console.status(_("Procesando…")):
        process_episode(cfg, name, log=ui.info, redo=redo)


def cmd_publish(cfg, args):
    ws = Workspace(cfg)
    name = args.name
    tty = interactive()
    if not name:
        if not tty:
            raise UsageError(_("Falta el nombre: spiral publish <nombre> --to <destino>[,...]"))
        name = ui.pick_episode(ws.episodes(), _("¿Qué episodio publicas?"),
                               lambda ep: None if ep.processed else _("sin procesar"))
        if not name:
            return
    ep = ws.episode(name)
    if not ep.processed:
        raise SpiralError(_("«{name}» no está procesado: usa `spiral process {name}`.", name=name))
    dests = discover(cfg)
    if args.to:
        ids = [i.strip() for i in args.to.split(",") if i.strip()]
    elif tty:
        ids = ui.pick_destinations(dests, set(ep.done_destinations))
    else:
        raise UsageError(_("Falta --to <destino>[,...]"))
    if not ids:
        return
    dry = args.dry_run
    if tty and not (args.yes or dry):
        mode = ui.pick_mode()
        if mode in (None, "cancel"):
            return
        dry = mode == "dry"

    def ask(kind, question):
        if kind == "manual":                  # solo se anota si el usuario lo confirma de verdad
            return tty and ui.confirm(question)
        return True if args.yes else (tty and ui.confirm(question, default=True))

    results = publish_episode(cfg, name, ids, dry=dry, log=ui.info, ask=ask)
    ui.show_results(results)
    return 1 if any(r.status in ("failed", "not-attempted") for r in results) else 0


def cmd_view(cfg, args):
    path, n = report.write(cfg)
    ui.info(_("{n} episodio(s) -> {path}", n=n, path=path))
    if not args.no_open and subprocess.run(["open", str(path)]).returncode != 0:
        ui.info(_("No pude abrirlo; ábrelo en el navegador."))


COMMANDS = {"list": cmd_list, "process": cmd_process, "publish": cmd_publish, "view": cmd_view}


def menu(cfg):
    if not interactive():
        raise UsageError(_("Sin terminal: usa un subcomando (list, process, publish, view). spiral --help"))
    ui.title("spiral")
    ui.show_destinations(discover(cfg))
    while True:
        action = ui.pick_action()
        if action in (None, "quit"):
            return 0
        try:
            COMMANDS[action](cfg, argparse.Namespace(name=None, redo=False, to=None, dry_run=False,
                                                     yes=False, no_open=False))
        except SpiralError as e:
            ui.error(str(e))


def main(argv=None):
    try:
        cfg = Config.load()
        set_language(cfg.language)
        args = parser().parse_args(argv)
        if args.cmd is None:
            return menu(cfg) or 0
        return COMMANDS[args.cmd](cfg, args) or 0
    except UsageError as e:
        print(f"spiral: {e}", file=sys.stderr)
        return 2
    except SpiralError as e:
        ui.error(str(e))
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
