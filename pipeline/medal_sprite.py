"""The necklace (ribbon + medal) drawn as 2D pixel art over the ORIGINAL body frames, from a posed 3D skeleton of it.

    python medal_sprite.py PATHS.json OUT_DIR [--base ../model/UO_Body_0x190.blend] [--actions 00_walk_unarmed,...] [--fixes fixes.json] [--vd out.vd]

At 36 px/m a necklace is 1-2 px wide, and a Cycles render of a 3D cord turns into smudges there; so it is drawn: the cord axis and the medal (centre, axes, radius; make_medal_necklace.py --paths)
follow the body skin (weights of the skin under each point; the lower V and the medal rigid on the chest), are posed per frame like an item (Armature modifier), projected with the UO camera
and drawn with a fixed width: the cord 2 px (a dark pixel row under a lighter one), the medal a shaded ellipse of its projected axes with a darker rim. A pixel is drawn only where the
item is not behind the 3D body (depth) and inside the silhouette of the ORIGINAL body frame (+1 px); from behind the medal is not drawn. fixes.json: {"action,frame,dir": [dx, dy]} moves a frame by whole pixels
(hand corrections). Writes OUT_DIR/frames/NN_action/dirK/II.png (256x256, anchor 128,192) + meta.json and, with --vd, the .vd (vdtool pack).
"""
import argparse, json, os, subprocess, sys
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument("paths"); ap.add_argument("out")
ap.add_argument("--base", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
ap.add_argument("--actions", default=""); ap.add_argument("--fixes", default=""); ap.add_argument("--vd", default="")
ap.add_argument("--medal-scale", type=float, default=0.85)            # drawn radius of the medal relative to the model's (the model's is 8.5 cm: 3 px)
ap.add_argument("--rigid-below", type=float, default=1.41)            # points under this height (|x| < 0.08) and the medal: rigid on the chest
ap.add_argument("--medal-px", type=float, default=2.9)               # radius of the drawn medal in px
ap.add_argument("--collar", type=float, default=0.72)                  # the cord at the neck is drawn this fraction of its width (round the neck, not out over the shoulders)
ap.add_argument("--collar-zmax", type=float, default=1.55)
ap.add_argument("--cord", default="128,24,30"); ap.add_argument("--cord-dark", default="88,12,18")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
CORD = tuple(int(x) for x in a.cord.split(",")); CORD_D = tuple(int(x) for x in a.cord_dark.split(","))
W = H = 256; ANCHOR = (128, 192); OANCHOR = (68, 86); STEP = 3
P = json.load(open(a.paths))
fixes = json.load(open(a.fixes)) if a.fixes else {}

bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.base))
sc = bpy.context.scene
rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
for o in list(bpy.data.collections["Clothing"].all_objects):
    bpy.data.objects.remove(o, do_unlink=True)
rig.data.pose_position = "REST"; bpy.context.view_layer.update()

# ---- camera: 36 px/m, the anchor on (128, 192) (render_uo_layer.py place_camera) ---------------------------------------------------------------------
cd = sc.camera.data


def anchor_px():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=W, y=H)) @ np.array(cam.matrix_world.inverted()) @ np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
    return np.array([(Pm[0] / Pm[3] + 1) * 0.5 * W, (1 - Pm[1] / Pm[3]) * 0.5 * H])


cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = W / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px()
k = (p1 - p0) / 0.01
want = np.array(ANCHOR, float) + (np.array(sc.get("uo_anchor_px", (OANCHOR[0] + 0.5, OANCHOR[1] + 0.0))) - np.array(OANCHOR))
sh = (want - p0) / k
cd.shift_x, cd.shift_y = [0.0 if abs(s * kk) < 1e-3 else float(s) for s, kk in zip(sh, k)]
assert np.abs(anchor_px() - want).max() < 1e-3

# ---- the points and their skin weights -------------------------------------------------------------------------------------------------------------
med = P["medal"]; R = med["radius"] * a.medal_scale
c0, rt, up, nm = (np.array(med[k_]) for k_ in ("centre", "right", "up", "normal"))
axis = np.array(P["axis"])
pts = np.vstack([axis, c0, c0 + rt * R, c0 + up * R, c0 + nm * R])     # cord axis ..., medal centre, right, up, front
n_axis = len(axis)
mesh = body.data
names = [g.name for g in body.vertex_groups]
deform = {n for n in names if rig.data.bones[n].use_deform}
tris, vcos = [], [tuple(v.co) for v in mesh.vertices]
mesh.calc_loop_triangles()
tris = [tuple(t.vertices) for t in mesh.loop_triangles]
bvh = BVHTree.FromPolygons(vcos, tris)
vw = [{names[g.group]: g.weight for g in v.groups if names[g.group] in deform} for v in mesh.vertices]
weights = []
for i, p in enumerate(pts):
    if i >= n_axis or (p[2] < a.rigid_below and abs(p[0]) < 0.08):
        weights.append({"chest": 1.0}); continue
    loc, nrm, fi, d = bvh.find_nearest(Vector(p))
    tri = tris[fi]
    bw = poly_3d_calc([Vector(vcos[j]) for j in tri], loc)
    acc = {}
    for j, w in zip(tri, bw):
        for n, x in vw[j].items():
            acc[n] = acc.get(n, 0.0) + w * x
    s = sum(acc.values()) or 1.0
    weights.append({n: x / s for n, x in acc.items() if x / s > 1e-3})
# pull the cord at the neck in towards the neck axis (the points lie on the shoulders beside the neck; the depth test tolerates a few cm), the higher the more
t_ = np.clip((pts[:n_axis, 2] - 1.45) / 0.06, 0.0, 1.0)
pts[:n_axis, 0] *= 1.0 - (1.0 - a.collar) * t_
pts[:n_axis, 1] = -0.03 + (pts[:n_axis, 1] + 0.03) * (1.0 - (1.0 - a.collar) * t_)
pts[:n_axis, 2] = np.minimum(pts[:n_axis, 2], a.collar_zmax)
ob = bpy.data.objects.new("uo_necklace_pts", bpy.data.meshes.new("uo_necklace_pts"))
sc.collection.objects.link(ob)
ob.data.from_pydata([tuple(p) for p in pts], [], [])
groups = {}
for i, wd in enumerate(weights):
    for n, x in wd.items():
        if n not in groups:
            groups[n] = ob.vertex_groups.new(name=n)
        groups[n].add([i], x, "REPLACE")
ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted()
m_ = ob.modifiers.new("Armature", "ARMATURE"); m_.object = rig; m_.use_vertex_groups = True; m_.use_bone_envelopes = False


# ---- per frame ---------------------------------------------------------------------------------------------------------------------------------------
def matrices():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    return dg, np.array(cam.calc_matrix_camera(dg, x=W, y=H)), np.array(cam.matrix_world.inverted()), np.array(cam.matrix_world)


def project(Xw, Pm, Vm):
    hv = np.c_[Xw, np.ones(len(Xw))] @ Vm.T; h = hv @ Pm.T
    return np.stack([(h[:, 0] / h[:, 3] + 1) * 0.5 * W, (1 - h[:, 1] / h[:, 3]) * 0.5 * H], 1), -hv[:, 2]


def body_depth(dg, Pm, Vm):
    """camera depth (m) of the posed 3D body per pixel (inf = none): the same rule as render_uo_layer.py raster()"""
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    me.calc_loop_triangles(); tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
    px, z = project((np.c_[co, np.ones(len(co))] @ Mw.T)[:, :3], Pm, Vm)
    Pp, Z = px[tri], z[tri]
    depth = np.full((H, W), np.inf)
    mn = np.floor(Pp.min(1)).astype(int); mx = np.ceil(Pp.max(1)).astype(int)
    A_, B_, C_ = Pp[:, 0], Pp[:, 1], Pp[:, 2]
    den = (B_[:, 1] - C_[:, 1]) * (A_[:, 0] - C_[:, 0]) + (C_[:, 0] - B_[:, 0]) * (A_[:, 1] - C_[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            xx = mn[t, 0] + dx; yy = mn[t, 1] + dy; cx, cy = xx + 0.5, yy + 0.5
            l0 = ((B_[t, 1] - C_[t, 1]) * (cx - C_[t, 0]) + (C_[t, 0] - B_[t, 0]) * (cy - C_[t, 1])) / den[t]
            l1 = ((C_[t, 1] - A_[t, 1]) * (cx - C_[t, 0]) + (A_[t, 0] - C_[t, 0]) * (cy - C_[t, 1])) / den[t]
            kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (xx >= 0) & (yy >= 0) & (xx < W) & (yy < H)
            z_ = l0[kk] * Z[t[kk], 0] + l1[kk] * Z[t[kk], 1] + (1 - l0[kk] - l1[kk]) * Z[t[kk], 2]
            np.minimum.at(depth, (yy[kk], xx[kk]), z_)
    return depth


def original_mask(act, d, i):
    import item_gif as G
    if not hasattr(original_mask, "meta"):
        original_mask.meta = json.load(open(os.path.join(G.BODY, "meta.json"))); original_mask.cache = {}
    key = (act, d)
    if key not in original_mask.cache:
        original_mask.cache[key] = [np.array(f.getchannel("A")) > 0 for f in G.body_frames(original_mask.meta, act, d)]
    fr = original_mask.cache[key]                                         # 256 x 256 canvas masks (item_gif.body_frames puts the frames on the canvas by their anchor)
    return fr[i] if i < len(fr) else None


def dilate(m):
    o = m.copy(); o[1:] |= m[:-1]; o[:-1] |= m[1:]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    return o


def stamp(img, zbuf, cx, cy, rad, color, z, zlim, allow):
    """a disc of radius `rad` px at (cx, cy), only where the item (depth z) is not behind the body (zlim) and the pixel is allowed"""
    x0, x1 = int(np.floor(cx - rad - 1)), int(np.ceil(cx + rad + 1)); y0, y1 = int(np.floor(cy - rad - 1)), int(np.ceil(cy + rad + 1))
    for y in range(max(y0, 0), min(y1, H - 1) + 1):
        for x in range(max(x0, 0), min(x1, W - 1) + 1):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= rad * rad and allow[y, x] and z <= zlim[y, x] and z <= zbuf[y, x] + 1e-9:
                img[y, x] = (*color, 255); zbuf[y, x] = z


def draw_frame(Xw, Pm, Vm, camw, depth_body, allow, dx, dy):
    img = np.zeros((H, W, 4), np.uint8); zbuf = np.full((H, W), np.inf)
    px, z = project(Xw, Pm, Vm); px = px + np.array([dx, dy])
    zlim = depth_body + 0.045                                            # the cord axis stands 2-3 cm off the skin
    # cord: pass 1 dark (2 px), pass 2 lighter and smaller, shifted up
    cc, pr, pu, pf = px[n_axis], px[n_axis + 1], px[n_axis + 2], px[n_axis + 3]
    ring = np.array([cc[0], cc[1] - a.medal_px + 0.6])                  # the top of the drawn medal
    chain = [(ring, z[n_axis])] + [(px[i], z[i]) for i in range(n_axis)] + [(ring, z[n_axis])]
    seg = []
    for i in range(len(chain) - 1):
        (p_a, z_a), (p_b, z_b) = chain[i], chain[i + 1]
        n = max(int(np.ceil(np.linalg.norm(p_b - p_a) / 0.4)), 1)
        for t in np.linspace(0, 1, n, endpoint=False):
            seg.append((p_a + (p_b - p_a) * t, z_a + (z_b - z_a) * t))
    seg.append(chain[-1])
    for rad, off, col in ((1.0, (0.0, 0.0), CORD),):                     # ONE flat colour, radius 1.0: always 2 pixel centres across, so neither the width nor the colour of a pixel flips between frames (the two-tone cord did)
        for (c, zz) in seg:
            stamp(img, zbuf, c[0] + off[0], c[1] + off[1], rad, col, zz, zlim, allow)
    # medal: drawn as a disc that faces the viewer (a 3D-projected disc on a chest seen from above is a flat 5 x 3 px ellipse that does not read as a medal);
    # seen from the side it narrows with the angle of its face to the camera, from behind it is not drawn
    nrm = Xw[n_axis + 3] - Xw[n_axis]; nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
    vh = camw[:3, 2].copy(); vh[2] = 0; vh = vh / (np.linalg.norm(vh) + 1e-9)    # horizontal direction to the camera
    f = float(np.dot(nrm, vh))
    if f > 0.05:
        ry = a.medal_px; rx = a.medal_px * max(f, 0.3)
        zc = z[n_axis]
        for y in range(max(int(cc[1] - ry) - 1, 0), min(int(cc[1] + ry) + 1, H - 1) + 1):
            for x in range(max(int(cc[0] - rx) - 1, 0), min(int(cc[0] + rx) + 1, W - 1) + 1):
                s_ = (x + 0.5 - cc[0]) / rx; t_ = (cc[1] - (y + 0.5)) / ry          # t_ > 0 = up
                r2 = s_ * s_ + t_ * t_
                if r2 > 1.0 or not (allow[y, x] and zc <= zlim[y, x] + 0.02):
                    continue
                if r2 > 0.5:
                    col = (118, 118, 130)
                else:
                    lit = 0.5 + 0.5 * np.clip(-s_ * 0.6 + t_ * 0.8, -1, 1)
                    v = int(178 + 50 * lit); col = (v, v, min(v + 6, 255))
                img[y, x] = (*col, 255)
    return img


rig.data.pose_position = "POSE"
acts = sorted([x for x in bpy.data.actions if "uo_action" in x], key=lambda x: int(x["uo_action"]))
only = [x for x in a.actions.split(",") if x]
root = os.path.abspath(a.out); meta_blocks = []
for act in acts:
    if only and act.name not in only:
        continue
    an = int(act["uo_action"]); rig.animation_data.action = act
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag()
        fdir = os.path.join(root, "frames", act.name, "dir%d" % d); os.makedirs(fdir, exist_ok=True); mf = []
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + i * STEP)
            dg, Pm, Vm, camw = matrices()
            eo = ob.evaluated_get(dg); me = eo.to_mesh()
            co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); Xw = (np.c_[co.reshape(-1, 3), np.ones(len(me.vertices))] @ np.array(eo.matrix_world).T)[:, :3]
            eo.to_mesh_clear()
            zb = body_depth(dg, Pm, Vm)
            om = original_mask(an, d, i)
            allow = dilate(om) if om is not None else np.ones((H, W), bool)
            dx, dy = fixes.get("%d,%d,%d" % (an, i, d), (0, 0))
            img = draw_frame(Xw, Pm, Vm, camw, zb, allow, dx, dy)
            Image.fromarray(img).save(os.path.join(fdir, "%02d.png" % i)); mf.append(dict(file="%02d.png" % i))
        meta_blocks.append(dict(action=an, dir=d, name=act.name, frames=mf))
        print("%s dir%d: %d frames" % (act.name, d, len(mf)), flush=True)
json.dump(dict(tool="medal_sprite", anim_type=2, actions=35, mode="canvas", canvas=[W, H], anchor=list(ANCHOR), blocks=meta_blocks), open(os.path.join(root, "meta.json"), "w"))
if a.vd:
    subprocess.run([sys.executable, os.path.join(HERE, "..", "vdtool", "vdtool.py"), "pack", root, os.path.abspath(a.vd)], check=True)
    print("vd:", a.vd)
sys.stdout.flush(); os._exit(0)
