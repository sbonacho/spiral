"""Duración de los ficheros para los listados: ffprobe en paralelo y con caché por ruta, tamaño y fecha."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def cache_file():
    return Path.home() / ".cache" / "spiral" / "durations.json"


def probe(path):
    """Segundos del fichero, o None si ffprobe no puede leerlo."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True, timeout=20)
        return int(float(out.stdout))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def durations(paths):
    """{ruta: segundos|None}. Solo se llama a ffprobe para lo que no está en la caché."""
    try:
        cache = json.loads(cache_file().read_text())
    except (OSError, ValueError):
        cache = {}
    keys, todo = {}, []
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        keys[p] = f"{p}|{st.st_size}|{st.st_mtime_ns}"
        if keys[p] not in cache:
            todo.append(p)
    if todo:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for p, secs in zip(todo, pool.map(probe, todo)):
                if secs is not None:
                    cache[keys[p]] = secs
        try:
            cache_file().parent.mkdir(parents=True, exist_ok=True)
            cache_file().write_text(json.dumps(cache))
        except OSError:
            pass
    return {p: cache.get(k) for p, k in keys.items()}


def clock(seconds):
    """47:12 o 1:02:03; '–' si no se conoce."""
    if seconds is None:
        return "–"
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
