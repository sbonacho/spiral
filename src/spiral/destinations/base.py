"""Piezas comunes de los destinos de publicación (red + cuenta)."""
import json
import os
from dataclasses import dataclass, field
from typing import Callable

from ..config import global_dir


class Pending(Exception):
    """El destino se ha preparado pero no queda registrado como publicado (p. ej. manual sin confirmar)."""


@dataclass(frozen=True)
class Network:
    key: str
    label: str
    publish: Callable
    preview: Callable
    required: tuple = ()
    check: Callable | None = None   # (cfg, account) -> lista de cosas que faltan, además de `required`
    manual: bool = False
    needs_url: bool = True          # enlaza al post del blog, así que necesita SITE_URL

    def missing(self, cfg, account):
        out = [f"{self.key.upper()}_{account.upper()}_{f}" for f in self.required
               if not cfg.field(self.key, account, f)]
        if self.check:
            out += self.check(cfg, account)
        if self.needs_url and not cfg.get("SITE_URL"):
            out.append("SITE_URL")
        return out


@dataclass(frozen=True)
class Destination:
    id: str
    key: str
    account: str
    label: str
    missing: tuple
    network: Network | None = None   # None = el sitio

    @property
    def is_site(self):
        return self.key == "site"

    @property
    def configured(self):
        return not self.missing


@dataclass
class Context:
    cfg: object
    ep: object
    content: dict
    key: str
    account: str
    url: str | None
    log: Callable
    ask: Callable                     # ask(kind, pregunta) -> bool; kinds: "push", "manual"
    partial: dict = field(default_factory=dict)
    checkpoint: Callable = lambda partial: None
    secrets: set = field(default_factory=set)

    def field(self, name):
        return self.cfg.field(self.key, self.account, name)


def token_path(network, account):
    return global_dir() / "tokens" / f"{network}-{account}.json"


def read_token(network, account):
    f = token_path(network, account)
    return json.loads(f.read_text()) if f.is_file() else None


def write_token(network, account, data):
    """Guarda un token con permisos 600 en ~/.config/spiral/tokens/ (nunca en el directorio de trabajo)."""
    f = token_path(network, account)
    f.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))
    f.chmod(0o600)


def fit(text, room):
    """Recorta en el límite de palabra, con puntos suspensivos."""
    if len(text) <= room:
        return text
    return text[:room - 1].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def hashtags(content, n=3):
    return " ".join("#" + "".join(w.capitalize() for w in t.split()) for t in content["tags"][:n])


def short_text(content):
    return f"{content['resumen_corto']} {hashtags(content)}"
