"""Phase 2 of docs/plans/original_items_calibration.md: does a thickness taken from the originals beat the hand-set one?

    python prior_thickness_test.py <vd_scan.json[.gz]> <out.json> [--jobs 4] [--items a,b,...] [--actions 04_stand,00_walk_unarmed,09_attack_1h_slash]

For every replica of `test_items.py` (the 6 default ones + the second group of originals) the replica is rendered with
  hand   the hand-set thickness of ITEMS,
  prior  leave-one-out prior: median over the OTHER animations of the item's layer of their stand standoff p50 (px, outside the body 400 silhouette) / 36 px per m,
  grid   uniform thicknesses 0.006 0.012 0.02 0.03 0.04 m (where the IoU of each slot peaks),
through `test_items.py` (UO_TEST_THICK) and the IoU against the original sprite is collected. Output: per item and thickness the IoU, plus the summary.
"""
import gzip, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_items as T                                                 # noqa: E402

GRID = [0.006, 0.012, 0.02, 0.03, 0.04]
PXM = 36.0


def layer_of(scan, anim):
    v = scan["animations"].get("anim:%d" % anim)
    return (v["layers"][0] if v else None), v


def loo_prior(scan, anim):
    """leave-one-out prior thickness (m) of animation `anim` from its layer"""
    layer, _ = layer_of(scan, anim)
    others = [v["actions"]["4"]["dist"]["p50"] for s, v in scan["animations"].items()
              if layer in v["layers"] and s != "anim:%d" % anim and "4" in v["actions"] and "dist" in v["actions"]["4"]]
    return float(np.median(others)) / PXM if others else None, len(others)


def job(args):
    item, thick, actions, tmp = args
    os.makedirs(tmp, exist_ok=True)
    out = os.path.join(tmp, "%s_%s.json" % (item, thick))
    env = dict(os.environ)
    if thick is not None:
        env["UO_TEST_THICK"] = "%.5f" % thick
    r = subprocess.run([sys.executable, os.path.join(HERE, "test_items.py"), "--items", item, "--actions", actions, "--tmp", os.path.join(tmp, "%s_%s" % (item, thick)), "--out", out],
                       capture_output=True, text=True, env=env, cwd=HERE)
    if r.returncode or not os.path.exists(out):
        return item, thick, None, r.stdout[-300:] + r.stderr[-300:]
    return item, thick, json.load(open(out))["items"][item]["iou"], ""


def main():
    args = sys.argv[1:]
    jobs, actions, items = 4, "04_stand,00_walk_unarmed,09_attack_1h_slash", None
    for opt in ("--jobs", "--actions", "--items"):
        if opt in args:
            i = args.index(opt)
            v = args[i + 1]
            del args[i:i + 2]
            if opt == "--jobs":
                jobs = int(v)
            elif opt == "--actions":
                actions = v
            else:
                items = v.split(",")
    src, out = args
    scan = json.load((gzip.open if src.endswith(".gz") else open)(src, "rt"))
    names = items or (T.DEFAULT_ITEMS + "," + T.EXTRA_ITEMS).split(",")
    names = [n for n in names if n != "helm"] if items is None else names           # helm is no body-hugging shell: its shape is the item
    tmp = tempfile.mkdtemp(prefix="prior_thick_")
    plan, meta = [], {}
    for n in names:
        sp = T.ITEMS[n]
        prior, k = loo_prior(scan, sp["anim"])
        layer, _ = layer_of(scan, sp["anim"])
        meta[n] = dict(anim=sp["anim"], layer=layer, hand=sp["thickness"], prior=round(prior, 5) if prior else None, prior_from=k)
        variants = {("hand", None)} | {("grid%.3f" % g, g) for g in GRID}
        if prior:
            variants.add(("prior", round(prior, 5)))
        for label, t in sorted(variants, key=lambda x: x[0]):
            plan.append((n, label, t))
    print("%d items, %d renders, %s" % (len(names), len(plan), actions), flush=True)
    res = {n: {} for n in names}
    with ThreadPoolExecutor(jobs) as ex:
        for (n, label, t), (item, thick, iou, err) in zip(plan, ex.map(job, [(n, t, actions, os.path.join(tmp, label)) for n, label, t in plan])):
            res[n][label] = iou
            print("%-12s %-9s %s %s" % (n, label, "%.4f" % iou if iou is not None else "FAILED", err), flush=True)
    json.dump(dict(actions=actions, items=meta, iou=res), open(out, "w"), indent=1)
    print("written", out, "(tmp", tmp, ")")


if __name__ == "__main__":
    main()
