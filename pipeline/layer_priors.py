"""Phase 1 of docs/plans/original_items_calibration.md: per-slot priors from the original wearables, all actions, from the output of `vd_scan.py --parts`.

    python layer_priors.py <scan.json> <layer_priors.json> <layer_priors.md>

Data-quality filter (one place, reused later): an animation is used only when it is in anim.mul..anim5.mul (the .uop ones are not scanned), is complete (all 35 actions with
all 5 directions), has no pixel outside the 256x256 canvas, is not a Nelderim-custom id (420-422 of anim3 / anim4), and - for layers that must lie on the body - covers at least
1 % of the body 400 silhouette in stand (otherwise it is not aligned to the body 400 anchor). The rest is listed with the reason.
Per layer and body part (parts of OUR 3D body nearest to each pixel): items n, share of the part covered (stand), standoff outside the body silhouette p50 / p90 / max (px, stand
and the median over all 35 actions of every item), highest / lowest row of the item at the part as z (m, z = 0.07 - row / (36 cos 28.4557); lowest row at the arm = sleeve end,
at torso / thigh / shin = hem). Every statistic is the median and the spread (p10-p90) BETWEEN items, not the mean of pixels.
Gate 1: the spread between items must be small enough to be a prior; here: (p90 - p10) of the p50 standoff <= 1 px for >= 80 % of the (layer, part) cells with >= 5 items
of the layers that lie on the body (hand-held OneHanded / TwoHanded are reported apart: their size is the weapon, not a slot property).
"""
import json, sys
from collections import defaultdict
import numpy as np

PXM, COS = 36.0, np.cos(np.radians(28.4557))
Z = lambda row: 0.07 - row / (PXM * COS)
BODY_LAYERS = {"Shoes", "Pants", "Shirt", "Gloves", "Arms", "InnerTorso", "MiddleTorso", "OuterTorso", "OuterLegs", "Waist", "Helm", "Hair"}
CUSTOM = {"anim3:420", "anim3:421", "anim3:422", "anim4:420", "anim4:421", "anim4:422"}
STAND = "4"
ACTIONS = [str(a) for a in range(35)]


def spread(v):
    v = [x for x in v if x is not None]
    return [round(float(np.percentile(v, q)), 2) for q in (10, 50, 90)] if v else None


def keep(src, v):
    """None when used, else the reason"""
    if src in CUSTOM:
        return "Nelderim custom id"
    if len(v["actions"]) < 35 or any(0 in r["frames"] for r in v["actions"].values()):
        return "incomplete (%d of 35 actions, blocks missing)" % len(v["actions"])
    if sum(r.get("clip", 0) for r in v["actions"].values()):
        return "pixels outside the 256x256 canvas"
    st = v["actions"].get(STAND, {})
    if set(v["layers"]) & BODY_LAYERS and not (st.get("cover") or 0) >= 0.01:
        return "no overlap with the body 400 in stand (not aligned to its anchor)"
    return None


def main():
    scan = json.load(open(sys.argv[1]))
    A, parts = scan["animations"], scan["parts"]
    used, dropped = {}, {}
    for s, v in A.items():
        r = keep(s, v)
        (dropped.__setitem__(s, r) if r else used.__setitem__(s, v))
    by = defaultdict(list)
    for s, v in used.items():
        for l in v["layers"]:
            by[l].append(s)
    out = dict(filter=dict(used=len(used), dropped=len(dropped), reasons={s: r for s, r in sorted(dropped.items())}), layers={})
    for l, ss in sorted(by.items()):
        L = dict(n=len(ss), items=ss, z_top=spread([Z(A[s]["actions"][STAND]["y0"]) for s in ss]), z_bottom=spread([Z(A[s]["actions"][STAND]["y1"]) for s in ss]), parts={})
        for g in parts:
            cell = {}
            st = [A[s]["actions"][STAND] for s in ss]
            cv = [r["cover_part"].get(g) for r in st if "cover_part" in r]
            if not cv or np.median([x or 0 for x in cv]) < 0.05:
                continue
            ops = [(s, A[s]["actions"][STAND]["out_part"][g]) for s in ss if g in A[s]["actions"][STAND].get("out_part", {}) and A[s]["actions"][STAND]["out_part"][g]["n"] >= 5]
            pool = {k: [] for k in ("p50", "p90", "max")}
            for s in ss:
                per = [A[s]["actions"][a]["out_part"][g] for a in ACTIONS if g in A[s]["actions"][a].get("out_part", {}) and A[s]["actions"][a]["out_part"][g]["n"] >= 5]
                for k in pool:
                    pool[k].append(float(np.median([o[k] for o in per])) if per else None)
            ys = [A[s]["actions"][STAND]["part_y"][g] for s in ss if g in A[s]["actions"][STAND].get("part_y", {})]
            cell = dict(n_cover=len(cv), cover=spread(cv), n_out=len(ops),
                        stand=dict(p50=spread([o["p50"] for _, o in ops]), p90=spread([o["p90"] for _, o in ops]), max=spread([o["max"] for _, o in ops])),
                        all_actions={k: spread(v) for k, v in pool.items()},
                        z_high=spread([Z(y[0]) for y in ys]), z_low=spread([Z(y[1]) for y in ys]),
                        item_p50={s: o["p50"] for s, o in ops})
            L["parts"][g] = cell
        out["layers"][l] = L
    # Gate 1
    allcells = [(l, g, c) for l, L in out["layers"].items() for g, c in L["parts"].items() if c["n_out"] >= 5 and c["stand"]["p50"]]
    held = [c["stand"]["p50"][2] - c["stand"]["p50"][0] <= 1.0 for l, _, c in allcells if l in ("OneHanded", "TwoHanded")]
    cells = [x for x in allcells if x[0] not in ("OneHanded", "TwoHanded")]
    ok = [c["stand"]["p50"][2] - c["stand"]["p50"][0] <= 1.0 for _, _, c in cells]
    floor = [c["stand"]["p50"][1] <= 1.0 for _, _, c in cells]
    out["gate1"] = dict(cells=len(cells), spread_le_1px=int(sum(ok)), share=round(float(np.mean(ok)), 3) if ok else None, median_p50_at_floor_1px=int(sum(floor)), hand_held_cells=len(held), hand_held_spread_le_1px=int(sum(held)),
                        failing=["%s/%s" % (l, g) for (l, g, c), o in zip(cells, ok) if not o],
                        passed=bool(ok and np.mean(ok) >= 0.8))
    json.dump(out, open(sys.argv[2], "w"), indent=1)

    w = []
    w.append("# Per-slot priors from the original wearables (`layer_priors.py`, Phase 1)\n")
    w.append("Source: `client/extract/vd_scan.json.gz` (all 35 actions x 5 directions x frames of the animations in anim.mul..anim5.mul against body 400, parts of our 3D body). Statistics are the median and "
             "[p10-p90] BETWEEN items. z in metres (ground = 0), standoff in px outside the body 400 silhouette (1 px = 2.78 cm; an item that is thicker than 0 shows as >= 1 px, so it is a coarse lower bound).\n")
    w.append("Filter: %d animations used, %d dropped:" % (len(used), len(dropped)))
    reasons = defaultdict(list)
    for s, r in dropped.items():
        reasons[r.split(" (")[0]].append(s)
    for r, ss in sorted(reasons.items()):
        w.append("- %s: %d (%s)" % (r, len(ss), ", ".join(ss[:12]) + (" ..." if len(ss) > 12 else "")))
    g = out["gate1"]
    w.append("\n**Gate 1 (body layers):** %d (layer, part) cells with >= 5 items; spread (p90 - p10) of the stand p50 standoff <= 1 px in %d of them (%.0f %%) -> %s. In %d of them the median p50 is the 1 px floor "
             "of the measure, i.e. the priors say 'thinner than about one pixel' and nothing finer. Failing cells: %s. Hand-held items (not in the gate): spread <= 1 px in %d of %d cells (the weapon size varies).\n" % (
        g["cells"], g["spread_le_1px"], 100 * (g["share"] or 0), "PASSED" if g["passed"] else "FAILED", g["median_p50_at_floor_1px"], ", ".join(g["failing"]) or "none", g["hand_held_spread_le_1px"], g["hand_held_cells"]))
    w.append("## Per layer: items, z range of the whole item (stand)\n")
    w.append("| layer | items | z top | z bottom |")
    w.append("|---|---|---|---|")
    for l, L in out["layers"].items():
        w.append("| %s | %d | %s | %s |" % (l, L["n"], L["z_top"], L["z_bottom"]))
    w.append("\n## Per layer and part (stand): cover of the part, standoff p50 / p90 / max (px), z of the highest and lowest row of the item at the part (lowest at the arm = sleeve end, at torso / thigh / shin = hem); `all` = median over the 35 actions of every item, p90\n")
    w.append("| layer | part | n cover | cover | n out | p50 | p90 | max | p90 all | z high | z low |")
    w.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for l, L in out["layers"].items():
        if l in ("OneHanded", "TwoHanded"):
            continue
        for gp, c in L["parts"].items():
            st = c["stand"]
            w.append("| %s | %s | %d | %s | %d | %s | %s | %s | %s | %s | %s |" % (l, gp, c["n_cover"], c["cover"], c["n_out"], st["p50"], st["p90"], st["max"], c["all_actions"]["p90"], c["z_high"], c["z_low"]))
    open(sys.argv[3], "w").write("\n".join(w) + "\n")
    print("\n".join(w[:14]))


if __name__ == "__main__":
    main()
