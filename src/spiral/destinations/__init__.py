"""Destinos de publicación: el sitio y cada red con sus cuentas (`red/cuenta`)."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..errors import SpiralError
from ..i18n import _
from ..workspace import Workspace, read_state, write_state
from . import bluesky, instagram, manual, mastodon, site, youtube
from .base import Context, Destination, Pending

NETWORKS = (youtube.NETWORK, bluesky.NETWORK, mastodon.NETWORK, instagram.NETWORK, manual.X, manual.TIKTOK)
BY_KEY = {n.key: n for n in NETWORKS}


@dataclass
class Result:
    id: str
    status: str   # ok | skipped | simulated | pending | failed | not-attempted
    detail: str = ""


def discover(cfg):
    """Todos los destinos conocidos, configurados o no: `site` y cada red con sus cuentas."""
    out = [Destination(site.ID, site.ID, "", _(site.LABEL), tuple(site.missing(cfg)))]
    for net in NETWORKS:
        for account in cfg.accounts(net.key):
            out.append(Destination(f"{net.key}/{account}", net.key, account, f"{_(net.label)} · {account}",
                                   tuple(net.missing(cfg, account)), net))
    return out


def publish(cfg, name, ids, *, dry=False, force=False, log=print, ask=lambda kind, question: False):
    """Publica el episodio `name` en los destinos `ids`; `force` repite los ya publicados. Devuelve Results."""
    ep = Workspace(cfg).episode(name)
    if not ep.processed:
        raise SpiralError(_("«{name}» no está procesado: procésalo antes de publicar.", name=name))
    dests = {d.id: d for d in discover(cfg)}
    if unknown := [i for i in ids if i not in dests]:
        raise SpiralError(_("Destino(s) desconocido(s): {unknown}. Disponibles: {available}", unknown=", ".join(unknown),
                          available=", ".join(dests) or _("ninguno")))
    if bad := [_("{id} (falta {missing})", id=i, missing=", ".join(dests[i].missing)) for i in ids if dests[i].missing]:
        raise SpiralError(_("No configurados: {list}", list="; ".join(bad)))

    content = json.loads((ep.dir / "contenido.json").read_text())
    url = site.episode_url(cfg, content) if cfg.get("SITE_URL") else None
    secrets = set(cfg.secrets())
    state = read_state(ep.published)
    logfile = ep.published / "publish.log"

    def redact(text):
        for s in secrets:
            text = text.replace(s, "***")
        return text

    def say(msg):
        log(redact(msg))

    def journal(did, status, detail=""):
        line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {did} {status} {detail}".rstrip()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open("a") as f:
            f.write(redact(line).replace("\n", " ") + "\n")

    results, site_failed = [], False
    for did in sorted(ids, key=lambda i: (i != site.ID, i)):
        d = dests[did]
        info = state["destinations"].get(did, {})
        if info.get("done") and not force:
            results.append(Result(did, "skipped", _("ya estaba publicado")))
            say(_("- {id}: ya estaba publicado, se omite", id=did))
            continue
        if site_failed and not d.is_site and d.key != "tiktok":
            results.append(Result(did, "not-attempted", _("depende del sitio, que ha fallado")))
            say(_("- {id}: no se intenta porque el sitio ha fallado", id=did))
            continue

        def checkpoint(partial, did=did):
            if not dry:
                state["destinations"][did] = {"done": False, "partial": partial}
                write_state(ep.published, state)

        ctx = Context(cfg=cfg, ep=ep, content=content, key=d.key, account=d.account, url=url, log=say,
                      ask=ask, partial=dict(info.get("partial", {})), checkpoint=checkpoint, secrets=secrets)
        handler = site if d.is_site else d.network
        try:
            if dry:
                say(handler.preview(ctx))
                results.append(Result(did, "simulated"))
                continue
            say(f"- {did}…")
            ref = handler.publish(ctx)
            state["destinations"][did] = {"done": True, "mode": "manual" if (d.network and d.network.manual) else "auto",
                                          "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ref": ref}
            write_state(ep.published, state)
            journal(did, "ok")
            results.append(Result(did, "ok"))
        except Pending as e:
            journal(did, "pending", str(e))
            results.append(Result(did, "pending", str(e)))
            say(_("- {id}: preparado, sin registrar como publicado", id=did))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            detail = redact(str(e))
            journal(did, "failed", detail)
            results.append(Result(did, "failed", detail))
            say(_("- {id}: ERROR {detail}", id=did, detail=detail))
            site_failed = site_failed or d.is_site
    return results
