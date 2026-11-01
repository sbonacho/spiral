import json
import urllib.error
import urllib.request

from ..errors import SpiralError
from ..i18n import _

DEFAULT_URL = "http://localhost:11434"


def check(cfg):
    if not cfg.get("OLLAMA_MODEL"):
        raise SpiralError(_("LLM_PROVIDER=ollama necesita OLLAMA_MODEL en el .env."))


def complete(cfg, prompt):
    url = cfg.get("OLLAMA_URL", DEFAULT_URL).rstrip("/") + "/api/chat"
    body = json.dumps({"model": cfg.get("OLLAMA_MODEL"), "stream": False, "format": "json",
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.load(r)["message"]["content"]
    except (urllib.error.URLError, KeyError) as e:
        raise SpiralError(_("No pude usar Ollama en {url}: {error}", url=url, error=e)) from e
