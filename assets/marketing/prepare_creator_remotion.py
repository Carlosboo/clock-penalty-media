"""Prepare and verify a local Remotion re-edit without changing the original."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import imageio_ffmpeg

import render_creator_pilot as original


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "creator-remotion/public"
OUT = ROOT / "creator-pilot-v2"
DEST = original.DOWNLOADS / "Clock-Penalty-Anuncios/presentacion-creador-v2"
FPS = 30


def run(args):
    return original.run([imageio_ffmpeg.get_ffmpeg_exe(), *args])


def prepare(transcript_path):
    PUBLIC.mkdir(parents=True, exist_ok=True)
    cuts = [(round(a*FPS)/FPS, round(b*FPS)/FPS, *rest)
            for a, b, *rest in original.CUTS]
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    words = original.edited_words(data, cuts)
    cursor, shots = 0, []
    for index, (start, end, kind, *_) in enumerate(cuts):
        frames = round((end-start)*FPS)
        inputs = ["-ss", str(start), "-i", str(original.SOURCE)]
        if kind == "live":
            inputs += ["-ss", "18.5", "-i", str(original.GAME)]
            layout = (
                "[0:v]crop=440:782:68:225,scale=290:516,setsar=1[pip];"
                "[1:v]scale=330:587:force_original_aspect_ratio=decrease,"
                "pad=330:587:(ow-iw)/2:(oh-ih)/2:color=0x061D2C[game];"
                f"color=c=0x061D2C:s=1080x1920:r=30:d={end-start}[bg];"
                "[bg][game]overlay=145:300[screen];"
                "[screen][pip]overlay=615:355[layout];"
            )
        else:
            crop = "440:782:68:225" if index % 2 == 0 else "480:853:48:171"
            layout = f"[0:v]crop={crop},scale=1080:1920,setsar=1[layout];"
        filters = (
            layout + "[layout]eq=contrast=1.035:saturation=1.04:brightness=0.006,"
            "setsar=1[v];"
            f"[0:a]atrim=duration={end-start},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.012,afade=t=out:st={end-start-.018}:d=0.018[a]"
        )
        run(["-v", "error", "-y", *inputs, "-filter_complex", filters,
             "-map", "[v]", "-map", "[a]", "-t", str(frames/FPS), "-r", "30",
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "2",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2",
             "-b:a", "192k", str(PUBLIC/f"shot-{index}.mp4")])
        shots.append({"sourceStart": start, "sourceEnd": end, "startFrame": cursor,
                      "frames": frames, "kind": kind})
        cursor += frames
        print(f"Prepared clean shot {index+1}/{len(cuts)}", flush=True)
    run(["-v", "error", "-y", "-f", "lavfi", "-i",
         "color=c=0x061D2C:s=1080x1920:r=30:d=2.6",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "2.6", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
         "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac",
         str(PUBLIC/"end.mp4")])
    (PUBLIC/"concat.txt").write_text(
        "".join(f"file 'shot-{i}.mp4'\n" for i in range(len(cuts))) +
        "file 'end.mp4'\n", encoding="utf-8")
    run(["-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(PUBLIC/"concat.txt"), "-c", "copy", str(PUBLIC/"base.mp4")])
    duration = (cursor+78)/FPS
    assert cursor == 727 and round(duration*FPS) == 805
    original.sound(PUBLIC, duration)
    run(["-v", "error", "-y", "-i", str(PUBLIC/"base.mp4"),
         "-i", str(PUBLIC/"bed.wav"), "-filter_complex",
         "[0:a]highpass=f=75,lowpass=f=12000,afftdn=nr=7:nf=-35,"
         "acompressor=threshold=0.12:ratio=2:attack=15:release=160[voice];"
         "[voice][1:a]amix=inputs=2:duration=first:normalize=0,"
         "loudnorm=I=-14:TP=-1.5:LRA=9[a]",
         "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s24le",
         "-t", str(duration), str(PUBLIC/"audio.wav")])
    (PUBLIC/"timeline.json").write_text(json.dumps({
        "words": words, "shots": shots, "duration": duration,
        "sourceSha256": hashlib.sha256(original.SOURCE.read_bytes()).hexdigest(),
    }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def finish():
    OUT.mkdir(exist_ok=True)
    timeline = json.loads((PUBLIC/"timeline.json").read_text())
    results = {}
    for stem in ("master", "clean"):
        source = PUBLIC/f"{stem}-silent.mp4"
        target = OUT/("clock-penalty-presentacion-creador-v2" +
                      ("-sin-subtitulos" if stem == "clean" else "") + ".mp4")
        run(["-v", "error", "-y", "-i", str(source), "-i", str(PUBLIC/"audio.wav"),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-ar", "48000", "-t", str(timeline["duration"]),
             "-movflags", "+faststart", str(target)])
        run(["-v", "error", "-xerror", "-i", str(target), "-f", "null", "-"])
        reader = imageio_ffmpeg.read_frames(str(target))
        metadata = next(reader)
        reader.close()
        if (metadata["size"] != (1080, 1920) or metadata["fps"] != FPS or
                abs(metadata["duration"]-timeline["duration"]) > .1 or
                not metadata["audio_codec"]):
            raise RuntimeError(f"Invalid export format: {metadata}")
        measurement = run(["-hide_banner", "-i", str(target), "-af",
                           "loudnorm=I=-14:TP=-1:LRA=9:print_format=json",
                           "-f", "null", "-"])
        levels, _ = json.JSONDecoder().raw_decode(
            measurement.stderr[measurement.stderr.rfind("{"):])
        if not -15 <= float(levels["input_i"]) <= -13 or float(levels["input_tp"]) > -1:
            raise RuntimeError(f"Invalid export audio: {levels}")
        results[target.name] = {
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "size": metadata["size"], "duration": metadata["duration"],
            "audioLevels": levels,
        }
    master = OUT/"clock-penalty-presentacion-creador-v2.mp4"
    run(["-v", "error", "-y", "-i", str(master),
         "-vf", "fps=1/3.5,scale=270:480,tile=4x2",
         "-frames:v", "1", str(OUT/"storyboard.jpg")])
    run(["-v", "error", "-y", "-ss", "10", "-i", str(master),
         "-frames:v", "1", str(OUT/"portada.jpg")])
    if hashlib.sha256(original.SOURCE.read_bytes()).hexdigest() != timeline["sourceSha256"]:
        raise RuntimeError("Original source recording changed")
    manifest = {
        "published": False, "renderer": "Remotion 4.0.361 / FFmpeg",
        "voice": "Original speaker, no synthesis or cloning",
        "sourceNativeSize": [576, 1024], "timeline": timeline,
        "outputs": results,
        "reference": "https://marbuilds.dev/resources/efectos-video-claude-code",
        "effects": ["Word-timed 1–3 word captions", "Spring checklist with SVG icons",
                    "Restrained 1.035x cut punch-in", "Gameplay and presenter split view",
                    "Animated end card"],
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    (OUT/"README.txt").write_text(
        "PRESENTACION CREADOR V2 · 1080 x 1920 · 30 fps · 26,83 s\n\n"
        "Voz humana original. No se ha enviado la grabacion a servicios externos.\n"
        "Composicion: Remotion; cortes/audio: FFmpeg; tiempos: faster-whisper local.\n"
        "Adaptacion de las tecnicas de @itsmarbuilds, no reproduccion de su video.\n"
        "Incluye master con subtitulos y variante sin subtitulos (con rotulos).\n"
        "Original y primera edicion conservados. No publicado en redes.\n"
        "No hay recorte de persona, orbitas, imagen generada ni zoom 2x.\n"
        "Iconos SVG de elaboracion propia, no logos oficiales.\n"
        "El master escala un original 576 x 1024, no tiene detalle Full HD nativo.\n"
        "Revisar reproduccion y subtitulos antes de publicar.\n", encoding="utf-8")
    DEST.mkdir(exist_ok=True)
    for path in OUT.iterdir():
        if path.is_file():
            target = DEST/path.name
            shutil.copy2(path, target)
            if path.read_bytes() != target.read_bytes():
                raise RuntimeError(f"Export copy differs: {target}")
    print(f"Verified both exports, audio, unchanged original and Windows copies: {DEST}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()
    if args.finish:
        finish()
    elif args.transcript:
        prepare(args.transcript)
    else:
        parser.error("--transcript or --finish is required")
