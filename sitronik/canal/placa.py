"""Placa de producto para el canal de WhatsApp de Sitronik (diseño basado en sitronik.com.ar)."""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

AQUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")
W, H = 1080, 1350
RED = (240, 29, 8)
NAVY = (47, 54, 69)
BEIGE = (252, 240, 210)
GREY = (125, 130, 140)
BG = (246, 244, 240)
WHITE = (255, 255, 255)


def F(peso, tam):
    return ImageFont.truetype(os.path.join(AQUI, f"Poppins-{peso}.ttf"), tam)


def centrar(d, y, t, f, fill, x0=0, x1=W):
    d.text((x0 + (x1 - x0 - d.textlength(t, font=f)) / 2, y), t, font=f, fill=fill)


def espaciado(d, xy, t, f, fill, sp):
    x, y = xy
    for ch in t:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + sp


def ancho_espaciado(d, t, f, sp):
    return sum(d.textlength(c, font=f) + sp for c in t) - sp


def cortar(d, t, f, maxw):
    lineas, cur = [], ""
    for w in t.split():
        s = (cur + " " + w).strip()
        if d.textlength(s, font=f) <= maxw:
            cur = s
        else:
            lineas.append(cur)
            cur = w
    lineas.append(cur)
    return lineas


def redondear(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], r, fill=255)
    o = Image.new("RGBA", img.size)
    o.paste(img, (0, 0), m)
    return o


def sombra(base, box, r, blur=22, alpha=45, dy=10):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + dy, box[2], box[3] + dy], r, fill=(20, 25, 40, alpha))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def placa(foto, nombre, lista, transf, cuota, salida, etiqueta="NUEVO INGRESO", descuento="25% OFF", cuotas=9):
    """foto: ruta de la imagen del producto. Precios como texto ya formateado ("$30.653")."""
    im = Image.new("RGBA", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    # Barras de beneficios, igual que la web
    d.rectangle([0, 0, W, 100], fill=RED)
    f = F("Bold", 36)
    centrar(d, 28, f"{cuotas} CUOTAS SIN INTERÉS", f, WHITE, 0, W // 2)
    centrar(d, 28, f"{descuento} TRANSFERENCIA", f, WHITE, W // 2, W)
    d.line([(W // 2, 22), (W // 2, 78)], fill=WHITE, width=3)
    d.rectangle([0, 100, W, 150], fill=NAVY)
    centrar(d, 107, "ENVÍO SIN CARGO SUPERANDO LOS $100.000", F("Medium", 28), WHITE)
    # Logo
    lg = Image.open(os.path.join(AQUI, "logo.png")).convert("RGB")
    lg = lg.resize((230, int(230 * lg.height / lg.width)), Image.LANCZOS)
    im.paste(lg, ((W - lg.width) // 2, 166))
    # Foto con sombra (el producto entero, sin recortar)
    box = (40, 250, W - 40, 958)
    sombra(im, box, 32)
    tam = (box[2] - box[0], box[3] - box[1])
    src = Image.open(foto).convert("RGB")
    fondo = ImageOps.fit(src, tam, Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    frente = src.copy()
    frente.thumbnail(tam, Image.LANCZOS)
    fondo.paste(frente, ((tam[0] - frente.width) // 2, (tam[1] - frente.height) // 2))
    im.alpha_composite(redondear(fondo, 32), (box[0], box[1]))
    d = ImageDraw.Draw(im)
    # Etiqueta
    fe = F("Bold", 24)
    tw = ancho_espaciado(d, etiqueta, fe, 2)
    d.rounded_rectangle([68, 276, 68 + tw + 48, 326], 25, fill=BEIGE)
    espaciado(d, (92, 284), etiqueta, fe, NAVY, 2)
    # Nombre (hasta 2 renglones)
    fn = F("Bold", 46)
    lineas = cortar(d, nombre, fn, W - 160)
    if len(lineas) > 1:
        fn = F("Bold", 40)
        lineas = cortar(d, nombre, fn, W - 160)
        if len(lineas) > 2:
            lineas = lineas[:2]
            while d.textlength(lineas[1] + "…", font=fn) > W - 160:
                lineas[1] = lineas[1].rsplit(" ", 1)[0]
            lineas[1] += "…"
    y = 984 if len(lineas) == 1 else 968
    for ln in lineas:
        centrar(d, y, ln, fn, NAVY)
        y += 56 if len(lineas) == 1 else 50
    # Precio de lista tachado
    y += 6 if len(lineas) == 1 else 10
    fl = F("Regular", 30)
    tl = f"Antes {lista}"
    centrar(d, y, tl, fl, GREY)
    tw = d.textlength(tl, font=fl)
    xs = (W - tw) / 2 + d.textlength("Antes ", font=fl)
    d.line([(xs, y + 22), ((W + tw) / 2, y + 22)], fill=GREY, width=2)
    y += 34
    # Precio por transferencia + badge
    fp, fb = F("Bold", 110), F("Bold", 30)
    bw = d.textlength(descuento, font=fb) + 40
    x = (W - (d.textlength(transf, font=fp) + 22 + bw)) / 2
    d.text((x, y - 10), transf, font=fp, fill=RED)
    bx = x + d.textlength(transf, font=fp) + 22
    d.rounded_rectangle([bx, y + 34, bx + bw, y + 88], 14, fill=RED)
    d.text((bx + 20, y + 40), descuento, font=fb, fill=WHITE)
    y += 120
    # Pastillas
    chips = ["con transferencia", f"{cuotas} cuotas sin interés de {cuota}"]
    fc = F("Medium", 26)
    anchos = [d.textlength(t, font=fc) + 48 for t in chips]
    cx = (W - sum(anchos) - 16) / 2
    for t, w in zip(chips, anchos):
        d.rounded_rectangle([cx, y, cx + w, y + 50], 25, fill=BG)
        d.text((cx + 24, y + 9), t, font=fc, fill=NAVY)
        cx += w + 16
    # Pie
    d.rectangle([0, H - 70, W, H], fill=NAVY)
    ff = F("Medium", 28)
    d.text((60, H - 55), "sitronik.com.ar", font=ff, fill=WHITE)
    t = "WhatsApp 11 2530-6577"
    d.text((W - 60 - d.textlength(t, font=ff), H - 55), t, font=ff, fill=BEIGE)
    im.convert("RGB").save(salida, quality=90)
