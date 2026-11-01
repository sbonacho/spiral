import shutil
import subprocess

from ..errors import SpiralError
from ..i18n import _

DEFAULT_MODEL = "claude-sonnet-5-5"   # sobrescribible con CLAUDE_MODEL; el alias por defecto de la CLI puede estar retirado


def check(cfg):
    if not shutil.which("claude"):
        raise SpiralError(_("LLM_PROVIDER=claude necesita la CLI 'claude' (Claude Code) en el PATH."))


def complete(cfg, prompt):
    try:
        out = subprocess.run(["claude", "-p", "--model", cfg.get("CLAUDE_MODEL", DEFAULT_MODEL)],
                             input=prompt, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        detail = (e.stderr.strip() or e.stdout.strip())[:300]   # la CLI escribe algunos errores en stdout
        raise SpiralError(_("'claude' falló: {detail}", detail=detail)) from e
    return out.stdout
