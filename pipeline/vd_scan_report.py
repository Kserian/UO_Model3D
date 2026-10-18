"""Report on the output of `vd_scan.py`: per slot (layer) statistics of the original wearable animations next to the body 400, data quality, outliers.

    python vd_scan_report.py <scan.json> <report.md> [<layers.json>]

Per layer (an animation with several layers counts in each): number of animations; for the stand action (4) the median and the spread between items (p10-p90)
of: share of the body silhouette that the item covers, share of the item outside the silhouette, standoff outside the silhouette per body part (p50 / p90 of
the distance of the outside pixels, px; 1 px = 2.78 cm; integer, so the quantisation is 1 px); z range from the top / bottom row (z = 0.07 - row / (36 cos 28.4557)).
Then the same pooled over all actions, the data-quality lists, and outliers by a fixed rule (outside the Tukey fences, 1.5 x IQR, of their layer).
"""
import json, sys
from collections import Counter, defaultdict
import numpy as np

PXM, COS = 36.0, np.cos(np.radians(28.4557))
ACTIONS = ["walk_unarmed", "walk_armed", "run_unarmed", "run_armed", "stand", "fidget_1", "fidget_2", "combat_idle_1h", "combat_idle_2h", "attack_1h_slash",
           "attack_1h_pierce", "attack_1h_bash", "attack_2h_bash", "attack_2h_slash", "attack_2h_pierce", "combat_advance", "spell_directed", "spell_area",
           "attack_bow", "attack_crossbow", "get_hit", "die_forward", "die_backward", "mounted_walk", "mounted_run", "mounted_stand", "mounted_attack_1h",
           "mounted_attack_bow", "mounted_attack_crossbow", "mounted_attack_2h", "block", "punch", "bow", "salute", "eat"]
STAND = "4"
ZTOP = lambda y: 0.07 - y / (PXM * COS)


def q(x, p):
    return float(np.percentile(x, p)) if len(x) else float("nan")


def spread(x, nd=2):
    return "%.*f [%.*f-%.*f]" % (nd, q(x, 50), nd, q(x, 10), nd, q(x, 90))


def main():
    scan = json.load(open(sys.argv[1]))
    A, parts = scan["animations"], scan["parts"]
    by = defaultdict(list)
    for s, v in A.items():
        for l in v["layers"]:
            by[l].append(s)
    L = []
    w = L.append

    # --- coverage and data quality
    w("# Original wearable animations vs body 400 (`vd_scan.py`)\n")
    w("Regenerate: `body_part_raster.py ../model/UO_Body_0x190.blend parts.npz`, `vd_scan.py <client> scan.json --parts parts.npz`, `vd_scan_report.py scan.json docs/qa/vd_scan.md client/extract/vd_scan_layers.json`.")
    w("Sanity: for the stand action the per-part cover equals `client/extract/layer_analysis.json` (frame 0 only; median |diff| 0.000, p95 0.031 over 3465 values).")
    w("Reading: the standoff outside the silhouette is a LOWER bound of the item thickness (inside the silhouette the item hides the body) and is integer (1 px = 2.78 cm). "
      "Clothing (shirt, pants, shoes, gloves, arms, helm, torso armour) has p50 = 1 px at every part with p10-p90 = 1-1: there is no spread to calibrate a thickness from; "
      "only loose parts (cloak, robes, dresses, hair, hand-held items) stand out further. Bands are proportional to the body bbox of the frame (head ... feet); parts are the nearest part of OUR 3D body.\n")
    nfr = sum(sum(r["frames"]) for v in A.values() for r in v["actions"].values())
    w("%d animations with frames (%s), %d tiledata animations without data in the client; %d frames over 35 actions x 5 directions." % (
        len(A), ", ".join("%s %d" % kv for kv in sorted(Counter(s.split(":")[0] for s in A).items())), len(scan["no_frames"]), nfr))
    inc = {s: [a for a, r in v["actions"].items() if 0 in r["frames"]] for s, v in A.items()}
    inc = {s: a for s, a in inc.items() if a}
    w("Complete (all 35 x 5 blocks): %d; incomplete: %d (%s)." % (len(A) - len(inc), len(inc), ", ".join("%s: %d actions" % (s, len(a)) for s, a in sorted(inc.items()))))
    mism = Counter(s for s, v in A.items() for r in v["actions"].values() if r["frame_count_mismatch"])
    w("Frame count differs from the body 400 in some blocks: %s." % (", ".join("%s (%d actions)" % kv for kv in mism.items()) or "none"))
    empty = Counter({s: sum(r["empty"] for r in v["actions"].values()) for s, v in A.items()})
    w("Frames without image (placeholder or empty): %d in %d animations." % (sum(empty.values()), sum(1 for x in empty.values() if x)))
    clip = {s: sum(r.get("clip", 0) for r in v["actions"].values()) for s, v in A.items()}
    clip = {s: c for s, c in clip.items() if c}
    w("Pixels outside the 256x256 canvas (anchor 128,192): %s.\n" % (", ".join("%s %d px" % kv for kv in sorted(clip.items())) or "none"))
    nof = defaultdict(list)
    for s, v in scan["no_frames"].items():
        for l in v["layers"]:
            nof[l].append(v["items"][0] if v["items"] else s)
    w("Tiledata animations with no frames (item invisible in this client), by layer: " + ", ".join("%s %d" % (l, len(x)) for l, x in sorted(nof.items())) + ".\n")

    # --- stand, per layer
    w("## Stand (action 4), per layer: median [p10-p90] between animations\n")
    w("| layer | n | cover of body | outside share | z top (m) | z bottom (m) | standoff p50 (px) | standoff p90 (px) | max (px) |")
    w("|---|---|---|---|---|---|---|---|---|")
    layers = {}
    for l, ss in sorted(by.items()):
        r = [A[s]["actions"][STAND] for s in ss if "out_frac" in A[s]["actions"].get(STAND, {})]
        if not r:
            continue
        cv = [x["cover"] for x in r if x["cover"] is not None]
        layers[l] = dict(n=len(r), cover=spread(cv, 3), out_frac=spread([x["out_frac"] for x in r], 3),
                         ztop=spread([ZTOP(x["y0"]) for x in r]), zbot=spread([ZTOP(x["y1"]) for x in r]),
                         p50=spread([x["dist"]["p50"] for x in r], 1), p90=spread([x["dist"]["p90"] for x in r], 1), max=spread([x["dist"]["max"] for x in r], 1))
        w("| %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (l, len(r), *[layers[l][k] for k in ("cover", "out_frac", "ztop", "zbot", "p50", "p90", "max")]))

    # --- per part, stand
    w("\n## Stand, per layer and body part: share of the part covered (median [p10-p90]) and standoff p50 / p90 (px, median of the animations that have outside pixels at that part, n of them)\n")
    w("| layer | part | cover | n out | standoff p50 | standoff p90 |")
    w("|---|---|---|---|---|---|")
    gate = {}
    for l, ss in sorted(by.items()):
        r = [A[s]["actions"][STAND] for s in ss if "cover_part" in A[s]["actions"].get(STAND, {})]
        if len(r) < 3:
            continue
        for g in parts:
            cv = [x["cover_part"][g] for x in r if g in x["cover_part"]]
            op = [x["out_part"][g] for x in r if g in x["out_part"] and x["out_part"][g]["n"] >= 5]
            if not cv or q(cv, 50) < 0.05:
                continue
            gate[(l, g)] = ([o["p50"] for o in op], [o["p90"] for o in op])
            w("| %s | %s | %s | %d | %s | %s |" % (l, g, spread(cv, 2), len(op), spread([o["p50"] for o in op], 1) if op else "-", spread([o["p90"] for o in op], 1) if op else "-"))

    # --- all actions pooled, per layer: extents
    w("\n## All 35 actions, per layer: extent from the anchor (px, min / max over the animations of the layer) and median cover of the body\n")
    w("| layer | n | left (min) | right (max) | up (min) | down (max) | median cover | median outside share |")
    w("|---|---|---|---|---|---|---|---|")
    for l, ss in sorted(by.items()):
        rs = [r for s in ss for r in A[s]["actions"].values() if "out_frac" in r]
        if not rs:
            continue
        w("| %s | %d | %d | %d | %d | %d | %.3f | %.3f |" % (l, len(ss), min(r["x0"] for r in rs), max(r["x1"] for r in rs), min(r["y0"] for r in rs), max(r["y1"] for r in rs),
                                                         q([r["cover"] for r in rs if r["cover"] is not None], 50), q([r["out_frac"] for r in rs], 50)))

    # --- per action
    w("\n## Per action: animations with data, median cover of the body and standoff p90 (px), over all layers except hand-held\n")
    w("| action | name | animations | median cover | median standoff p90 | blocks with frame-count mismatch |")
    w("|---|---|---|---|---|---|")
    worn = [s for s in A if not set(A[s]["layers"]) <= {"OneHanded", "TwoHanded"}]
    for a in range(35):
        rs = [A[s]["actions"][str(a)] for s in worn if "out_frac" in A[s]["actions"].get(str(a), {})]
        w("| %d | %s | %d | %.3f | %.1f | %d |" % (a, ACTIONS[a], len(rs), q([r["cover"] for r in rs if r["cover"] is not None], 50), q([r["dist"]["p90"] for r in rs], 50),
                                                   sum(1 for s in A if A[s]["actions"].get(str(a), {}).get("frame_count_mismatch"))))

    # --- outliers
    w("\n## Outliers in the stand frames (outside the Tukey fences of their layer on cover or standoff p90; layers with >= 5 animations)\n")
    out = []
    for l, ss in sorted(by.items()):
        if len(ss) < 5:
            continue
        for key, get in (("cover", lambda r: r["cover"]), ("standoff p90", lambda r: r["dist"]["p90"])):
            vals = {s: get(A[s]["actions"][STAND]) for s in ss if "out_frac" in A[s]["actions"].get(STAND, {})}
            vals = {s: v for s, v in vals.items() if v is not None}
            if len(vals) < 5:
                continue
            q1, q3 = q(list(vals.values()), 25), q(list(vals.values()), 75)
            lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            for s, v in vals.items():
                if v < lo or v > hi:
                    out.append((l, s, key, v, "%.2f..%.2f" % (lo, hi), ", ".join(A[s]["items"][:2])))
    w("| layer | animation | metric | value | fences | items |")
    w("|---|---|---|---|---|---|")
    for o in out:
        w("| %s | %s | %s | %.3f | %s | %s |" % o)
    w("\n%d outlier entries." % len(out))

    open(sys.argv[2], "w").write("\n".join(L) + "\n")
    if len(sys.argv) > 3:
        json.dump(dict(layers=layers, parts={"%s/%s" % k: dict(p50=v[0], p90=v[1]) for k, v in gate.items()}), open(sys.argv[3], "w"), indent=1)
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
