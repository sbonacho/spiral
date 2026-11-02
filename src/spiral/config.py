"""Configuración en capas: entorno del proceso > .env local > ~/.config/spiral/.env.

Las capas se combinan variable a variable; un valor vacío cuenta como no definido.
"""
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import SpiralError
from .i18n import _

PODCAST_REQUIRED = ("PODCAST_TITLE", "PODCAST_DESCRIPTION", "PODCAST_AUTHOR", "PODCAST_EMAIL",
                    "PODCAST_CATEGORY", "SITE_URL")
_SECRET_NAME = re.compile(r"TOKEN|PASSWORD|SECRET|KEY")
_ACCOUNT_NAME = re.compile(r"^[a-z0-9_]+$")


def global_dir():
    return Path.home() / ".config" / "spiral"


def parse_env(path):
    """Lee un fichero KEY=value; ignora comentarios, líneas sin '=' y valores vacíos."""
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            values[key.strip()] = value
    return values


@dataclass
class Config:
    root: Path
    values: dict

    @classmethod
    def load(cls, root=None, environ=None):
        root = Path(root or Path.cwd()).resolve()
        values = parse_env(global_dir() / ".env")
        values.update(parse_env(root / ".env"))
        env = os.environ if environ is None else environ
        values.update({k: v for k, v in env.items() if v})
        return cls(root, values)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def _folder(self, key, default):
        name = self.get(key, default)
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or str(path) == ".":
            raise SpiralError(_("{key}={name}: debe ser una ruta relativa dentro del directorio de trabajo, sin '..'",
                                key=key, name=name))
        return self.root / path

    @property
    def processed_dir(self):
        return self._folder("PROCESSED_DIR", "processed")

    @property
    def published_dir(self):
        return self._folder("PUBLISHED_DIR", "published")

    @property
    def site_dir(self):
        return self.root / "site"

    @property
    def language(self):
        return self.get("PODCAST_LANGUAGE", "es")

    def missing_podcast(self):
        return [k for k in PODCAST_REQUIRED if not self.get(k)]

    def podcast(self):
        """Metadatos del programa; falla si falta alguno obligatorio."""
        if missing := self.missing_podcast():
            raise SpiralError(_("Faltan en el .env: {missing}", missing=", ".join(missing)))
        site_url = self.get("SITE_URL").rstrip("/")
        if site_url.endswith(".git") or "//github.com/" in site_url:
            raise SpiralError(_("SITE_URL={url} es la dirección del repositorio; debe ser la de GitHub Pages "
                                "(https://<usuario>.github.io/<repo>).", url=site_url))
        return {"title": self.get("PODCAST_TITLE"), "description": self.get("PODCAST_DESCRIPTION"),
                "author": self.get("PODCAST_AUTHOR"), "email": self.get("PODCAST_EMAIL"),
                "language": self.language, "category": self.get("PODCAST_CATEGORY"),
                "image": self.get("PODCAST_IMAGE", ""), "site_url": site_url}

    def accounts(self, network):
        names = [a.strip().lower() for a in self.get(f"{network.upper()}_ACCOUNTS", "").split(",") if a.strip()]
        for name in names:
            if not _ACCOUNT_NAME.match(name):
                raise SpiralError(_("{var}: '{name}' solo puede tener letras, números y '_'",
                                    var=f"{network.upper()}_ACCOUNTS", name=name))
        return names

    def field(self, network, account, name):
        return self.get(f"{network.upper()}_{account.upper()}_{name}")

    def find_piece(self, name):
        """intro/outro: primero en el directorio de trabajo, luego en ~/.config/spiral/."""
        for folder in (self.root, global_dir()):
            if (folder / f"{name}.mov").is_file():
                return folder / f"{name}.mov"
        return None

    def secrets(self):
        return [v for k, v in self.values.items() if _SECRET_NAME.search(k) and len(v) >= 6]


def init_workspace(root):
    """Crea el .env del directorio copiando la plantilla del paquete (no pisa uno existente)."""
    target = Path(root) / ".env"
    if target.exists():
        return None
    shutil.copyfile(Path(__file__).with_name("env.example"), target)
    target.chmod(0o600)
    return target
