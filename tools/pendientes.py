# Busca chats privados cuyo ultimo mensaje es del cliente (sin respuesta) en las ultimas HORAS y,
# si ENVIAR=1, se los pasa al bot (webhook) juntando los mensajes seguidos del cliente en uno.
import os, json, time, urllib.request
T = os.environ["WT"]; H = {"Authorization": "Bearer " + T, "User-Agent": "Mozilla/5.0 negobazar-pendientes", "Content-Type": "application/json"}
BOT = "https://bot-negobazar.negobazar.deno.net/webhook"
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request("https://gate.whapi.cloud" + u, headers=H), timeout=60))
desde = time.time() - float(os.environ.get("HORAS", "30")) * 3600
chats = get("/chats?count=200").get("chats", [])
pend = []
for c in chats:
    cid = c.get("id", ""); lm = c.get("last_message") or {}
    if not cid.endswith("@s.whatsapp.net") or lm.get("from_me") or (lm.get("timestamp") or 0) < desde: continue
    msgs = get(f"/messages/list/{cid}?count=20").get("messages", [])
    msgs.sort(key=lambda m: m["timestamp"])
    seg = []
    for m in reversed(msgs):
        if m.get("from_me"): break
        seg.insert(0, m)
    textos = [(m.get("text") or {}).get("body") or (m.get("image") or {}).get("caption") or "" for m in seg]
    textos = [t for t in textos if t]
    pend.append((cid, lm.get("from_name") or c.get("name") or "", seg, textos))
print("chats sin responder:", len(pend))
for cid, nom, seg, textos in pend:
    print(f"- {nom[:20]} ...{cid[-19:-15]} {time.strftime('%d/%m %H:%M', time.gmtime(seg[-1]['timestamp']-10800))} | {' / '.join(textos)[:90]}")
if os.environ.get("ENVIAR") == "1":
    for cid, nom, seg, textos in pend:
        m = dict(seg[-1]); 
        if textos: m["type"] = "text"; m["text"] = {"body": "\n".join(textos)}
        r = urllib.request.urlopen(urllib.request.Request(BOT, data=json.dumps({"messages": [m]}).encode(), headers={"Content-Type": "application/json"}), timeout=120)
        print("enviado al bot", cid[-19:-15], r.status); time.sleep(3)
