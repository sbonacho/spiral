import json

from conftest import make_cfg
from spiral.workspace import DONE, Workspace, write_state


def processed(work, name, title="Título"):
    d = work / "processed" / name
    d.mkdir(parents=True)
    (d / "contenido.json").write_text(json.dumps({"titulo": title}))
    (d / DONE).write_text("{}")


def test_pending_processed_published_states(work):
    (work / "a.mov").write_bytes(b"x")
    processed(work, "b")
    processed(work, "c")
    write_state(work / "published" / "c", {"destinations": {"bluesky/p": {"done": True}}})
    eps = {e.name: e for e in Workspace(make_cfg(work)).episodes()}
    assert [eps[n].stage for n in "abc"] == ["pending", "processed", "published"]
    assert eps["b"].title == "Título" and eps["c"].done_destinations == ["bluesky/p"]


def test_processed_without_original_still_listed(work):
    processed(work, "a")
    assert Workspace(make_cfg(work)).episode("a").stage == "processed"


def test_incomplete_processed_dir_is_not_processed(work):
    (work / "processed" / "a").mkdir(parents=True)
    (work / "a.mov").write_bytes(b"x")
    assert Workspace(make_cfg(work)).episode("a").stage == "pending"


def test_intro_outro_and_subdirs_are_not_episodes(work):
    for n in ("intro", "outro", "a"):
        (work / f"{n}.mov").write_bytes(b"x")
    (work / "sub").mkdir()
    (work / "sub" / "c.mov").write_bytes(b"x")
    assert Workspace(make_cfg(work)).names() == ["a"]


def test_failed_destination_is_not_published(work):
    processed(work, "a")
    write_state(work / "published" / "a", {"destinations": {"x/p": {"done": False, "partial": {}}}})
    assert Workspace(make_cfg(work)).episode("a").stage == "processed"


def test_conflict_when_original_and_processed_coexist(work):
    processed(work, "a")
    (work / "a.mov").write_bytes(b"x")
    assert Workspace(make_cfg(work)).episode("a").conflict


def test_durations_are_listed_and_cached(work, monkeypatch):
    from spiral import media
    from spiral.workspace import Workspace
    from conftest import make_cfg
    (work / "a.mov").write_bytes(b"x")
    (work / "b.mov").write_bytes(b"yy")
    calls = []
    monkeypatch.setattr(media, "probe", lambda p: calls.append(p.name) or (3725 if p.name == "a.mov" else None))
    eps = {e.name: e for e in Workspace(make_cfg(work)).episodes()}
    assert eps["a"].duration == 3725 and eps["b"].duration is None
    assert media.clock(3725) == "1:02:05" and media.clock(754) == "12:34" and media.clock(None) == "–"
    Workspace(make_cfg(work)).episodes()
    assert sorted(calls) == ["a.mov", "b.mov", "b.mov"]   # a viene de la caché; b falló y se reintenta
