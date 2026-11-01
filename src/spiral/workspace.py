"""Episodios del directorio de trabajo: el estado se deduce de las carpetas.

  pendiente  <nombre>.mov en el directorio y sin processed/<nombre>/ completa
  procesado  processed/<nombre>/ con done.json (se escribe lo último)
  publicado  published/<nombre>/state.json con algún destino hecho
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

DONE = "done.json"
STATE = "state.json"
RESERVED = ("intro", "outro")


@dataclass
class Episode:
    name: str
    mov: Path | None          # .mov original en el directorio de trabajo, si sigue ahí
    dir: Path                 # processed/<nombre>
    published: Path           # published/<nombre>
    processed: bool
    title: str = ""
    destinations: dict = field(default_factory=dict)

    @property
    def stage(self):
        if any(d.get("done") for d in self.destinations.values()):
            return "published"
        return "processed" if self.processed else "pending"

    @property
    def done_destinations(self):
        return [k for k, v in self.destinations.items() if v.get("done")]

    @property
    def conflict(self):
        return self.mov is not None and self.processed

    @property
    def original(self):
        """Dónde está el original: en el directorio (pendiente) o dentro de processed/."""
        if self.mov:
            return self.mov
        inside = self.dir / f"{self.name}.mov"
        return inside if inside.is_file() else None


def read_state(published_dir):
    f = published_dir / STATE
    if not f.is_file():
        return {"destinations": {}}
    state = json.loads(f.read_text())
    state.setdefault("destinations", {})
    return state


def write_state(published_dir, state):
    published_dir.mkdir(parents=True, exist_ok=True)
    (published_dir / STATE).write_text(json.dumps(state, ensure_ascii=False, indent=1))


class Workspace:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = cfg.root
        self.processed_root = cfg.processed_dir
        self.published_root = cfg.published_dir

    def names(self):
        found = {p.stem for p in self.root.glob("*.mov") if p.stem not in RESERVED}
        for folder in (self.processed_root, self.published_root):
            if folder.is_dir():
                found |= {d.name for d in folder.iterdir() if d.is_dir() and not d.name.startswith(".")}
        return sorted(found)

    def episode(self, name):
        mov = self.root / f"{name}.mov"
        pdir = self.processed_root / name
        processed = (pdir / DONE).is_file()
        ep = Episode(name=name, mov=mov if mov.is_file() else None, dir=pdir,
                     published=self.published_root / name, processed=processed)
        if processed:
            try:
                ep.title = json.loads((pdir / "contenido.json").read_text()).get("titulo", "")
            except (OSError, ValueError):
                pass
        ep.destinations = read_state(ep.published)["destinations"]
        return ep

    def episodes(self):
        return [self.episode(n) for n in self.names()]
