"""Deja en la agenda solo lo que se publica en una prueba: (bienvenida) + N placas intercalando productos y combos."""
import json
import os
import sys

ruta, cantidad, bienvenida = sys.argv[1], int(sys.argv[2] or 1), sys.argv[3] == "si"
a = json.load(open(ruta, encoding="utf-8"))
prods = [i for i in a["items"] if not i["ref"].startswith(("combo", "ig"))]
combos = [i for i in a["items"] if i["ref"].startswith("combo")]
mezcla = []
for k in range(max(len(prods), len(combos))):
    mezcla += prods[k:k + 1] + combos[k:k + 1]
items = mezcla[:cantidad]
for n, it in enumerate(items):
    it["hora"] = f"00:{n + 1:02d}"
if bienvenida:
    txt = open(os.path.join(os.path.dirname(__file__), "bienvenida.txt"), encoding="utf-8").read().strip()
    items.insert(0, {"hora": "00:00", "tipo": "texto", "texto": txt, "ref": "buenos_dias"})
a["items"] = items
json.dump(a, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
print("Prueba:", [i["ref"] for i in items])
