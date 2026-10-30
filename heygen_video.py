"""
Genera un video con un clon de HeyGen y lo descarga.
Prueba primero la API v3 (studio, Avatar IV); si la rechaza, prueba la v2 (talking photo).
Deja todo en la carpeta de salida: video.mp4 (si salio) y log.json con las respuestas.

Uso: python heygen_video.py config.json salida/
config: {"look_id", "voice_id", "script", "motion_prompt", "titulo", "speed"}
"""
import json
import os
import sys
import time

import requests

KEY = os.environ["HEYGEN_API_KEY"]
H = {"x-api-key": KEY, "Content-Type": "application/json", "Accept": "application/json"}
API = "https://api.heygen.com"
LOG = []


def log(paso, r=None, **extra):
    item = {"paso": paso, **extra}
    if r is not None:
        item["http"] = r.status_code
        try:
            item["resp"] = r.json()
        except Exception:
            item["resp"] = r.text[:2000]
    LOG.append(item)
    print(json.dumps(item, ensure_ascii=False)[:1500], flush=True)
    return item


def buscar(obj, claves):
    """Busca recursivamente la primera clave de la lista con valor no vacio."""
    if isinstance(obj, dict):
        for k in claves:
            if obj.get(k):
                return obj[k]
        for v in obj.values():
            x = buscar(v, claves)
            if x:
                return x
    elif isinstance(obj, list):
        for v in obj:
            x = buscar(v, claves)
            if x:
                return x
    return None


def buscar_mp4(obj):
    if isinstance(obj, str):
        return obj if obj.startswith("http") and ".mp4" in obj else None
    if isinstance(obj, dict):
        for k in ("video_url", "url", "download_url"):
            v = obj.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            x = buscar_mp4(v)
            if x:
                return x
    return None


def intentos(c):
    v3 = {
        "type": "studio", "title": c.get("titulo", "Negobazar"), "aspect_ratio": "9:16", "resolution": "1080p",
        "scenes": [{
            "type": "avatar_video",
            "input": {"type": "avatar", "avatar_id": c["look_id"], "script": c["script"], "voice_id": c["voice_id"],
                      "expressiveness": "high", "motion_prompt": c.get("motion_prompt", ""),
                      "voice_settings": {"speed": c.get("speed", 1.0)}},
        }],
    }
    v2 = {
        "title": c.get("titulo", "Negobazar"),
        "video_inputs": [{
            "character": {"type": "talking_photo", "talking_photo_id": c["look_id"], "use_avatar_iv_model": True,
                          "talking_style": "expressive"},
            "voice": {"type": "text", "input_text": c["script"], "voice_id": c["voice_id"], "speed": c.get("speed", 1.0)},
        }],
        "dimension": {"width": 1080, "height": 1920},
    }
    v2b = json.loads(json.dumps(v2))
    v2b["video_inputs"][0]["character"] = {"type": "talking_photo", "talking_photo_id": c["look_id"]}
    return [("v3", API + "/v3/videos", v3), ("v2_iv", API + "/v2/video/generate", v2), ("v2", API + "/v2/video/generate", v2b)]


def estado(version, vid):
    if version == "v3":
        return requests.get(f"{API}/v3/videos/{vid}", headers=H, timeout=30)
    return requests.get(f"{API}/v1/video_status.get", params={"video_id": vid}, headers=H, timeout=30)


def main():
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    try:
        version, vid = None, None
        for nombre, url, body in intentos(c):
            r = requests.post(url, headers=H, json=body, timeout=60)
            log("crear_" + nombre, r)
            if r.status_code < 300:
                try:
                    vid = buscar(r.json(), ["video_id", "id"])
                except Exception:
                    vid = None
                if vid:
                    version = nombre
                    break
        if not vid:
            log("sin_video", nota="ninguna version acepto el pedido")
            return
        inicio = time.time()
        url_mp4 = None
        while time.time() - inicio < 40 * 60:
            time.sleep(20)
            r = estado(version, vid)
            try:
                j = r.json()
            except Exception:
                j = {}
            st = str(buscar(j, ["status"]) or "").lower()
            print(int(time.time() - inicio), "s", st, flush=True)
            if st in ("completed", "complete", "success", "succeeded", "done"):
                log("estado_final", r)
                url_mp4 = buscar_mp4(j)
                break
            if st in ("failed", "error"):
                log("estado_final", r)
                return
        if not url_mp4:
            log("sin_url", nota="no termino o no encontre la url")
            return
        v = requests.get(url_mp4, timeout=300)
        open(os.path.join(out, "video.mp4"), "wb").write(v.content)
        log("descargado", bytes=len(v.content))
    finally:
        json.dump(LOG, open(os.path.join(out, "log.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
