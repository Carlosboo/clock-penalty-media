"""Create Instagram beta-install carousel, story set and highlight cover."""

from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parent
SOURCE = Path("/mnt/c/Users/juan.crugeiras/Downloads/Clock-Penalty-Anuncios/contenido aplicacion")
OUT = ROOT / "beta-install"
DESTINATION = Path("/mnt/c/Users/juan.crugeiras/Downloads/Clock-Penalty-Anuncios/instagram-beta-install")
URL = "clockpenalty.com"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
BG = "#061D2C"
CARD = "#0C2A3A"
MINT = "#73F8C9"
GOLD = "#FFE399"
WHITE = "#F2F6F3"
MUTED = "#AFC5C9"
RED = "#FF8E9F"


def font(size, bold=True, mono=False):
    return ImageFont.truetype(FONT_MONO if mono else (FONT_BOLD if bold else FONT_REG), size)


def wrap(draw, value, face, width):
    lines, current = [], ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(draw, value, x, y, width, face, color=WHITE, spacing=12):
    for line in wrap(draw, value, face, width):
        draw.text((x, y), line, font=face, fill=color)
        y += face.size + spacing
    return y


def canvas(size, section, index=None):
    image = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(image)
    w, h = size
    for radius in range(450, max(w, h), 190):
        draw.ellipse((w // 2 - radius, int(h * .57) - radius,
                      w // 2 + radius, int(h * .57) + radius),
                     outline="#10353E", width=2)
    draw.text((w // 2, 74 if h > 1500 else 55), "CLOCK PENALTY",
              font=font(26 if h > 1500 else 23), fill=GOLD, anchor="mm")
    if index:
        draw.text((w // 2, h - (72 if h > 1500 else 54)),
                  f"{index}  ·  {section}", font=font(21 if h > 1500 else 18),
                  fill=MINT, anchor="mm")
    return image


def header(draw, title, subtitle, y, story=False):
    draw.text((540, y), title, font=font(55 if story else 49),
              fill=WHITE, anchor="mm")
    draw.text((540, y + (76 if story else 67)), subtitle,
              font=font(31 if story else 26), fill=MINT, anchor="mm")


def fit_screenshot(path, max_size):
    with Image.open(path) as source:
        image = source.convert("RGB")
    # Update the displayed address without altering the supplied source captures.
    draw = ImageDraw.Draw(image)
    if path.name == "anadir a pantalla de inicio parte 1.jpeg":
        draw.rectangle((250, 1460, 505, 1520), fill="#002600")
        draw.text((377, 1490), URL, font=font(25, bold=False),
                  fill=WHITE, anchor="mm")
    elif path.name == "anadir a pantalla de inicio parte 2.jpeg":
        draw.rectangle((195, 201, 563, 240), fill="#1D5838")
        draw.text((200, 220), URL, font=font(27, bold=False),
                  fill="#A6D9AF", anchor="lm")
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image


def put_phone(image, screenshot, box, border=True):
    x, y, w, h = box
    screen = fit_screenshot(screenshot, (w - 30, h - 30))
    frame = Image.new("RGB", (screen.width + 24, screen.height + 24), "#020C13")
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1),
                                 radius=32, fill="#020C13",
                                 outline="#53727B" if border else "#020C13", width=3)
    frame.paste(screen, (12, 12))
    image.paste(frame, (x + (w - frame.width) // 2, y + (h - frame.height) // 2))


def qr_like(draw, center, radius, color):
    cx, cy = center
    draw.rounded_rectangle((cx-radius, cy-radius, cx+radius, cy+radius),
                           radius=radius//4, outline=color, width=6)
    for dx, dy in ((-1,-1),(1,-1),(-1,1)):
        x, y = cx + dx * radius * .52, cy + dy * radius * .52
        draw.rectangle((x-15, y-15, x+15, y+15), outline=color, width=5)


def android_menu(draw, x, y, scale=1):
    width, height = int(430 * scale), int(745 * scale)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=int(34 * scale),
                           fill="#111D27", outline="#566974", width=max(2, int(3 * scale)))
    # Browser toolbar: the menu icon and URL help people recognize where to start.
    draw.rounded_rectangle((x+22*scale, y+22*scale, x+width-22*scale, y+99*scale),
                           radius=int(28*scale), fill="#24333D")
    draw.text((x+54*scale, y+61*scale), "‹", font=font(int(46*scale)), fill=WHITE, anchor="mm")
    draw.text((x+width*.5, y+61*scale), URL, font=font(int(17*scale), mono=True),
              fill=WHITE, anchor="mm")
    draw.text((x+width-50*scale, y+61*scale), "⋮", font=font(int(38*scale)),
              fill=WHITE, anchor="mm")
    draw.rectangle((x+width-75*scale, y+30*scale, x+width-20*scale, y+90*scale),
                   outline=MINT, width=max(2, int(4*scale)))
    draw.text((x+42*scale, y+137*scale), "Menú de Chrome", font=font(int(23*scale)),
              fill=MUTED)
    items = [
        ("Nueva pestaña", MUTED),
        ("Historial", MUTED),
        ("Descargas", MUTED),
        ("Instalar aplicación", MINT),
        ("Añadir a pantalla de inicio", MINT),
        ("Compartir…", MUTED),
        ("Buscar en la página", MUTED),
    ]
    row_y = y + 198 * scale
    for label, color in items:
        if color == MINT:
            draw.rounded_rectangle((x+16*scale, row_y-10*scale,
                                    x+width-16*scale, row_y+63*scale),
                                   radius=int(16*scale), outline=GOLD, width=max(2, int(4*scale)))
        draw.text((x+37*scale, row_y+22*scale), label,
                  font=font(int(22*scale), bold=color == MINT), fill=color, anchor="lm")
        row_y += 76 * scale
    draw.line((x+width*.65, y+139*scale, x+width-48*scale, y+139*scale),
              fill=GOLD, width=max(3, int(5*scale)))


def android_home(draw, x, y):
    draw.rounded_rectangle((x, y, x+390, y+430), radius=36,
                           fill="#0D2738", outline="#48636E", width=4)
    draw.text((x+195, y+48), "Pantalla de inicio", font=font(25), fill=WHITE, anchor="mm")
    draw.ellipse((x+128, y+91, x+262, y+225), fill="#0A4F4C", outline=GOLD, width=5)
    draw.ellipse((x+142, y+105, x+248, y+211), fill="#0B2539", outline=MINT, width=3)
    draw.text((x+195, y+158), ".00", font=font(31, mono=True), fill=MINT, anchor="mm")
    draw.text((x+195, y+259), "Penalty", font=font(27), fill=WHITE, anchor="mm")
    draw.rounded_rectangle((x+56, y+321, x+334, y+385), radius=20, fill="#183749")
    draw.text((x+195, y+353), "Toca el icono para abrir", font=font(17, bold=False),
              fill=MUTED, anchor="mm")


def slide_cover(size, story=False):
    image = canvas(size, "GUÍA BETA", "1 / 6" if not story else "GUÍA")
    draw = ImageDraw.Draw(image)
    h = size[1]
    title_y = 270 if story else 190
    header(draw, "Cómo instalar", "la beta en tu móvil", title_y, story)
    avatar_path = ROOT / "clock-penalty-social-avatar.png"
    with Image.open(avatar_path) as avatar:
        avatar = avatar.convert("RGB").resize((600, 600), Image.Resampling.LANCZOS)
    image.paste(avatar, ((1080-600)//2, 540 if story else 470))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((100, 1250 if story else 1040, 980, 1455 if story else 1235),
                           radius=38, fill=CARD, outline="#315564", width=3)
    lines = [
        ("No se descarga de Play Store ni App Store.", GOLD),
        ("Es la web de prueba añadida a tu pantalla de inicio.", WHITE),
    ]
    yy = 1300 if story else 1065
    for text, color in lines:
        yy = paragraph(draw, text, 145, yy, 790, font(30 if story else 25),
                       color=color, spacing=8) + (18 if story else 10)
    if story:
        draw.text((540, 1650), "iPhone y Android · 2 guías", font=font(29),
                  fill=MINT, anchor="mm")
    return image


def feed_pages():
    w, h = 1080, 1350
    pages = []
    pages.append(slide_cover((w, h)))

    # iOS 2 pages, using the supplied real Safari screenshots.
    for index, title, subtitle, file, copy, foot in (
        (2, "En iPhone · paso 1", "Abre la beta en Safari", "anadir a pantalla de inicio parte 1.jpeg",
         "Abre clockpenalty.com en Safari. Toca el botón Compartir.",
         "Usa Safari; otros navegadores pueden mostrar opciones distintas."),
        (3, "En iPhone · paso 2", "Añade el icono a Inicio", "anadir a pantalla de inicio parte 2.jpeg",
         "En el menú, toca «Añadir a pantalla de inicio» y confirma.",
         "Luego abre Penalty desde el icono que aparece en Inicio."),
    ):
        page = canvas((w,h), "IPHONE", f"{index} / 6")
        d = ImageDraw.Draw(page)
        header(d, title, subtitle, 155)
        shot = SOURCE / file
        put_phone(page, shot, (42, 325, 430, 900))
        d = ImageDraw.Draw(page)
        paragraph(d, copy, 520, 565, 495, font(36), color=WHITE, spacing=16)
        d.rounded_rectangle((500, 855, 1020, 1055), radius=30,
                            fill=CARD, outline="#355565", width=3)
        paragraph(d, foot, 535, 900, 450, font(25, bold=False), color=GOLD, spacing=12)
        pages.append(page)

    # Android: accurate help text from the app. The UI is schematic and says labels vary.
    page = canvas((w,h), "ANDROID", "4 / 6")
    d = ImageDraw.Draw(page)
    header(d, "En Android · paso 1", "Abre la beta en Chrome", 155)
    android_menu(d, 98, 365, .93)
    d.rounded_rectangle((571, 400, 1018, 1060), radius=34,
                        fill=CARD, outline="#355565", width=3)
    paragraph(d, "1. Abre clockpenalty.com en Chrome.", 605, 452, 380,
              font(29), spacing=12)
    paragraph(d, "2. Toca ⋮ arriba a la derecha.", 605, 630, 380,
              font(29), color=MINT, spacing=12)
    paragraph(d, "3. Elige «Instalar aplicación» o «Añadir a pantalla de inicio».",
              605, 763, 380, font(29), color=GOLD, spacing=12)
    d.text((540, 1125), "El nombre de la opción puede variar según el móvil.",
           font=font(23, bold=False), fill=MUTED, anchor="mm")
    pages.append(page)

    page = canvas((w,h), "ANDROID", "5 / 6")
    d = ImageDraw.Draw(page)
    header(d, "En Android · paso 2", "Confirma y abre Penalty", 155)
    android_home(d, 345, 380)
    d.rounded_rectangle((115, 855, 965, 1130), radius=36,
                        fill=CARD, outline="#355565", width=3)
    paragraph(d, "Confirma «Instalar» o «Añadir». Después toca el icono Penalty en Inicio.",
              165, 890, 750, font(28), color=WHITE, spacing=12)
    paragraph(d, "Si no ves «Instalar aplicación», prueba «Añadir a pantalla de inicio».",
              165, 1015, 750, font(22, bold=False), color=GOLD, spacing=8)
    pages.append(page)

    page = canvas((w,h), "ANTES DE JUGAR", "6 / 6")
    d = ImageDraw.Draw(page)
    header(d, "Y ya está.", "La beta se abre desde el icono.", 190)
    d.rounded_rectangle((90, 440, 990, 930), radius=40,
                        fill=CARD, outline="#355565", width=3)
    yy = 500
    for line, color in [
        ("Es una web app de prueba, no una descarga de tienda.", WHITE),
        ("Entra y practica contra el bot.", MINT),
        ("La beta puede cambiar mientras la seguimos probando.", GOLD),
    ]:
        yy = paragraph(d, line, 145, yy, 790, font(32), color=color, spacing=14) + 40
    d.rounded_rectangle((110, 1010, 970, 1165), radius=33, fill=GOLD)
    d.text((540, 1085), URL, font=font(36, mono=True), fill=BG, anchor="mm")
    pages.append(page)
    return pages


def story_pages():
    w, h = 1080, 1920
    pages = [slide_cover((w,h), story=True)]
    for title, subtitle, file, copy in (
        ("En iPhone · 1/2", "Abre la web en Safari y toca Compartir.",
         "anadir a pantalla de inicio parte 1.jpeg",
         "Safari → Compartir"),
        ("En iPhone · 2/2", "En el menú, elige «Añadir a pantalla de inicio».",
         "anadir a pantalla de inicio parte 2.jpeg",
         "Añadir a pantalla de inicio → Añadir"),
    ):
        page = canvas((w,h), "IPHONE", f"{title.rsplit(' ', 1)[-1]}")
        d = ImageDraw.Draw(page)
        header(d, title, subtitle, 230, True)
        put_phone(page, SOURCE / file, (95, 440, 520, 1110))
        d = ImageDraw.Draw(page)
        d.rounded_rectangle((620, 720, 1010, 1030), radius=32,
                            fill=CARD, outline=MINT, width=3)
        paragraph(d, copy, 660, 790, 310, font(34), color=GOLD, spacing=15)
        d.text((540, 1640), URL, font=font(32, mono=True), fill=MINT, anchor="mm")
        pages.append(page)

    page = canvas((w,h), "ANDROID", "1 / 2")
    d = ImageDraw.Draw(page)
    header(d, "En Android · 1/2", "Abre la web en Chrome y toca ⋮", 230, True)
    android_menu(d, 65, 455, 1.17)
    d.rounded_rectangle((602, 620, 1020, 1085), radius=34,
                        fill=CARD, outline=GOLD, width=3)
    paragraph(d, "Busca «Instalar aplicación» o «Añadir a pantalla de inicio».",
              646, 700, 330, font(36), color=MINT, spacing=18)
    d.text((540, 1585), "El texto puede variar según el dispositivo.",
           font=font(27, bold=False), fill=MUTED, anchor="mm")
    d.text((540, 1660), URL, font=font(32, mono=True), fill=MINT, anchor="mm")
    pages.append(page)

    page = canvas((w,h), "ANDROID", "2 / 2")
    d = ImageDraw.Draw(page)
    header(d, "En Android · 2/2", "Confirma y abre desde el icono.", 230, True)
    android_home(d, 345, 500)
    d.rounded_rectangle((115, 1050, 965, 1310), radius=36,
                        fill=CARD, outline="#355565", width=3)
    paragraph(d, "No es una descarga de Play Store: es la beta web añadida a Inicio.",
              165, 1110, 750, font(34), color=WHITE, spacing=18)
    d.text((540, 1515), URL, font=font(32, mono=True), fill=MINT, anchor="mm")
    pages.append(page)
    return pages


def highlight_cover():
    image = Image.new("RGB", (1080, 1080), BG)
    draw = ImageDraw.Draw(image)
    draw.ellipse((100, 100, 980, 980), fill=CARD, outline=GOLD, width=13)
    draw.ellipse((216, 216, 864, 864), fill="#09253A", outline=MINT, width=10)
    draw.rounded_rectangle((295, 390, 785, 610), radius=40,
                           fill="#03131F", outline="#3F6473", width=8)
    draw.text((540, 500), "BETA", font=font(92, mono=True), fill=MINT, anchor="mm")
    draw.ellipse((540-70, 670-70, 540+70, 670+70),
                 fill="#FFF5DA", outline=GOLD, width=5)
    draw.ellipse((508, 638, 572, 702), fill="#132B3C")
    return image


def save_assets():
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    for filename in ("anadir a pantalla de inicio parte 1.jpeg",
                     "anadir a pantalla de inicio parte 2.jpeg"):
        if not (SOURCE / filename).is_file():
            raise FileNotFoundError(SOURCE / filename)
    OUT.mkdir(parents=True, exist_ok=True)
    feed_dir, story_dir = OUT / "pinned-carousel", OUT / "stories"
    feed_dir.mkdir(exist_ok=True)
    story_dir.mkdir(exist_ok=True)
    for directory in (feed_dir, story_dir):
        for old in directory.glob("*.jpg"):
            old.unlink()
    for index, page in enumerate(feed_pages(), 1):
        page.save(feed_dir / f"{index:02d}-instalacion-beta.jpg", quality=93, optimize=True)
    stories = story_pages()
    for index, page in enumerate(stories, 1):
        page.save(story_dir / f"{index:02d}-instalacion-beta.jpg", quality=93, optimize=True)
    highlight_cover().save(OUT / "highlight-cover-instalacion-beta.jpg", quality=94)
    (OUT / "caption.txt").write_text(
        "Estoy dejando aquí cómo instalar la beta en iPhone y Android. "
        "No hace falta bajarla de una tienda: es la web de prueba añadida a la "
        "pantalla de inicio. En iPhone, Safari → Compartir → Añadir a pantalla "
        "de inicio. En Android, Chrome → ⋮ → Instalar aplicación o Añadir a "
        "pantalla de inicio. Los nombres pueden variar un poco según el móvil. "
        "Después abre Penalty desde el icono y prueba la demo contra el bot. "
        "Si algo no te funciona, escríbeme qué móvil y navegador usas.\n",
        encoding="utf-8",
    )
    (OUT / "README.txt").write_text(
        "6 JPG para carrusel; 5 JPG para historias y destacado; portada del destacado.\n"
        "Este generador no publica. Consulta published.json para el registro "
        "de publicaciones y tareas pendientes, si existe.\n"
        "La guía Android es una ilustración explicativa, no una captura "
        "literal de Chrome. El texto indica que las etiquetas pueden variar.\n"
        "Para añadir el destacado: publica las historias, abre el perfil, crea "
        "un destacado llamado «Instalación Beta» y selecciónalas.\n",
        encoding="utf-8",
    )
    for path in OUT.rglob("*.jpg"):
        with Image.open(path) as image:
            image.verify()
    if DESTINATION.parent.is_dir():
        DESTINATION.mkdir(exist_ok=True)
        for path in OUT.rglob("*"):
            if path.is_file():
                target = DESTINATION / path.relative_to(OUT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                if target.read_bytes() != path.read_bytes():
                    raise RuntimeError(f"Windows copy differs: {target}")
    print(f"Created installation guide assets in {OUT}")
    print(f"Copied assets to {DESTINATION}")


if __name__ == "__main__":
    save_assets()
