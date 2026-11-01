"""Prueba de humo de los selectores interactivos en un pseudo-terminal."""
import json
import sys

import pytest

pexpect = pytest.importorskip("pexpect")

DOWN, SPACE, ENTER = "\x1b[B", " ", "\r"


CONFIGURED = {"SITE_URL": "https://e.github.io/p", "PODCAST_TITLE": "T", "PODCAST_DESCRIPTION": "d",
              "PODCAST_AUTHOR": "a", "PODCAST_EMAIL": "a@e.com", "PODCAST_CATEGORY": "Society",
              "IA_ACCESS_KEY": "k", "IA_SECRET_KEY": "s", "BLUESKY_ACCOUNTS": "programa",
              "BLUESKY_PROGRAMA_HANDLE": "h", "BLUESKY_PROGRAMA_APP_PASSWORD": "secreto123",
              "MASTODON_ACCOUNTS": "canal"}


def spawn(tmp_path, home, config):
    """Lanza `spiral` en un pseudo-terminal con un episodio procesado y otro pendiente."""
    work = tmp_path / "work"
    ep = work / "processed" / "2026-11-01_charla"
    ep.mkdir(parents=True)
    (work / "pendiente.mov").write_bytes(b"x")
    (ep / "contenido.json").write_text(json.dumps({
        "titulo": "Charla de prueba", "resumen_corto": "Resumen corto", "resumen_largo": "l",
        "capitulos": [{"inicio": 0, "titulo": "a"}], "tags": ["radio"], "hilo_x": ["t"],
        "post_blog_md": "x", "clips": []}))
    (ep / "done.json").write_text("{}")
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "NO_COLOR": "1",
           "PYTHONPATH": str(__import__("pathlib").Path(__file__).parents[1] / "src")} | config
    return pexpect.spawn(sys.executable, ["-c", "import sys; from spiral.cli import main; sys.exit(main())"],
                         cwd=str(work), env=env, dimensions=(40, 120), encoding="utf-8", timeout=30)


@pytest.fixture
def session(tmp_path, isolated_home):
    child = spawn(tmp_path, isolated_home, CONFIGURED)
    yield child
    child.close(force=True)


@pytest.fixture
def bare_session(tmp_path, isolated_home):
    """Sin ningún .env: ningún destino configurado."""
    child = spawn(tmp_path, isolated_home, {})
    yield child
    child.close(force=True)


def test_arrows_filter_space_disabled_and_dry_run(session, tmp_path):
    c = session
    c.expect("falta: MASTODON_CANAL_URL")             # panel: destino sin configurar con su motivo
    c.expect("Qué quieres hacer")
    c.send(DOWN * 2 + ENTER)                          # flechas: publish
    c.expect("Qué episodio publicas")
    c.expect("pendiente")                             # el pendiente aparece pero deshabilitado
    c.send("char")                                    # filtra al escribir
    c.send(ENTER)
    c.expect("Dónde publicar")
    c.expect("falta: MASTODON_CANAL_URL")             # casilla deshabilitada con motivo
    c.send(SPACE + DOWN + SPACE + ENTER)              # espacio marca site y bluesky
    c.expect("2 selections")
    c.expect("Cómo")
    c.send(DOWN + ENTER)                              # Simular
    c.expect(r"\[bluesky/programa\] Resumen corto")
    c.expect("Resultado")
    c.expect("Qué quieres hacer")
    c.send(DOWN * 4 + ENTER)                          # salir
    c.expect(pexpect.EOF)
    c.close()
    assert c.exitstatus == 0
    assert not (tmp_path / "work" / "published").exists()   # simular no escribe nada


def test_ctrl_c_in_a_selector_cancels_without_changes(session, tmp_path):
    c = session
    c.expect("Qué quieres hacer")
    c.send(DOWN * 2 + ENTER)
    c.expect("Qué episodio publicas")
    c.send("\x03")                                    # Ctrl-C en el selector
    c.expect("Qué quieres hacer")                     # vuelve al menú
    c.send(DOWN * 4 + ENTER)
    c.expect(pexpect.EOF)
    c.close()
    assert c.exitstatus == 0 and not (tmp_path / "work" / "published").exists()


def test_publish_with_nothing_configured_explains_instead_of_crashing(bare_session):
    c = bare_session
    c.expect("Qué quieres hacer")
    c.send(DOWN * 2 + ENTER)                          # publish
    c.expect("Qué episodio publicas")
    c.send(ENTER)                                     # el procesado
    c.expect("Ningún destino configurado")            # mensaje claro, no un Traceback
    c.expect("Qué quieres hacer")                     # y vuelve al menú
    c.send(DOWN * 4 + ENTER)
    c.expect(pexpect.EOF)
    c.close()
    assert c.exitstatus == 0
    assert "Traceback" not in c.before
