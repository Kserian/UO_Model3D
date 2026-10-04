"""Does uo_autofit_item.py find the size and place of an item? Test with items whose right answer is known.

    python test_autofit.py [--out ../docs/qa/autofit.json] [--jobs 4] [--cases shirt,plate,...]

For every case a replica of an original UO item (test_items.py: the skin the item covers, moved out by its thickness) is made "foreign" (another scale, another
place; test_import_item.py), brought back by uo_import_item.py with the old method (one height per KIND, `height`) and by uo_autofit_item.py (`wrap`), and compared with the
replica as it was: nearest-vertex distance in mm (mean / p95 / max) and the ratio of heights / widths. "short" cases cut the replica to a height range (a jacket that ends at the
ribs, shorts): the old method stretches such an item to the height of the typical one, the wrap fit must not.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = {   # name: (item, scale of the foreign file, offset, zrange or None)
    "shirt":       ("shirt", 1.15, "0.12,0.05,-0.20", None),
    "shirt_small": ("shirt", 0.80, "-0.10,0.04,0.15", None),
    "shirt_short": ("shirt", 1.00, "0.05,0.03,-0.10", "1.25,9"),
    "plate":       ("plate", 0.85, "0.10,0.05,0.20", None),
    "plate_short": ("plate", 1.10, "-0.05,0.03,-0.30", "1.0,1.6"),
    "pants":       ("pants", 1.30, "0.10,-0.05,0.30", None),
    "pants_short": ("pants", 1.00, "0.00,0.03,0.20", "0.55,1.17"),
    "legs":        ("legs", 1.00, "0.15,0.05,0.10", None),
    "boots":       ("boots", 1.20, "0.00,0.04,-0.10", None),
    "gloves":      ("gloves", 0.90, "0.10,0.00,0.20", None),
    "helm":        ("helm", 1.10, "0.05,0.03,-0.20", None),
    "arms":        ("arms", 1.15, "0.00,0.03,-0.15", None),
}


ENV = {}


def one(case, mode, tmp):
    item, sc, off, zr = CASES[case]
    cmd = [sys.executable, os.path.join(HERE, "test_import_item.py"), "--item", item, "--mode", mode, "--scale", str(sc), "--offset=" + off,
           "--tmp", os.path.join(tmp, "%s_%s" % (case, mode))] + (["--zrange", zr] if zr else [])
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, **ENV))
    out = r.stdout
    m = re.search(r"nearest-vertex error mm \(ref -> got\): mean ([\d.]+)  p95 ([\d.]+)  max ([\d.]+) \| height ratio ([\d.]+)  width ratio ([\d.]+)", out)
    if not m:
        return dict(case=case, mode=mode, error=(out + r.stderr)[-600:])
    mean, p95, mx, hr, wr = (float(x) for x in m.groups())
    a = re.search(r"uo_autofit_item: .*", out)
    return dict(case=case, mode=mode, mean_mm=mean, p95_mm=p95, max_mm=mx, height_ratio=hr, width_ratio=wr, autofit=a.group(0)[:300] if a else None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--cases", default=",".join(CASES)); ap.add_argument("--modes", default="height,wrap")
    ap.add_argument("--env", default="", help="NAME=value,...: tuning of uo_autofit_item.py (UO_AUTOFIT_NAME), e.g. BAND_LOW=0.006,BAND_HIGH=0.01")
    a = ap.parse_args()
    ENV.update({"UO_AUTOFIT_" + kv.split("=")[0]: kv.split("=")[1] for kv in a.env.split(",") if kv})
    tmp = tempfile.mkdtemp(prefix="test_autofit_")
    jobs = [(c, m) for c in a.cases.split(",") for m in a.modes.split(",")]
    with ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(lambda j: one(j[0], j[1], tmp), jobs))
    print("%-12s %-7s %8s %8s %8s %8s %8s" % ("case", "mode", "mean mm", "p95 mm", "max mm", "h ratio", "w ratio"))
    for r in res:
        print("%-12s %-7s " % (r["case"], r["mode"]) + ("%8.1f %8.1f %8.1f %8.3f %8.3f" % (r["mean_mm"], r["p95_mm"], r["max_mm"], r["height_ratio"], r["width_ratio"]) if "mean_mm" in r else "FAILED " + r["error"][-200:].replace("\n", " ")))
    ok = [r["mean_mm"] for r in res if "mean_mm" in r]
    print("mean of the mean errors: %.1f mm over %d runs" % (sum(ok) / max(len(ok), 1), len(ok)))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
