"""Baja el ultimo video terminado de la cuenta de HeyGen (o el video_id indicado) a out/video.mp4."""
import json, os, sys, requests
H = {"x-api-key": os.environ["HEYGEN_API_KEY"], "Accept": "application/json"}
API = "https://api.heygen.com"
os.makedirs("out", exist_ok=True)
log = []
def get(url, **kw):
    r = requests.get(url, headers=H, timeout=60, **kw)
    try: j = r.json()
    except Exception: j = {"texto": r.text[:500]}
    log.append({"url": url, "http": r.status_code, "resp": j}); return j
vid = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
if not vid:
    for url in (API + "/v3/videos?limit=10", API + "/v1/video.list?limit=10"):
        j = get(url)
        lista = (j.get("data") or {})
        lista = lista.get("videos") if isinstance(lista, dict) else lista
        if lista:
            for v in lista:
                if str(v.get("status", "")).lower() in ("completed", "complete", "success"):
                    vid = v.get("video_id") or v.get("id"); break
        if vid: break
url_mp4 = None
if vid:
    for url in (f"{API}/v3/videos/{vid}", f"{API}/v1/video_status.get?video_id={vid}"):
        j = get(url)
        d = j.get("data") or {}
        url_mp4 = d.get("video_url") or d.get("url") or d.get("download_url")
        if url_mp4: break
if url_mp4:
    open("out/video.mp4", "wb").write(requests.get(url_mp4, timeout=300).content)
    log.append({"bajado": vid, "bytes": os.path.getsize("out/video.mp4")})
json.dump(log, open("out/log.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(log, ensure_ascii=False)[:3000])
