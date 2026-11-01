import json
import urllib.error
import urllib.request

from ..errors import SpiralError

DEFAULT_MODEL = "gemini-2.5-flash"


def check(cfg):
    if not cfg.get("GEMINI_API_KEY"):
        raise SpiralError("LLM_PROVIDER=gemini necesita GEMINI_API_KEY en el .env.")


def complete(cfg, prompt):
    model = cfg.get("GEMINI_MODEL", DEFAULT_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "x-goog-api-key": cfg.get("GEMINI_API_KEY")})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        raise SpiralError(f"Gemini respondió {e.code}: {e.read().decode()[:200]}") from e
    except (urllib.error.URLError, KeyError, IndexError) as e:
        raise SpiralError(f"No pude usar Gemini: {e}") from e
