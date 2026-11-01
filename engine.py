#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["mlx-whisper", "internetarchive", "google-api-python-client", "google-auth-oauthlib", "atproto", "Mastodon.py"]
# ///
"""Procesa los .mov de OBS de un directorio: intro+programa+outro, mp3, transcripción y resumen.

Uso: ./engine.py process DIRECTORIO [--intro intro.mov] [--outro outro.mov]
        opciones: --episodio NOMBRE (repetible, solo esos) y --rehacer (borra lo generado antes)
     ./engine.py publish DIRECTORIO EPISODIO [--push]   (mp3 -> Archive.org, blog y feed.xml en site/)
     ./engine.py archive                    (mueve los episodios procesados a ARCHIVE_DIR/<episodio>/)
     ./engine.py report [-o informe.html]   (tabla HTML: qué se ha subido y dónde)
     ./engine.py social DIRECTORIO EPISODIO [--only youtube,bluesky,mastodon,x,instagram] [--dry-run]

Cada .mov del directorio (salvo intro/outro) es un episodio. Si intro.mov / outro.mov
existen en el directorio (o se indican con --intro/--outro) se pegan delante/detrás.
Salida en DIRECTORIO/out/<episodio>/. Es re-ejecutable: salta lo que ya está hecho.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import library
import social

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
LLM_MODEL = "sonnet"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"

PROMPT = """Eres el editor de un programa de radio. Te paso la transcripción (con tiempos en segundos)
de un episodio. Devuelve SOLO un objeto JSON (sin texto alrededor, sin ```), en español, con:
{
  "titulo": "título atractivo, máx. 80 caracteres",
  "resumen_corto": "2-3 frases para descripción de plataforma",
  "resumen_largo": "resumen de 150-250 palabras del contenido",
  "capitulos": [{"inicio": segundos, "titulo": "..."}],
  "tags": ["..."],
  "hilo_x": ["tweet de gancho (<=270 car.)", "..."],
  "post_blog_md": "entrada de blog en markdown, 250-400 palabras",
  "clips": [{"inicio": segundos, "fin": segundos, "gancho": "frase de arranque", "titulo": "..."}]
}
Reglas: 5-8 capítulos; 3-5 clips de 30-90 s que funcionen solos, empezando y acabando en
límites de frase y sin solaparse entre sí; no inventes nada que no esté en la transcripción.

TRANSCRIPCIÓN:
"""


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
              capture_output=True, text=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    a = next(s for s in data["streams"] if s["codec_type"] == "audio")
    return {
        "video": (v["codec_name"], v["width"], v["height"], v["r_frame_rate"], v["pix_fmt"]),
        "audio": (a["codec_name"], a["sample_rate"], a["channels"]),
        "duration": float(data["format"]["duration"]),
        "size": (v["width"], v["height"]),
        "fps": v["r_frame_rate"],
    }


def concat(parts, program, dest):
    """Une los vídeos. Sin recodificar si todos tienen los mismos parámetros.
    Si hay que recodificar, se usa el formato del programa."""
    if len(parts) == 1:
        run(["ffmpeg", "-y", "-v", "error", "-i", parts[0], "-c", "copy", dest])
        return
    info = [probe(p) for p in parts]
    same = all(i["video"] == info[0]["video"] and i["audio"] == info[0]["audio"] for i in info)
    if same:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.writelines(f"file '{Path(p).resolve()}'\n" for p in parts)
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f.name,
             "-c", "copy", dest])
        return
    print("  formatos distintos: recodifico al formato del programa")
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


def transcribe(program, outdir, prompt_hint):
    """Transcribe solo el programa (sin intro/outro) para evitar alucinaciones con la música."""
    import mlx_whisper
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", program, "-vn", "-ac", "1", "-ar", "16000", wav])
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=WHISPER_MODEL, language="es",
                                     initial_prompt=prompt_hint, condition_on_previous_text=False)
    segs = res["segments"]
    (outdir / "transcripcion.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1))
    (outdir / "transcripcion.txt").write_text("\n".join(s["text"].strip() for s in segs))
    (outdir / "transcripcion.srt").write_text("\n".join(
        f"{i}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text'].strip()}\n"
        for i, s in enumerate(segs, 1)))
    return segs


def summarize(segs, dest, intro_len):
    text = "\n".join(f"[{s['start']:.0f}] {s['text'].strip()}" for s in segs)
    out = run(["claude", "-p", "--model", LLM_MODEL], input=PROMPT + text,
              capture_output=True, text=True).stdout
    data = json.loads(out[out.index("{"): out.rindex("}") + 1])
    for k in ("titulo", "resumen_corto", "resumen_largo", "capitulos", "hilo_x", "post_blog_md", "clips"):
        if k not in data:
            raise ValueError(f"falta '{k}' en la respuesta del LLM")
    # los tiempos son del programa; en el episodio final hay que sumar la intro
    data["offset_intro"] = intro_len
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2))


FONT = "/System/Library/Fonts/Helvetica.ttc"


def snap(segs, start, end):
    """Ajusta el clip a límites de frase de whisper (el LLM da tiempos aproximados)."""
    s = min(segs, key=lambda x: abs(x["start"] - start))["start"]
    ends = [x["end"] for x in segs if x["end"] >= s + 10]
    e = min(ends, key=lambda x: abs(x - end)) if ends else end
    return s, min(e, s + 90)


def wrap(text, width=26):
    return "\n".join(textwrap.wrap(text.strip(), width))


def make_clip(ep, segs, clip, dest):
    """Vertical 9:16 con fondo desenfocado, título arriba y subtítulos abajo (drawtext: este
    ffmpeg no trae libass)."""
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
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", ep,
             "-filter_complex", graph, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "21",
             "-preset", "fast", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dest])


def reset(out):
    """Borra lo generado para rehacerlo, salvo publicado.json (evita duplicar publicaciones)."""
    for f in out.iterdir() if out.exists() else []:
        if f.name != "publicado.json":
            shutil.rmtree(f) if f.is_dir() else f.unlink()


def process(ep, intro, outro, root, rehacer=False):
    out = root / "out" / ep.stem
    if rehacer:
        reset(out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"== {ep.name}")
    final_mov, mp3 = out / "episodio.mov", out / "episodio.mp3"

    if not final_mov.exists():
        parts = [p for p in (intro, ep, outro) if p]
        raw = out / "_concat.mov"
        concat(parts, ep, raw)
        loudnorm(raw, final_mov)
        raw.unlink()
    print("  mov OK")

    if not mp3.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", final_mov, "-vn", "-c:a", "libmp3lame",
             "-b:a", "128k", mp3])
    print("  mp3 OK")

    if not (out / "transcripcion.json").exists():
        transcribe(ep, out, "Programa de radio en español.")
    segs = json.loads((out / "transcripcion.json").read_text())
    print("  transcripción OK")

    if not (out / "contenido.json").exists():
        summarize(segs, out / "contenido.json", probe(intro)["duration"] if intro else 0)
    print("  resumen OK")

    (out / "clips").mkdir(exist_ok=True)
    for n, clip in enumerate(json.loads((out / "contenido.json").read_text())["clips"], 1):
        dest = out / "clips" / f"clip{n}.mp4"
        if not dest.exists():
            make_clip(ep, segs, clip, dest)
    print(f"  clips OK -> {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("process")
    p.add_argument("dir", type=Path)
    p.add_argument("--intro", type=Path)
    p.add_argument("--outro", type=Path)
    p.add_argument("--episodio", action="append", help="solo este .mov (sin extensión); repetible")
    p.add_argument("--rehacer", action="store_true", help="borra lo generado y lo vuelve a hacer")
    q = sub.add_parser("publish")
    q.add_argument("dir", type=Path)
    q.add_argument("episodio", help="nombre del .mov sin extensión")
    q.add_argument("--push", action="store_true", help="git commit + push de site/")
    r = sub.add_parser("social")
    r.add_argument("dir", type=Path)
    r.add_argument("episodio")
    r.add_argument("--only", default="youtube,bluesky,mastodon,x,instagram")
    r.add_argument("--dry-run", action="store_true", help="muestra los textos sin publicar")
    sub.add_parser("archive")
    s = sub.add_parser("report")
    s.add_argument("-o", "--output", type=Path, default=Path(__file__).parent / "informe.html")
    a = ap.parse_args()
    social.load_env()

    if a.cmd == "archive":
        moved, skipped = library.archive_all(library.source_dir(), library.env_dir("ARCHIVE_DIR"))
        print(f"Archivados: {', '.join(moved) or 'ninguno'}")
        if skipped:
            print(f"Omitidos (ya existe su carpeta en el archivo): {', '.join(skipped)}")
        return
    if a.cmd == "report":
        n = library.write_report(library.source_dir(), library.env_dir("ARCHIVE_DIR"), a.output)
        print(f"{n} episodio(s) -> {a.output}")
        return

    if a.cmd == "social":
        import publish
        only = a.only.split(",")
        if bad := set(only) - set(social.TARGETS):
            sys.exit(f"--only desconocido: {', '.join(sorted(bad))}")
        contenido = json.loads((a.dir / "out" / a.episodio / "contenido.json").read_text())
        return social.run(a.dir.resolve(), a.episodio, publish.episode_url(publish.load_config(), contenido),
                          only, a.dry_run)
    if a.cmd == "publish":
        import publish
        return publish.publish(a.dir.resolve(), a.episodio, a.push)
    root = a.dir.resolve()
    intro = a.intro or (root / "intro.mov")
    outro = a.outro or (root / "outro.mov")
    intro = intro.resolve() if intro.exists() else None
    outro = outro.resolve() if outro.exists() else None
    episodes = sorted(p for p in root.glob("*.mov") if p not in (intro, outro))
    if a.episodio:
        if missing := set(a.episodio) - {p.stem for p in episodes}:
            sys.exit(f"No existe en {root}: {', '.join(sorted(missing))}")
        episodes = [p for p in episodes if p.stem in a.episodio]
    if not episodes:
        sys.exit(f"No hay .mov en {root}")
    print(f"intro: {intro or 'no'} | outro: {outro or 'no'}")
    for ep in episodes:
        process(ep, intro, outro, root, a.rehacer)


if __name__ == "__main__":
    main()
