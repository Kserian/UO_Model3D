"""Audit of the rig: which bones and which per-frame keys earn their place (measured, not assumed).

    python audit_rig.py bones [../model/UO_Body_0x190.blend]        # table: bone, parent, deform, weighted vertices, keyed motion
    python audit_rig.py ablate NAME [..blend]                       # silhouette IoU of the body (1050 frames) without a group of bones
    NAME: twist | toes | thumbs | fingers | neck | spine | noscale  (several: twist,toes)

`bones` reads the actions of the .blend: per bone the mean / max rotation angle of the keys over all 35 actions, the largest location and the
largest scale deviation. A bone whose keys are all the identity (twist bones) is a no-op for the animation.
`ablate` builds a temporary copy of the .blend (the file given is never saved): the weights of the named bones are merged into their
parent bone (twist -> limb, toes -> foot, thumbs / fingers -> hand, neck -> head, spine -> chest) or the scale keys are set to 1 (`noscale`),
renders the part labels with body_part_raster.py (no Cycles, ~30 s) and prints the IoU against the original frames (body_part_qa.analyse).
Results of 2026-10-03: docs/qa/audit_rig.json. Needs: pip install numpy pillow scipy "bpy==4.2.*".
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "model", "UO_Body_0x190.blend")

MERGE = {
    "twist": {"upper_arm_twist.%s" % s: "upper_arm.%s" % s for s in "LR"} | {"forearm_twist.%s" % s: "forearm.%s" % s for s in "LR"},
    "toes": {"toe.%s" % s: "foot.%s" % s for s in "LR"},
    "thumbs": {"finger1-%d.%s" % (j, s): "hand.%s" % s for s in "LR" for j in (1, 2, 3)},
    "fingers": {"finger%d-%d.%s" % (f, j, s): "hand.%s" % s for s in "LR" for f in range(1, 6) for j in (1, 2, 3)},
    "neck": {"neck": "head"},
    "spine": {"spine": "chest"},
}


def bones(blend):
    import bpy, collections, math
    from mathutils import Quaternion
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    gname = {g.index: g.name for g in body.vertex_groups}
    nv, ws = collections.Counter(), collections.defaultdict(float)
    for v in body.data.vertices:
        for g in v.groups:
            nv[gname[g.group]] += 1; ws[gname[g.group]] += g.weight
    keys = collections.defaultdict(lambda: {"q": {}, "l": {}, "s": {}})
    for a in bpy.data.actions:
        for fc in a.fcurves:
            m = re.match(r'pose\.bones\["(.+?)"\]\.(\w+)', fc.data_path)
            k = {"rotation_quaternion": "q", "location": "l", "scale": "s"}.get(m.group(2)) if m else None
            if k:
                for kp in fc.keyframe_points:
                    keys[m.group(1)][k].setdefault((a.name, int(kp.co[0])), [None] * 4)[fc.array_index] = kp.co[1]
    out = []
    for b in rig.data.bones:
        d = keys.get(b.name)
        ang = []
        if d:
            for v in d["q"].values():
                if None not in v:
                    a = math.degrees(Quaternion(v).angle); ang.append(a if a <= 180 else 360 - a)
        loc = max((math.sqrt(sum(x * x for x in v[:3])) for v in d["l"].values() if None not in v[:3]), default=0) if d else 0
        sc = max((max(abs(x - 1) for x in v[:3]) for v in d["s"].values() if None not in v[:3]), default=0) if d else 0
        out.append(dict(bone=b.name, parent=b.parent.name if b.parent else None, deform=b.use_deform, verts=nv.get(b.name, 0), weight=round(ws.get(b.name, 0), 2),
                        keys=len(ang), mean_angle=round(sum(ang) / len(ang), 2) if ang else 0, max_angle=round(max(ang), 2) if ang else 0,
                        max_loc=round(loc, 4), max_scale_dev=round(sc, 3)))
    for r in out:
        print("%-22s %-16s def=%d verts=%5d w=%8.2f keys=%3d angle mean %6.2f max %6.2f loc %.3f scale %.3f" % (
            r["bone"], r["parent"] or "-", r["deform"], r["verts"], r["weight"], r["keys"], r["mean_angle"], r["max_angle"], r["max_loc"], r["max_scale_dev"]))
    return out


def make_variant(src, dst, names):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=src)
    body = bpy.data.objects["UO_Body"]; vg = body.vertex_groups
    merge = {}
    for n in names:
        merge.update(MERGE.get(n, {}))
    for s, d in merge.items():
        if s not in vg:
            continue
        if d not in vg:
            vg.new(name=d)
        si, di = vg[s].index, vg[d].index
        for v in body.data.vertices:
            w = next((g.weight for g in v.groups if g.group == si), 0.0)
            if w:
                vg[d].add([v.index], w, "ADD")
        vg.remove(vg[s])
    if "noscale" in names:
        for a in bpy.data.actions:
            for fc in a.fcurves:
                if re.match(r'pose\.bones\["(.+?)"\]\.scale', fc.data_path):
                    for kp in fc.keyframe_points:
                        kp.co[1] = kp.handle_left[1] = kp.handle_right[1] = 1.0
                    fc.update()
    bpy.ops.wm.save_as_mainfile(filepath=dst, copy=True)


def ablate(blend, names):
    import numpy as np
    sys.path.insert(0, HERE)
    import body_part_qa as q
    with tempfile.TemporaryDirectory() as tmp:
        var, npz = os.path.join(tmp, "v.blend"), os.path.join(tmp, "v.npz")
        subprocess.run([sys.executable, __file__, "_variant", blend, var, ",".join(names)], check=True)
        subprocess.run([sys.executable, os.path.join(HERE, "body_part_raster.py"), var, npz], check=True, stdout=subprocess.DEVNULL)
        d = np.load(npz)
        iou, sp, mo, ok = q.analyse(d["lab"], d["key"], [str(p) for p in d["parts"]])
        r = dict(variant=",".join(names), iou=round(float(iou[ok].mean()), 5), model_plus=round(float(mo[ok].sum(1).mean()), 2), sprite_plus=round(float(sp[ok].sum(1).mean()), 2))
        print(json.dumps(r))
        return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "_variant":
        make_variant(os.path.abspath(a[1]), os.path.abspath(a[2]), a[3].split(","))
    elif a and a[0] == "bones":
        bones(os.path.abspath(a[1] if len(a) > 1 else DEFAULT))
    elif a and a[0] == "ablate":
        ablate(os.path.abspath(a[2] if len(a) > 2 else DEFAULT), a[1].split(","))
    else:
        print(__doc__)
