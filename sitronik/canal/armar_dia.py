"""
Arma la agenda del día del canal de WhatsApp de Sitronik.

Lee la tienda (tiendasitronik.com.ar): los más vendidos y lo nuevo, elige los productos del día
intercalando unos y otros, genera las placas y escribe agenda.json para publicador.py.

Uso: python sitronik/canal/armar_dia.py --salida sitronik_dia
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import zoneinfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from placa import placa  # noqa: E402

TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
AQUI = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Sitronik canal)"}


def precio_num(txt):
    """'$18.653,33' -> 18653.33"""
    if not txt:
        return None
    t = re.sub(r"[^\d,]", "", str(txt)).replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def pesos(n):
    return "$" + f"{round(n):,}".replace(",", ".")


def leer_listado(url, paginas):
    productos = []
    for p in range(1, paginas + 1):
        u = url + ("&" if "?" in url else "?") + f"page={p}"
        try:
            r = requests.get(u, headers=UA, timeout=40)
        except requests.RequestException as e:
            print("No pude leer", u, e)
            break
        if r.status_code != 200:
            break
        sopa = BeautifulSoup(r.text, "html.parser")
        items = sopa.select(".js-item-product")
        if not items:
            break
        for it in items:
            try:
                var = json.loads(html.unescape(it.get("data-variants", "[]")))[0]
            except (ValueError, IndexError):
                continue
            nom = it.select_one(".js-item-name")
            link = it.select_one('a[href*="/productos/"]')
            if not nom or not link or not var.get("available") or not var.get("image_url"):
                continue
            if var.get("stock") is not None and var["stock"] <= 0:
                continue
            lista = var.get("price_number") or precio_num(var.get("price_short"))
            transf = precio_num(var.get("price_with_payment_discount_short"))
            if not lista or not transf:
                continue
            cuotas, valor_cuota = 9, lista / 9
            try:
                plan = json.loads(var.get("installments_data") or "{}")
                for medio in plan.values():
                    for n, dato in medio.items():
                        if dato.get("without_interests") and int(n) >= cuotas:
                            cuotas, valor_cuota = int(n), float(dato["installment_value"])
            except (ValueError, AttributeError):
                pass
            productos.append({
                "id": var.get("product_id"),
                "nombre": " ".join(nom.get_text(" ").split()),
                "url": link["href"].split("?")[0],
                "imagen": "https:" + var["image_url"] if var["image_url"].startswith("//") else var["image_url"],
                "lista": lista, "transf": transf, "cuotas": cuotas, "cuota": valor_cuota,
            })
    return productos


def elegir(vendidos, nuevos, orden, dia):
    """Intercala según 'orden' y rota cada día para no repetir siempre los mismos."""
    usados, elegidos = set(), []
    pos = {"vendido": dia * 3, "nuevo": dia * 2}
    pools = {"vendido": vendidos, "nuevo": nuevos}
    for tipo in orden:
        pool = pools[tipo] or pools["vendido" if tipo == "nuevo" else "nuevo"]
        for _ in range(len(pool)):
            p = pool[pos[tipo] % len(pool)]
            pos[tipo] += 1
            if p["id"] not in usados:
                usados.add(p["id"])
                elegidos.append((tipo, p))
                break
    return elegidos


def texto(p, desc):
    return (f"✨ *{p['nombre']}*\n\n"
            f"💸 *{pesos(p['transf'])}* con transferencia ({desc})\n"
            f"💳 o {p['cuotas']} cuotas sin interés de {pesos(p['cuota'])}\n"
            f"🚚 Envío sin cargo superando los $100.000\n\n"
            f"🛒 Compralo acá 👉 {p['url']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="sitronik_dia")
    args = ap.parse_args()
    cfg = json.load(open(os.path.join(AQUI, "config.json"), encoding="utf-8"))
    os.makedirs(args.salida, exist_ok=True)

    vendidos = leer_listado(cfg["url_mas_vendidos"], cfg["paginas"])
    nuevos = leer_listado(cfg["url_nuevos"], cfg["paginas"])
    print(f"Leí {len(vendidos)} más vendidos y {len(nuevos)} nuevos")
    if not vendidos and not nuevos:
        sys.exit("No pude leer productos de la tienda.")

    hoy = datetime.datetime.now(TZ).date()
    orden = cfg["orden"][:len(cfg["horarios"])]
    elegidos = elegir(vendidos, nuevos, orden, hoy.toordinal())
    etiquetas = cfg["etiquetas"]

    items = []
    for n, ((tipo, p), hora) in enumerate(zip(elegidos, cfg["horarios"]), 1):
        foto = os.path.join(args.salida, f"foto_{n}.jpg")
        r = requests.get(p["imagen"], headers=UA, timeout=60)
        r.raise_for_status()
        with open(foto, "wb") as f:
            f.write(r.content)
        desc = f"{round((1 - p['transf'] / p['lista']) * 100)}% OFF"
        archivo = f"placa_{n}.jpg"
        placa(foto, p["nombre"], pesos(p["lista"]), pesos(p["transf"]), pesos(p["cuota"]),
              os.path.join(args.salida, archivo), etiqueta=etiquetas[tipo], descuento=desc, cuotas=p["cuotas"])
        items.append({"hora": hora, "tipo": "imagen", "archivo": archivo, "texto": texto(p, desc),
                      "ref": f"{tipo}-{p['id']}"})
        print(hora, tipo, p["nombre"], pesos(p["transf"]))

    with open(os.path.join(args.salida, "agenda.json"), "w", encoding="utf-8") as f:
        json.dump({"fecha": hoy.isoformat(), "items": items}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
