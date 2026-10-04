"""One regression run with thresholds (exit code != 0 when something got worse): the numbers that the decisions of CLAUDE.md stand on.

    python run_qa.py [--quick] [--skip canvas,items,...]

  items     test_items.py          mean IoU of the 6 replicas against the original sprites           >= 0.715   (baseline 0.718, docs/qa/items_after_fingers.json)
  canvas    test_canvas.py         every case pixel-identical to the reference render (CANVAS / ANCHOR)           all OK
  autofit   test_autofit.py        mean vertex error of 12 foreign replicas (wrap)                       <= 20 mm   (13.6 mm, docs/qa/autofit.json)
  robe      test_robe.py           lower-body IoU of the robe replica against the original robe 469       >= 0.74    (0.757, docs/qa/robe_physics.json)
  materials test_materials.py      "RESULT OK"
  import    test_import_item.py    the chain from a foreign file runs and puts the item where the old method did (bbox)  (runs without error)
--quick drops items and canvas (about 6 minutes less). Needs the same as the tests (bpy 4.2, numpy, scipy, pillow); each test is the script of the same name in this folder.
"""
import argparse, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    t = time.time()
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, cwd=HERE)
    return r.returncode, r.stdout + r.stderr, time.time() - t


CHECKS = {}


def check(name):
    def deco(f):
        CHECKS[name] = f
        return f
    return deco


@check("items")
def _items(tmp):
    code, out, dt = run(["test_items.py", "--tmp", tmp])
    m = re.search(r"mean IoU over items: ([\d.]+)", out)
    v = float(m.group(1)) if m else 0.0
    return code == 0 and v >= 0.715, "mean IoU %.3f (>= 0.715)" % v, dt


@check("canvas")
def _canvas(tmp):
    code, out, dt = run(["test_canvas.py", "--tmp", tmp])
    bad = [l for l in out.splitlines() if " OK" not in l and "canvas" in l and "frames" in l]
    ok = code == 0 and not bad and out.count("| OK") >= 10
    return ok, "%d cases OK, %d not" % (out.count("| OK"), len(bad)), dt


@check("autofit")
def _autofit(tmp):
    code, out, dt = run(["test_autofit.py", "--modes", "wrap", "--jobs", "4"])
    m = re.search(r"mean of the mean errors: ([\d.]+) mm", out)
    v = float(m.group(1)) if m else 1e9
    return code == 0 and v <= 20.0, "mean error %.1f mm (<= 20)" % v, dt


@check("robe")
def _robe(tmp):
    code, out, dt = run(["test_robe.py", "--tmp", tmp])
    m = re.search(r"lower-body IoU ([\d.]+)", out)
    v = float(m.group(1)) if m else 0.0
    return code == 0 and v >= 0.74, "lower-body IoU %.3f (>= 0.74)" % v, dt


@check("materials")
def _mat(tmp):
    code, out, dt = run(["test_materials.py"])
    return code == 0 and "RESULT OK" in out, "RESULT OK" if "RESULT OK" in out else out[-200:], dt


@check("import")
def _import(tmp):
    code, out, dt = run(["test_import_item.py", "--item", "shirt", "--mode", "wrap", "--tmp", tmp])
    m = re.search(r"nearest-vertex error mm.*?mean ([\d.]+)", out)
    v = float(m.group(1)) if m else 1e9
    return code == 0 and v < 30, "recovery error %.1f mm (< 30)" % v, dt


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true"); ap.add_argument("--skip", default="")
    a = ap.parse_args()
    skip = set(filter(None, a.skip.split(","))) | ({"items", "canvas"} if a.quick else set())
    failed = []
    for name, f in CHECKS.items():
        if name in skip:
            print("%-10s skipped" % name); continue
        ok, msg, dt = f(tempfile.mkdtemp(prefix="qa_%s_" % name))
        print("%-10s %s  %s  (%.0f s)" % (name, "OK  " if ok else "FAIL", msg, dt), flush=True)
        if not ok:
            failed.append(name)
    print("QA %s" % ("PASSED" if not failed else "FAILED: " + ", ".join(failed)))
    sys.exit(1 if failed else 0)
