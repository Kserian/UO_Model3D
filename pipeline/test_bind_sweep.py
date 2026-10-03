"""Weight policy sweep: SMOOTH / STIFF of uo_bind_item.py per item against the original sprites (full-density replicas of test_items.py).

    python test_bind_sweep.py --items plate --tmp DIR --out sweep.json [--actions 00_walk_unarmed,...]
"""
import argparse, json, os, shutil, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_items as T                                           # noqa: E402

JOINTS = "00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,12_attack_2h_bash,16_spell_directed,17_spell_area,18_attack_bow,21_die_forward,22_die_backward,31_punch,33_salute"
GRID = [("S4/K1", "SMOOTH=4,STIFF=1"), ("S0/K1", "SMOOTH=0,STIFF=1"), ("S12/K1", "SMOOTH=12,STIFF=1"), ("S4/K2", "SMOOTH=4,STIFF=2"),
        ("S4/K4", "SMOOTH=4,STIFF=4"), ("S4/K0.5", "SMOOTH=4,STIFF=0.5"), ("S12/K2", "SMOOTH=12,STIFF=2"), ("S0/K2", "SMOOTH=0,STIFF=2")]
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--items", required=True); ap.add_argument("--actions", default=JOINTS)
    ap.add_argument("--tmp", required=True); ap.add_argument("--out"); ap.add_argument("--fit", action="store_true")
    a = ap.parse_args()
    canvas, anchor = (256, 256), (128, 192); tmp = os.path.abspath(a.tmp); os.makedirs(tmp, exist_ok=True)
    spec_path = os.path.join(tmp, "spec.json"); json.dump(T.ITEMS, open(spec_path, "w"))
    res = {}
    for item in a.items.split(","):
        for label, bind in GRID:
            os.environ["UO_TEST_BIND"] = bind
            out = os.path.join(tmp, item, label.replace("/", "_")); shutil.rmtree(out, ignore_errors=True)
            root = T.render(os.path.abspath(os.path.join(T.HERE, "..", "model", "UO_Body_0x190.blend")), out, item, a.actions.split(","), canvas, anchor, a.fit, spec_path)
            rows, blocks, _ = T.measure(root, item, canvas, anchor, set())
            s = T.summarize(rows, blocks)
            res.setdefault(item, {})[label] = dict(iou=s["iou"], outside=s["outside"], missing=s["missing"], by_action=s["by_action"])
            print("%-7s %-9s IoU %.4f  out %.1f miss %.1f" % (item, label, s["iou"], s["outside"], s["missing"]), flush=True)
            if a.out: json.dump(res, open(a.out, "w"), indent=1)
