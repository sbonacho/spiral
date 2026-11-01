"""Procesado de un episodio: intro + programa + outro, mp3, transcripción, resumen y clips.

Todo se construye en processed/.<nombre>.tmp/; solo cuando está completo se renombra a
processed/<nombre>/ y se mueve el original dentro. Si algo falla, el original no se toca y los
pasos ya hechos se reutilizan en el siguiente intento.
"""
import json
import re
import shutil
import subprocess
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from . import summary
from .errors import SpiralError
from .workspace import DONE, Workspace

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
FONT = "/System/Library/Fonts/Helvetica.ttc"


def run(cmd, **kw):
    try:
        return subprocess.run([str(c) for c in cmd], check=True, **kw)
    except FileNotFoundError:
        raise SpiralError(f"No encuentro '{cmd[0]}'. Instálalo (por ejemplo: brew install ffmpeg).")
    except subprocess.CalledProcessError as e:
        raise SpiralError(f"Falló {cmd[0]} (código {e.returncode}).") from e


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
              capture_output=True, text=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    a = next(s for s in data["streams"] if s["codec_type"] == "audio")
    return {"video": (v["codec_name"], v["width"], v["height"], v["r_frame_rate"], v["pix_fmt"]),
            "audio": (a["codec_name"], a["sample_rate"], a["channels"]),
            "duration": float(data["format"]["duration"]),
            "size": (v["width"], v["height"]), "fps": v["r_frame_rate"]}


def concat(parts, program, dest, log):
    """Une los vídeos sin recodificar si tienen los mismos parámetros; si no, al formato del programa."""
    if len(parts) == 1:
        run(["ffmpeg", "-y", "-v", "error", "-i", parts[0], "-c", "copy", dest])
        return
    info = [probe(p) for p in parts]
    if all(i["video"] == info[0]["video"] and i["audio"] == info[0]["audio"] for i in info):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.writelines(f"file '{Path(p).resolve()}'\n" for p in parts)
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f.name, "-c", "copy", dest])
        return
    log("  formatos distintos: recodifico al formato del programa")
    ref = info[parts.index(program)]
    w, h = ref["size"]
    ins, chains = [], []
    for n, p in enumerate(parts):
        ins += ["-i", p]
        chains.append(f"[{n}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                      f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={ref['fps']},format=yuv420p[v{n}];"
                      f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo[a{n}]")
    labels = "".join(f"[v{n}][a{n}]" for n in range(len(parts)))
    graph = ";".join(chains) + f";{labels}concat=n={len(parts)}:v=1:a=1[v][a]"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-c:v", "h264_videotoolbox", "-b:v", "8M", "-c:a", "aac", "-b:a", "192k", dest])


def loudnorm(src, dest):
    """Normaliza el volumen en 2 pasadas; el vídeo no se recodifica."""
    r = run(["ffmpeg", "-v", "info", "-i", src, "-vn", "-af", f"{LOUDNORM}:print_format=json",
             "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
    af = (f"{LOUDNORM}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:v", "copy", "-af", af,
         "-ar", "48000", "-c:a", "aac", "-b:a", "192k", dest])


def srt_time(t):
    ms = int(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def transcribe(program, outdir, language, hint):
    """Transcribe solo el programa (sin intro/outro) para evitar alucinaciones con la música."""
    import mlx_whisper
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", program, "-vn", "-ac", "1", "-ar", "16000", wav])
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=WHISPER_MODEL, language=language,
                                     initial_prompt=hint, condition_on_previous_text=False)
    segs = res["segments"]
    (outdir / "transcripcion.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1))
    (outdir / "transcripcion.txt").write_text("\n".join(s["text"].strip() for s in segs))
    (outdir / "transcripcion.srt").write_text("\n".join(
        f"{i}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text'].strip()}\n"
        for i, s in enumerate(segs, 1)))
    return segs


def snap(segs, start, end):
    """Ajusta el clip a límites de frase de whisper (el LLM da tiempos aproximados)."""
    s = min(segs, key=lambda x: abs(x["start"] - start))["start"]
    ends = [x["end"] for x in segs if x["end"] >= s + 10]
    e = min(ends, key=lambda x: abs(x - end)) if ends else end
    return s, min(e, s + 90)


def wrap(text, width=26):
    return "\n".join(textwrap.wrap(text.strip(), width))


def make_clip(program, segs, clip, dest):
    """Vertical 9:16 con fondo desenfocado, título arriba y subtítulos abajo (drawtext: muchos
    ffmpeg no traen libass)."""
    start, end = snap(segs, clip["inicio"], clip["fin"])
    with tempfile.TemporaryDirectory() as tmp:
        draws = []

        def draw(text, name, pos, size, enable=""):
            f = Path(tmp) / name
            f.write_text(wrap(text, 22 if size > 60 else 26))
            draws.append(f"drawtext=fontfile={FONT}:textfile={f}:fontsize={size}:fontcolor=white:"
                         f"borderw=4:bordercolor=black:line_spacing=10:x=(w-text_w)/2:y={pos}{enable}")

        draw(clip["titulo"], "titulo.txt", "150", 72)
        for i, s in enumerate(x for x in segs if x["end"] > start and x["start"] < end):
            a, b = max(s["start"] - start, 0), min(s["end"] - start, end - start)
            draw(s["text"], f"s{i}.txt", "h-520", 56, f":enable='between(t,{a:.2f},{b:.2f})'")
        graph = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
                 "crop=1080:1920,boxblur=30[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                 + ",".join(draws) + ",format=yuv420p[v]")
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", program,
             "-filter_complex", graph, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "21",
             "-preset", "fast", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dest])


def process_episode(cfg, name, log=print, redo=False):
    """Procesa `name`. Si ya está procesado, solo se rehace con redo=True (conserva published/)."""
    ws = Workspace(cfg)
    ep = ws.episode(name)
    if ep.conflict:
        raise SpiralError(f"Conflicto: existen {name}.mov en el directorio y {ep.dir}. No toco nada; "
                          "renombra o mueve uno de los dos.")
    if ep.processed and not redo:
        raise SpiralError(f"{name} ya está procesado; para rehacerlo hay que confirmarlo explícitamente.")
    src = ep.original
    if src is None:
        raise SpiralError(f"No encuentro el .mov de «{name}» (ni en el directorio ni en {ep.dir}).")

    ws.processed_root.mkdir(parents=True, exist_ok=True)
    tmp = ws.processed_root / f".{name}.tmp"
    if redo and tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(exist_ok=True)
    intro, outro = cfg.find_piece("intro"), cfg.find_piece("outro")
    log(f"== {name}  (intro: {'sí' if intro else 'no'}, outro: {'sí' if outro else 'no'})")

    final_mov, mp3 = tmp / "episodio.mov", tmp / "episodio.mp3"
    if not final_mov.exists():
        parts = [p for p in (intro, src, outro) if p]
        raw = tmp / "_concat.mov"
        concat(parts, src, raw, log)
        loudnorm(raw, final_mov)
        raw.unlink()
    log("  vídeo final OK")

    if not mp3.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", final_mov, "-vn", "-c:a", "libmp3lame", "-b:a", "128k", mp3])
    log("  mp3 OK")

    if not (tmp / "transcripcion.json").exists():
        log("  transcribiendo…")
        transcribe(src, tmp, cfg.language, cfg.get("PODCAST_TITLE"))
    segs = json.loads((tmp / "transcripcion.json").read_text())
    log("  transcripción OK")

    if not (tmp / "contenido.json").exists():
        content = summary.summarize(cfg, segs, log, probe(intro)["duration"] if intro else 0)
        (tmp / "contenido.json").write_text(json.dumps(content, ensure_ascii=False, indent=2))
    content = json.loads((tmp / "contenido.json").read_text())
    log("  resumen OK")

    (tmp / "clips").mkdir(exist_ok=True)
    for n, clip in enumerate(content["clips"], 1):
        dest = tmp / "clips" / f"clip{n}.mp4"
        if not dest.exists():
            log(f"  clip {n}/{len(content['clips'])}…")
            make_clip(src, segs, clip, dest)
    log("  clips OK")

    files = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
    (tmp / DONE).write_text(json.dumps(
        {"version": 1, "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "provider": cfg.get("LLM_PROVIDER", "claude"), "files": files}, indent=1))
    _swap_in(tmp, ep, src)
    log(f"  listo -> {ep.dir}")


def _swap_in(tmp, ep, src):
    """tmp -> processed/<nombre>/ y el original dentro (también al reprocesar)."""
    if ep.processed:  # reprocesado: el original ya vive dentro de la carpeta antigua
        old = ep.dir.with_name(f".{ep.name}.old")
        shutil.move(str(src), str(tmp / src.name))
        ep.dir.rename(old)
        tmp.rename(ep.dir)
        shutil.rmtree(old)
    else:
        tmp.rename(ep.dir)
        shutil.move(str(src), str(ep.dir / src.name))
