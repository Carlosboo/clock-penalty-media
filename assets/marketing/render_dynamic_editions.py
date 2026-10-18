"""Create pitch-preserving faster editions and explicit reel covers locally."""

import hashlib
import json
from pathlib import Path
import shutil

import imageio_ffmpeg
from PIL import Image, ImageDraw

import render_beta_install_video as video


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "relaunch-dynamic"
DEST = video.WINDOWS / "instagram-version-dinamica"
SPEED = 1.15
LABELS = {
    "presentacion": ("NO CHUTAS.", "PARAS EL RELOJ.", "Así es Clock Penalty"),
}


def cover(name, target):
    image = Image.new("RGB", (1080, 1920), video.BG)
    draw = ImageDraw.Draw(image)
    for radius in range(360, 1400, 190):
        draw.ellipse((540-radius, 960-radius, 540+radius, 960+radius),
                     outline="#123842", width=3)
    video.centered(draw, "CLOCK PENALTY", 440, 36, video.GOLD)
    title, subtitle, detail = LABELS[name]
    video.centered(draw, title, 570, 69)
    video.centered(draw, subtitle, 670, 66, video.MINT)
    with Image.open(REPO / "assets/marketing/clock-penalty-social-avatar.png") as source:
        image.paste(source.convert("RGB").resize((520, 520)), (280, 770))
    draw = ImageDraw.Draw(image)
    video.centered(draw, detail, 1360, 35)
    video.centered(draw, "clockpenalty.com", 1470, 42, video.MINT)
    image.save(target, quality=96)


def metadata(path):
    reader = imageio_ffmpeg.read_frames(str(path))
    try:
        return next(reader)
    finally:
        reader.close()


def render():
    OUT.mkdir(exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    manifest = {"speed": SPEED, "domain": "clockpenalty.com", "published": False,
                "pitchPreserved": True, "files": {}}
    for name in LABELS:
        cover(name, OUT / f"portada-{name}.jpg")
    for name in ("presentacion",):
        source = REPO / "relaunch" / f"{name}.mp4"
        output = OUT / f"{name}-dinamico.mp4"
        args = [ffmpeg, "-v", "error", "-y", "-i", str(source)]
        base = f"[0:v]setpts=PTS/{SPEED},fps=30[v0];"
        if name in LABELS:
            args += ["-loop", "1", "-i", str(OUT / f"portada-{name}.jpg")]
            base += "[v0][1:v]overlay=enable='lt(t,0.5)':shortest=1[v];"
        else:
            base += "[v0]null[v];"
        base += f"[0:a]atempo={SPEED},loudnorm=I=-16:TP=-1.5:LRA=9[a]"
        expected = metadata(source)["duration"] / SPEED
        video.run(args + [
            "-filter_complex", base, "-map", "[v]", "-map", "[a]",
            "-t", str(expected), "-c:v", "libx264", "-preset", "fast",
            "-crf", "18", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart", str(output)])
        video.run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
        meta = metadata(output)
        if (meta["size"] != (1080, 1920) or meta["fps"] != 30 or
                not meta["audio_codec"] or abs(meta["duration"] - expected) > .15):
            raise RuntimeError(f"Invalid faster edition: {name}")
        measured = video.run([ffmpeg, "-hide_banner", "-i", str(output),
                              "-af", "loudnorm=I=-16:TP=-1:LRA=9:print_format=json",
                              "-f", "null", "-"])
        levels, _ = json.JSONDecoder().raw_decode(measured.stderr[measured.stderr.rfind("{"):])
        if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1:
            raise RuntimeError(f"Invalid audio levels: {name}")
        manifest["files"][output.name] = {
            "duration": meta["duration"], "originalDuration": metadata(source)["duration"],
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "audioLevels": levels,
            "cover": f"portada-{name}.jpg" if name in LABELS else None,
        }
        print(f"Verified {name}: {meta['duration']:.2f}s at {SPEED}x", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    DEST.mkdir(exist_ok=True)
    for path in OUT.iterdir():
        if path.is_file():
            shutil.copy2(path, DEST / path.name)
            if path.read_bytes() != (DEST / path.name).read_bytes():
                raise RuntimeError(f"Windows copy differs: {path.name}")


if __name__ == "__main__":
    render()
