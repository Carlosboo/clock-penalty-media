"""Edit user-provided recordings locally into a 30-second vertical promotion."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FLASH = "Partido Flash completo con comienzo dinamico.mp4"
CLUB = "Personalizacion Club.mp4"
LEAGUE = "Creacion Liga y comienzo partido liguero.mp4"
SHOTS = [
    (FLASH, 18.5, 5, "Estoy haciendo un juego", "de fútbol sin chutar.", "Paras en .00 y marcas."),
    (FLASH, 24, 3, "Y si cae en .99...", "tienes un penalti.", "Grabación real de la aplicación"),
    (FLASH, 27, 4, "Aquí me salió impar.", "Penalti fallado.", "Par = gol · Impar = fallo"),
    (CLUB, 7, 3, "También puedes montar", "tu propio club.", "Nombre, colores y escudo"),
    (CLUB, 24, 3, "Y darle tu pinta", "al avatar.", "Grabación real de la aplicación"),
    (LEAGUE, 20, 4, "Así va quedando", "la parte de ligas.", "Clasificación dentro de la aplicación"),
    (FLASH, 121, 4, "Pero lo importante", "es clavar esto.", "Otra parada en .00"),
    (None, 0, 4, "Clock Penalty", "Lo estoy construyendo.", "Si lo pruebas, dime qué cambiarías."),
]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-7000:])
    return result


def label(draw, value, y, size, color="#F2F6F3"):
    font = ImageFont.truetype(FONT, size)
    if draw.textbbox((0, 0), value, font=font)[2] > 970:
        raise ValueError(f"Text exceeds safe area: {value}")
    draw.text((540, y), value, font=font, fill=color, anchor="mm")


def overlay(path, shot):
    end = shot[0] is None
    image = Image.new("RGBA", (1080, 1920), "#061D2C" if end else (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if end:
        with Image.open(ROOT / "clock-penalty-social-avatar.png") as avatar:
            image.paste(avatar.resize((650, 650), Image.Resampling.LANCZOS), (215, 515))
        label(draw, shot[3], 290, 74, "#FFE399")
        label(draw, shot[4], 400, 44)
        label(draw, "clockpenalty.com", 1290, 57, "#73F8C9")
        label(draw, shot[5], 1410, 38)
        label(draw, "@clock.penalty", 1550, 36)
    else:
        draw.rectangle((0, 0, 1080, 194), fill="#061D2C")
        draw.rectangle((0, 1726, 1080, 1920), fill="#061D2C")
        label(draw, shot[3], 67, 45)
        label(draw, shot[4], 132, 48, "#73F8C9")
        label(draw, shot[5], 1785, 33, "#FFE399")
        label(draw, "@clock.penalty", 1840, 29)
    image.save(path)


def music(path):
    rate, duration = 44100, 30
    t = np.arange(rate * duration) / rate
    rng = np.random.default_rng(481)
    signal = np.zeros_like(t)
    for start in np.arange(0, 26, .5):
        local = t - start
        active = local >= 0
        tau = np.maximum(local, 0)
        signal += .21 * np.sin(2 * np.pi * (48 * tau + 2 * (1 - np.exp(-tau * 26)))) * np.exp(-tau * 18) * active
        signal += .025 * rng.normal(size=len(t)) * np.exp(-tau * 100) * active
    notes = (146.83, 174.61, 220, 196)
    for beat in range(60):
        tau = np.maximum(t - beat * .5, 0)
        signal += .038 * np.sin(2 * np.pi * notes[(beat // 4) % 4] * tau) * np.exp(-tau * 7) * (t >= beat * .5)
    for start in (1.6, 6.3, 12, 15, 18, 22):
        tau = np.maximum(t - start, 0)
        signal += .13 * rng.normal(size=len(t)) * np.exp(-tau * 24) * (t >= start)
    for frequency in (146.83, 174.61, 220):
        tau = np.maximum(t - 26, 0)
        signal += .07 * np.sin(2 * np.pi * frequency * tau) * np.exp(-tau * 1.2) * (t >= 26)
    signal *= np.minimum(t / .15, 1) * np.minimum((duration - t) / .7, 1)
    stereo = np.column_stack((signal, signal * .96))
    if not np.isfinite(stereo).all() or np.max(np.abs(stereo)) >= 1:
        raise RuntimeError("Invalid music samples")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((stereo * 32767).astype("<i2").tobytes())


def render(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for name in (FLASH, CLUB, LEAGUE):
        if not (source / name).is_file():
            raise FileNotFoundError(source / name)
    output = destination / "clock-penalty-gameplay-30s.mp4"
    with tempfile.TemporaryDirectory(prefix="penalty-gameplay-") as folder:
        temp = Path(folder)
        for index, shot in enumerate(SHOTS):
            name, start, duration, *_ = shot
            art = temp / f"overlay-{index}.png"
            overlay(art, shot)
            inputs = (["-ss", str(start), "-i", str(source / name)]
                      if name else ["-f", "lavfi", "-i", "color=c=0x061D2C:s=1080x1920:r=30"])
            filters = (
                "[0:v]fps=30,scale=1080:1532:force_original_aspect_ratio=decrease:"
                "flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x061D2C,"
                "setsar=1[screen];[screen][1:v]overlay=0:0:format=auto,"
                "format=yuv420p,fade=t=in:d=0.10"
            )
            run([ffmpeg, "-v", "error", "-y", *inputs, "-loop", "1", "-i", str(art),
                 "-filter_complex", filters, "-t", str(duration), "-an", "-c:v",
                 "libx264", "-preset", "fast", "-crf", "19", "-threads", "2",
                 str(temp / f"part-{index}.mp4")])
            print(f"Rendered shot {index + 1}/{len(SHOTS)}", flush=True)
        listing = temp / "parts.txt"
        listing.write_text("".join(f"file 'part-{i}.mp4'\n" for i in range(len(SHOTS))))
        sound = temp / "music.wav"
        music(sound)
        run([ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listing), "-i", str(sound), "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
             "-c:a", "aac", "-b:a", "192k", "-t", "30", "-movflags", "+faststart", str(output)])
    run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    reader = imageio_ffmpeg.read_frames(str(output))
    meta = next(reader)
    reader.close()
    assert meta["size"] == (1080, 1920) and abs(meta["duration"] - 30) < .1, meta
    assert meta["audio_codec"] and meta["fps"] == 30, meta
    run([ffmpeg, "-v", "error", "-y", "-i", str(output), "-vf",
         "fps=1/4,scale=270:480,tile=4x2", "-frames:v", "1", str(destination / "storyboard.jpg")])
    caption = (
        "Estoy haciendo un juego de fútbol en el que paras un reloj.\n\n"
        ".00 es gol. .99 es penalti. Y en el penalti: par, gol; impar, fallo.\n\n"
        "Esto es una grabación de cómo va quedando: partido flash, club, avatar y ligas. "
        "La demo pública puede ir por detrás de esta versión.\n\n"
        "Puedes probar la demo en clockpenalty.com. Si la pruebas, dime qué cambiarías."
    )
    (destination / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    manifest = {
        "status": "rendered_not_published", "duration_seconds": 30,
        "resolution": [1080, 1920], "fps": 30,
        "source_note": "Screen recordings at 464/480 pixels wide; scaled, not native Full HD.",
        "audio": "Original locally synthesized music and effects; no licensed songs or cloned voices.",
        "shots": [{"source": s[0], "start": s[1], "duration": s[2]} for s in SHOTS],
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    windows = source.parent / "promocional-gameplay"
    windows.mkdir(exist_ok=True)
    for path in destination.iterdir():
        if path.is_file():
            target = windows / path.name
            shutil.copy2(path, target)
            assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
    print(f"Verified video and Windows copies: {windows}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "gameplay-ad")
    args = parser.parse_args()
    render(args.source.resolve(), args.output_dir.resolve())
