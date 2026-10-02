"""Per-layer table (markdown) from layer_analysis.py output.   python layer_analysis_report.py layer_analysis.json out.md"""
import json, sys
import numpy as np
from layer_analysis import ORDER

PX_CM = 100 / 36.0
d = json.load(open(sys.argv[1]))["animations"]
by = {}
for k, r in d.items():
    for l in r["layers"]:
        by.setdefault(l, []).append(r)
L = ["# Warstwy ubieralne z klienta: zasięg i odstęp od ciała (poza `stand`, 5 kierunków)", "",
     "Źródło: `pipeline/layer_analysis.py` (anim, anim2, anim3, anim4, anim5; %d animacji). 1 px = %.2f cm. Szczegóły: `client/extract/layer_analysis.json`." % (len(d), PX_CM), "",
     "## Zasięg wysokości w pozie spoczynkowej (m, podłoga = 0)", "",
     "| warstwa | animacji | dół: min / mediana / max | góra: min / mediana / max | przykłady |", "|---|---|---|---|---|"]
for l, rs in sorted(by.items()):
    lo, hi = np.array([r["zlo"] for r in rs]), np.array([r["zhi"] for r in rs])
    ex = ", ".join(sorted({n for r in rs for n in r["items"]})[:3])
    L.append("| %s | %d | %.2f / %.2f / %.2f | %.2f / %.2f / %.2f | %s |" % (l, len(rs), lo.min(), np.median(lo), lo.max(), hi.min(), np.median(hi), hi.max(), ex))
L += ["", "## Pokrycie części ciała (mediana po animacjach, udział pikseli części ciała zakrytych przez przedmiot)", "",
      "| warstwa | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
for l, rs in sorted(by.items()):
    L.append("| %s | " % l + " | ".join("%.2f" % np.median([r["cover"].get(g, 0) for r in rs]) for g in ORDER) + " |")
L += ["", "## Wystawanie poza sylwetkę oryginalnego ciała (cm; p90 odległości pikseli przedmiotu od sylwetki, mediana po animacjach; tylko animacje z ≥ 5 pikselami poza sylwetką na kierunek)", "",
      "To dolne oszacowanie odstępu od skóry (wewnątrz sylwetki ciało jest zasłonięte). `—` = przedmiot prawie nie wystaje.", "",
      "| warstwa | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
for l, rs in sorted(by.items()):
    cells = []
    for g in ORDER:
        v = [r["out"][g]["p90"] for r in rs if g in r["out"] and r["out"][g]["n"] >= 5]
        cells.append("%.1f" % (np.median(v) * PX_CM) if len(v) >= 2 else "—")
    L.append("| %s | " % l + " | ".join(cells) + " |")
open(sys.argv[2], "w").write("\n".join(L) + "\n")
print("\n".join(L))
