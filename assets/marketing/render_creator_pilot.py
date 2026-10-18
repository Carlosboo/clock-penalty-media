"""Edit the creator's recording locally; no uploads, generated voice or face changes."""

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
DOWNLOADS = Path("/mnt/c/Users/juan.crugeiras/Downloads")
SOURCE = DOWNLOADS / "prueba pilot generacion de contenido.mp4"
GAME = DOWNLOADS / "Clock-Penalty-Anuncios/contenido aplicacion/Partido Flash completo con comienzo dinamico.mp4"
OUT = ROOT / "creator-pilot"
DEST = DOWNLOADS / "Clock-Penalty-Anuncios/presentacion-creador"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG, MINT, GOLD = "#061D2C", "#73F8C9", "#FFE399"
FPS, RATE = 30, 44100
# Frame-aligned cuts retain one complete clean take of each technology.
CUTS = [
    (.70, 2.80, "hook", "PRUEBA REAL CON IA", "Tu voz. Un montaje nuevo."),
    (3.77, 9.90, "intro", "EL STACK DE MI JUEGO", "Clock Penalty · desarrollo"),
    (61.50, 63.97, "database", "Supabase", "Base de datos"),
    (64.50, 68.20, "cloud", "Cloudflare Pages", "Frontend web"),
    (68.70, 73.93, "live", "WebSockets", "Comunicación durante el partido"),
    (74.60, 79.20, "shield", "Cloudflare Turnstile", "Filtro antibots"),
]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-7000:])
    return result


def font(size):
    return ImageFont.truetype(FONT, size)


def text(draw, value, x, y, size, color="white", anchor="mm"):
    if draw.textbbox((0, 0), value, font=font(size))[2] > 920:
        raise ValueError(f"Text exceeds safe width: {value}")
    draw.text((x, y), value, font=font(size), fill=color, anchor=anchor)


def timestamp(seconds, ass=False):
    units = round(seconds * (100 if ass else 1000))
    scale = 100 if ass else 1000
    hours, remainder = divmod(units, 3600 * scale)
    minutes, remainder = divmod(remainder, 60 * scale)
    secs, fraction = divmod(remainder, scale)
    return (f"{hours}:{minutes:02}:{secs:02}.{fraction:02}" if ass
            else f"{hours:02}:{minutes:02}:{secs:02},{fraction:03}")


def transcript(path):
    """Decode with FFmpeg because some PyAV builds reject metadata_errors."""
    from faster_whisper import WhisperModel
    raw = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(SOURCE),
        "-vn", "-ar", "16000", "-ac", "1", "-f", "f32le", "-",
    ], capture_output=True, check=True).stdout
    model = WhisperModel("small", device="cpu", compute_type="int8",
                         cpu_threads=2, num_workers=1)
    segments, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32),
                                  language="es", beam_size=5,
                                  word_timestamps=True, vad_filter=True)
    data = [{"start": s.start, "end": s.end, "text": s.text,
             "words": [{"start": w.start, "end": w.end, "word": w.word}
                       for w in s.words]} for s in segments]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def edited_words(data, cuts):
    words, cursor = [], 0
    for start, end, *_ in cuts:
        for segment in data:
            for word in segment["words"]:
                if word["start"] >= start and word["end"] <= end:
                    words.append({
                        "start": cursor + word["start"] - start,
                        "end": cursor + word["end"] - start,
                        "word": word["word"].strip(),
                    })
        cursor += round((end-start)*FPS)/FPS
    replacements = {"Supabeis": "Supabase", "cloud": "Cloudflare",
                    "for": "", "throne": "Turnstile", "style": ""}
    for word in words:
        word["word"] = replacements.get(word["word"], word["word"])
        if word["word"] == "pages":
            word["word"] = "Pages"
        if word["word"] == "websockets":
            word["word"] = "WebSockets"
    words = [word for word in words if word["word"]]
    merged = []
    for word in words:
        if word["word"] == "-bots" and merged and merged[-1]["word"] == "anti":
            merged[-1]["word"] = "antibots."
            merged[-1]["end"] = word["end"]
        else:
            merged.append(word)
    return merged


def subtitles(data, cuts, folder):
    words = edited_words(data, cuts)
    groups, group = [], []
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for word in words:
        proposed = " ".join(item["word"] for item in group + [word])
        gap = bool(group and word["start"] - group[-1]["end"] > .45)
        wide = measure.textbbox((0, 0), proposed, font=font(58))[2] > 820
        if group and (len(group) == 4 or wide or gap):
            groups.append(group)
            group = []
        group.append(word)
        if word["word"].endswith((".", ",")):
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,58,&H00C9F873,&H00FFFFFF,&H00201808,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,100,160,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, srt = [], []
    for index, group in enumerate(groups):
        start, end = group[0]["start"], group[-1]["end"] + .10
        if index+1 < len(groups):
            end = min(end, groups[index+1][0]["start"])
        if end <= start:
            raise ValueError("Invalid subtitle timing")
        current, karaoke = start, []
        for word in group:
            gap = max(0, round((word["start"]-current)*100))
            if gap:
                karaoke.append(r"{\k" + str(gap) + "} ")
            length = max(1, round((word["end"]-word["start"])*100))
            karaoke.append(r"{\kf" + str(length) + "}" + word["word"] + " ")
            current = word["end"]
        events.append(f"Dialogue: 0,{timestamp(start, True)},{timestamp(end, True)},"
                      "Caption,,0,0,0,," + r"{\fad(60,70)}" + "".join(karaoke))
        srt.append(f"{index+1}\n{timestamp(start)} --> {timestamp(end)}\n"
                   + " ".join(word["word"] for word in group))
    (folder / "captions.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    (OUT / "subtitulos.srt").write_text("\n\n".join(srt) + "\n", encoding="utf-8")
    return words


def icon(draw, kind, x, y, color=MINT):
    if kind == "database":
        draw.rounded_rectangle((x-48, y-45, x+48, y+50), radius=12, outline=color, width=5)
        for dy in (-45, 0, 45):
            draw.ellipse((x-48, y+dy-15, x+48, y+dy+15), outline=color, width=5)
    elif kind == "cloud":
        for dx, dy, radius in [(-30, 4, 30), (5, -18, 39), (45, 8, 27)]:
            draw.ellipse((x+dx-radius, y+dy-radius, x+dx+radius, y+dy+radius), fill=color)
        draw.rounded_rectangle((x-60, y+5, x+70, y+40), radius=10, fill=color)
    elif kind == "shield":
        draw.polygon([(x,y-62),(x+52,y-40),(x+43,y+24),(x,y+65),
                      (x-43,y+24),(x-52,y-40)], outline=color, width=6)
        draw.line((x-25,y,x-5,y+22,x+30,y-20), fill=color, width=7)
    elif kind == "live":
        for dx in (-35,35):
            draw.rounded_rectangle((x+dx-21,y-42,x+dx+21,y+42), radius=10,
                                   outline=color,width=5)
        draw.line((x-12,y,x+12,y),fill=GOLD,width=6)
    else:
        draw.rounded_rectangle((x-48,y-40,x+48,y+40),radius=20,outline=color,width=5)
        draw.line((x-27,y,x+27,y),fill=color,width=5)
        draw.line((x,y-22,x,y+22),fill=color,width=5)


def overlays(cuts, folder):
    """Short entrance animations and restrained cards keep faces unobstructed."""
    paths = []
    for index, (start, end, kind, title, subtitle) in enumerate(cuts):
        duration = round((end-start)*FPS)/FPS
        target = folder / f"overlay-{index}.mp4"
        writer = imageio_ffmpeg.write_frames(
            str(target), (1080,1920), fps=FPS, codec="libx264",
            macro_block_size=8, output_params=["-preset","fast","-crf","18","-threads","2"])
        writer.send(None)
        try:
            for frame in range(round(duration*FPS)):
                t = frame/FPS
                image = Image.new("RGB",(1080,1920),"black")
                draw = ImageDraw.Draw(image)
                # This layer is screened over footage; black is transparent.
                draw.rounded_rectangle((65,150,475,207),radius=18,fill=BG)
                text(draw,"@clock.penalty",270,178,29,MINT)
                if kind in ("hook","intro"):
                    y = 305 + round(40 * max(0,1-t/.3)**3)
                    draw.rounded_rectangle((55,y-62,1015,y+62),radius=24,fill=BG)
                    text(draw,title,535,y,48,GOLD)
                else:
                    offset = round(120 * max(0,1-t/.3)**3)
                    y = 1190 if kind != "live" else 330
                    draw.rounded_rectangle((65+offset,y-105,1015,y+105),radius=30,fill=BG)
                    icon(draw,kind,160+offset,y)
                    text(draw,title,615,y-27,43,MINT)
                    text(draw,subtitle,615,y+40,29)
                    if kind == "live":
                        text(draw,"Grabación de desarrollo",354,465,25,GOLD)
                    if kind == "shield":
                        draw.rounded_rectangle((100,1340,980,1400),radius=15,fill=BG)
                        text(draw,"Antitrampas: validación en el servidor",540,1370,27,GOLD)
                draw.rounded_rectangle((65,1770,1015,1780),radius=5,fill=BG)
                draw.rounded_rectangle((65,1770,65+max(6,round(950*t/duration)),1780),
                                       radius=5,fill=MINT)
                writer.send(np.asarray(image))
        finally:
            writer.close()
        paths.append(target)
    return paths


def sound(folder, duration):
    t = np.arange(round(duration*RATE))/RATE
    audio = np.zeros_like(t)
    for beat in np.arange(0,duration,.6):
        local = t-beat
        active = local >= 0
        tau = np.maximum(local,0)
        audio += .012*np.sin(2*math.pi*(65*tau+1-np.exp(-25*tau)))*np.exp(-18*tau)*active
    cursor = 0
    for index,(start,end,*_) in enumerate(CUTS):
        tau = np.maximum(t-cursor,0)
        audio += .018*np.sin(2*math.pi*(660+index*55)*tau)*np.exp(-24*tau)*(t>=cursor)
        cursor += round((end-start)*FPS)/FPS
    audio *= np.minimum(1,t/.15)*np.maximum(0,np.minimum(1,(duration-t)/.4))
    with wave.open(str(folder/"bed.wav"),"wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((audio*32767).astype("<i2").tobytes())


def render(transcript_path):
    for path in (SOURCE,GAME,transcript_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    OUT.mkdir(exist_ok=True)
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cuts = [(round(a*FPS)/FPS,round(b*FPS)/FPS,*rest) for a,b,*rest in CUTS]
    with tempfile.TemporaryDirectory(prefix="penalty-creator-") as folder:
        temp = Path(folder)
        words = subtitles(data,cuts,temp)
        overlays_paths = overlays(cuts,temp)
        for index,(start,end,kind,*_) in enumerate(cuts):
            length = end-start
            inputs = ["-ss",str(start),"-i",str(SOURCE),"-i",str(overlays_paths[index])]
            if kind == "live":
                inputs += ["-ss","18.5","-i",str(GAME)]
                layout = (
                    "[0:v]crop=440:782:68:225,scale=292:520,setsar=1[pip];"
                    "[2:v]scale=568:1010:force_original_aspect_ratio=decrease,"
                    "pad=568:1010:(ow-iw)/2:(oh-ih)/2:color=0x061D2C[game];"
                    f"color=c=0x061D2C:s=1080x1920:r={FPS}:d={length}[bg];"
                    "[bg][game]overlay=70:490[screen];"
                    "[screen][pip]overlay=728:928[base];"
                )
            else:
                crop = "440:782:68:225" if index%2 == 0 else "480:853:48:171"
                layout = f"[0:v]crop={crop},scale=1080:1920,setsar=1[base];"
            filters = (
                layout
                + "[base]eq=contrast=1.035:saturation=1.04:brightness=0.006[grade];"
                "[1:v]colorkey=black:0.01:0.0[art];"
                "[grade][art]overlay=0:0,format=yuv420p[v];"
                f"[0:a]atrim=duration={length},asetpts=PTS-STARTPTS,"
                "afade=t=in:d=0.012,afade=t=out:st="
                f"{length-.018}:d=0.018[a]"
            )
            run([ffmpeg,"-v","error","-y",*inputs,"-filter_complex",filters,
                 "-map","[v]","-map","[a]","-t",str(length),"-r",str(FPS),
                 "-c:v","libx264","-preset","fast","-crf","19","-threads","2",
                 "-c:a","aac","-ar",str(RATE),"-ac","2","-b:a","192k",
                 str(temp/f"part-{index}.mp4")])
            print(f"Edited shot {index+1}/{len(cuts)}",flush=True)
        duration = sum(b-a for a,b,*_ in cuts)
        # End card is silent except for the original instrumental bed.
        card = Image.new("RGB",(1080,1920),BG)
        draw = ImageDraw.Draw(card)
        draw.ellipse((455,355,625,525),outline=MINT,width=6)
        draw.rounded_rectangle((510,326,570,350),radius=7,fill=GOLD)
        draw.line((540,440,540,385),fill=GOLD,width=7)
        draw.line((540,440,580,460),fill=MINT,width=6)
        text(draw,"CLOCK PENALTY",540,650,68,MINT)
        text(draw,"Lo estoy construyendo.",540,780,43)
        text(draw,"Si lo pruebas, dime qué mejorarías.",540,860,33)
        draw.rounded_rectangle((70,1090,1010,1260),radius=28,fill=GOLD)
        text(draw,"clockpenalty.com",540,1175,43,BG)
        text(draw,"@clock.penalty",540,1450,36,MINT)
        card.save(temp/"end.png")
        run([ffmpeg,"-v","error","-y","-loop","1","-i",str(temp/"end.png"),
             "-f","lavfi","-i",f"anullsrc=r={RATE}:cl=stereo","-t","2.6",
             "-vf","fade=t=in:d=0.18,fade=t=out:st=2.3:d=0.3",
             "-r",str(FPS),"-c:v","libx264","-preset","fast","-crf","19",
             "-pix_fmt","yuv420p","-threads","2","-c:a","aac","-b:a","192k",str(temp/"end.mp4")])
        listing = temp/"list.txt"
        listing.write_text("".join(f"file 'part-{i}.mp4'\n" for i in range(len(cuts)))+"file 'end.mp4'\n")
        run([ffmpeg,"-v","error","-y","-f","concat","-safe","0","-i",str(listing),
             "-c","copy",str(temp/"joined.mp4")])
        duration += 2.6
        sound(temp,duration)
        output = OUT/"clock-penalty-presentacion-creador.mp4"
        run([ffmpeg,"-v","error","-y","-i",str(temp/"joined.mp4"),"-i",str(temp/"bed.wav"),
             "-filter_complex",
             "[0:a]highpass=f=75,lowpass=f=12000,afftdn=nr=7:nf=-35,"
             "acompressor=threshold=0.12:ratio=2:attack=15:release=160,"
             "loudnorm=I=-16:TP=-2:LRA=9[voice];"
             "[voice][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]",
             "-vf",f"ass={temp/'captions.ass'}","-map","0:v","-map","[a]",
             "-c:v","libx264","-preset","fast","-crf","18","-threads","2",
             "-c:a","aac","-b:a","192k","-ar",str(RATE),"-t",str(duration),
             "-movflags","+faststart",str(output)])
        run([ffmpeg,"-v","error","-xerror","-i",str(output),"-f","null","-"])
        reader = imageio_ffmpeg.read_frames(str(output))
        meta = next(reader)
        reader.close()
        if (meta["size"] != (1080,1920) or meta["fps"] != FPS
                or not meta["audio_codec"] or abs(meta["duration"]-duration)>.18):
            raise RuntimeError(f"Invalid deliverable format: {meta}")
        run([ffmpeg,"-v","error","-y","-i",str(output),"-vf",
             "fps=1/3.5,scale=216:384,tile=4x2","-frames:v","1",str(OUT/"storyboard.jpg")])
        run([ffmpeg,"-v","error","-y","-ss","0.8","-i",str(output),
             "-frames:v","1",str(OUT/"portada.jpg")])
        measure = run([ffmpeg,"-hide_banner","-i",str(output),"-af",
                       "loudnorm=I=-16:TP=-1:LRA=9:print_format=json","-f","null","-"])
        analysis, _ = json.JSONDecoder().raw_decode(measure.stderr[measure.stderr.rfind("{"):])
        if not -18 <= float(analysis["input_i"]) <= -14 or float(analysis["input_tp"]) > -.8:
            raise RuntimeError(f"Audio loudness/peak outside delivery range: {analysis}")
        manifest = {
            "published":False,"source":SOURCE.name,"sourceDuration":91.07,
            "duration":meta["duration"],"size":[1080,1920],"fps":FPS,
            "sourceNativeSize":[576,1024],"voice":"Original speaker; no voice cloning or generation",
            "audio":analysis,"cuts":[{"in":a,"out":b,"scene":k} for a,b,k,*_ in cuts],
            "subtitles":"Local Whisper small ASR, brand spelling corrected; inspect before publication",
            "notes":["Retakes, clothing-change request and editing directions removed.",
                     "Turnstile shown as antibot filter, not as standalone anticheat.",
                     "Screen recording is development footage; not a claim of current public availability.",
                     "No clothing, face, body or background replacement.",
                     "Upscaled export, not native Full HD detail."],
            "sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
            "captionWords":words,
        }
        (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (OUT/"caption.txt").write_text(
            "Una prueba real: mi grabación, editada con ayuda de IA.\n\n"
            "Este es parte del stack con el que estoy construyendo Clock Penalty: "
            "Supabase, Cloudflare Pages, WebSockets y Turnstile para filtrar bots. "
            "Las jugadas se validan en el servidor; Turnstile no sustituye esa validación.\n\n"
            "El gameplay es una grabación de desarrollo. Puedes probar la beta en "
            "https://clockpenalty.com/ y contarme qué mejorarías.\n",
            encoding="utf-8")
        (OUT/"README.txt").write_text(
            "Versión nueva, no publicada. Voz y rostro originales. Edición local.\n"
            "Cortes: se eliminan ensayos, repeticiones y peticiones de producción.\n"
            "Incluye reencuadre, planos alternos, tarjetas e iconos animados, juego con "
            "presentador en ventana, subtítulos destacados y cierre con URL.\n"
            "Revisar el vídeo con sonido antes de publicarlo: subtítulos generados con ASR local.\n"
            "Exportación H.264/AAC 1080x1920 30 fps, desde original vertical 576x1024.\n"
            "No se ha cambiado ropa, rostro o fondo. Música/acentos discretos sintetizados localmente.\n",
            encoding="utf-8")
        DEST.mkdir(parents=True,exist_ok=True)
        for path in OUT.iterdir():
            if path.is_file():
                target = DEST/path.name
                shutil.copy2(path,target)
                if target.read_bytes()!=path.read_bytes():
                    raise RuntimeError(f"Windows copy differs: {target}")
        print(f"VERIFIED: {output}, {duration:.2f}s; audio {analysis['input_i']} LUFS, "
              f"{analysis['input_tp']} dBTP; Windows copies identical.",flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript",type=Path,required=True)
    parser.add_argument("--transcribe",action="store_true")
    args = parser.parse_args()
    if args.transcribe:
        transcript(args.transcript)
    render(args.transcript)
