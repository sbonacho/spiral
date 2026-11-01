import shutil
import subprocess

import pytest

from spiral.config import Config

ENV_KEYS = ("LLM_PROVIDER", "PROCESSED_DIR", "PUBLISHED_DIR", "SITE_URL", "GEMINI_API_KEY", "OLLAMA_MODEL")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """HOME temporal: ni lee ni escribe ~/.config/spiral real."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return home


@pytest.fixture
def work(tmp_path, monkeypatch):
    d = tmp_path / "work"
    d.mkdir()
    monkeypatch.chdir(d)
    return d


def make_cfg(root, **values):
    return Config(root.resolve(), values)


def make_mov(path, seconds=3):
    """Un .mov mínimo con vídeo y audio (requiere ffmpeg)."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg no instalado")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=320x240:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=d={seconds}", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path
