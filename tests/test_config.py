import pytest

from spiral.config import Config, global_dir, parse_env
from spiral.errors import SpiralError


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_local_overrides_global(work):
    write(global_dir() / ".env", "LLM_PROVIDER=claude\n")
    write(work / ".env", "LLM_PROVIDER=ollama\n")
    assert Config.load(work, environ={}).get("LLM_PROVIDER") == "ollama"


def test_global_only_value_is_kept(work):
    write(global_dir() / ".env", "IA_ACCESS_KEY=abc\n")
    assert Config.load(work, environ={}).get("IA_ACCESS_KEY") == "abc"


def test_empty_local_value_does_not_override(work):
    write(global_dir() / ".env", "BLUESKY_PROGRAMA_HANDLE=global.bsky.social\n")
    write(work / ".env", "BLUESKY_PROGRAMA_HANDLE=\n")
    assert Config.load(work, environ={}).get("BLUESKY_PROGRAMA_HANDLE") == "global.bsky.social"


def test_process_environment_wins(work):
    write(work / ".env", "LLM_PROVIDER=ollama\n")
    assert Config.load(work, environ={"LLM_PROVIDER": "gemini"}).get("LLM_PROVIDER") == "gemini"


def test_no_env_files_is_fine(work):
    cfg = Config.load(work, environ={})
    assert cfg.values == {} and cfg.processed_dir == work.resolve() / "processed"


def test_parse_env_handles_quotes_comments_export(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# c\nexport A="x y"\nB=\'z\'\nC=\nbad line\n')
    assert parse_env(f) == {"A": "x y", "B": "z"}


@pytest.mark.parametrize("value", ["../fuera", "/tmp/x", "a/../../b", "."])
def test_folder_outside_workdir_is_rejected(work, value):
    cfg = Config(work, {"PROCESSED_DIR": value})
    with pytest.raises(SpiralError, match="PROCESSED_DIR"):
        cfg.processed_dir
    assert not (work.parent / "fuera").exists()


def test_custom_folder_name(work):
    assert Config(work, {"PUBLISHED_DIR": "listos"}).published_dir == work / "listos"


def test_missing_podcast_names_variables(work):
    cfg = Config(work, {"PODCAST_TITLE": "T"})
    assert "SITE_URL" in cfg.missing_podcast()
    with pytest.raises(SpiralError, match="SITE_URL"):
        cfg.podcast()


def test_intro_local_beats_global_and_absent_is_none(work):
    assert Config(work, {}).find_piece("intro") is None
    (global_dir()).mkdir(parents=True)
    (global_dir() / "intro.mov").write_bytes(b"g")
    assert Config(work, {}).find_piece("intro") == global_dir() / "intro.mov"
    (work / "intro.mov").write_bytes(b"l")
    assert Config(work, {}).find_piece("intro") == work / "intro.mov"


def test_accounts_parse_and_validate(work):
    cfg = Config(work, {"BLUESKY_ACCOUNTS": "Programa, personal", "MASTODON_ACCOUNTS": "mal-nombre"})
    assert cfg.accounts("bluesky") == ["programa", "personal"]
    with pytest.raises(SpiralError, match="MASTODON_ACCOUNTS"):
        cfg.accounts("mastodon")
