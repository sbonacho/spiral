"""Punto de entrada `spiral`: menú guiado y subcomandos list, process, publish y view."""
import argparse
import subprocess
import sys

from . import __version__, report, ui
from .config import Config, init_workspace
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
    p = sub.add_parser("process", help=_("procesar uno o varios ficheros"))
    p.add_argument("names", nargs="*", metavar="name", help=_("nombres de los .mov sin extensión"))
    p.add_argument("--redo", action="store_true", help=_("rehacer un episodio ya procesado (sin preguntar)"))
    p = sub.add_parser("publish", help=_("publicar uno o varios episodios procesados"))
    p.add_argument("names", nargs="*", metavar="name")
    p.add_argument("--to", help=_("destinos separados por comas, p. ej. site,bluesky/programa"))
    p.add_argument("--dry-run", action="store_true", help=_("muestra el contenido sin publicar nada"))
    p.add_argument("--force", action="store_true", help=_("volver a publicar en los destinos ya publicados"))
    p.add_argument("--yes", action="store_true", help=_("no preguntar"))
    p = sub.add_parser("view", help=_("informe HTML de todos los ficheros"))
    p.add_argument("--no-open", action="store_true", help=_("solo generarlo"))
    return ap


def cmd_list(cfg, args):
    ui.show_list(Workspace(cfg).episodes())


def cmd_process(cfg, args):
    ws = Workspace(cfg)
    names = args.names
    if not names:
        if not interactive():
            raise UsageError(_("Falta el nombre: spiral process <nombre>..."))
        names = ui.pick_episodes(ws.episodes(), _("¿Qué ficheros procesas?"),
                                 lambda ep: None if ep.original else _("no se encuentra el .mov"))
    done = [n for n in names if ws.episode(n).processed]
    redo = set()
    if done and args.redo:
        redo = set(done)
    elif done and not interactive():
        raise SpiralError(_("«{name}» ya está procesado; usa --redo para rehacerlo.", name=done[0]))
    elif done and ui.confirm(_("Ya procesados: {names}. Rehacerlos borra la transcripción, contenido.json "
                               "(también tus ediciones) y los clips; lo ya publicado se conserva. ¿Rehacerlos?",
                               names=", ".join(done))):
        redo = set(done)
    failed = []
    for name in names:
        if name in done and name not in redo:
            continue
        try:
            with ui.console.status(_("Procesando…")):
                process_episode(cfg, name, log=ui.info, redo=name in redo)
        except SpiralError as e:
            ui.error(f"{name}: {e}" if len(names) > 1 else str(e))
            failed.append(name)
    if len(names) > 1:
        ui.info(_("Procesados {ok} de {total}.", ok=len(names) - len(failed), total=len(names)))
    return 1 if failed else 0


def cmd_publish(cfg, args):
    ws = Workspace(cfg)
    names = args.names
    tty = interactive()
    if not names:
        if not tty:
            raise UsageError(_("Falta el nombre: spiral publish <nombre>... --to <destino>[,...]"))
        names = ui.pick_episodes(ws.episodes(), _("¿Qué episodios publicas?"),
                                 lambda ep: None if ep.processed else _("sin procesar"))
    if not names:
        return
    eps = [ws.episode(n) for n in names]
    for ep in eps:
        if not ep.processed:
            raise SpiralError(_("«{name}» no está procesado: usa `spiral process {name}`.", name=ep.name))
    dests = discover(cfg)
    if args.to:
        ids = [i.strip() for i in args.to.split(",") if i.strip()]
    elif tty:
        if not any(d.configured for d in dests):   # questionary falla si todas las casillas están deshabilitadas
            ui.show_destinations(dests)
            raise SpiralError(_("Ningún destino configurado: rellena el .env (mira el README)."))
        already = set.intersection(*(set(ep.done_destinations) for ep in eps))
        ids = ui.pick_destinations(dests, already)
    else:
        raise UsageError(_("Falta --to <destino>[,...]"))
    if not ids:
        return
    dry = args.dry_run
    force = args.force
    again = [i for i in ids if any(i in ep.done_destinations for ep in eps)]
    if again and tty and not (force or dry or args.yes):
        force = ui.confirm(_("Ya publicado en: {ids}. Volver a publicar repite los posts y vídeos en las redes "
                             "(en site solo regenera el feed). ¿Volver a publicar? (no = se omiten)",
                             ids=", ".join(again)))
    if tty and not (args.yes or dry):
        mode = ui.pick_mode()
        if mode in (None, "cancel"):
            return
        dry = mode == "dry"

    def ask(kind, question):
        if kind == "manual":                  # solo se anota si el usuario lo confirma de verdad
            return tty and ui.confirm(question)
        return True if args.yes else (tty and ui.confirm(question, default=True))

    code = 0
    for name in names:
        if len(names) > 1:
            ui.title(name)
        results = publish_episode(cfg, name, ids, dry=dry, force=force, log=ui.info, ask=ask)
        ui.show_results(results)
        if any(r.status in ("failed", "not-attempted") for r in results):
            code = 1
    return code


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
            COMMANDS[action](cfg, argparse.Namespace(names=[], redo=False, to=None, dry_run=False,
                                                     force=False, yes=False, no_open=False))
        except SpiralError as e:
            ui.error(str(e))


def offer_workspace(cfg):
    """Con .mov y sin .env aquí, ofrece crear el .env; devuelve la configuración al día."""
    if (cfg.root / ".env").exists() or not any(cfg.root.glob("*.mov")) or not interactive():
        return cfg
    if not ui.confirm(_("Hay .mov aquí pero no hay .env: ¿crear un repositorio spiral en este directorio "
                        "(copia la plantilla a .env) para publicarlos?"), default=True):
        return cfg
    ui.info(_("Creado {path}: rellénalo antes de publicar.", path=init_workspace(cfg.root)))
    cfg = Config.load(cfg.root)
    set_language(cfg.language)
    return cfg


def main(argv=None):
    try:
        cfg = Config.load()
        set_language(cfg.language)
        args = parser().parse_args(argv)
        if args.cmd is None:
            return menu(offer_workspace(cfg)) or 0
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
