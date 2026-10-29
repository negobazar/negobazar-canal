"""
Publicador del canal de WhatsApp de Negobazar.

Lee la agenda del dia (agenda.json, que genera el repo privado) y publica cada item en su horario:
placas de productos, mensajes de texto, encuestas y estados. Usa Whapi.Cloud.

Uso:  python publicador.py --desde 07:00 --hasta 10:59
Variables: WHAPI_TOKEN (obligatoria), WHAPI_CANAL (opcional, xxxx@newsletter).
"""
import argparse
import base64
import datetime
import json
import os
import sys
import time
import zoneinfo

import requests

TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
API = "https://gate.whapi.cloud"
TOKEN = os.environ.get("WHAPI_TOKEN", "").strip()
CANAL = os.environ.get("WHAPI_CANAL", "").strip()
NOMBRE_CANAL = "negobazar"
TOLERANCIA_MIN = 20  # si un item se atraso mas que esto, se saltea


def h():
    return {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json", "Accept": "application/json"}


def ahora():
    return datetime.datetime.now(TZ)


def hora_hoy(hhmm):
    hh, mm = map(int, hhmm.split(":"))
    return ahora().replace(hour=hh, minute=mm, second=0, microsecond=0)


def buscar_canal():
    r = requests.get(API + "/newsletters", headers=h(), timeout=30)
    r.raise_for_status()
    canales = r.json().get("newsletters", [])
    for c in canales:
        if NOMBRE_CANAL in str(c.get("name", "")).lower():
            return c["id"]
    sys.exit("No encontré un canal con 'negobazar' en el nombre. Cargá el secreto WHAPI_CANAL.")


def imagen_b64(ruta):
    with open(ruta, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def enviar(item, canal):
    tipo = item["tipo"]
    if tipo == "imagen":
        url, body = "/messages/image", {"to": canal, "media": imagen_b64(item["archivo"]), "caption": item.get("texto", "")}
    elif tipo == "texto":
        url, body = "/messages/text", {"to": canal, "body": item["texto"]}
    elif tipo == "encuesta":
        url, body = "/messages/poll", {"to": canal, "title": item["texto"], "options": item["opciones"], "count": 1}
    elif tipo == "historia":
        url, body = "/stories/send/media", {"media": imagen_b64(item["archivo"]), "mime_type": "image/jpeg",
                                             "caption": item.get("texto", ""), "width": 1080, "height": 1920}
    else:
        return False, "tipo desconocido " + tipo
    ultimo = ""
    for intento in range(3):
        try:
            r = requests.post(API + url, headers=h(), json=body, timeout=90)
            if r.status_code in (200, 201):
                return True, ""
            ultimo = f"{r.status_code} {r.text[:250]}"
            if r.status_code in (401, 402, 403):
                return False, ultimo
        except Exception as e:  # noqa: BLE001
            ultimo = "red: " + str(e)
        time.sleep(20 * (intento + 1))
    return False, ultimo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agenda", default="dia/agenda.json")
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    args = ap.parse_args()
    if not TOKEN:
        sys.exit("Falta el secreto WHAPI_TOKEN.")

    with open(args.agenda, encoding="utf-8") as f:
        agenda = json.load(f)
    base = os.path.dirname(args.agenda)
    hoy = ahora().strftime("%Y-%m-%d")
    if agenda.get("fecha") != hoy:
        print(f"La agenda es del {agenda.get('fecha')} y hoy es {hoy}: no publico nada.")
        return

    desde, hasta = hora_hoy(args.desde), hora_hoy(args.hasta)
    items = [i for i in agenda["items"] if desde <= hora_hoy(i["hora"]) <= hasta]
    items.sort(key=lambda i: i["hora"])
    if not items or ahora() > hasta + datetime.timedelta(minutes=TOLERANCIA_MIN):
        print("Nada para publicar en esta franja.")
        return

    canal = CANAL or buscar_canal()
    print("Canal:", canal, "· items en franja:", len(items))
    fallas = 0
    for item in items:
        momento = hora_hoy(item["hora"])
        if ahora() > momento + datetime.timedelta(minutes=TOLERANCIA_MIN):
            print(f"{item['hora']} {item['tipo']}: salteado (atrasado)")
            continue
        espera = (momento - ahora()).total_seconds()
        if espera > 0:
            time.sleep(espera)
        if "archivo" in item:
            item["archivo"] = os.path.join(base, item["archivo"])
        ok, info = enviar(item, canal)
        print(f"{ahora():%H:%M} {item['hora']} {item['tipo']:<9} {item.get('ref', '')}: {'OK' if ok else 'ERROR ' + info}")
        fallas = 0 if ok else fallas + 1
        if fallas >= 3 or info.startswith(("401", "402", "403")):
            sys.exit("Corto por errores repetidos (revisar la conexión del número en Whapi).")


if __name__ == "__main__":
    main()
