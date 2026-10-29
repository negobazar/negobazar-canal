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
TOLERANCIA_MIN = 5  # si un item se atraso mas que esto, se saltea (evita rafagas de publicaciones)


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
                                             "caption": item.get("texto", "")}
        if os.path.basename(item["archivo"]).startswith(("h_", "inv_")):
            body.update({"width": 1080, "height": 1920})
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
    ap.add_argument("--cada", type=float, default=0,
                    help="si se indica, ignora los horarios y publica todo lo de la franja ahora, cada N minutos")
    ap.add_argument("--saltear", type=int, default=0, help="(modo seguido) saltear los primeros N items ya publicados")
    ap.add_argument("--terminar", default="", help="(modo seguido) HH:MM: a esa hora publica el cierre y termina")
    ap.add_argument("--historias-cada", type=int, default=0,
                    help="(modo seguido) cada K publicaciones del canal, sube tambien un estado")
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
    # Los mensajes de apertura (07:00 y 19:00) salen siempre primero, aunque el bloque arranque tarde
    if not items or ahora() > hasta + datetime.timedelta(minutes=TOLERANCIA_MIN):
        print("Nada para publicar en esta franja.")
        return

    canal = CANAL or buscar_canal()
    print("Canal:", canal, "· items en franja:", len(items))
    if args.cada:
        # Modo seguido: aperturas primero, despues el resto, uno cada N minutos (las historias no cuentan para el ritmo)
        items.sort(key=lambda i: (0 if i["hora"] == "19:00" or i.get("ref") == "buenos_dias" else 1, i["hora"]))
        cierres = [i for i in items if str(i.get("ref", "")).startswith("cierre")]
        resto = [i for i in items if i not in cierres][args.saltear:]
        fin = hora_hoy(args.terminar) if args.terminar else None
        link = agenda.get("canal", "")
        invitaciones = sorted(f for f in os.listdir(base) if f.startswith("inv_"))
        fallas, publicados, n_estado = 0, 0, 0

        def mandar(item):
            nonlocal fallas
            if "archivo" in item and not item["archivo"].startswith(base):
                item["archivo"] = os.path.join(base, item["archivo"])
            ok, info = enviar(item, canal)
            print(f"{ahora():%H:%M:%S} {item['hora']} {item['tipo']:<9} {item.get('ref', '')}: {'OK' if ok else 'ERROR ' + info}")
            fallas = 0 if ok else fallas + 1
            if fallas >= 3 or info.startswith(("401", "402", "403")):
                sys.exit("Corto por errores repetidos (revisar la conexión del número en Whapi).")

        for item in resto:
            if fin and ahora() >= fin - datetime.timedelta(minutes=args.cada):
                break
            mandar(item)
            if item["tipo"] == "historia":
                continue
            publicados += 1
            if args.historias_cada and publicados % args.historias_cada == 0 and item["tipo"] == "imagen":
                n_estado += 1
                if n_estado % 2 == 0 and invitaciones:
                    txt = ("📢 *Las mejores ofertas salen primero en nuestro CANAL*\nSeguinos y activá la 🔔"
                           + (f" 👉 {link}" if link else ""))
                    mandar({"hora": item["hora"], "tipo": "historia", "ref": "invitacion",
                            "archivo": os.path.join(base, invitaciones[n_estado % len(invitaciones)]), "texto": txt})
                else:
                    pie = f"\n📢 Más ofertas en nuestro canal 👉 {link}" if link else ""
                    mandar({"hora": item["hora"], "tipo": "historia", "ref": "estado-" + str(item.get("ref", "")),
                            "archivo": item["archivo"], "texto": "🌙 Oferta de la noche · Precio mayorista" + pie})
            time.sleep(args.cada * 60)
        if fin and ahora() < fin:
            time.sleep(max(0, (fin - ahora()).total_seconds()))
        for c in cierres:
            mandar(c)
        return
    fallas = 0
    for item in items:
        momento = hora_hoy(item["hora"])
        es_apertura = item.get("ref") == "buenos_dias" or item["hora"] == "19:00"
        if ahora() > momento + datetime.timedelta(minutes=TOLERANCIA_MIN) and not es_apertura:
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
