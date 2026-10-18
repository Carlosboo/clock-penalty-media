"""Render the introductory announcement with cached ElevenLabs voice and animation."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

import render_beta_install_video as video


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "intro-video"
DEST = video.WINDOWS / "instagram-presentacion-video"
TITLES = [
    ("Estoy haciendo un juego.", "De fútbol. Pero aquí no se chuta."),
    ("Paras el reloj.", "Clavar las centésimas tiene premio."),
    ("¿Y si paras en .99?", "Tienes un penalti."),
    ("Cada posesión cuenta.", "Tú decides cuándo parar."),
    ("Ya puedes probar la beta.", "De momento, contra un bot."),
    ("Lo estoy construyendo.", "Si lo pruebas, dime qué mejorarías."),
]


def frame(index, elapsed, duration, cues, game_frame):
    image = Image.new("RGB", (1080, 1920), video.BG)
    draw = ImageDraw.Draw(image)
    for radius in range(300, 1400, 180):
        draw.ellipse((540-radius, 890-radius, 540+radius, 890+radius),
                     outline="#123842", width=2)
    video.centered(draw, "CLOCK PENALTY", 175, 29, video.GOLD)
    video.centered(draw, TITLES[index][0], 285, 52)
    video.centered(draw, TITLES[index][1], 360, 30, video.MINT)
    entry = max(0, 1-min(1, elapsed/.45))**3
    if index in (3, 4):
        image.paste(game_frame, (300+round(entry*90), 430))
        draw = ImageDraw.Draw(image)
        video.centered(draw, "Grabación de desarrollo", 1320, 24, video.GOLD)
    elif index in (0, 5):
        with Image.open(ROOT/"clock-penalty-social-avatar.png") as art:
            size = round(700*(1+.025*elapsed/duration))
            art = art.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
            image.paste(art, ((1080-size)//2, 480+round(entry*60)))
        draw = ImageDraw.Draw(image)
        video.centered(draw, "clockpenalty.com", 1310, 52, video.MINT)
    else:
        draw.rounded_rectangle((120, 540, 960, 930), radius=45,
                               fill="#03131F", outline=video.MINT, width=4)
        value = ".00" if index == 1 else ".99"
        if elapsed < .65:
            value = f".{int(elapsed*180)%100:02}"
        video.centered(draw, value, 730, 180, video.MINT if index == 1 else video.GOLD)
        if index == 1:
            scale = min(1, max(0, (elapsed-.65)/.2))
            video.centered(draw, "¡GOOOL!", 1100+round((1-scale)*25), 95, video.GOLD)
        else:
            video.centered(draw, "CENTÉSIMAS PARES → GOL", 1080, 42, video.MINT)
            video.centered(draw, "IMPARES → FALLO", 1170, 42, "#FF8E9F")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((65, 1440, 1015, 1680), radius=30, fill="#102E40")
    cue = next((text for a, b, text in cues if a <= elapsed <= b), "")
    lines = video.lines(cue, 36, 850)
    if len(lines) > 3:
        raise ValueError(f"Intro caption too long: {cue}")
    for row, line in enumerate(lines):
        video.centered(draw, line, 1560+(row-(len(lines)-1)/2)*51, 36)
    video.centered(draw, "clockpenalty.com", 1760, 34, video.MINT)
    video.centered(draw, "@clock.penalty", 1830, 25, video.GOLD)
    opacity = max(0, min(1, elapsed/.15, (duration-elapsed)/.15))
    return Image.blend(Image.new("RGB", image.size, video.BG), image, opacity)


def render(narration):
    request = json.loads((ROOT.parent.parent/"scripts/elevenlabs-intro-request.json").read_text())
    video.SCENES = [(*TITLES[i], None, None, text) for i, text in enumerate(request["scenes"])]
    voice, decoded = video.load_narration(narration)
    OUT.mkdir(exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    game = video.WINDOWS/"contenido aplicacion/Partido Flash completo con comienzo dinamico.mp4"
    with tempfile.TemporaryDirectory(prefix="penalty-intro-") as folder:
        temp = Path(folder)
        scenes, captions, duration = video.prepare_audio(temp, decoded)
        writer = imageio_ffmpeg.write_frames(
            str(temp/"silent.mp4"), (1080, 1920), fps=30, codec="libx264",
            macro_block_size=8, output_params=["-crf", "19", "-preset", "fast", "-threads", "2"])
        writer.send(None)
        sheet = Image.new("RGB", (810, 960), video.BG)
        try:
            for index, scene in enumerate(scenes):
                reader = None
                if index in (3, 4):
                    reader = imageio_ffmpeg.read_frames(
                        str(game), input_params=["-ss", "18.5"],
                        output_params=["-vf", "scale=480:854", "-r", "30"])
                    next(reader)
                try:
                    for number in range(scene["frames"]):
                        art = Image.frombytes("RGB", (480, 854), next(reader)) if reader else None
                        image = frame(index, number/30, scene["duration"], scene["cues"], art)
                        writer.send(np.asarray(image))
                        if number == 30:
                            sheet.paste(image.resize((270, 480)),
                                        ((index%3)*270, (index//3)*480))
                finally:
                    if reader:
                        reader.close()
                print(f"Rendered introduction scene {index+1}/6", flush=True)
        finally:
            writer.close()
        output = OUT/"clock-penalty-presentacion-voz.mp4"
        video.run([ffmpeg, "-v", "error", "-y", "-i", str(temp/"silent.mp4"),
                   "-i", str(temp/"narration.wav"), "-c:v", "copy",
                   "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
                   "-c:a", "aac", "-ar", "48000", "-b:a", "192k",
                   "-t", str(duration), "-movflags", "+faststart", str(output)])
        video.run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
        reader = imageio_ffmpeg.read_frames(str(output))
        meta = next(reader)
        reader.close()
        if meta["size"] != (1080, 1920) or meta["fps"] != 30 or abs(meta["duration"]-duration) > .15:
            raise RuntimeError("Invalid introductory video export")
        result = video.run([ffmpeg, "-hide_banner", "-i", str(output), "-af",
                            "loudnorm=I=-16:TP=-1:LRA=9:print_format=json", "-f", "null", "-"])
        levels, _ = json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind("{"):])
        if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1:
            raise RuntimeError(f"Invalid introduction audio levels: {levels}")
        sheet.save(OUT/"storyboard.jpg", quality=93)
        (OUT/"subtitulos.srt").write_text("\n\n".join(
            f"{i}\n{video.stamp(a)} --> {video.stamp(b)}\n{text}"
            for i, (a, b, text) in enumerate(captions, 1))+"\n", encoding="utf-8")
        (OUT/"manifest.json").write_text(json.dumps({
            "published": False, "domain": "clockpenalty.com", "voice": voice["voice"],
            "duration": meta["duration"], "audioLevels": levels, "scenes": scenes,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        DEST.mkdir(exist_ok=True)
        for path in OUT.iterdir():
            if path.is_file():
                shutil.copy2(path, DEST/path.name)
                if path.read_bytes() != (DEST/path.name).read_bytes():
                    raise RuntimeError("Introduction Windows copy differs")
        print(f"Verified {duration:.2f}s narrated announcement and Windows copies", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", type=Path, required=True)
    render(parser.parse_args().narration)
