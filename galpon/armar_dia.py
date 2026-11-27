"""
Arma la agenda del dia del canal de WhatsApp NEGO3AZAR (el "galpon digital" de pedidos.negobazar.com.ar).

- Lee https://pedidos.negobazar.com.ar/difusiones.json (con flyer).
- Usa SOLO la imagen de `flyerUrl`. Si no tiene flyer o falla la descarga, el producto queda pendiente.
- No publica productos con disponible == false. stock null (sin confirmar) se publica.
- No repite productos publicados en los ultimos DIAS_SIN_REPETIR dias (registro en la rama galpon-registro).
- Primero los destacados, despues el resto rotando.

Uso: python galpon/armar_dia.py --salida galpon_dia
Escribe agenda.json (para publicador.py) y pendientes.txt.
"""
import argparse
import datetime
import json
import os
import random
import zoneinfo

import shutil

import requests

TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
FEED = "https://pedidos.negobazar.com.ar/difusiones.json"
UA = {"User-Agent": "Mozilla/5.0 (Negobazar galpon canal)"}
DIAS_SIN_REPETIR = 3

# Franjas: 07:00-08:30 / 11:00-14:30 / 17:00-20:30
# Un producto cada 30 minutos, corrido de 08:30 (despues del anuncio) a 20:00
def _cada(desde, hasta, paso=30):
    h, m = map(int, desde.split(":")); fin = tuple(map(int, hasta.split(":")))
    out = []
    while (h, m) <= fin:
        out.append(f"{h:02d}:{m:02d}")
        m += paso
        h, m = h + m // 60, m % 60
    return out


HORARIOS = _cada("08:30", "20:00")
COMUNIDAD = {
    "07:00": ("buendia", "☀️ ¡Buen día! Abrió el *galpón digital de Negobazar* 🏭\n\n"
                         "Hoy vamos a ir subiendo ofertas durante el día.\n"
                         "✅ Sin mínimo de compra\n🛒 Para tu emprendimiento o para renovar tu casa\n\n"
                         "👉 https://pedidos.negobazar.com.ar"),
    "20:30": ("cierre", "🌙 Eso fue todo por hoy en el galpón 🏭\n\n"
                        "¿Te quedaste con ganas? Todo el catálogo está acá 👇\n"
                        "https://pedidos.negobazar.com.ar\n\nMañana a las 7 volvemos con más 🔥"),
}


def pesos(n):
    return "$" + f"{round(n):,}".replace(",", ".")


def leer(params):
    r = requests.get(FEED, params=params, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json().get("productos", [])


def texto(p):
    pl, pv = p.get("precio_lista") or 0, p.get("precio_venta") or 0
    if pl and pv and pl > pv:
        precio = (f"🏷️ Precio de lista: ~{pesos(pl)}~\n"
                  f"🔥 *Precio promo: {pesos(pv)}* ({round((1 - pv / pl) * 100)}% OFF)\n")
    else:
        precio = f"🔥 *{pesos(pv or pl)}*\n"
    return (f"🏭 *{p['titulo']}*\n\n{precio}"
            f"✅ Sin mínimo de compra\n\n"
            f"🛒 Pedilo acá 👉 {p['url']}")


def novedades(hoy, salida):
    """Mensajes especiales del dia (galpon/novedades.json)."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    try:
        todo = json.load(open(os.path.join(aqui, "novedades.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = []
    for n, m in enumerate(todo.get(hoy.isoformat(), []), 1):
        it = {"hora": m["hora"], "tipo": m["tipo"], "texto": m["texto"], "ref": f"galpon-nov-{hoy.isoformat()}-{n}"}
        if m.get("archivo"):
            shutil.copy(os.path.join(aqui, "recursos", m["archivo"]), os.path.join(salida, m["archivo"]))
            it["archivo"] = m["archivo"]
        items.append(it)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="galpon_dia")
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    hoy = datetime.datetime.now(TZ).date()

    todos = leer({})
    con_flyer = leer({"con_flyer": 1})
    print(f"Catalogo: {len(todos)} productos, {len(con_flyer)} con flyer")

    pendientes = [p for p in todos if p.get("origen") == "showroom" and p.get("disponible") is not False
                  and not (p.get("flyerUrl") or "").strip()]
    candidatos = [p for p in con_flyer if p.get("disponible") is not False and p.get("url")]

    recientes = set()
    try:
        reg = json.load(open(os.environ.get("REGISTRO", ""), encoding="utf-8"))
        desde = (hoy - datetime.timedelta(days=DIAS_SIN_REPETIR)).isoformat()
        for fecha, refs in reg.items():
            if desde <= fecha < hoy.isoformat():
                recientes |= set(refs)
    except (OSError, ValueError):
        pass

    def ref(p):
        return "galpon-" + str(p["id"])

    # primero los que no salieron en los ultimos dias; si no alcanzan, se completa con los ya publicados
    frescos = [p for p in candidatos if ref(p) not in recientes]
    usados = [p for p in candidatos if ref(p) in recientes]
    random.Random(hoy.toordinal() + 7).shuffle(usados)
    nuevos = frescos
    resto = [p for p in nuevos if not p.get("destacado")]
    random.Random(hoy.toordinal()).shuffle(resto)      # mezcla distinta cada dia (no 3 baterias seguidas)
    vistos_cat, primero, despues = set(), [], []
    for p in resto:                                     # una por categoria antes de repetir categoria
        (despues if p.get("categoria") in vistos_cat else primero).append(p)
        vistos_cat.add(p.get("categoria"))
    resto = primero + despues
    orden = [p for p in nuevos if p.get("destacado")][:3] + resto + usados

    especiales = novedades(hoy, args.salida)
    ocupadas = {m["hora"] for m in especiales}
    horas = [h for h in HORARIOS if h not in ocupadas]
    items, fallas = [], []
    for p in orden:
        if len(items) >= len(horas):
            break
        archivo = f"flyer_{len(items) + 1}.jpg"
        try:
            r = requests.get(p["flyerUrl"], headers=UA, timeout=60)
            r.raise_for_status()
            if not r.headers.get("content-type", "").startswith("image") or len(r.content) < 3000:
                raise ValueError("no es una imagen")
            with open(os.path.join(args.salida, archivo), "wb") as f:
                f.write(r.content)
        except Exception as e:  # noqa: BLE001
            fallas.append(p)
            print("Flyer con problemas:", p["titulo"], e)
            continue
        hora = horas[len(items)]
        items.append({"hora": hora, "tipo": "imagen", "archivo": archivo, "texto": texto(p), "ref": ref(p)})
        print(hora, p["titulo"], pesos(p.get("precio_venta") or 0))

    for hora, (nombre, msg) in COMUNIDAD.items():
        if hora not in ocupadas:
            items.append({"hora": hora, "tipo": "texto", "texto": msg, "ref": f"galpon-{nombre}"})
    items += especiales

    with open(os.path.join(args.salida, "agenda.json"), "w", encoding="utf-8") as f:
        json.dump({"fecha": hoy.isoformat(), "items": items}, f, ensure_ascii=False, indent=1)

    pend = pendientes + fallas
    lineas = [f"- {p['titulo']}" for p in pend[:20]]
    resumen = ""
    if pend:
        resumen = (f"🏭 Canal NEGO3AZAR: hay *{len(pend)} productos sin flyer* (o con el flyer roto), "
                   f"así que no se publican hasta que tengan uno:\n" + "\n".join(lineas)
                   + (f"\n…y {len(pend) - 20} más" if len(pend) > 20 else ""))
    with open(os.path.join(args.salida, "pendientes.txt"), "w", encoding="utf-8") as f:
        f.write(resumen)
    print(f"Agenda: {len(items)} mensajes. Pendientes sin flyer: {len(pend)}")


if __name__ == "__main__":
    main()
