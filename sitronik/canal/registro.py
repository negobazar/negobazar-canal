"""
Registro de lo que ya se publicó en el canal de Sitronik, para no repetir difusiones.

El registro vive en la rama "sitronik-registro" (archivo registro.json: {fecha: [refs enviadas]}).

  python sitronik/canal/registro.py filtrar AGENDA REGISTRO   -> saca de la agenda lo ya enviado hoy
  python sitronik/canal/registro.py unir LOCAL REMOTO SALIDA  -> une dos registros (por si corrieron dos jobs)
"""
import datetime
import json
import sys
import zoneinfo

TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
DIAS_GUARDADOS = 15


def leer(ruta):
    try:
        return json.load(open(ruta, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def filtrar(agenda, registro):
    a = json.load(open(agenda, encoding="utf-8"))
    ya = set(leer(registro).get(a.get("fecha", ""), []))
    antes = len(a["items"])
    a["items"] = [i for i in a["items"] if i.get("ref") not in ya]
    json.dump(a, open(agenda, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Registro: {antes - len(a['items'])} ya enviados hoy, quedan {len(a['items'])} por publicar")


def unir(local, remoto, salida):
    r = leer(remoto)
    for fecha, refs in leer(local).items():
        r[fecha] = list(dict.fromkeys(r.get(fecha, []) + refs))
    limite = (datetime.datetime.now(TZ).date() - datetime.timedelta(days=DIAS_GUARDADOS)).isoformat()
    r = {f: v for f, v in sorted(r.items()) if f >= limite}
    json.dump(r, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    {"filtrar": filtrar, "unir": unir}[sys.argv[1]](*sys.argv[2:])
