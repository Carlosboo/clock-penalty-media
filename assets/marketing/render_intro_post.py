"""Generate the first social photo carousel and copy-ready profile metadata."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "social-intro"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MINT, GOLD, WHITE = "#73F8C9", "#FFE399", "#F2F6F3"
BIO = "Estoy haciendo un juego de fútbol en el que paras un reloj.\nPuedes probarlo aquí: clockpenalty.com"
URL = "https://clockpenalty.com/"
CAPTION = (
    "Estoy haciendo un juego de fútbol en el que no chutas. Paras un reloj.\n\n"
    "Si lo paras en .00, marcas. Si cae en .99, tienes un penalti: "
    "vuelves a pararlo y las centésimas deciden. Par, gol. Impar, fallo.\n\n"
    "La idea es acabar jugando partidos y ligas con los colegas. "
    "De momento he dejado una demo para probar contra un bot.\n\n"
    "Voy a ir subiendo por aquí cómo va quedando. "
    "Si lo pruebas, dime qué cambiarías, que para eso lo estoy enseñando.\n\n"
    "Está en clockpenalty.com. También lo he puesto en la bio."
)


def text(draw, value, y, size, color=WHITE):
    font = ImageFont.truetype(FONT, size)
    bounds = draw.textbbox((0, 0), value, font=font)
    if bounds[2] - bounds[0] > 950:
        raise ValueError(f"Text overflows the safe area: {value}")
    draw.text((540, y), value, font=font, fill=color, anchor="mm")


def canvas(index, label):
    image = Image.new("RGB", (1080, 1350), "#061D2C")
    draw = ImageDraw.Draw(image)
    for radius in (470, 640, 810):
        draw.ellipse((540 - radius, 710 - radius, 540 + radius, 710 + radius),
                     outline="#123C43", width=3)
    text(draw, "CLOCK PENALTY", 100, 28, GOLD)
    text(draw, f"{index}/4  ·  {label}", 1240, 22, MINT)
    return image, draw


def render():
    OUT.mkdir(exist_ok=True)
    image, draw = canvas(1, "DESLIZA")
    text(draw, "Estoy haciendo", 260, 66)
    text(draw, "un juego de fútbol.", 350, 66, MINT)
    with Image.open(ROOT / "clock-penalty-social-avatar.png") as avatar:
        avatar = avatar.resize((580, 580), Image.Resampling.LANCZOS)
        mask = Image.new("L", avatar.size)
        ImageDraw.Draw(mask).ellipse((0, 0, 580, 580), fill=255)
        image.paste(avatar, (250, 470), mask)
    text(draw, "Pero aquí no se chuta.", 1110, 39)
    image.save(OUT / "01-portada.png")

    image, draw = canvas(2, "LA REGLA")
    text(draw, "Va de parar un reloj.", 305, 64)
    text(draw, "Si lo clavas en...", 410, 58)
    draw.rounded_rectangle((110, 535, 970, 820), radius=45,
                           fill="#03131F", outline=MINT, width=5)
    text(draw, ".00", 670, 190, MINT)
    text(draw, "...es gol.", 945, 88, GOLD)
    text(draw, "Esa es la idea.", 1090, 39)
    image.save(OUT / "02-gol.png")

    image, draw = canvas(3, "EL PENALTI")
    text(draw, "¿Y si paras en .99?", 280, 64)
    text(draw, "Tienes un penalti.", 385, 65, GOLD)
    text(draw, "Vuelves a parar el reloj.", 560, 43)
    draw.rounded_rectangle((110, 675, 970, 960), radius=40,
                           fill="#03131F", outline="#355565", width=3)
    text(draw, "CENTÉSIMAS PARES → GOL", 765, 43, MINT)
    text(draw, "IMPARES → FALLO", 870, 43, "#FF8E9F")
    text(draw, "Se miran las centésimas, no los segundos.", 1080, 33)
    image.save(OUT / "03-penalti.png")

    image, draw = canvas(4, "PRIMERA DEMO")
    text(draw, "Ya puedes probarlo.", 340, 65)
    text(draw, "He dejado una demo", 560, 60, MINT)
    text(draw, "para jugar contra un bot.", 690, 43)
    text(draw, "Si la pruebas, dime qué cambiarías.", 785, 36)
    text(draw, "Iré enseñando por aquí cómo va.", 850, 36)
    draw.rounded_rectangle((190, 965, 890, 1090), radius=30, fill=GOLD)
    text(draw, "Te dejo la web en la bio", 1025, 37, "#061D2C")
    image.save(OUT / "04-demo.png")

    metadata = {
        "status": "draft_not_published",
        "account": "clock.penalty",
        "display_name": "Clock Penalty",
        "bio": BIO,
        "website": URL,
        "caption": CAPTION,
        "media": [path.name for path in sorted(OUT.glob("0[1-4]-*.png"))],
        "platforms": ["instagram_carousel"],
        "note": "Set the profile link if the platform/account permits it; do not claim it is live before verifying.",
    }
    (OUT / "publication.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "caption.txt").write_text(CAPTION + "\n", encoding="utf-8")
    (OUT / "profile.txt").write_text(
        f"Nombre: Clock Penalty\nUsuario: @clock.penalty\n\n{BIO}\n\n{URL}\n",
        encoding="utf-8",
    )
    print(f"Generated 4 slides and publication metadata: {OUT}")


if __name__ == "__main__":
    render()
