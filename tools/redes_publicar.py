"""
Publica en Instagram (@negobazar) y Facebook (NegoBazar) el contenido de redes del dia,
que arma cada madrugada distriecono-automatico en la rama "dia" (redes.json + imagenes sin precio).

Uso: python tools/redes_publicar.py [manana|mediodia|tarde|noche]   (sin argumento: segun la hora)
"""
import datetime, json, os, subprocess, sys, zoneinfo, requests

RAW = "https://raw.githubusercontent.com/negobazar/negobazar-canal/" + os.environ.get("REDES_RAMA", "dia") + "/"
TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")


def momento_actual():
    h = datetime.datetime.now(TZ).hour
    return "manana" if h < 12 else "mediodia" if h < 16 else "tarde" if h < 19 else "noche"


def meta(*args):
    print(">", args[0], flush=True)
    r = subprocess.run([sys.executable, "tools/meta_publicar.py", *args], text=True, capture_output=True)
    print((r.stdout + r.stderr).strip()[-600:], flush=True)
    return r.returncode == 0


def main():
    momento = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else momento_actual()
    plan = requests.get(RAW + "redes.json", timeout=30)
    if plan.status_code != 200:
        sys.exit("Todavia no hay redes.json en la rama dia")
    plan = plan.json()
    hoy = datetime.datetime.now(TZ).date().isoformat()
    if plan.get("fecha") != hoy and not (momento == "noche" and datetime.datetime.now(TZ).hour < 4):
        print(f"El plan es de {plan.get('fecha')}, hoy es {hoy}: no publico contenido viejo.")
        return
    ok = True
    for p in plan.get("posts", []):
        if p["momento"] != momento:
            continue
        urls = [RAW + a for a in p["archivos"]]
        if p["tipo"] == "carrusel":
            ok &= meta("carrusel", ",".join(urls), p["texto"])
            ok &= meta("imagen", urls[0], p["texto"], "--solo", "fb")
        else:
            ok &= meta("imagen", urls[0], p["texto"])
    for h in plan.get("historias", []):
        if h["momento"] == momento:
            ok &= meta("historia", RAW + h["archivo"])
    print("Listo" if ok else "Hubo errores")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
