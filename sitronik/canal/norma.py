"""
Mensajes de texto del canal de Sitronik con la voz de Norma (la cara de Sitronik Home).

Todos los días agrega 2 mensajes a la agenda (horarios en config.json -> "norma.horarios"):
  - uno de NOVEDAD con un producto de "lo nuevo"
  - uno de la tarde que rota: más vendido / mensaje firmado por los dos
Además, mensajes de comunidad: buen día, beneficios, encuesta y cierre del día.
Usa productos que no salieron ese día en las placas. Las plantillas rotan por día para no repetirse.
"""

NOVEDAD = [
    "¡Holaaa! 🙋‍♀️ Les cuento algo: entró *{nombre}* y me encantó 😍\n"
    "Está a *{precio}* por transferencia.\n\n"
    "Lo ven acá 👉 {url}\n\nNorma 💜",

    "Novedad en Sitronik ✨\nLlegó *{nombre}*. Cuando lo vi dije: esto tiene que estar en el canal 🙌\n"
    "*{precio}* pagando por transferencia.\n\n👉 {url}\n\nNorma 💜",

    "Chicas, chicos, ¡llegó algo nuevo! 🎉\n*{nombre}* a *{precio}* por transferencia.\n"
    "Si les gusta no lo dejen pasar, que estas cositas vuelan 😉\n\n👉 {url}\n\nNorma 💜",
]

VENDIDO = [
    "Lo que más se llevan estos días es *{nombre}* 🔥 ¡y no me sorprende! 😄\n"
    "*{precio}* por transferencia.\n\n👉 {url}\n\n"
    "¿Alguna duda? Escríbannos, que respondemos nosotros 💬",

    "Top de la semana en Sitronik 🏆\n*{nombre}*. Ustedes lo eligieron y nosotros lo amamos 💜\n"
    "*{precio}* pagando por transferencia.\n\n👉 {url}\n\nNorma y David",
]

FIRMA = [
    "Hoy les escribimos los dos 🙌\nLes queremos recomendar *{nombre}*: *{precio}* por transferencia.\n\n"
    "Gracias por estar acá, este canal es nuestro rinconcito con ustedes 💜\n\n"
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
        turno = dia % 3
        p = _elegir(vendidos or nuevos, usados, dia * 7 + 2)
        if p:
            plantilla = FIRMA[0] if turno == 2 else VENDIDO[turno]
            items.append({"hora": horarios[1], "tipo": "texto", "ref": f"norma-tarde-{p['id']}",
                          "texto": _texto(plantilla, p)})
    return items + comunidad(dia, cfg)

# ---------- Mensajes de comunidad (sin producto) ----------
BUEN_DIA = [
    "¡Buen día! ☀️ ¿Ya tomaron el mate? 🧉 Les cuento que estamos preparando los pedidos de hoy y no paramos 📦\n"
    "Si vieron algo que les gustó, no lo dejen para después, que algunas cosas vuelan 😉\n\nNorma 💜",
    "¡Buen día, buen día! ☀️ Arrancamos con todo en Sitronik. Hoy les traigo cositas lindas para la cocina, "
    "así que estén atentos al canal 👀\n\nNorma 💜",
    "¡Hola, hola! ☀️ Arranca un día nuevo y ya estamos con las manos en los paquetes 📦\n"
    "Hoy van a ver varias novedades por acá, ¡no se las pierdan! 😉\n\nNorma 💜",
]

BENEFICIOS = [
    "¿Sabían que pagando con transferencia tienen *{desc} OFF* en toda la web? 💸\n"
    "Y si superan los $100.000, el envío va de regalo 🚚\n\nTodo en sitronik.com.ar 💜",
    "Recordatorio rapidito 📌\n✨ {desc} OFF pagando por transferencia\n🚚 Envío gratis superando $100.000\n"
    "🎁 5% extra en tu primera compra\n\nTodo en sitronik.com.ar 💜\nNorma",
    "Dato útil del día 💡 Si es tu primera compra en sitronik.com.ar, tenés un 5% extra de regalo 🎁\n"
    "Y pagando con transferencia, *{desc} OFF* 💸\n\nNorma 💜",
]

# Encuestas para que la comunidad participe (en el canal no se puede responder, pero sí votar)
ENCUESTAS = [
    ("Pausa para el café ☕ ¿Qué les gustaría ver más seguido por acá?",
     ["Ollas y sartenes", "Cosas para la mesa", "Organización y orden", "Electro para la cocina"]),
    ("Cuéntenme 💬 ¿Qué es lo que más usan en la cocina?", ["Sartén", "Olla", "Wok", "Air fryer"]),
    ("¿Cómo es su cocina soñada? 🎨", ["Negra total", "Blanca y luminosa", "Verde musgo", "Madera y tonos cálidos"]),
    ("¿Cuándo cocinan más? 🍳", ["Al mediodía", "A la noche", "Los fines de semana", "Todos los días, ¡no paro!"]),
    ("Para regalar, ¿qué elegirían? 🎁", ["Un set de ollas", "Algo para el mate", "Vajilla linda", "Algo para ordenar la cocina"]),
    ("¿Mate o café para arrancar el día? ☀️", ["Mate 🧉", "Café ☕", "Té 🍵", "¡Los dos, obvio!"]),
    ("¿Qué les cuesta más ordenar en casa? 🙈", ["La alacena", "La heladera", "Los cajones", "El placard"]),
]

CIERRE = [
    "Bueno, cerramos el día 🌙 Gracias por estar acá y por cada pedido, de verdad 💜\n"
    "Mañana seguimos con más novedades. ¡Que descansen!\n\nNorma y David",
    "¡Fin del día por acá! 🌙 Gracias por acompañarnos siempre, este canal es nuestro rinconcito con ustedes 💜\n"
    "Mañana les traemos más cositas lindas.\n\nNorma y David",
    "Nos vamos a descansar 😴 Gracias por cada mensaje y cada compra, nos llena el corazón 💜\n"
    "¡Hasta mañana!\n\nNorma y David",
]


def comunidad(dia, cfg):
    """Buen día, beneficios, encuesta y cierre. Horarios en config.json -> norma.comunidad."""
    c = (cfg.get("norma") or {})
    h = c.get("comunidad") or {}
    desc = c.get("descuento", "20%")
    items = []
    if h.get("buen_dia"):
        items.append({"hora": h["buen_dia"], "tipo": "texto", "ref": "norma-buendia",
                      "texto": BUEN_DIA[dia % len(BUEN_DIA)]})
    if h.get("beneficios"):
        items.append({"hora": h["beneficios"], "tipo": "texto", "ref": "norma-beneficios",
                      "texto": BENEFICIOS[dia % len(BENEFICIOS)].format(desc=desc)})
    if h.get("encuesta"):
        titulo, opciones = ENCUESTAS[dia % len(ENCUESTAS)]
        items.append({"hora": h["encuesta"], "tipo": "encuesta", "ref": "norma-encuesta",
                      "texto": titulo, "opciones": opciones})
    if h.get("cierre"):
        items.append({"hora": h["cierre"], "tipo": "texto", "ref": "norma-cierre",
                      "texto": CIERRE[dia % len(CIERRE)]})
    return items
