"""Invitación al canal de WhatsApp para los que ya nos escribieron (desde el 1053, por Whapi).
  plan   -> arma la lista (quién, qué versión, de qué hablamos) y la deja CIFRADA para revisar.
  enviar -> manda la invitación a los chats aprobados (por hash), de a uno, con pausas, y anota a quién se le mandó.
Nunca guarda números ni nombres en texto plano en el repo (es público): solo hashes."""
import hashlib, json, os, random, re, sys, time, unicodedata, requests

API = "https://gate.whapi.cloud"
H = {"Authorization": "Bearer " + os.environ.get("WHAPI_TOKEN", "")}
CANAL = "https://whatsapp.com/channel/0029VbDc32VHgZWW9hoWUx3t"
EXCLUIR = {"5491168169442", "5491125371053"}
norm = lambda s: "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
hid = lambda chat_id: hashlib.sha256(chat_id.encode()).hexdigest()[:12]

TEMAS = [(r"\bcopas?\b", "las copas"), (r"\bvasos?\b", "los vasos"), (r"\btermos?\b", "los termos"), (r"\bmates?\b", "los mates"),
         (r"\bsillon", "los sillones"), (r"\bsillas?\b", "las sillas"), (r"conservadora", "las conservadoras"),
         (r"\b(ollas?|cacerolas?)\b", "las ollas y cacerolas"), (r"\bsarten", "las sartenes"), (r"\bhudson\b", "los productos Hudson"),
         (r"\bcarol\b", "los productos Carol"), (r"tramontina", "los productos Tramontina"), (r"\bcubiertos?\b", "los cubiertos"),
         (r"\bplatos?\b", "los platos"), (r"\btazas?\b", "las tazas"), (r"hermetic", "los herméticos"), (r"limpieza", "los artículos de limpieza"),
         (r"\b(reposeras?|camping|pileta)\b", "lo de camping y verano"), (r"\bbazar\b", "los artículos de bazar"),
         (r"(catalogo|lista de precio)", "el catálogo"), (r"\b(combo|kit)\b", "los combos")]
NO_MOLESTAR = re.compile(r"(no me interesa|no gracias|baja\b|no me escriban|no molest|reclamo|roto|rota|fallad|devoluc|estafa|denunc)")


def primer_nombre(n):
    n = (n or "").strip().split(" ")[0]
    return n.capitalize() if n and n.replace(".", "").isalpha() and len(n) > 1 else ""


def armar_texto(nombre, tema):
    hola = f"Hola {nombre}" if nombre else "Hola"
    if tema:
        return (f"{hola}, ¿cómo andás? Soy David de Negobazar 🙌\nTe escribo porque hace unos días me habías consultado por {tema}.\n"
                "Te cuento que armamos un canal de WhatsApp donde subimos todos los días lo que va ingresando, con foto y precio mayorista, "
                "y a la noche unas ofertas que duran pocas horas. Así no te perdés nada y ves todo desde el celu, sin tener que preguntar.\n"
                f"Te dejo el link por si te sirve: {CANAL}\nY cualquier cosa me escribís por acá 👍")
    return (f"{hola}, ¿cómo va? Soy David de Negobazar 🙌\nTe quería contar que armamos un canal de WhatsApp para clientes: todos los días "
            "subimos lo que va entrando al depósito con foto y precio mayorista, y a la noche hay ofertas que duran unas horas.\n"
            f"Es gratis y no molesta, lo mirás cuando querés. Te dejo el link: {CANAL}\nCualquier cosa que necesites, me escribís por acá.")


def plan(ya_enviados):
    chats = requests.get(API + "/chats", headers=H, params={"count": 500}, timeout=60).json().get("chats", [])
    ahora = time.time(); salida = []
    for c in chats:
        cid = c["id"]
        if not cid.endswith("@s.whatsapp.net") or cid.split("@")[0] in EXCLUIR or hid(cid) in ya_enviados:
            continue
        ms = requests.get(f"{API}/messages/list/{cid}", headers=H, params={"count": 40}, timeout=60).json().get("messages", [])
        ms.sort(key=lambda m: m.get("timestamp", 0))
        txt = lambda m: (m.get("text") or {}).get("body") or (m.get("image") or {}).get("caption") or ""
        cliente = [m for m in ms if not m.get("from_me")]
        if not cliente:
            continue                                   # nunca nos escribió: no se le manda
        ult = ms[-1]
        motivo = ""
        textos_cliente = norm(" ".join(txt(m) for m in cliente))
        if NO_MOLESTAR.search(textos_cliente): motivo = "dijo que no / reclamo"
        elif not ult.get("from_me"): motivo = "espera respuesta nuestra"
        elif ahora - ult.get("timestamp", 0) < 2 * 86400: motivo = "charla activa (menos de 2 días)"
        elif CANAL.split("/")[-1] in " ".join(txt(m) for m in ms if m.get("from_me")): motivo = "ya recibió el link del canal"
        tema = ""
        for patron, frase in TEMAS:
            if re.search(patron, textos_cliente):
                tema = frase; break
        nombre = primer_nombre(next((m.get("from_name") for m in cliente if m.get("from_name")), "") or c.get("name"))
        salida.append({"h": hid(cid), "fin": cid.split("@")[0][-4:], "nombre": nombre, "tema": tema, "motivo": motivo,
                       "ult": int(ult.get("timestamp", 0)), "texto": armar_texto(nombre, tema)})
        time.sleep(0.3)
    salida.sort(key=lambda x: -x["ult"])
    return salida


def enviar(hashes, ya_enviados):
    chats = requests.get(API + "/chats", headers=H, params={"count": 500}, timeout=60).json().get("chats", [])
    por_hash = {hid(c["id"]): c for c in chats if c["id"].endswith("@s.whatsapp.net")}
    hechos = []
    for h in hashes:
        c = por_hash.get(h)
        if not c or h in ya_enviados:
            continue
        p = [x for x in plan_de_uno(c)]
        if not p or p[0]["motivo"]:
            print(h, "salteado:", p[0]["motivo"] if p else "sin datos"); continue
        r = requests.post(API + "/messages/text", headers=H, json={"to": c["id"], "body": p[0]["texto"]}, timeout=60)
        print(h, r.status_code); hechos.append(h)
        time.sleep(random.randint(90, 180))         # pausa de 1,5 a 3 minutos entre mensajes
    return hechos


def plan_de_uno(c):
    global requests
    chats_orig = requests.get
    cid = c["id"]
    ms = requests.get(f"{API}/messages/list/{cid}", headers=H, params={"count": 40}, timeout=60).json().get("messages", [])
    ms.sort(key=lambda m: m.get("timestamp", 0))
    txt = lambda m: (m.get("text") or {}).get("body") or (m.get("image") or {}).get("caption") or ""
    cliente = [m for m in ms if not m.get("from_me")]
    if not cliente:
        return []
    ult = ms[-1]; tc = norm(" ".join(txt(m) for m in cliente)); motivo = ""
    if NO_MOLESTAR.search(tc): motivo = "dijo que no / reclamo"
    elif not ult.get("from_me"): motivo = "espera respuesta nuestra"
    elif time.time() - ult.get("timestamp", 0) < 2 * 86400: motivo = "charla activa"
    tema = next((f for p, f in TEMAS if re.search(p, tc)), "")
    nombre = primer_nombre(next((m.get("from_name") for m in cliente if m.get("from_name")), "") or c.get("name"))
    return [{"motivo": motivo, "texto": armar_texto(nombre, tema)}]


if __name__ == "__main__":
    ya = set(open("enviados.txt").read().split()) if os.path.exists("enviados.txt") else set()
    if sys.argv[1] == "plan":
        json.dump(plan(ya), open("plan.json", "w"), ensure_ascii=False)
    else:
        hechos = enviar([x.strip() for x in sys.argv[2].split(",") if x.strip()], ya)
        open("enviados.txt", "a").write("".join(h + "\n" for h in hechos))
