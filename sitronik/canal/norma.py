"""
Mensajes de texto del canal de Sitronik con la voz de Norma (la cara de Sitronik Home).

Todos los días agrega 2 mensajes a la agenda (horarios en config.json -> "norma.horarios"):
  - uno de NOVEDAD con un producto de "lo nuevo"
  - uno de la tarde que rota: más vendido / beneficios de la tienda / mensaje firmado por los dos
Usa productos que no salieron ese día en las placas. Las plantillas rotan por día para no repetirse.
"""

NOVEDAD = [
    "¡Holaaa! 🙋‍♀️ Les cuento algo: entró *{nombre}* y me encantó 😍\n"
    "Está a *{precio}* por transferencia, o en {cuotas} cuotas sin interés.\n\n"
    "Lo ven acá 👉 {url}\n\nNorma 💜",

    "Novedad en Sitronik ✨\nLlegó *{nombre}*. Cuando lo vi dije: esto tiene que estar en el canal 🙌\n"
    "*{precio}* pagando por transferencia.\n\n👉 {url}\n\nNorma 💜",

    "Chicas, chicos, ¡llegó algo nuevo! 🎉\n*{nombre}* a *{precio}* por transferencia.\n"
    "Si les gusta no lo dejen pasar, que estas cositas vuelan 😉\n\n👉 {url}\n\nNorma 💜",
]

VENDIDO = [
    "Lo que más se llevan estos días es *{nombre}* 🔥 ¡y no me sorprende! 😄\n"
    "*{precio}* por transferencia o en {cuotas} cuotas sin interés.\n\n👉 {url}\n\n"
    "¿Alguna duda? Escríbannos, que respondemos nosotros 💬",

    "Top de la semana en Sitronik 🏆\n*{nombre}*. Ustedes lo eligieron y nosotros lo amamos 💜\n"
    "*{precio}* pagando por transferencia.\n\n👉 {url}\n\nNorma y David",
]

FIRMA = [
    "Hoy les escribimos los dos 🙌\nLes queremos recomendar *{nombre}*: *{precio}* por transferencia "
    "o en {cuotas} cuotas sin interés.\n\nGracias por estar acá, este canal es nuestro rinconcito con ustedes 💜\n\n"
    "👉 {url}\n\nNorma y David",
]


def _pesos(n):
    return "$" + f"{round(n):,}".replace(",", ".")


def _texto(plantilla, p):
    return plantilla.format(nombre=p["nombre"], precio=_pesos(p["transf"]), cuotas=p["cuotas"], url=p["url"])


def _elegir(pool, usados, desde):
    for k in range(len(pool)):
        p = pool[(desde + k) % len(pool)]
        if str(p["id"]) not in usados:
            usados.add(str(p["id"]))
            return p
    return None


def mensajes(vendidos, nuevos, usados, dia, cfg):
    """Devuelve los items de texto del día. usados = ids (str) ya publicados en placas hoy."""
    c = cfg.get("norma") or {}
    horarios = c.get("horarios") or []
    if not horarios:
        return []
    usados = set(usados)
    items = []

    # 1) Novedad
    p = _elegir(nuevos or vendidos, usados, dia * 5 + 1)
    if p:
        items.append({"hora": horarios[0], "tipo": "texto", "ref": f"norma-novedad-{p['id']}",
                      "texto": _texto(NOVEDAD[dia % len(NOVEDAD)], p)})

    # 2) Tarde: rota entre más vendido, beneficios y firma de los dos
    if len(horarios) > 1:
        turno = dia % 4
        if turno == 1 and c.get("beneficios"):
            items.append({"hora": horarios[1], "tipo": "texto", "ref": "norma-beneficios", "texto": c["beneficios"]})
        else:
            p = _elegir(vendidos or nuevos, usados, dia * 7 + 2)
            if p:
                plantilla = FIRMA[0] if turno == 3 else VENDIDO[(dia // 4) % len(VENDIDO)]
                items.append({"hora": horarios[1], "tipo": "texto", "ref": f"norma-tarde-{p['id']}",
                              "texto": _texto(plantilla, p)})
    return items
