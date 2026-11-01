"""Publica en redes (IG/FB) a horario exacto desde el workflow del canal, que arranca puntual.
Uso: python tools/redes_turno.py manana=10:07 mediodia=12:33
Espera hasta cada hora (hora Argentina), y si ese momento no se publico hoy, lo publica y lo anota en la rama redes-estado."""
import datetime, os, subprocess, sys, time, zoneinfo

TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
REPO = os.environ["GITHUB_REPOSITORY"]
URL = f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{REPO}"


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, **kw)


def hechos():
    sh("git fetch -q origin redes-estado")
    r = sh("git show FETCH_HEAD:hechos.txt")
    return r.stdout.splitlines() if r.returncode == 0 else []


def anotar(clave):
    for _ in range(3):
        lineas = hechos()
        if clave in lineas:
            return
        os.makedirs("/tmp/e", exist_ok=True)
        open("/tmp/e/hechos.txt", "w").write("\n".join(lineas + [clave]) + "\n")
        sh("rm -rf /tmp/e/.git && cd /tmp/e && git init -q && git config user.name bot && git config user.email bot@x && git add . && git commit -qm h")
        if sh(f"cd /tmp/e && git push -fq {URL} HEAD:redes-estado").returncode == 0:
            return
        time.sleep(5)


for arg in sys.argv[1:]:
    mom, hora = arg.split("=")
    hh, mm = map(int, hora.split(":"))
    ahora = datetime.datetime.now(TZ)
    objetivo = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
    espera = (objetivo - ahora).total_seconds()
    if espera > 0:
        print(f"{mom}: espero {int(espera)} s hasta {hora}", flush=True)
        time.sleep(espera)
    elif espera < -90 * 60:
        print(f"{mom}: ya paso la hora ({hora}), no lo publico tarde", flush=True)
        continue
    clave = f"{datetime.datetime.now(TZ).date().isoformat()} {mom}"
    if clave in hechos():
        print(f"{mom}: ya estaba publicado", flush=True)
        continue
    r = subprocess.run([sys.executable, "tools/redes_publicar.py", mom])
    print(f"{mom}: termino con codigo {r.returncode}", flush=True)
    if r.returncode == 0:
        anotar(clave)
