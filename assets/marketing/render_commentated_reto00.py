"""Render a private 20-25 second narrated .00 challenge preview."""

import argparse
import hashlib
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
SOURCE_START, SOURCE_DURATION = 121.2, 5.4
TARGET_DURATION, MAX_SPEED = 23.5, 1.18
CTA = "Invita a tu amigo a jugar ahora en clockpenalty.com"
FORBIDDEN = re.compile(r"carlostest(?:chrome)?|penaltygamer|clock-penalty\.pages\.dev", re.I)


def draw_text(draw, value, xy, size, color="#F2F6F3", anchor="mm"):
    draw.text(
        xy,
        value,
        font=ImageFont.truetype(original.FONT, size),
        fill=color,
        anchor=anchor,
        stroke_width=1 if size >= 38 else 0,
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def words_for_clip(clip, speed, start):
    alignment = clip["alignment"]
    text = clip["text"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if (
        "".join(alignment["characters"]) != text
        or len(starts) != len(text)
        or len(ends) != len(text)
        or not all(math.isfinite(a) and math.isfinite(b) and 0 <= a <= b for a, b in zip(starts, ends))
        or any(a > b for a, b in zip(starts, starts[1:]))
    ):
        raise ValueError("Invalid narration timing")

    tokens = list(re.finditer(r"\S+", text))
    entries = []
    for index in range(0, len(tokens), 3):
        group = tokens[index:index + 3]
        first, last = group[0], group[-1]
        entries.append((
            start + starts[first.start()] / speed,
            start + ends[last.end() - 1] / speed,
            " ".join(token.group() for token in group),
        ))
    return entries


def decode_clip(path, speed, ffmpeg):
    result = subprocess.run(
        [
            ffmpeg, "-v", "error", "-i", str(path),
            "-af", f"atempo={speed:.6f}", "-ac", "1", "-ar", str(RATE),
            "-f", "f32le", "-",
        ],
        check=True,
        capture_output=True,
    )
    samples = np.frombuffer(result.stdout, dtype="<f4").copy()
    if not len(samples) or not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1.2:
        raise ValueError("Invalid narration samples")
    return samples


def load_narration(folder, ffmpeg):
    manifest_path = folder / "narration.json"
    manifest = json.loads(manifest_path.read_text())
    clips = manifest.get("clips")
    if (
        manifest.get("provider") != "ElevenLabs"
        or manifest.get("model") != "eleven_multilingual_v2"
        or not isinstance(clips, list)
        or len(clips) != 12
    ):
        raise ValueError("Expected twelve verified ElevenLabs narration clips")
    for index, clip in enumerate(clips, start=1):
        expected = f"phrase-{index:02d}.mp3"
        path = folder / expected
        if (
            clip.get("file") != expected
            or clip.get("complete") is not True
            or not path.is_file()
            or sha256(path) != clip.get("sha256")
        ):
            raise ValueError("Narration clip failed its integrity check")
    all_text = " ".join(clip["text"] for clip in clips)
    if CTA not in all_text or FORBIDDEN.search(all_text):
        raise ValueError("Narration is missing the approved CTA or contains a private identifier")

    speed = 1.0
    audio = [decode_clip(folder / clip["file"], speed, ffmpeg) for clip in clips]
    speech_duration = sum(len(samples) for samples in audio) / RATE
    base_pause, scene_pause = 0.08, 0.30
    required_speech = TARGET_DURATION - 11 * base_pause - 5 * scene_pause
    if speech_duration > required_speech:
        speed = speech_duration / required_speech
        if speed > MAX_SPEED:
            raise ValueError("Narration exceeds the 25-second target at natural pacing")
        audio = [decode_clip(folder / clip["file"], speed, ffmpeg) for clip in clips]
        speech_duration = sum(len(samples) for samples in audio) / RATE

    scene_pause = (TARGET_DURATION - speech_duration - 11 * base_pause) / 5
    if not 0.24 <= scene_pause <= 1.0:
        raise ValueError("Narration is too short or long for a natural 20-25 second cut")

    cues = []
    cursor = 0.0
    for index, clip in enumerate(clips):
        samples = audio[index]
        duration = len(samples) / RATE
        cues.extend(words_for_clip(clip, speed, cursor))
        cursor += duration
        if index < len(clips) - 1:
            cursor += base_pause
        if index % 2 == 1 and index < len(clips) - 1:
            cursor += scene_pause
    samples = np.concatenate([
        np.concatenate((
            clip,
            np.zeros(round((
                base_pause + (scene_pause if i % 2 == 1 and i < len(audio) - 1 else 0)
            ) * RATE), dtype=np.float32),
        ))
        if i < len(audio) - 1 else clip
        for i, clip in enumerate(audio)
    ])
    duration = len(samples) / RATE
    if not 20 <= duration <= 25:
        raise ValueError(f"Narrated cut duration is outside 20-25 seconds: {duration:.2f}")
    return samples, cues, duration, speed


def make_music(duration, output):
    time = np.arange(round(duration * RATE), dtype=np.float32) / RATE
    bass = 0.012 * np.sin(2 * np.pi * 55 * time)
    pulse = np.zeros_like(time)
    for start in np.arange(0, duration, 0.5):
        local = time - start
        active = local >= 0
        pulse += 0.035 * np.sin(2 * np.pi * (68 + 14 * np.exp(-10 * local)) * local) * np.exp(-12 * local) * active
    music = (bass + pulse) * np.minimum(time / 0.08, 1) * np.minimum((duration - time) / 0.35, 1)
    stereo = np.column_stack((music, music * 0.97))
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes((np.clip(stereo, -0.9, 0.9) * 32767).astype("<i2").tobytes())


def compose_frame(art, elapsed, duration, cues, cover_art):
    canvas = Image.new("RGB", (1080, 1920), BG)
    draw = ImageDraw.Draw(canvas)
    draw_text(draw, "RETO .00  /  EPISODIO 1", (540, 72), 29, GOLD)
    cta_start = max(0, duration - 4.0)

    if elapsed >= cta_start:
        shown = cover_art.crop((0, 0, 480, 660)).resize((620, 853), Image.Resampling.LANCZOS)
        canvas.paste(shown, (230, 205))
        draw = ImageDraw.Draw(canvas)
        draw_text(draw, "Invita a tu amigo", (540, 1195), 56, GOLD)
        draw_text(draw, "a jugar ahora en", (540, 1280), 48)
        draw_text(draw, DOMAIN, (540, 1420), 68, MINT)
    else:
        canvas.paste(art.resize((840, 1456), Image.Resampling.LANCZOS), (120, 200))
        draw = ImageDraw.Draw(canvas)
        if elapsed < 2.0:
            headline = "EMPATE A UNO. ÚLTIMA JUGADA."
        elif elapsed < 6.0:
            headline = "¿DÓNDE PARARÍAS EL RELOJ?"
        elif elapsed < 6.0 + SOURCE_DURATION:
            headline = "CADA CENTÉSIMA CUENTA."
        else:
            headline = "¡GOL! DEL 1–1 AL 2–1."
        draw_text(draw, headline, (540, 153), 38, GOLD if elapsed < 6 else MINT)
        draw_text(draw, DOMAIN, (540, 1730), 35, MINT)

    active = next((caption for start, end, caption in cues if start <= elapsed <= end), None)
    if active:
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((70, 1510, 1010, 1630), radius=25, fill="#061D2C", outline=GOLD, width=2)
        draw_text(draw, active, (540, 1570), 38)
    draw = ImageDraw.Draw(canvas)
    draw_text(draw, "Gameplay de desarrollo · alias ficticios", (540, 1805), 23)
    draw_text(draw, "@clock.penalty", (540, 1855), 25, GOLD)
    return canvas


def render(source_dir, narration_dir, destination, windows_copy=None):
    source = source_dir / original.FLASH
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    voice, cues, duration, speed = load_narration(narration_dir, ffmpeg)
    video = destination / "clock-penalty-reto-00-narrado.mp4"
    stills = destination / "fotogramas"
    stills.mkdir(exist_ok=True)

    reader = imageio_ffmpeg.read_frames(
        str(source),
        input_params=["-ss", str(SOURCE_START)],
        output_params=["-vf", "fps=30", "-t", str(SOURCE_DURATION)],
    )
    metadata = next(reader)
    if metadata["size"] != (480, 832):
        reader.close()
        raise ValueError("Unreviewed gameplay source geometry")
    first_frame = next(reader)
    first_art = sanitize(Image.frombytes("RGB", (480, 832), first_frame), "match")

    with tempfile.TemporaryDirectory(prefix="penalty-commentated-") as temporary:
        folder = Path(temporary)
        silent = folder / "silent.mp4"
        writer = imageio_ffmpeg.write_frames(
            str(silent), (1080, 1920), fps=FPS, codec="libx264",
            macro_block_size=8,
            output_params=["-preset", "fast", "-crf", "18", "-threads", "2"],
        )
        writer.send(None)
        sheet = Image.new("RGB", (1350, 1920), BG)
        goal_art, cover_art = None, first_art
        try:
            for frame_number in range(round(duration * FPS)):
                elapsed = frame_number / FPS
                if elapsed < 6.0:
                    art = first_art
                elif elapsed < 6.0 + SOURCE_DURATION:
                    source_frame = round((elapsed - 6.0) * FPS)
                    if source_frame == 0:
                        art = first_art
                    else:
                        art = sanitize(
                            Image.frombytes("RGB", (480, 832), next(reader)),
                            "match",
                        )
                    if source_frame == round(4.85 * FPS):
                        goal_art = art.copy()
                        cover_art = art.copy()
                else:
                    if goal_art is None:
                        goal_art = first_art
                    art = goal_art
                still = compose_frame(art, elapsed, duration, cues, cover_art)
                writer.send(np.asarray(still))
                if frame_number % FPS == 0:
                    still.save(stills / f"{elapsed:05.2f}.jpg", quality=93)
                    thumb = still.resize((270, 480), Image.Resampling.LANCZOS)
                    slot = frame_number // FPS
                    sheet.paste(thumb, (slot % 5 * 270, slot // 5 * 480))
        finally:
            reader.close()
            writer.close()

        music = folder / "music.wav"
        voice_file = folder / "voice.wav"
        make_music(duration, music)
        with wave.open(str(voice_file), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(RATE)
            stream.writeframes(
                (np.clip(voice, -0.98, 0.98) * 32767).astype("<i2").tobytes()
            )
        original.run([
            ffmpeg, "-v", "error", "-y", "-i", str(silent),
            "-i", str(voice_file), "-i", str(music),
            "-filter_complex",
            "[1:a]loudnorm=I=-15:TP=-2:LRA=9,aresample=48000[v];[2:a]volume=0.10[m];"
            "[v][m]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.80[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", str(video),
        ])
    result = original.run([ffmpeg, "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"])
    _ = result
    measured = original.run([
        ffmpeg, "-hide_banner", "-i", str(video), "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-",
    ])
    levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
    final_reader = imageio_ffmpeg.read_frames(str(video))
    meta = next(final_reader)
    final_reader.close()
    if (
        meta["size"] != (1080, 1920)
        or meta["fps"] != FPS
        or not 20 <= meta["duration"] <= 25
        or not meta["audio_codec"]
        or not -18 <= float(levels["input_i"]) <= -14
        or float(levels["input_tp"]) > -1
    ):
        raise RuntimeError(f"Invalid narrated export: {meta}; {levels}")

    cover = compose_frame(cover_art, 0, duration, cues, cover_art)
    cover.save(destination / "portada-reto-00-narrado.jpg", quality=95)
    sheet.save(destination / "storyboard-reto-00-narrado.jpg", quality=94)
    manifest = {
        "published": False,
        "status": "private_review",
        "duration": meta["duration"],
        "size": meta["size"],
        "fps": FPS,
        "audio": "ElevenLabs narration, original subdued synthesized music",
        "narration_speed_factor": speed,
        "cta": CTA,
        "domain": DOMAIN,
        "aliases": ["RayoFC", "FuriaFC"],
        "privacy": "Source-resolution opaque account-name replacement and full generated-timing privacy mask",
        "source_start": SOURCE_START,
        "source_duration": SOURCE_DURATION,
        "audio_levels": levels,
        "sha256": sha256(video),
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if windows_copy:
        windows_copy.mkdir(parents=True, exist_ok=True)
        for item in (video, destination / "portada-reto-00-narrado.jpg",
                     destination / "storyboard-reto-00-narrado.jpg"):
            shutil.copy2(item, windows_copy / item.name)
        if sha256(video) != sha256(windows_copy / video.name):
            raise RuntimeError("Review copy differs from the final export")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--windows-copy", type=Path)
    arguments = parser.parse_args()
    render(arguments.source, arguments.narration, arguments.output, arguments.windows_copy)


if __name__ == "__main__":
    main()
