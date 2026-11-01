"""Destinos de publicación: el sitio y cada red con sus cuentas (`red/cuenta`)."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..errors import SpiralError
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
    out = [Destination(site.ID, site.ID, "", site.LABEL, tuple(site.missing(cfg)))]
    for net in NETWORKS:
        for account in cfg.accounts(net.key):
            out.append(Destination(f"{net.key}/{account}", net.key, account, f"{net.label} · {account}",
                                   tuple(net.missing(cfg, account)), net))
    return out


def publish(cfg, name, ids, *, dry=False, log=print, ask=lambda kind, question: False):
    """Publica el episodio `name` en los destinos `ids`. Devuelve una lista de Result."""
    ep = Workspace(cfg).episode(name)
    if not ep.processed:
        raise SpiralError(f"«{name}» no está procesado: procésalo antes de publicar.")
    dests = {d.id: d for d in discover(cfg)}
    if unknown := [i for i in ids if i not in dests]:
        raise SpiralError(f"Destino(s) desconocido(s): {', '.join(unknown)}. "
                          f"Disponibles: {', '.join(dests) or 'ninguno'}")
    if bad := [f"{i} (falta {', '.join(dests[i].missing)})" for i in ids if dests[i].missing]:
        raise SpiralError("No configurados: " + "; ".join(bad))

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
        if info.get("done"):
            results.append(Result(did, "skipped", "ya estaba publicado"))
            say(f"- {did}: ya estaba publicado, se omite")
            continue
        if site_failed and not d.is_site and d.key != "tiktok":
            results.append(Result(did, "not-attempted", "depende del sitio, que ha fallado"))
            say(f"- {did}: no se intenta porque el sitio ha fallado")
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
            say(f"- {did}: preparado, sin registrar como publicado")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            detail = redact(str(e))
            journal(did, "failed", detail)
            results.append(Result(did, "failed", detail))
            say(f"- {did}: ERROR {detail}")
            site_failed = site_failed or d.is_site
    return results
