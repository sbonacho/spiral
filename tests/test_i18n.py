import ast
import pathlib
import string

import pytest

from conftest import make_cfg
from spiral import cli, i18n, report
from spiral.destinations import discover
from spiral.i18n import EN, _, set_language
from spiral.workspace import DONE, Workspace

SRC = pathlib.Path(__file__).parents[1] / "src" / "spiral"


def literal_messages():
    found = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                found.add(node.args[0].value)
    return found


def fields(text):
    return {f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f}


def test_every_message_has_an_english_translation_with_same_placeholders():
    messages = literal_messages()
    assert messages, "no se encontraron mensajes"
    missing = sorted(m for m in messages if m not in EN)
    assert not missing, f"sin traducir: {missing}"
    for msg in messages:
        assert fields(msg) == fields(EN[msg]), msg


def test_no_stale_catalog_entries():
    dynamic = {"pendiente", "procesado", "publicado", "Audio + blog + RSS", "YouTube (episodio y Shorts)", "Bluesky",
               "Mastodon", "Instagram (Reels)", "X (enlaces; publicas tú)", "TikTok (subida a mano)"}
    assert set(EN) - literal_messages() <= dynamic


@pytest.mark.parametrize("code,expected", [(None, "es"), ("es", "es"), ("es-MX", "es"), ("ES_ar", "es"),
                                           ("en", "en"), ("en-US", "en"), ("fr", "en"), ("", "es")])
def test_language_selection(code, expected):
    set_language(code)
    assert i18n.language() == expected


def test_default_without_podcast_language_is_spanish(work, capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "Procesa y publica" in capsys.readouterr().out


@pytest.mark.parametrize("code", ["en", "fr"])
def test_help_and_list_in_english(work, capsys, monkeypatch, code):
    monkeypatch.setenv("PODCAST_LANGUAGE", code)
    (work / "a.mov").write_bytes(b"x")
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "Process and publish" in capsys.readouterr().out
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Episode" in out and "pending" in out and "Episodio" not in out


def test_regional_spanish_stays_spanish(work, capsys, monkeypatch):
    monkeypatch.setenv("PODCAST_LANGUAGE", "es-MX")
    (work / "a.mov").write_bytes(b"x")
    cli.main(["list"])
    assert "pendiente" in capsys.readouterr().out


def test_error_messages_follow_language(work, capsys, monkeypatch):
    monkeypatch.setenv("PODCAST_LANGUAGE", "en")
    (work / "a.mov").write_bytes(b"x")
    assert cli.main(["publish", "a", "--to", "site", "--yes"]) == 1
    assert "is not processed" in capsys.readouterr().out


def test_usage_error_in_english_without_terminal(work, capsys, monkeypatch):
    monkeypatch.setenv("PODCAST_LANGUAGE", "en")
    assert cli.main(["publish"]) == 2
    assert "Missing name" in capsys.readouterr().err


def test_destination_labels_are_translated(work):
    set_language("en")
    cfg = make_cfg(work, X_ACCOUNTS="show", TIKTOK_ACCOUNTS="show")
    labels = {d.id: d.label for d in discover(cfg)}
    assert labels["site"] == "Audio + blog + RSS" and "links; you post" in labels["x/show"]
    set_language("es")
    assert "publicas tú" in {d.id: d.label for d in discover(cfg)}["x/show"]


def test_report_in_english_has_lang_and_labels(work):
    d = work / "processed" / "a"
    d.mkdir(parents=True)
    (d / "contenido.json").write_text('{"titulo": "T"}')
    (d / DONE).write_text("{}")
    set_language("en")
    html = report.render(make_cfg(work), Workspace(make_cfg(work)).episodes())
    assert '<html lang="en">' in html and "Episodes report" in html and "processed" in html
    set_language("es")
    assert '<html lang="es">' in report.render(make_cfg(work), Workspace(make_cfg(work)).episodes())


def test_underscore_formats_placeholders():
    set_language("en")
    assert _("{n} episodio(s) -> {path}", n=2, path="/x") == "2 episode(s) -> /x"
