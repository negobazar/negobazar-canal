"""Carga productos al catalogo de WhatsApp Business (via Whapi) y arma una coleccion por linea.
Uso: python tools/catalogo_wa.py catalogo_wa/hudson.json estado.json
Sin precio (0): el cliente consulta por WhatsApp. Guarda codigo -> id de producto en estado.json."""
import json, os, sys, time, requests

H = {"Authorization": "Bearer " + os.environ["WHAPI_TOKEN"], "Content-Type": "application/json"}
API = "https://gate.whapi.cloud"
lista = json.load(open(sys.argv[1], encoding="utf-8"))
ruta_estado = sys.argv[2]
estado = json.load(open(ruta_estado)) if os.path.exists(ruta_estado) else {"productos": {}, "colecciones": {}}
log = []


def pedir(metodo, url, **kw):
    for intento in range(5):
        r = requests.request(metodo, API + url, headers=H, timeout=120, **kw)
        if r.status_code != 429:
            return r
        time.sleep(15 * (intento + 1))
    return r


# productos que ya existen en el catalogo (por codigo)
r = pedir("GET", "/business/products", params={"count": 500})
for p in (r.json().get("products") or []):
    if p.get("product_retailer_id"):
        estado["productos"].setdefault(p["product_retailer_id"], p["id"])

for p in lista:
    if p["code"] in estado["productos"]:
        continue
    body = {"name": p["name"], "description": p["description"], "price": 0, "currency": "ARS",
            "images": [p["img"]], "availability": "in stock", "product_retailer_id": p["code"], "url": p["url"]}
    r = pedir("POST", "/business/products", json=body)
    ok = r.status_code == 200
    if ok:
        estado["productos"][p["code"]] = r.json().get("id")
    log.append(f"{p['code']} {r.status_code} {'' if ok else r.text[:200]}")
    print(log[-1], flush=True)
    time.sleep(2)

# una coleccion por linea
lineas = {}
for p in lista:
    if p["code"] in estado["productos"]:
        lineas.setdefault(p["linea"], []).append(estado["productos"][p["code"]])
for linea, ids in lineas.items():
    nombre = f"Hudson {linea}"
    if nombre in estado["colecciones"]:
        continue
    r = pedir("POST", "/business/collections", json={"name": nombre, "products": ids})
    log.append(f"coleccion {nombre} {r.status_code} {r.text[:300]}")
    print(log[-1], flush=True)
    if r.status_code == 200:
        estado["colecciones"][nombre] = r.json().get("id") or r.json()
    time.sleep(3)

json.dump(estado, open(ruta_estado, "w"), ensure_ascii=False, indent=1)
open("log.txt", "w").write("\n".join(log))
print("productos en catalogo:", len(estado["productos"]), "colecciones:", list(estado["colecciones"]))
