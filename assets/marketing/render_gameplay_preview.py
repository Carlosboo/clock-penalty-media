"""Build a private gameplay review using cached voice, never a publishing API."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import render_gameplay_ad as original
from render_beta_install_video import stamp


BG, MINT, GOLD, WHITE = "#061D2C", "#73F8C9", "#FFD43B", "#F2F6F3"
FPS, RATE, SPEED = 30, 48000, 1.30
DOMAIN = "clockpenalty.com"
ALIASES = {"home": "RayoFC", "away": "FuriaFC", "league": "Liga del Minuto"}
FORBIDDEN = re.compile(r"carlostest(?:chrome)?|penaltygamer|clock-penalty\.pages\.dev", re.I)
PHRASES = [4, 3, 5, 6, 10, None, 11]
TITLES = [
    ("UNA CENTÉSIMA", "¿GOL O FALLO?"),
    ("NO CHUTAS.", "PARAS EL RELOJ."),
    ("TE QUEDAS EN .99", "¡PENALTI!"),
    ("PAR: GOL.", "IMPAR: FALLO."),
    ("TU CLUB. TU ESTILO.", "TU PRÓXIMA LIGA."),
    ("EMPATE A UNO...", "MIRA ESTA PARADA"),
    ("¿TÚ LO CLAVAS?", "PRUEBA LA BETA"),
]


def text(draw, value, xy, size, color=WHITE, anchor="mm"):
    font = ImageFont.truetype(original.FONT, size)
    draw.text(xy, value, font=font, fill=color, anchor=anchor,
              stroke_width=1 if size >= 32 else 0)


def wrap(value, size, max_width):
    font = ImageFont.truetype(original.FONT, size)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    rows, line = [], ""
    for word in value.split():
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            if not line:
                raise ValueError("Caption word exceeds safe area")
            rows.append(line)
            line = word
        else:
            line = candidate
    return rows + ([line] if line else [])


def sanitize(image, kind, comment=""):
    """Opaque replacements happen at source resolution, before any resizing."""
    image = image.convert("RGB").copy()
    draw = ImageDraw.Draw(image)
    w, h = image.size
    if kind == "match":
        if (w, h) != (480, 832):
            raise ValueError("Unreviewed match source geometry")
        draw.rectangle((0, 170, w, 252), fill=BG)
        for x, name, club, color in [
            (10, ALIASES["home"], "Atlético Marisma", GOLD),
            (247, ALIASES["away"], "Unión Chispa", MINT),
        ]:
            draw.rounded_rectangle((x, 179, x + 222, 242), radius=14,
                                   fill="#102E40", outline=color, width=2)
            text(draw, name, (x + 111, 201), 20, color)
            text(draw, club, (x + 111, 226), 12)
        # The penalty taker and commentator can repeat the original account name.
        draw.rectangle((0, 307, w, 339), fill="#174A46")
        text(draw, "RAYO FC  vs  FURIA FC", (240, 323), 12)
        draw.rectangle((0, 660, w, 773), fill=BG)
        for row, line in enumerate(wrap(comment, 17, 446)[:2]):
            text(draw, line, (240, 700 + row * 25), 17, GOLD)
    elif kind == "league":
        if (w, h) != (464, 816):
            raise ValueError("Unreviewed league source geometry")
        draw.rectangle((15, 94, 450, 250), fill="#163F4B")
        text(draw, ALIASES["league"], (232, 127), 24, GOLD)
        text(draw, "División 1 · Temporada piloto", (232, 164), 15)
        text(draw, "Grabación de desarrollo", (232, 201), 15, MINT)
        draw.rectangle((106, 770, 305, 815), fill="#224E2C")
        text(draw, "Atlético Marisma", (115, 785), 15, anchor="lm")
        text(draw, ALIASES["home"], (115, 808), 13, MINT, anchor="lm")
    elif kind != "club":
        raise ValueError("Unknown source privacy profile")
    return image


def cached_voice(folder, number, temp):
    manifest = json.loads((folder / "narration.json").read_text())
    clip = manifest["clips"][number - 1]
    path = folder / clip["file"]
    if (path.name != clip["file"] or not clip.get("complete")
            or hashlib.sha256(path.read_bytes()).hexdigest() != clip["sha256"]):
        raise ValueError("Cached narration is incomplete or differs from its receipt")
    alignment = clip["alignment"]
    if "".join(alignment["characters"]) != clip["text"]:
        raise ValueError("Narration alignment differs from the script")
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if (len(starts) != len(clip["text"]) or len(ends) != len(starts)
            or not all(math.isfinite(a) and math.isfinite(b) and 0 <= a <= b
                       for a, b in zip(starts, ends))
            or any(a > b for a, b in zip(starts, starts[1:]))):
        raise ValueError("Invalid cached narration timing")
    begin = max(0, starts[0] - .025)
    finish = ends[-1] + .06
    raw = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path),
        "-af", f"atrim=start={begin}:end={finish},asetpts=PTS-STARTPTS,atempo={SPEED}",
        "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-",
    ], check=True, capture_output=True)
    samples = np.frombuffer(raw.stdout, dtype="<f4").copy()
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Invalid decoded narration")
    words = []
    for match in re.finditer(r"\S+", clip["text"]):
        words.append((
            max(0, (starts[match.start()] - begin) / SPEED),
            (ends[match.end() - 1] - begin) / SPEED,
            match.group(),
        ))
    cues = [(words[i][0], words[min(i + 2, len(words)-1)][1],
             " ".join(word[2] for word in words[i:i+3]))
            for i in range(0, len(words), 3)]
    return samples, cues, clip["text"], manifest["voice"]


def source_reader(source, filename, start, size):
    reader = imageio_ffmpeg.read_frames(
        str(source / filename), input_params=["-ss", str(start)],
        output_params=["-vf", "fps=30", "-t", "8"])
    meta = next(reader)
    if meta["size"] != size:
        reader.close()
        raise ValueError("Source dimensions changed; privacy profile needs review")
    return reader


def backdrop(index, elapsed, duration):
    image = Image.new("RGB", (1080, 1920), BG)
    draw = ImageDraw.Draw(image)
    for radius in range(280, 1450, 180):
        draw.ellipse((540-radius, 880-radius, 540+radius, 880+radius),
                     outline="#103440", width=2)
    text(draw, "CLOCK PENALTY", (540, 59), 25, GOLD)
    text(draw, TITLES[index][0], (540, 124), 43)
    text(draw, TITLES[index][1], (540, 188), 49, MINT)
    return image


def render(source, narration, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for filename in (original.FLASH, original.CLUB, original.LEAGUE):
        if not (source / filename).is_file():
            raise FileNotFoundError(source / filename)
    scenes, caption_entries, cursor = [], [], 0
    output = output_dir / "clock-penalty-gameplay-revision.mp4"
    with tempfile.TemporaryDirectory(prefix="penalty-preview-") as folder:
        temp = Path(folder)
        audios = []
        for index, phrase in enumerate(PHRASES):
            samples, cues, spoken, voice = (
                cached_voice(narration, phrase, temp) if phrase
                else (np.zeros(round(2.7*RATE)), [], "", None))
            duration = math.ceil((len(samples)/RATE + .15)*FPS)/FPS
            samples = np.pad(samples, (0, round(duration*RATE)-len(samples)))
            raw = temp / f"voice-{index}.f32"
            raw.write_bytes(samples.astype("<f4").tobytes())
            audios.append(raw)
            scenes.append({"start": cursor, "duration": duration, "cues": cues,
                           "text": spoken, "phrase": phrase})
            caption_entries.extend((cursor+a, cursor+b, value) for a, b, value in cues)
            cursor += duration

        writer = imageio_ffmpeg.write_frames(
            str(temp / "silent.mp4"), (1080, 1920), fps=FPS, codec="libx264",
            macro_block_size=8, output_params=[
                "-preset", "fast", "-crf", "19", "-threads", "2"])
        writer.send(None)
        storyboard = Image.new("RGB", (1080, 960), BG)
        review = output_dir / "revision-fotogramas"
        review.mkdir(exist_ok=True)
        try:
            for index, scene in enumerate(scenes):
                duration = scene["duration"]
                readers = []
                try:
                    if index in (0, 1, 2, 3, 5):
                        start = {0: 121.6, 1: 19.3, 2: 23.6, 3: 27.1, 5: 121.8}[index]
                        reader = source_reader(source, original.FLASH, start, (480, 832))
                        readers.append(reader)
                    elif index == 4:
                        club = source_reader(source, original.CLUB, 7.5, (480, 832))
                        avatar = source_reader(source, original.CLUB, 25.4, (480, 832))
                        league = source_reader(source, original.LEAGUE, 23, (464, 816))
                        readers.extend([club, avatar, league])
                        league_image = Image.frombytes("RGB", (464, 816), next(league))
                    frame_count = round(duration*FPS)
                    for number in range(frame_count):
                        elapsed = number/FPS
                        image = backdrop(index, elapsed, duration)
                        draw = ImageDraw.Draw(image)
                        if index in (0, 1, 2, 3, 5):
                            # Hold the opening before the answer; reveal it in scene 6.
                            if index != 0 or number < 25:
                                art = Image.frombytes("RGB", (480, 832), next(reader))
                            comments = [
                                "Una centésima. Todo un partido.",
                                ".00: ¡gol de RayoFC!",
                                ".99: RayoFC tiene un penalti.",
                                "Par: gol. Impar: fallo.",
                                "", "¿Quién se lleva este duelo?", "",
                            ]
                            art = sanitize(art, "match", comments[index])
                            image.paste(art.resize((840, 1456), Image.Resampling.LANCZOS),
                                        (120, 240))
                            if index == 0 and elapsed > .85:
                                draw = ImageDraw.Draw(image)
                                draw.rounded_rectangle((265, 1100, 815, 1210),
                                                       radius=24, fill=BG, outline=GOLD, width=3)
                                text(draw, "¿LO CLAVAS?", (540, 1155), 52, GOLD)
                        elif index == 4:
                            if elapsed < .8:
                                art = Image.frombytes("RGB", (480, 832), next(club))
                                kind = "club"
                            elif elapsed < 1.6:
                                art = Image.frombytes("RGB", (480, 832), next(avatar))
                                kind = "club"
                            else:
                                art, kind = league_image, "league"
                            art = sanitize(art, kind)
                            factor = min(840/art.width, 1456/art.height)
                            art = art.resize((round(art.width*factor), round(art.height*factor)),
                                             Image.Resampling.LANCZOS)
                            image.paste(art, ((1080-art.width)//2, 240))
                        else:
                            with Image.open(original.ROOT/"clock-penalty-social-avatar.png") as logo:
                                image.paste(logo.convert("RGB").resize((610, 610)),
                                            (235, 365))
                            draw = ImageDraw.Draw(image)
                            text(draw, "NO CHUTAS.", (540, 1100), 70)
                            text(draw, "PARAS EL RELOJ.", (540, 1200), 61, MINT)
                            draw.rounded_rectangle((120, 1330, 960, 1450),
                                                   radius=28, fill=GOLD)
                            text(draw, DOMAIN, (540, 1390), 58, BG)
                        draw = ImageDraw.Draw(image)
                        cue = next((value for a, b, value in scene["cues"]
                                    if a <= elapsed <= b), "")
                        if cue:
                            rows = wrap(cue, 43, 820)
                            draw.rounded_rectangle((110, 1480, 970, 1655),
                                                   radius=24, fill=BG)
                            for row, line in enumerate(rows):
                                text(draw, line, (540, 1565+(row-(len(rows)-1)/2)*54),
                                     43, GOLD)
                        text(draw, DOMAIN, (540, 1745), 39, MINT)
                        text(draw, "Gameplay de desarrollo · nombres ficticios",
                             (540, 1800), 23)
                        text(draw, "@clock.penalty", (540, 1840), 25, GOLD)
                        draw.rectangle((100, 1880, 980, 1887), fill="#244653")
                        progress = (scene["start"]+elapsed)/cursor
                        draw.rectangle((100, 1880, 100+round(880*progress), 1887), fill=MINT)
                        writer.send(np.asarray(image))
                        if number % 15 == 0:
                            image.resize((270, 480)).save(
                                review / f"{scene['start']+elapsed:06.2f}.jpg", quality=88)
                        if number == min(30, frame_count-1):
                            storyboard.paste(image.resize((270, 480)),
                                             (index%4*270, index//4*480))
                finally:
                    for reader in readers:
                        reader.close()
                print(f"Rendered reviewed scene {index+1}/{len(scenes)}", flush=True)
        finally:
            writer.close()
        (temp/"narration.f32").write_bytes(b"".join(path.read_bytes() for path in audios))
        music = temp/"music.wav"
        original.music(music)
        original.run([
            ffmpeg, "-v", "error", "-y", "-i", str(temp/"silent.mp4"),
            "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", str(temp/"narration.f32"),
            "-i", str(music), "-filter_complex",
            "[1:a]volume=1.0,pan=stereo|c0=c0|c1=c0[v];"
            "[2:a]volume=0.11[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
            "loudnorm=I=-16:TP=-1.5:LRA=9[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-t", str(cursor), "-movflags", "+faststart", str(output),
        ])
        storyboard.save(output_dir/"storyboard.jpg", quality=94)
    original.run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    reader = imageio_ffmpeg.read_frames(str(output))
    metadata = next(reader)
    reader.close()
    if (metadata["size"] != (1080, 1920) or metadata["fps"] != FPS
            or not metadata["audio_codec"] or abs(metadata["duration"]-cursor) > .15):
        raise RuntimeError(f"Invalid export metadata: {metadata}")
    measured = original.run([
        ffmpeg, "-hide_banner", "-i", str(output), "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"])
    levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
    if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1:
        raise RuntimeError(f"Invalid preview audio levels: {levels}")
    (output_dir/"subtitulos.srt").write_text("\n\n".join(
        f"{i}\n{stamp(a)} --> {stamp(b)}\n{value}"
        for i, (a, b, value) in enumerate(caption_entries, 1))+"\n")
    cover = backdrop(0, 0, 1)
    draw = ImageDraw.Draw(cover)
    text(draw, ".00", (540, 800), 220, GOLD)
    text(draw, "¿LO CLAVAS?", (540, 1110), 92)
    text(draw, DOMAIN, (540, 1450), 54, MINT)
    cover.save(output_dir/"portada.jpg", quality=95)
    result = {
        "status": "private_visual_edit_complete_new_energetic_voice_pending",
        "published": False, "duration": metadata["duration"],
        "resolution": metadata["size"], "fps": FPS, "domain": DOMAIN,
        "aliases": ALIASES, "narration": {
            "provider": "ElevenLabs", "source": "previously generated catalog narration",
            "speed": SPEED, "new_energetic_performance": False,
            "blocker": "No authenticated access to marketing voice generation.",
        },
        "audio_levels": levels, "scenes": scenes,
        "source_note": "Real development recordings, upscaled from 464/480 pixels wide.",
        "privacy": {
            "method": "Source-level opaque replacements; league scene is a redacted still.",
            "match_regions": [[0, 170, 480, 253], [0, 307, 480, 340],
                              [0, 660, 480, 774]],
            "league_regions": [[15, 94, 451, 251], [106, 770, 306, 816]],
        },
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    if FORBIDDEN.search(json.dumps(result, ensure_ascii=False)):
        raise RuntimeError("Private text found in delivery metadata")
    (output_dir/"manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(f"Verified {metadata['duration']:.2f}s local preview: {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.source, args.narration, args.output)
