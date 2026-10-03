"""Density experiment: does a coarse (low-poly) item bend angularly, and does uo_densify_item.py fix it?

    python test_density.py --items shirt,pants,gloves,boots [--actions ...] [--out docs/qa/density.json] [--tmp DIR]

The replica of test_items.py (full density = reference) is decimated to a ratio (UO_TEST_DECIMATE, a stand-in for a foreign low-poly model), optionally
densified (uo_densify_item.py: TARGET_EDGE, SMOOTH) and bound/rendered like in test_items.py. Per configuration: vertices, IoU with the sprite and
`dev` = 1 - IoU of the render with the render of the full-density reference (pure effect of the mesh: folds at the joints, flattened curves), px
`ref_diff` per frame.
"""
import argparse, json, os, sys, time
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_items as T                                           # noqa: E402

CONFIGS = [   # label, env
    ("ref", {}),
    ("dec0.10", {"UO_TEST_DECIMATE": "0.10"}),
    ("dec0.03", {"UO_TEST_DECIMATE": "0.03"}),
    ("dec0.10+simple", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_DENSIFY": "0.03,0"}),
    ("dec0.10+smooth", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_DENSIFY": "0.03,1"}),
    ("dec0.03+simple", {"UO_TEST_DECIMATE": "0.03", "UO_TEST_DENSIFY": "0.03,0"}),
    ("dec0.03+smooth", {"UO_TEST_DECIMATE": "0.03", "UO_TEST_DENSIFY": "0.03,1"}),
    ("dec0.10+slot", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_PREPARE": "1"}),
    ("dec0.03+slot", {"UO_TEST_DECIMATE": "0.03", "UO_TEST_PREPARE": "1"}),
    ("dec0.10+e05", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_DENSIFY": "0.05,0"}),
    ("dec0.10+e02", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_DENSIFY": "0.02,0"}),
    ("dec0.10+e012", {"UO_TEST_DECIMATE": "0.10", "UO_TEST_DENSIFY": "0.012,0"}),
]


def frames(root):
    out = {}
    for act in sorted(os.listdir(root)):
        for d in range(5):
            fdir = os.path.join(root, act, "dir%d" % d)
            for fn in sorted(os.listdir(fdir)):
                out[(act, d, fn)] = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))[..., 3] > 0
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="shirt,pants,gloves,boots"); ap.add_argument("--actions", default=T.DEFAULT_ACTIONS)
    ap.add_argument("--configs"); ap.add_argument("--tmp", required=True); ap.add_argument("--out"); ap.add_argument("--fit", action="store_true")
    a = ap.parse_args()
    canvas, anchor = (256, 256), (128, 192)
    tmp = os.path.abspath(a.tmp); os.makedirs(tmp, exist_ok=True)
    spec_path = os.path.join(tmp, "spec.json"); json.dump(T.ITEMS, open(spec_path, "w"))
    cfgs = [c for c in CONFIGS if not a.configs or c[0] in a.configs.split(",") or c[0] == "ref"]
    res = {}
    print("%-7s %-16s %7s %6s %9s" % ("item", "config", "verts", "IoU", "ref_diff"))
    for item in a.items.split(","):
        ref = None
        for label, env in cfgs:
            for k in ("UO_TEST_DECIMATE", "UO_TEST_DENSIFY", "UO_TEST_PREPARE"):
                os.environ.pop(k, None)
            os.environ.update(env)
            out = os.path.join(tmp, item, label)
            import shutil; shutil.rmtree(out, ignore_errors=True)
            root = T.render(os.path.abspath(os.path.join(T.HERE, "..", "model", "UO_Body_0x190.blend")), out, item, a.actions.split(","), canvas, anchor, a.fit, spec_path)
            rows, blocks, _ = T.measure(root, item, canvas, anchor, set())
            s = T.summarize(rows, blocks)
            fr = frames(root)
            if label == "ref":
                ref = fr
            diff = float(np.mean([(fr[k] ^ ref[k]).sum() for k in fr])) if ref else 0.0
            log = open(os.path.join(out, "log.txt")).read()
            nv = [int(x.split()[0]) for x in [l.split("->")[1] for l in log.splitlines() if "test_items_pre" in l]]
            res.setdefault(item, {})[label] = dict(verts=nv[-1] if nv else 0, iou=s["iou"], ref_diff=diff, missing=s["missing"], outside=s["outside"])
            print("%-7s %-16s %7d %6.3f %9.1f" % (item, label, res[item][label]["verts"], s["iou"], diff), flush=True)
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
