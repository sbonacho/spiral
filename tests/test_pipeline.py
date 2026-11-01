import json

import pytest

from conftest import make_cfg, make_mov
from spiral import pipeline, summary
from spiral.errors import SpiralError
from spiral.workspace import Workspace

CONTENT = {"titulo": "Prueba", "resumen_corto": "corto", "resumen_largo": "largo",
           "capitulos": [{"inicio": 0, "titulo": "a"}], "tags": ["radio"], "hilo_x": ["t"],
           "post_blog_md": "x", "clips": [{"inicio": 0, "fin": 2, "gancho": "g", "titulo": "t"}]}


@pytest.fixture
def fakes(monkeypatch):
    calls = {"transcribe": 0}

    def fake_transcribe(program, outdir, language, hint):
        calls["transcribe"] += 1
        segs = [{"start": 0.0, "end": 2.5, "text": "hola"}]
        (outdir / "transcripcion.json").write_text(json.dumps(segs))
        (outdir / "transcripcion.txt").write_text("hola")
        (outdir / "transcripcion.srt").write_text("1\n")
        return segs

    monkeypatch.setattr(pipeline, "transcribe", fake_transcribe)
    monkeypatch.setattr(summary, "summarize", lambda cfg, segs, log, off=0: dict(CONTENT, offset_intro=off))
    return calls


def test_process_moves_original_and_writes_outputs(work, fakes):
    make_mov(work / "a.mov")
    pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    out = work / "processed" / "a"
    for f in ("episodio.mov", "episodio.mp3", "contenido.json", "transcripcion.txt", "done.json",
              "a.mov", "clips/clip1.mp4"):
        assert (out / f).exists(), f
    assert not (work / "a.mov").exists() and not (work / "processed" / ".a.tmp").exists()
    assert Workspace(make_cfg(work)).episode("a").stage == "processed"


def test_failure_keeps_original_and_retry_does_not_retranscribe(work, fakes, monkeypatch):
    make_mov(work / "a.mov")

    def boom(*a, **k):
        raise SpiralError("proveedor caído")

    monkeypatch.setattr(summary, "summarize", boom)
    with pytest.raises(SpiralError):
        pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    assert (work / "a.mov").exists()
    assert Workspace(make_cfg(work)).episode("a").stage == "pending"
    assert fakes["transcribe"] == 1

    monkeypatch.setattr(summary, "summarize", lambda cfg, segs, log, off=0: dict(CONTENT))
    pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    assert fakes["transcribe"] == 1 and not (work / "a.mov").exists()


def test_conflict_changes_nothing(work, fakes):
    make_mov(work / "a.mov")
    (work / "processed" / "a").mkdir(parents=True)
    (work / "processed" / "a" / "done.json").write_text("{}")
    with pytest.raises(SpiralError, match="Conflicto"):
        pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    assert (work / "a.mov").exists() and fakes["transcribe"] == 0


def test_redo_regenerates_and_keeps_published(work, fakes):
    make_mov(work / "a.mov")
    cfg = make_cfg(work)
    pipeline.process_episode(cfg, "a", log=lambda m: None)
    (work / "published" / "a").mkdir(parents=True)
    (work / "published" / "a" / "state.json").write_text('{"destinations": {"x/p": {"done": true}}}')
    (work / "processed" / "a" / "contenido.json").write_text('{"editado": true}')
    with pytest.raises(SpiralError, match="ya está procesado"):
        pipeline.process_episode(cfg, "a", log=lambda m: None)
    pipeline.process_episode(cfg, "a", log=lambda m: None, redo=True)
    assert json.loads((work / "processed" / "a" / "contenido.json").read_text())["titulo"] == "Prueba"
    assert (work / "processed" / "a" / "a.mov").exists()
    assert json.loads((work / "published" / "a" / "state.json").read_text())["destinations"]["x/p"]["done"]


def test_no_intro_outro_means_program_only(work, fakes):
    make_mov(work / "a.mov", seconds=2)
    pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    dur = float(pipeline.probe(work / "processed" / "a" / "episodio.mov")["duration"])
    assert 1.5 < dur < 3


def test_global_intro_is_added(work, fakes, isolated_home):
    make_mov(work / "a.mov", seconds=2)
    (isolated_home / ".config" / "spiral").mkdir(parents=True)
    make_mov(isolated_home / ".config" / "spiral" / "intro.mov", seconds=2)
    pipeline.process_episode(make_cfg(work), "a", log=lambda m: None)
    assert pipeline.probe(work / "processed" / "a" / "episodio.mov")["duration"] > 3.5
