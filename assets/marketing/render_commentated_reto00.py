"""Render a private narrated challenge from verified ElevenLabs clips."""

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import render_gameplay_ad as original
from render_gameplay_preview import BG, DOMAIN, GOLD, MINT, sanitize

FPS, RATE = 30, 48000
SOURCE_START, SOURCE_DURATION, SOURCE_GOAL = 120.5, 5.0, 122.65
CTA = "Invita a tu amigo a jugar ahora en clockpenalty.com"
FORBIDDEN = re.compile(r"carlostest(?:chrome)?|penaltygamer|clock-penalty\.pages\.dev", re.I)


def draw_text(draw, value, xy, size, color="#F2F6F3"):
    font = ImageFont.truetype(original.FONT, size)
    if draw.textbbox((0, 0), value, font=font)[2] > 960:
        raise ValueError(f"Text exceeds video safe area: {value}")
    draw.text(xy, value, font=font, fill=color, anchor="mm")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aligned_clip(clip, path, ffmpeg, speed):
    alignment, text = clip["alignment"], clip["text"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    if (
        "".join(alignment["characters"]) != text
        or len(starts) != len(text) or len(ends) != len(text)
        or not all(math.isfinite(a) and math.isfinite(b) and 0 <= a <= b for a, b in zip(starts, ends))
        or any(a > b for a, b in zip(starts, starts[1:]))
    ):
        raise ValueError("Invalid narration alignment")
    begin, end = max(0, starts[0] - .025), ends[-1] + .07
    result = subprocess.run([
        ffmpeg, "-v", "error", "-i", str(path), "-af",
        f"atrim=start={begin}:end={end},asetpts=PTS-STARTPTS,atempo={speed}",
        "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-",
    ], check=True, capture_output=True)
    samples = np.frombuffer(result.stdout, dtype="<f4").copy()
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Invalid narration audio")
    tokens = list(re.finditer(r"\S+", text))
    cues = []
    for index in range(0, len(tokens), 3):
        group = tokens[index:index + 3]
        cues.append((
            max(0, (starts[group[0].start()] - begin) / speed),
            (ends[group[-1].end() - 1] - begin) / speed,
            " ".join(token.group() for token in group),
        ))
    return samples, cues


def load_narration(folder, ffmpeg):
    receipt = json.loads((folder / "narration.json").read_text())
    clips = receipt.get("clips")
    if receipt.get("provider") != "ElevenLabs" or not isinstance(clips, list) or len(clips) != 12:
        raise ValueError("Expected twelve verified ElevenLabs clips")
    for index, clip in enumerate(clips, 1):
        name = f"phrase-{index:02d}.mp3"
        if clip.get("file") != name or not clip.get("complete") or sha256(folder / name) != clip.get("sha256"):
            raise ValueError("Narration integrity check failed")
    text = " ".join(clip["text"] for clip in clips)
    if CTA not in text or FORBIDDEN.search(text):
        raise ValueError("Narration has an invalid CTA or private identifiers")
    decoded = [aligned_clip(c, folder / c["file"], ffmpeg, 1) for c in clips]
    speech_duration = sum(len(audio) / RATE for audio, _ in decoded)
    speed = max(1.0, speech_duration / 23.15)
    if speed > 1.20:
        raise ValueError("Narration needs shortening, not excessive speed-up")
    if speed > 1:
        decoded = [aligned_clip(c, folder / c["file"], ffmpeg, speed) for c in clips]
    speech_duration = sum(len(audio) / RATE for audio, _ in decoded)
    pause = max(.06, (max(22.5, speech_duration + .66) - speech_duration) / 11)
    if pause > .45:
        raise ValueError("Narration is too short for this edit")
    blocks, cues, clip_starts, cursor = [], [], [], 0
    for index, (samples, entries) in enumerate(decoded):
        clip_starts.append(cursor / RATE)
        cues.extend((a + cursor / RATE, b + cursor / RATE, value) for a, b, value in entries)
        blocks.append(samples)
        cursor += len(samples)
        if index < 11:
            silence = np.zeros(round(pause * RATE), dtype=np.float32)
            blocks.append(silence)
            cursor += len(silence)
    blocks.append(np.zeros(round(.35 * RATE), dtype=np.float32))
    audio = np.concatenate(blocks)
    duration = math.ceil(len(audio) / RATE * FPS) / FPS
    audio = np.pad(audio, (0, round(duration * RATE) - len(audio)))
    if not 20 <= duration <= 25:
        raise ValueError(f"Cut must last 20-25 seconds, got {duration}")
    return audio, cues, clip_starts, speed, duration, receipt


def source_time(elapsed, starts):
    run, goal, replay, cta = starts[4], starts[6], starts[9], starts[11]
    if elapsed < run:
        return 120.7 + .65 * elapsed / run
    if elapsed < goal:
        return 121.35 + (SOURCE_GOAL - 121.35) * (elapsed - run) / (goal - run)
    if elapsed < replay:
        return SOURCE_GOAL + (124.5 - SOURCE_GOAL) * (elapsed - goal) / (replay - goal)
    if elapsed < cta:
        return 121.6 + (124.3 - 121.6) * (elapsed - replay) / (cta - replay)
    return 124.1


def compose_frame(art, elapsed, duration, cues, starts):
    image = Image.new("RGB", (1080, 1920), BG)
    draw = ImageDraw.Draw(image)
    for radius in range(300, 1400, 180):
        draw.ellipse((540-radius, 850-radius, 540+radius, 850+radius), outline="#113E49", width=2)
    draw_text(draw, "CLOCK PENALTY  /  RETO .00", (540, 80), 29, GOLD)
    if elapsed >= starts[11]:
        # This is a deliberately framed replay still, not a fabricated game state.
        shown = art.crop((0, 0, 480, 660))
        width = round(610 + 18 * min(1, (elapsed - starts[11]) / 3))
        shown = shown.resize((width, round(width * 660 / 480)), Image.Resampling.LANCZOS)
        image.paste(shown, ((1080-width)//2, 205))
        draw = ImageDraw.Draw(image)
        draw_text(draw, "Invita a tu amigo", (540, 1180), 61, GOLD)
        draw_text(draw, "a jugar ahora en", (540, 1270), 52)
        draw_text(draw, DOMAIN, (540, 1410), 70, MINT)
    else:
        game = art.resize((840, 1456), Image.Resampling.LANCZOS)
        image.paste(game, (120, 200))
        draw = ImageDraw.Draw(image)
        if elapsed < starts[2]:
            title = "EMPATE A UNO. ¿QUIÉN LO CLAVA?"
        elif elapsed < starts[4]:
            title = "SI TERMINA EN .00, ES GOL."
        elif elapsed < starts[6]:
            title = "MIRA ESTA PARADA..."
        elif elapsed < starts[9]:
            title = "¡DIECISÉIS EXACTOS! ¡GOL!"
        else:
            title = "REPETICIÓN  /  DEL 1–1 AL 2–1"
        draw_text(draw, title, (540, 150), 38, GOLD)
        if starts[2] <= elapsed < starts[4]:
            draw.rounded_rectangle((270, 1380, 810, 1495), radius=25, fill="#102E40", outline=MINT, width=3)
            draw_text(draw, ".00 = GOL", (540, 1438), 66, MINT)
        draw_text(draw, DOMAIN, (540, 1720), 36, MINT)
    caption = next((value for start, end, value in cues if start <= elapsed <= end), None)
    if caption:
        draw.rounded_rectangle((70, 1530, 1010, 1650), radius=25, fill=BG, outline=GOLD, width=2)
        draw_text(draw, caption, (540, 1590), 42)
    draw_text(draw, "Gameplay de desarrollo · alias ficticios", (540, 1800), 24)
    draw_text(draw, "@clock.penalty", (540, 1850), 26, GOLD)
    return image


def soundtrack(voice, goal_time, duration, output):
    time = np.arange(len(voice), dtype=np.float64) / RATE
    music = .008 * np.sin(2 * np.pi * 55 * time)
    for start in np.arange(0, duration, .5):
        active = time >= start
        local = np.maximum(time-start, 0)
        music += .018 * np.sin(2*np.pi*62*local) * np.exp(-18*local) * active
    local = np.maximum(time-goal_time, 0)
    for frequency in (523.25, 659.25, 783.99):
        music += .045*np.sin(2*np.pi*frequency*local)*np.exp(-4*local)*(time >= goal_time)
    mixed = voice * .90 + music
    mixed *= np.minimum(time/.015, 1) * np.minimum((duration-time)/.15, 1)
    stereo = np.column_stack((mixed, mixed))
    if np.max(np.abs(stereo)) >= 1 or not np.isfinite(stereo).all():
        raise ValueError("Soundtrack has invalid or clipped samples")
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes((stereo*32767).astype("<i2").tobytes())


def render(source_dir, narration_dir, destination, windows_copy=None):
    source = source_dir / original.FLASH
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    voice, cues, starts, speed, duration, receipt = load_narration(narration_dir, ffmpeg)
    destination.mkdir(parents=True, exist_ok=True)
    stills = destination / "fotogramas"
    stills.mkdir(exist_ok=True)
    reader = imageio_ffmpeg.read_frames(str(source), input_params=["-ss", str(SOURCE_START)],
                                       output_params=["-vf", "fps=30", "-t", str(SOURCE_DURATION)])
    meta = next(reader)
    if meta["size"] != (480, 832):
        reader.close()
        raise ValueError("Unreviewed source geometry")
    try:
        frames = [sanitize(Image.frombytes("RGB", (480, 832), frame), "match") for frame in reader]
    finally:
        reader.close()
    if len(frames) < round(SOURCE_DURATION * FPS) - 1:
        raise ValueError("Gameplay source is incomplete")
    video = destination / "clock-penalty-reto-00-narrado.mp4"
    with tempfile.TemporaryDirectory(prefix="penalty-commentated-") as temporary:
        temp = Path(temporary)
        writer = imageio_ffmpeg.write_frames(str(temp/"silent.mp4"), (1080, 1920), fps=FPS,
            codec="libx264", macro_block_size=8,
            output_params=["-preset", "fast", "-crf", "18", "-threads", "2"])
        writer.send(None)
        sheet = Image.new("RGB", (1350, 480 * math.ceil(duration / 5)), BG)
        try:
            for number in range(round(duration*FPS)):
                elapsed = number/FPS
                index = min(len(frames)-1, max(0, round((source_time(elapsed, starts)-SOURCE_START)*FPS)))
                image = compose_frame(frames[index], elapsed, duration, cues, starts)
                writer.send(np.asarray(image))
                if number % FPS == 0:
                    image.save(stills/f"{elapsed:05.2f}.jpg", quality=94)
                    slot = number//FPS
                    sheet.paste(image.resize((270, 480)), (slot % 5 * 270, slot // 5 * 480))
        finally:
            writer.close()
        sheet.save(destination/"storyboard-reto-00-narrado.jpg", quality=94)
        cover = compose_frame(frames[20], 0, duration, [], starts)
        cover.save(destination/"portada-reto-00-narrado.jpg", quality=95)
        soundtrack(voice, starts[7], duration, temp/"sound.wav")
        measured = original.run([ffmpeg, "-hide_banner", "-i", str(temp/"sound.wav"), "-af",
            "loudnorm=I=-16:TP=-2:LRA=9:print_format=json", "-f", "null", "-"])
        levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
        normalize = ("loudnorm=I=-16:TP=-2:LRA=9:"
            f"measured_I={levels['input_i']}:measured_TP={levels['input_tp']}:"
            f"measured_LRA={levels['input_lra']}:measured_thresh={levels['input_thresh']}:"
            f"offset={levels['target_offset']}:linear=true")
        original.run([ffmpeg, "-v", "error", "-y", "-i", str(temp/"silent.mp4"),
            "-i", str(temp/"sound.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-af", normalize, "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-b:a", "192k", "-t", str(duration), "-movflags", "+faststart", str(video)])
    original.run([ffmpeg, "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"])
    reader = imageio_ffmpeg.read_frames(str(video))
    final = next(reader)
    reader.close()
    measured = original.run([ffmpeg, "-hide_banner", "-i", str(video), "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"])
    levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
    if (final["size"] != (1080, 1920) or final["fps"] != FPS
        or not 20 <= final["duration"] <= 25 or final.get("audio_codec") != "aac"
        or not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1):
        raise ValueError(f"Invalid video export: {final}; {levels}")
    manifest = {"published": False, "status": "private_review", "duration": final["duration"],
        "size": final["size"], "fps": FPS, "cta": CTA, "domain": DOMAIN,
        "voice": receipt["voice"], "narration_speed_factor": speed,
        "clip_starts": starts, "source_goal": SOURCE_GOAL, "source_sha256": sha256(source),
        "source_privacy_masks": [[0, 170, 480, 253], [0, 307, 480, 340], [0, 660, 480, 774]],
        "aliases": ["RayoFC", "FuriaFC"], "audio_levels": levels, "sha256": sha256(video)}
    (destination/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    (destination/"caption.txt").write_text(
        "¿Lo clavas en .00? Una centésima puede cambiar el partido. ⚽\n\n"
        + CTA + "\n\nGameplay de desarrollo, alias ficticios y narración sintética de ElevenLabs.\n")
    (destination/"ver-video.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Reto .00 narrado · Revisión privada</title>'
        '<style>body{background:#061d2c;color:white;font:18px sans-serif;text-align:center}'
        'video{height:80vh;max-width:95vw}a{color:#73f8c9}</style>'
        '<h1>Reto .00 · Borrador narrado</h1><p>No publicado · Voz ElevenLabs</p>'
        '<p><button id="play">Reproducir desde el principio</button></p>'
        f'<video controls preload="metadata" src="{html.escape(video.name)}"></video>'
        '<p id="status" role="status">Listo para revisar</p>'
        f'<p><a href="{html.escape(video.name)}">Descargar vídeo</a></p>'
        '<script>const v=document.querySelector("video"),s=document.getElementById("status");'
        'document.getElementById("play").onclick=async()=>{v.currentTime=0;'
        'try{await v.play()}catch(e){s.textContent="Error al reproducir: "+e.message}};'
        'v.ontimeupdate=()=>s.textContent="Reproduciendo: "+v.currentTime.toFixed(1)+" s";'
        'v.onended=()=>s.textContent="Reproducción completa: "+v.duration.toFixed(1)+" s";'
        'v.onerror=()=>s.textContent="Error de vídeo: "+v.error.code;</script>')
    if windows_copy:
        windows_copy.mkdir(parents=True, exist_ok=True)
        for name in [video.name, "portada-reto-00-narrado.jpg", "storyboard-reto-00-narrado.jpg",
                     "ver-video.html", "manifest.json", "caption.txt"]:
            shutil.copy2(destination/name, windows_copy/name)
            if sha256(destination/name) != sha256(windows_copy/name):
                raise ValueError("Review copy differs from export")
    print(json.dumps({"video": str(video), "duration": duration, "audio_levels": levels}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--windows-copy", type=Path)
    args = parser.parse_args()
    render(args.source, args.narration, args.output, args.windows_copy)
