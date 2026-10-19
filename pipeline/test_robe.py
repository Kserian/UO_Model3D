"""Loose garments (robe, dress, skirt, kilt, cloak): how well does a robe bound with a given PART follow the legs like the original one?

    python test_robe.py [--part robe] [--follow "thigh=0.9,0,1,0.5;shin=0.6,0,1,0.6"] [--sprite pipeline/body13/mul/anim_0469.vd] [--actions ...]
                        [--tmp DIR] [--out qa.json] [--img overlay.png] [--hip 0.95]

A replica of a robe (the part of the body skin above the hips moved out by 3.5 cm, plus a tube from the waist to the hem whose radii are measured on the original robe 469
in the stand pose: half width 0.215 m at the hip -> 0.30 m at the hem, half depth 0.22 m) is bound with `uo_bind_item.py` PART (`robe`: FOLLOW = how much of the thigh /
shin weight of the skin underneath stays on the leg, the rest moves with the pelvis), rendered with the whole pipeline (render_uo_layer.py) and compared with the sprite
frame by frame. The numbers that matter are for the part BELOW the hips (rows under `--hip` m): the legs push the hem there. Output per action: IoU of the lower part,
`wide` = how many px the replica's hem is wider than the sprite's (positive: the legs push the cloth too far out), `narrow` the opposite, `hem` = mean error of the lowest row.
"""
import argparse, json, os, subprocess, sys, tempfile, re

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
sys.path.insert(0, os.path.join(HERE, "body13"))
import vdtool                                                                # noqa: E402
from itemframes import canvas as sprite_canvas                              # noqa: E402

DEFAULT_ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward"
PRE = r'''
import bpy, os, re, json, numpy as np, bmesh
from mathutils import Vector
scripts = os.environ["UO_TEST_SCRIPTS"]; env = os.environ
body, rig = bpy.data.objects["UO_Body"], bpy.data.objects["UO_Rig"]
me = body.data
rig.data.pose_position = "REST"; bpy.context.view_layer.update()
names = [g.name for g in body.vertex_groups]
def base(n):
    b = n[:-2] if n.endswith((".L", ".R")) else n
    return "hand" if b.startswith("finger") else b
dom = [base(names[max(v.groups, key=lambda g: g.weight).group]) if v.groups else "" for v in me.vertices]
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
nrm = np.empty_like(co); me.vertices.foreach_get("normal", nrm.ravel())
M = np.array(body.matrix_world); zw = co @ M[:3, :3].T + M[:3, 3]
keep = np.isin(dom, ["pelvis", "spine", "chest", "clavicle", "upper_arm", "neck"]) & (zw[:, 2] >= float(env["ROBE_HIP"]) + 0.02)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
for v in bm.verts:
    v.co += type(v.co)(nrm[v.index] * 0.035)
for lay in list(bm.verts.layers.deform):
    bm.verts.layers.deform.remove(lay)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context="VERTS")
# the skirt tube: waist -> hem, ellipse, radii measured on the original robe (stand): half width 0.215 -> 0.30, half depth 0.22
N, K = 40, 28
PROF = json.load(open(env["ROBE_PROFILE"])) if env.get("ROBE_PROFILE") else None
z_top, z_hem = float(env["ROBE_HIP"]) + 0.07, float(env["ROBE_HEM"])
ring = []
for k in range(K + 1):
    z = z_top + (z_hem - z_top) * k / K
    t = (z_top - z) / (z_top - z_hem)
    ax = 0.215 + (0.30 - 0.215) * t ** 0.8; ay = 0.17 + (0.22 - 0.17) * min(1, t * 3)
    if env.get("ROBE_PROFILE"):                                          # radii measured on another original (--derive): half width / depth by height
        ax = float(np.interp(z, PROF["z"][::-1], PROF["ax"][::-1])); ay = float(np.interp(z, PROF["z"][::-1], PROF["ay"][::-1]))
    ring.append([bm.verts.new((ax * np.cos(2 * np.pi * i / N), -0.02 + ay * np.sin(2 * np.pi * i / N), z)) for i in range(N)])
for k in range(K):
    for i in range(N):
        bm.faces.new((ring[k][i], ring[k][(i + 1) % N], ring[k + 1][(i + 1) % N], ring[k + 1][i]))
item_me = bpy.data.meshes.new("robe_replica"); bm.to_mesh(item_me); bm.free()
item = bpy.data.objects.new("robe_replica", item_me); item.matrix_world = body.matrix_world.copy()
clo = bpy.data.collections["Clothing"]
for o in list(clo.all_objects):
    bpy.data.objects.remove(o, do_unlink=True)
clo.objects.link(item)
shirt = bpy.data.objects.get("Example_Shirt")
bpy.context.view_layer.update()
for o in bpy.context.view_layer.objects:
    o.select_set(False)
item.select_set(True); bpy.context.view_layer.objects.active = item
text = open(os.path.join(scripts, "uo_bind_item.py")).read()
if env.get("ROBE_FOLLOW"):                                               # "thigh=0.9,0,1,0.5;shin=0.6,0,1,0.6"
    fol = {}
    for part in env["ROBE_FOLLOW"].split(";"):
        k, v = part.split("="); fol[k] = tuple(float(x) for x in v.split(",")) if "," in v else float(v)
    fol.update({"hand": 0.0, "foot": 0.0})
    text, n = re.subn(r'^    "robe":.*$', '    "robe": (None, %r),' % (fol,), text, count=1, flags=re.M); assert n == 1
if env.get("ROBE_DROP"):
    text, n = re.subn(r"^CLOTH_DROP = [0-9.]+", "CLOTH_DROP = %s" % env["ROBE_DROP"], text, count=1, flags=re.M); assert n == 1
if env.get("ROBE_MARGIN"):
    text, n = re.subn(r"^CLOTH_MARGIN = [0-9.]+", "CLOTH_MARGIN = %s" % env["ROBE_MARGIN"], text, count=1, flags=re.M); assert n == 1
if env.get("ROBE_KAPPA"):
    text, n = re.subn(r"^CLOTH_KAPPA = [0-9.]+", "CLOTH_KAPPA = %s" % env["ROBE_KAPPA"], text, count=1, flags=re.M); assert n == 1
text = re.sub(r"^PART = .*$", "PART = %r" % env["ROBE_PART"], text, count=1, flags=re.M)
exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
print("test_robe: %d vertices, PART %s" % (len(item.data.vertices), env["ROBE_PART"]))
'''


def measure(frames_root, sprites, canvas, anchor, hip, imgs_for=()):
    st = ndimage.generate_binary_structure(2, 2)
    row_hip = int(round(anchor[1] - (hip - 0.07) * 36 * np.cos(np.radians(28.4557))))
    rows, imgs = [], []
    for act in sorted(os.listdir(frames_root)):
        a = int(act[:2])
        for d in range(5):
            fdir = os.path.join(frames_root, act, "dir%d" % d)
            for fn in sorted(os.listdir(fdir)):
                i = int(fn[:2])
                R = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))
                G = sprite_canvas(sprites.get((a, d)), i, anchor, canvas)
                r, g = R[..., 3] > 0, G[..., 3] > 0
                if not g.any():
                    continue
                rl, gl = r[row_hip:], g[row_hip:]
                inter, union = (rl & gl).sum(), max((rl | gl).sum(), 1)
                # width of the hem: mean over the lowest 8 rows of the sprite
                ys = np.nonzero(g.any(1))[0]; hem_rows = [y for y in range(ys.max() - 7, ys.max() + 1) if g[y].any()]      # rows without sprite pixels (gaps between the legs of a skirt) are skipped
                wr = [(np.ptp(np.nonzero(r[y])[0]) + 1) if r[y].any() else 0 for y in hem_rows]; wg = [np.ptp(np.nonzero(g[y])[0]) + 1 for y in hem_rows]
                rows.append(dict(a=a, d=d, i=i, iou=inter / union, iou_all=(r & g).sum() / max((r | g).sum(), 1), hem_dw=float(np.mean(wr) - np.mean(wg)),
                                 hem_y=float((np.nonzero(r.any(1))[0].max() if r.any() else ys.max()) - ys.max())))
                if (act, d, i) in imgs_for:
                    im = np.zeros(r.shape + (3,), np.uint8) + 25
                    im[r & g] = (190, 190, 190); im[r & ~g] = (230, 60, 60); im[g & ~r] = (60, 120, 255)
                    imgs.append(im)
    return rows, imgs


def summarize(rows):
    out = dict(frames=len(rows), iou_low=float(np.mean([r["iou"] for r in rows])), iou_all=float(np.mean([r["iou_all"] for r in rows])),
               hem_wider=float(np.mean([max(r["hem_dw"], 0) for r in rows])), hem_narrower=float(np.mean([max(-r["hem_dw"], 0) for r in rows])),
               hem_abs=float(np.mean([abs(r["hem_dw"]) for r in rows])), hem_y_abs=float(np.mean([abs(r["hem_y"]) for r in rows])), by_action={})
    for a in sorted({r["a"] for r in rows}):
        q = [r for r in rows if r["a"] == a]
        out["by_action"][str(a)] = dict(iou_low=float(np.mean([r["iou"] for r in q])), hem_dw=float(np.mean([r["hem_dw"] for r in q])),
                                        hem_abs=float(np.mean([abs(r["hem_dw"]) for r in q])))
    return out


def sprite_profile(sprites, hip):
    """half width (dirs 0 and 4 = front / back) and half depth (dir 2 = profile) of the stand silhouette by height (m), from the hip to the hem, and the hem height"""
    cos = np.cos(np.radians(28.4557))
    G = {d: sprite_canvas(sprites[(4, d)], 0, (128, 192), (256, 256))[..., 3] > 0 for d in range(5)}
    rows = np.nonzero(np.any([g.any(1) for g in G.values()], 0))[0]
    hem = 0.07 - (rows[-1] + 1 - 192) / (36 * cos)
    zs = np.linspace(hip + 0.07, hem, 29)
    def half(d):
        w = []
        for z in zs:
            r = int(round(192 - (z - 0.07) * 36 * cos)); xs = np.nonzero(G[d][min(max(r, 0), 255)])[0]
            w.append((xs.max() - xs.min() + 1) / 72.0 if xs.size else 0.0)
        return np.array(w)
    ax = (half(0) + half(4)) / 2; ay = half(2)
    sm = lambda v: np.array([np.median(v[max(i - 1, 0):i + 2]) for i in range(len(v))])
    return dict(z=[float(z) for z in zs], ax=[float(x) for x in sm(ax)], ay=[float(x) for x in sm(ay)], hem=float(hem))


def run(a, tmp):
    os.makedirs(tmp, exist_ok=True)
    pre = os.path.join(tmp, "pre.py"); open(pre, "w").write("exec(%r)\n" % PRE)
    blend = os.path.abspath(os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    prof_path = None
    if a.derive:                                                         # radii and hem of the tube from the stand pose of --sprite
        _, bl = vdtool.read_vd(a.sprite)
        prof = sprite_profile({(b["action"], b["dir"]): b for b in bl}, a.hip)
        a.hem = prof.pop("hem") + a.hem_offset             # the lowest sprite row is the FRONT edge of the hem: lower on screen than the hem height (robe 469: 0.007 -> the hand-set 0.08)
        prof_path = os.path.join(tmp, "profile.json"); json.dump(prof, open(prof_path, "w"))
    env = dict(os.environ, UO_TEST_SCRIPTS=HERE, ROBE_PART=a.part, ROBE_HIP=str(a.hip), ROBE_HEM=str(a.hem), ROBE_FOLLOW=a.follow or "", ROBE_MARGIN=str(a.margin) if a.margin is not None else "", ROBE_KAPPA=str(a.kappa) if a.kappa is not None else "", ROBE_DROP=str(a.drop) if a.drop is not None else "", ROBE_PROFILE=prof_path or "")
    actions = a.actions.split(",")
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, tmp, "--pre", pre, 'LAYER="clothing"', "ONLY=%r" % (actions,),
           "CANVAS=(256, 256)", "ANCHOR=(128, 192)"] + a.set
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        sys.exit("render failed:\n%s\n%s" % (r.stdout[-2500:], r.stderr[-2500:]))
    _, blocks = vdtool.read_vd(a.sprite)
    sprites = {(b["action"], b["dir"]): b for b in blocks}
    show = {("09_attack_1h_slash", 3, 1), ("00_walk_unarmed", 2, 2), ("00_walk_unarmed", 2, 6), ("02_run_unarmed", 2, 3), ("21_die_forward", 3, 2)}
    rows, imgs = measure(os.path.join(tmp, "clothing", "frames"), sprites, (256, 256), (128, 192), a.hip, show)
    return summarize(rows), imgs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="robe"); ap.add_argument("--follow"); ap.add_argument("--margin", type=float); ap.add_argument("--drop", type=float); ap.add_argument("--kappa", type=float); ap.add_argument("--hip", type=float, default=0.95); ap.add_argument("--hem", type=float, default=0.08)
    ap.add_argument("--hem-offset", type=float, default=0.073, help="with --derive: added to the hem height read from the lowest sprite row")
    ap.add_argument("--derive", action="store_true", help="radii and hem of the tube from the stand pose of --sprite (needed for any original but robe 469)")
    ap.add_argument("--sprite", default=os.path.join(HERE, "body13", "mul", "anim_0469.vd")); ap.add_argument("--actions", default=DEFAULT_ACTIONS)
    ap.add_argument("--tmp"); ap.add_argument("--out"); ap.add_argument("--img"); ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_robe_")
    s, imgs = run(a, tmp)
    print("PART %s follow %s | frames %d | lower-body IoU %.3f (whole %.3f) | hem width error: wider %.2f px, narrower %.2f px (abs %.2f) | hem height error %.2f px | %s" % (
        a.part, a.follow or "default", s["frames"], s["iou_low"], s["iou_all"], s["hem_wider"], s["hem_narrower"], s["hem_abs"], s["hem_y_abs"],
        " ".join("%s:%.2f" % (k, v["iou_low"]) for k, v in s["by_action"].items())))
    if a.out:
        json.dump(dict(args=vars(a), result=s), open(a.out, "w"), indent=1)
    if a.img and imgs:
        im = np.concatenate([np.pad(i[110:200, 80:176], ((1, 1), (1, 1), (0, 0)), constant_values=90) for i in imgs], 1)
        Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(a.img)
