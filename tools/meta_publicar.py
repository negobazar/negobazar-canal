"""
Publica en Instagram (@negobazar) y en la página de Facebook de Negobazar con la API oficial de Meta (gratis).

Uso:
  python tools/meta_publicar.py imagen  URL_PUBLICA_JPG  "texto"      [--solo ig|fb]
  python tools/meta_publicar.py reel    URL_PUBLICA_MP4  "texto"      [--solo ig|fb]
  python tools/meta_publicar.py historia URL_PUBLICA_JPG_O_MP4         (solo IG)
  python tools/meta_publicar.py carrusel URL1,URL2,URL3 "texto"        (solo IG)
  python tools/meta_publicar.py cuentas   -> muestra la página y la cuenta de IG que ve el token

Variables: META_TOKEN (token de página permanente), FB_PAGE_ID, IG_USER_ID.
Los archivos tienen que estar en una URL pública (IG los descarga desde ahí).
"""
import os, sys, time, json, argparse, requests

G = "https://graph.facebook.com/v21.0"
T = os.environ.get("META_TOKEN", "").strip()
PAGE = os.environ.get("FB_PAGE_ID", "").strip()
IG = os.environ.get("IG_USER_ID", "").strip()


def api(metodo, ruta, **datos):
    datos["access_token"] = T
    r = requests.request(metodo, f"{G}/{ruta}", data=datos if metodo == "POST" else None,
                         params=datos if metodo == "GET" else None, timeout=120)
    j = r.json()
    if "error" in j:
        raise SystemExit(f"Error Meta en {ruta}: {json.dumps(j['error'], ensure_ascii=False)}")
    return j


def esperar_contenedor(cid, maximo=600):
    t0 = time.time()
    while time.time() - t0 < maximo:
        s = api("GET", cid, fields="status_code,status").get("status_code")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise SystemExit(f"IG no pudo procesar el archivo ({s})")
        time.sleep(8)
    raise SystemExit("IG tardó demasiado en procesar")


def ig_publicar(cid):
    esperar_contenedor(cid)
    return api("POST", f"{IG}/media_publish", creation_id=cid)["id"]


def ig_imagen(url, texto):
    return ig_publicar(api("POST", f"{IG}/media", image_url=url, caption=texto)["id"])


def ig_reel(url, texto):
    return ig_publicar(api("POST", f"{IG}/media", media_type="REELS", video_url=url, caption=texto, share_to_feed="true")["id"])


def ig_historia(url):
    campo = {"video_url": url} if url.lower().split("?")[0].endswith(".mp4") else {"image_url": url}
    return ig_publicar(api("POST", f"{IG}/media", media_type="STORIES", **campo)["id"])


def ig_carrusel(urls, texto):
    hijos = [api("POST", f"{IG}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    for h in hijos:
        esperar_contenedor(h)
    return ig_publicar(api("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(hijos), caption=texto)["id"])


def fb_imagen(url, texto):
    return api("POST", f"{PAGE}/photos", url=url, message=texto)["id"]


def fb_video(url, texto):
    return api("POST", f"{PAGE}/videos", file_url=url, description=texto)["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tipo", choices=["imagen", "reel", "historia", "carrusel", "cuentas"])
    ap.add_argument("url", nargs="?")
    ap.add_argument("texto", nargs="?", default="")
    ap.add_argument("--solo", choices=["ig", "fb"])
    a = ap.parse_args()
    if not T:
        sys.exit("Falta META_TOKEN")
    if a.tipo == "cuentas":
        print(json.dumps(api("GET", PAGE or "me", fields="id,name,instagram_business_account{id,username}"), ensure_ascii=False))
        return
    hechos = {}
    if a.solo != "fb" and IG:
        if a.tipo == "imagen": hechos["ig"] = ig_imagen(a.url, a.texto)
        elif a.tipo == "reel": hechos["ig"] = ig_reel(a.url, a.texto)
        elif a.tipo == "historia": hechos["ig"] = ig_historia(a.url)
        elif a.tipo == "carrusel": hechos["ig"] = ig_carrusel(a.url.split(","), a.texto)
    if a.solo != "ig" and PAGE and a.tipo in ("imagen", "reel"):
        hechos["fb"] = fb_imagen(a.url, a.texto) if a.tipo == "imagen" else fb_video(a.url, a.texto)
    print(json.dumps(hechos))


if __name__ == "__main__":
    main()
