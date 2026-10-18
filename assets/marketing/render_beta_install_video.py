"""Render the beta tutorial from cached ElevenLabs narration, without API keys."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "beta-install-video"
WINDOWS = Path("/mnt/c/Users/juan.crugeiras/Downloads/Clock-Penalty-Anuncios")
WIDTH, HEIGHT, FPS, RATE = 1080, 1920, 30, 44100
BG, MINT, GOLD, WHITE = "#061D2C", "#73F8C9", "#FFE399", "#F2F6F3"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SCENES = [
    ("La beta, en tu móvil", "Sin App Store ni Play Store", None, None, [
        "Te enseño cómo poner la beta en tu móvil.",
        "No necesitas buscarla en ninguna tienda.",
    ]),
    ("En iPhone · 1/2", "Safari → menú → Compartir", 2, (530, 1450), [
        "En iPhone, abre el enlace del perfil en Safari, no dentro de Instagram.",
        "Abre el menú del navegador y toca Compartir.",
    ]),
    ("En iPhone · 2/2", "Añadir a pantalla de inicio", 3, (175, 1105), [
        "Elige Añadir a pantalla de inicio.",
        "Confirma en Añadir y ya tendrás el icono.",
    ]),
    ("En Android · 1/2", "Chrome → menú ⋮", 4, (510, 526), [
        "En Android, abre la web en Chrome y toca los tres puntos.",
        "Busca Instalar aplicación, o Añadir a pantalla de inicio.",
    ]),
    ("En Android · 2/2", "Confirma y abre Penalty", 5, (540, 650), [
        "Confirma la instalación y abre Penalty desde el icono.",
        "El nombre de la opción puede variar según tu móvil.",
    ]),
    ("Y ya puedes probarlo", "Lo estoy construyendo. Cuéntame qué mejorarías.", None, None, [
        "Ya puedes probar el juego.",
        "Si algo no funciona, escríbeme y dime qué móvil usas.",
    ]),
]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result


def face(size):
    return ImageFont.truetype(FONT, size)


def lines(value, size, width=920):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    output, current = [], ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face(size))[2] > width:
            if not current:
                raise ValueError(f"Word exceeds caption width: {word}")
            output.append(current)
            current = word
        else:
            current = candidate
    return output + ([current] if current else [])


def centered(draw, value, y, size, color=WHITE):
    if draw.textbbox((0, 0), value, font=face(size))[2] > 960:
        raise ValueError(f"Title exceeds safe area: {value}")
    draw.text((540, y), value, font=face(size), fill=color, anchor="mm")


def stamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def load_narration(narration_dir):
    manifest = json.loads((narration_dir / "narration.json").read_text(encoding="utf-8"))
    expected = [phrase for scene in SCENES for phrase in scene[4]]
    clips = manifest.get("clips", [])
    if (manifest.get("provider") != "ElevenLabs" or len(clips) != len(expected)
            or not manifest.get("voice", {}).get("id")):
        raise ValueError("Complete ElevenLabs narration and voice metadata are required")
    decoded = []
    for clip, phrase in zip(clips, expected):
        if not clip.get("complete") or clip.get("text") != phrase:
            raise ValueError("Narration script mismatch or incomplete audio")
        if Path(clip["file"]).name != clip["file"]:
            raise ValueError("Narration file must be inside the audio directory")
        path = narration_dir / clip["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != clip["sha256"]:
            raise ValueError("Narration audio hash mismatch")
        alignment = clip["alignment"]
        chars = alignment["characters"]
        starts = alignment["character_start_times_seconds"]
        ends = alignment["character_end_times_seconds"]
        if ("".join(chars) != phrase or len(chars) != len(starts)
                or len(chars) != len(ends)
                or not all(math.isfinite(a) and math.isfinite(b) and 0 <= a <= b
                           for a, b in zip(starts, ends))
                or any(a > b for a, b in zip(starts, starts[1:]))
                or any(a > b for a, b in zip(ends, ends[1:]))):
            raise ValueError("Invalid narration alignment")
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path),
             "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
            capture_output=True, check=True)
        samples = np.frombuffer(result.stdout, dtype="<f4").astype(float)
        if not len(samples) or not np.isfinite(samples).all() or ends[-1] > len(samples)/RATE + .15:
            raise ValueError("Audio duration does not match its alignment")
        first = next(i for i, char in enumerate(chars) if not char.isspace())
        last = max(i for i, char in enumerate(chars) if not char.isspace())
        begin, finish = max(0, starts[first] - .04), min(len(samples)/RATE, ends[last] + .10)
        samples = samples[round(begin*RATE):round(finish*RATE)]
        decoded.append((samples, starts[first]-begin, ends[last]-begin))
    return manifest, decoded


def prepare_audio(folder, decoded):
    scenes, cursor, captions, combined = [], 0.0, [], []
    clip_index = 0
    for index, scene in enumerate(SCENES):
        audio = [np.zeros(round(.45 * RATE))]
        cues, position = [], .45
        for phrase in scene[4]:
            samples, spoken_start, spoken_end = decoded[clip_index]
            clip_index += 1
            if not len(samples) or not np.isfinite(samples).all():
                raise RuntimeError("Invalid narration audio")
            duration = len(samples) / RATE
            cues.append((position + spoken_start, position + spoken_end, phrase))
            captions.append((cursor + position + spoken_start,
                             cursor + position + spoken_end, phrase))
            audio.extend([samples * .85, np.zeros(round(.25 * RATE))])
            position += duration + .25
        raw = np.concatenate(audio + [np.zeros(round(.65 * RATE))])
        frames = math.ceil(len(raw) / RATE * FPS)
        raw = np.pad(raw, (0, round(frames / FPS * RATE) - len(raw)))
        # A quiet original chime marks the change of step, underneath the voice.
        t = np.arange(min(round(.22 * RATE), len(raw))) / RATE
        raw[:len(t)] += .055 * np.sin(2 * math.pi * (660 + 55 * index) * t) * np.exp(-t * 22)
        if np.max(np.abs(raw)) >= 1:
            raise RuntimeError("Narration clips")
        scenes.append({"start": cursor, "duration": frames / FPS, "frames": frames, "cues": cues})
        cursor += frames / FPS
        combined.append(raw)
    with wave.open(str(folder / "narration.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((np.concatenate(combined) * 32767).astype("<i2").tobytes())
    return scenes, captions, cursor


def artwork(index):
    scene = SCENES[index]
    if scene[2]:
        with Image.open(ROOT / "beta-install" / "stories" / f"{scene[2]:02}-instalacion-beta.jpg") as source:
            # Preserve source screenshot geometry; remove the static titles/footer.
            return source.convert("RGB").crop((60, 430, 1020, 1550))
    with Image.open(ROOT / "clock-penalty-social-avatar.png") as source:
        return source.convert("RGB").resize((740, 740), Image.Resampling.LANCZOS)


def frame(index, elapsed, duration, art):
    scene = SCENES[index]
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    for radius in range(280, 1400, 170):
        draw.ellipse((540-radius, 930-radius, 540+radius, 930+radius),
                     outline="#123842", width=2)
    centered(draw, "CLOCK PENALTY", 175, 28, GOLD)
    centered(draw, scene[0], 265, 53)
    centered(draw, scene[1], 340, 29, MINT)
    progress = min(1, elapsed / .5)
    offset = round(65 * (1 - progress) ** 3)
    if scene[2]:
        x, y = 60 + offset, 405
        image.paste(art, (x, y))
        if elapsed > .7 and scene[3]:
            px = scene[3][0] + offset
            py = scene[3][1] - 430 + y
            radius = 32 + round(13 * (1 + math.sin(elapsed * 5)))
            draw = ImageDraw.Draw(image)
            draw.ellipse((px-radius, py-radius, px+radius, py+radius), outline=GOLD, width=6)
            draw.line((px+radius+12, py-45, px+radius+95, py-90), fill=GOLD, width=5)
            draw.polygon([(px+radius+10, py-43), (px+radius+36, py-46),
                          (px+radius+23, py-65)], fill=GOLD)
    else:
        zoom = 1 + .035 * min(1, elapsed / duration)
        side = round(740 * zoom)
        animated = art.resize((side, side), Image.Resampling.BICUBIC)
        image.paste(animated, ((WIDTH-side)//2, 470 + offset))
        draw = ImageDraw.Draw(image)
        centered(draw, "clockpenalty.com", 1330, 42, MINT)
    draw = ImageDraw.Draw(image)
    if index in (3, 4):
        draw.rectangle((0, 1410, WIDTH, 1490), fill=BG)
    # Fixed caption region keeps all spoken instructions readable without sound.
    draw.rounded_rectangle((65, 1490, 1015, 1710), radius=30, fill="#102E40")
    cue = next((value for start, end, value in duration_cues[index]
                if start <= elapsed <= end), "")
    caption_lines = lines(cue, 35, 860)
    if len(caption_lines) > 3:
        raise ValueError("Caption exceeds three lines")
    for row, text in enumerate(caption_lines):
        centered(draw, text, 1600 + (row - (len(caption_lines)-1)/2) * 49, 35)
    centered(draw, "clockpenalty.com", 1760, 29, MINT)
    draw.rounded_rectangle((110, 1810, 970, 1818), radius=4, fill="#244653")
    draw.rounded_rectangle((110, 1810, 110 + max(8, round(860 * elapsed / duration)), 1818),
                           radius=4, fill=MINT)
    centered(draw, f"{index + 1} / {len(SCENES)}  ·  @clock.penalty", 1850, 23, GOLD)
    if index in (3, 4):
        centered(draw, "Android: ilustración orientativa", 1445, 22, GOLD)
    # Dip to the background between steps instead of abrupt cuts.
    opacity = min(1, elapsed / .2, (duration - elapsed) / .2)
    return Image.blend(Image.new("RGB", image.size, BG), image, max(0, opacity))


duration_cues = []


def render(narration_dir):
    global duration_cues
    voice_manifest, decoded = load_narration(narration_dir)
    OUT.mkdir(exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="penalty-install-") as folder:
        temp = Path(folder)
        scenes, captions, duration = prepare_audio(temp, decoded)
        duration_cues = [scene["cues"] for scene in scenes]
        writer = imageio_ffmpeg.write_frames(
            str(temp / "silent.mp4"), (WIDTH, HEIGHT), fps=FPS, codec="libx264",
            pix_fmt_in="rgb24", pix_fmt_out="yuv420p", macro_block_size=8,
            output_params=["-preset", "fast", "-crf", "20", "-threads", "2"],
        )
        writer.send(None)
        sheet = Image.new("RGB", (3 * 270, 2 * 480), BG)
        try:
            for index, scene in enumerate(scenes):
                art = artwork(index)
                for number in range(scene["frames"]):
                    image = frame(index, number / FPS, scene["duration"], art)
                    writer.send(np.asarray(image))
                preview = frame(index, scene["cues"][0][0] + .8, scene["duration"], art)
                sheet.paste(preview.resize((270, 480)), ((index % 3)*270, (index // 3)*480))
                print(f"Rendered scene {index + 1}/{len(scenes)}", flush=True)
        finally:
            writer.close()
        output = OUT / "clock-penalty-instalacion-beta-voz.mp4"
        run([ffmpeg, "-v", "error", "-y", "-i", str(temp / "silent.mp4"),
             "-i", str(temp / "narration.wav"), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
             "-c:a", "aac", "-b:a", "160k", "-t", str(duration),
             "-movflags", "+faststart", str(output)])
        sheet.save(OUT / "storyboard.jpg", quality=93)
        (OUT / "subtitulos.srt").write_text("\n\n".join(
            f"{i}\n{stamp(start)} --> {stamp(end)}\n{text}"
            for i, (start, end, text) in enumerate(captions, 1)) + "\n", encoding="utf-8")
        exports = [output]
        for name, first, last in [("historia-iphone", 1, 2), ("historia-android", 3, 4)]:
            clip = OUT / f"{name}.mp4"
            start = scenes[first]["start"]
            length = sum(scene["duration"] for scene in scenes[first:last+1])
            run([ffmpeg, "-v", "error", "-y", "-ss", str(start), "-i", str(output),
                 "-t", str(length), "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-threads", "2", "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(clip)])
            exports.append(clip)
        run([ffmpeg, "-v", "error", "-y", "-i", str(temp / "narration.wav"),
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-c:a", "libmp3lame",
             "-b:a", "192k", str(OUT / "locucion-elevenlabs.mp3")])
        manifest = {"published": False, "provider": "ElevenLabs",
                    "voice": voice_manifest["voice"], "model": voice_manifest["model"],
                    "subtitleTiming": "ElevenLabs character alignment",
                    "size": [WIDTH, HEIGHT], "fps": FPS, "duration": duration,
                    "scenes": scenes, "files": {}}
        for path in exports:
            run([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])
            reader = imageio_ffmpeg.read_frames(str(path))
            meta = next(reader)
            reader.close()
            if meta["size"] != (WIDTH, HEIGHT) or meta["fps"] != FPS or not meta["audio_codec"]:
                raise RuntimeError(f"Invalid video/audio format: {path}")
            expected = duration if path == output else (
                sum(scenes[i]["duration"] for i in ((1, 2) if "iphone" in path.name else (3, 4))))
            if abs(meta["duration"] - expected) > .15:
                raise RuntimeError(f"Incorrect export duration: {path}")
            manifest["files"][path.name] = {
                "duration": meta["duration"], "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            measured = run([ffmpeg, "-hide_banner", "-i", str(path), "-af",
                            "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json",
                            "-f", "null", "-"])
            levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
            if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1:
                raise RuntimeError(f"Audio outside delivery loudness/peak range: {path}")
            manifest["files"][path.name]["audioLevels"] = levels
        (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        (OUT / "locucion.txt").write_text("\n\n".join(
            scene[0] + "\n" + " ".join(scene[4]) for scene in SCENES) + "\n", encoding="utf-8")
        (OUT / "README.txt").write_text(
            "Versión ElevenLabs: no publicada. Tutorial con voz masculina de catálogo "
            "en español de España; no se ha clonado la voz del creador.\n"
            "Incluye subtítulos integrados y SRT sincronizados con la locución generada.\n"
            "Animación: entradas, acercamiento del logo, indicadores pulsantes y transiciones.\n"
            "Android es una ilustración; las opciones varían según el dispositivo.\n"
            "La locución explica abrir la web fuera de Instagram. El vídeo no contiene enlaces clicables.\n"
            "La salida es 1080x1920; las capturas originales se escalan, no ganan detalle nativo.\n",
            encoding="utf-8")
        if not WINDOWS.is_dir():
            raise FileNotFoundError(f"Windows destination is unavailable: {WINDOWS}")
        destination = WINDOWS / "instagram-beta-video"
        destination.mkdir(exist_ok=True)
        for path in OUT.iterdir():
            if path.is_file():
                target = destination / path.name
                shutil.copy2(path, target)
                if target.read_bytes() != path.read_bytes():
                    raise RuntimeError(f"Windows copy mismatch: {target}")
        print(f"Verified {duration:.2f}s tutorial, two story clips and Windows copies.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", type=Path, required=True,
                        help="Private audio branch checkout containing narration.json")
    render(parser.parse_args().narration)
