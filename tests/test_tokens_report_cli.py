import json
import stat

from conftest import make_cfg
from spiral import cli, report
from spiral.config import global_dir
from spiral.destinations.base import read_token, token_path, write_token
from spiral.workspace import DONE, write_state


def test_token_saved_globally_with_600(work, isolated_home):
    write_token("youtube", "canal", '{"a": 1}')
    p = token_path("youtube", "canal")
    assert p == global_dir() / "tokens" / "youtube-canal.json"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600 and read_token("youtube", "canal") == {"a": 1}
    assert not list(work.rglob("*.json"))


def test_report_states_icons_and_escaping(work):
    for n, title in (("b", "<script>alert(1)</script>"), ("c", "ok")):
        d = work / "processed" / n
        d.mkdir(parents=True)
        (d / "contenido.json").write_text(json.dumps({"titulo": title}))
        (d / DONE).write_text("{}")
    (work / "a.mov").write_bytes(b"x")
    write_state(work / "published" / "c", {"destinations": {"bluesky/p": {
        "done": True, "ref": "https://bsky.app/x", "mode": "auto"}}})
    html = report.render(make_cfg(work), __import__("spiral.workspace", fromlist=["x"]).Workspace(make_cfg(work)).episodes())
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "📢" in html and "⏳" in html and "⚙️" in html and "bluesky/p" in html
    assert html.count("<tr>") == 1 + 3 + 1  # cabecera + 3 episodios + pie


def test_report_written_in_published_dir(work):
    path, n = report.write(make_cfg(work))
    assert path == work.resolve() / "published" / "report.html" and n == 0


def run(work, argv, capsys):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_usage_errors_without_terminal(work, capsys):
    assert run(work, ["publish"], capsys)[0] == 2
    assert run(work, ["process"], capsys)[0] == 2
    assert run(work, [], capsys)[0] == 2


def test_help_has_no_archive_and_version_works(work, capsys):
    import pytest
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0 and "archive" not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "spiral 0.1.0" in capsys.readouterr().out


def test_list_works_without_env(work, capsys):
    (work / "a.mov").write_bytes(b"x")
    code, out = run(work, ["list"], capsys)
    assert code == 0 and "a" in out


def test_publish_pending_fails_with_hint(work, capsys):
    (work / "a.mov").write_bytes(b"x")
    code, out = run(work, ["publish", "a", "--to", "site", "--yes"], capsys)
    assert code == 1 and "no está procesado" in out


def test_process_several_continues_after_a_failure(work, capsys, monkeypatch):
    from spiral.errors import SpiralError
    calls = []

    def fake(cfg, name, log, redo):
        calls.append(name)
        if name == "b":
            raise SpiralError("ffmpeg falló")
    monkeypatch.setattr(cli, "process_episode", fake)
    for n in "abc":
        (work / f"{n}.mov").write_bytes(b"x")
    code, out = run(work, ["process", "a", "b", "c"], capsys)
    assert code == 1 and calls == ["a", "b", "c"] and "b: ffmpeg falló" in out and "2 de 3" in out


def test_publish_several_checks_all_are_processed_before_publishing(work, capsys, monkeypatch):
    published = []
    monkeypatch.setattr(cli, "publish_episode", lambda *a, **k: published.append(a[1]) or [])
    (work / "processed" / "a").mkdir(parents=True)
    (work / "processed" / "a" / "done.json").write_text("{}")
    (work / "b.mov").write_bytes(b"x")
    code, out = run(work, ["publish", "a", "b", "--to", "site", "--yes"], capsys)
    assert code == 1 and "«b» no está procesado" in out and published == []


def test_publish_force_flag_reaches_the_publisher(work, capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "publish_episode", lambda *a, **k: seen.append(k["force"]) or [])
    (work / "processed" / "a").mkdir(parents=True)
    (work / "processed" / "a" / "done.json").write_text("{}")
    run(work, ["publish", "a", "--to", "site", "--yes"], capsys)
    run(work, ["publish", "a", "--to", "site", "--yes", "--force"], capsys)
    assert seen == [False, True]
