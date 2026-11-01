"""Resumen y contenido derivado del episodio con el proveedor elegido en LLM_PROVIDER."""
import json

from ..errors import SpiralError
from . import claude, gemini, ollama

PROVIDERS = {"claude": claude, "gemini": gemini, "ollama": ollama}
REQUIRED = ("titulo", "resumen_corto", "resumen_largo", "capitulos", "tags", "hilo_x", "post_blog_md", "clips")

PROMPT = """You are the editor of a radio show. Below is the transcript of an episode, with times in seconds.
Reply with ONLY a JSON object (no surrounding text, no code fences), written in the language with ISO
code "{language}", with these keys:
{{
  "titulo": "catchy title, max 80 characters",
  "resumen_corto": "2-3 sentences for a platform description",
  "resumen_largo": "150-250 word summary of the content",
  "capitulos": [{{"inicio": seconds, "titulo": "..."}}],
  "tags": ["..."],
  "hilo_x": ["hook tweet (<=270 chars)", "..."],
  "post_blog_md": "blog post in markdown, 250-400 words",
  "clips": [{{"inicio": seconds, "fin": seconds, "gancho": "opening sentence", "titulo": "..."}}]
}}
Rules: 5-8 chapters; 3-5 clips of 30-90 s that work on their own, starting and ending on sentence
boundaries and not overlapping each other; do not invent anything that is not in the transcript.

TRANSCRIPT:
"""


def validate(data):
    """Comprueba la estructura; lanza SpiralError con el primer problema."""
    if not isinstance(data, dict):
        raise SpiralError("La respuesta del proveedor no es un objeto JSON.")
    for key in REQUIRED:
        if key not in data:
            raise SpiralError(f"Falta '{key}' en la respuesta del proveedor.")
    for key in ("capitulos", "tags", "hilo_x", "clips"):
        if not isinstance(data[key], list):
            raise SpiralError(f"'{key}' debe ser una lista.")
    if not data["hilo_x"]:
        raise SpiralError("'hilo_x' no puede estar vacío.")
    for clip in data["clips"]:
        if not isinstance(clip, dict) or not {"inicio", "fin", "gancho", "titulo"} <= clip.keys():
            raise SpiralError("Cada clip necesita inicio, fin, gancho y titulo.")
    return data


def parse(text):
    try:
        return validate(json.loads(text[text.index("{"): text.rindex("}") + 1]))
    except ValueError as e:  # incluye JSONDecodeError y .index() sin llaves
        raise SpiralError(f"La respuesta del proveedor no es JSON válido: {e}") from e


def summarize(cfg, segs, log, offset_intro=0):
    provider = cfg.get("LLM_PROVIDER", "claude")
    module = PROVIDERS.get(provider)
    if module is None:
        raise SpiralError(f"LLM_PROVIDER={provider} no es válido; usa uno de: {', '.join(PROVIDERS)}")
    module.check(cfg)  # falla antes de enviar nada si falta configuración
    where = "se queda en tu máquina" if provider == "ollama" else f"se enviará a {provider}"
    log(f"  resumen con {provider}: la transcripción {where}")
    transcript = "\n".join(f"[{s['start']:.0f}] {s['text'].strip()}" for s in segs)
    data = parse(module.complete(cfg, PROMPT.format(language=cfg.language) + transcript))
    data["offset_intro"] = offset_intro  # los tiempos son del programa; en el vídeo final suma la intro
    return data
