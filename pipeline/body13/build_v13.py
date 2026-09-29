"""build the v13 .blend: MakeHuman-based UO_Body on the 55-bone UO_Rig, actions re-keyed with the refit poses.
usage: python build_v13.py src.blend shape.json poses.json out.blend
- the 19 UO bones keep their rest pose; new bones: upper_arm_twist / forearm_twist, 15 finger bones, toe (per side)
- forearm / hand / shin / foot do not inherit the parent's scale (the parent's scale X/Z is its girth)
- UO_Body (v12) is replaced by the v13 mesh (no corrective shape keys); the old one is removed
- every refit frame is keyed: bone rotations, pelvis location, girth scale, finger curl and toe"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, sys, os, json, numpy as np
from mathutils import Matrix, Quaternion, Vector
sys.path.insert(0, HERE)
from shape13 import Shape, load_params
from skel13 import Skel13, SIDES
from posefit13 import Frame13, Layout, GIRTH, NO_INHERIT, EXTRA0
from posefit import rotvec
from fk import qmat

pos = [a for a in sys.argv[1:] if not a.startswith("--")]
CLOTHS = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--cloth=")]   # e.g. --cloth=449:cloth_449.json
MOUNTED = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--mounted=")]
TEXDIR = ([a.split("=", 1)[1] for a in sys.argv if a.startswith("--tex=")] or [None])[0]   # baked albedo folder
src, shape_fn, poses_fn, out = pos[-4:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects["UO_Rig"]; old = bpy.data.objects["UO_Body"]
v = np.load(os.path.join(HERE, "views_all.npz"))
r = np.load(os.path.join(HERE, "rig_poses.npz"))
bones = list(r["bones"])
S = Shape(v["U"], v["BV"], v["BDOM"], bones)
Vf = S.build(load_params(shape_fn), full=True); V = Vf[S.used]
K = Skel13(S, r["R"], r["parent"], bones, Vf)
P = json.load(open(poses_fn)) if poses_fn != "-" else {}
for fn in MOUNTED:
    P.update(json.load(open(fn)))

# ------------------------------------------------------------------ rig
bpy.context.view_layer.objects.active = rig
for o in bpy.context.selected_objects: o.select_set(False)
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = rig.data.edit_bones
for i in range(19, len(K.names)):
    n = K.names[i]; R = K.R[i]
    b = eb.new(n); b.head = Vector(R[:3, 3]); b.tail = Vector(R[:3, 3] + R[:3, 1] * K.L[i]); b.align_roll(Vector(R[:3, 2]))
    b.parent = eb[K.names[K.parent[i]]]; b.use_connect = False; b.use_deform = True
for n in NO_INHERIT:
    eb[n].inherit_scale = "NONE"
bpy.ops.object.mode_set(mode="OBJECT")
err = max(np.abs(np.array(rig.data.bones[n].matrix_local) - K.R[i]).max() for i, n in enumerate(K.names))
print("rig: %d bones, max rest matrix error %.2e" % (len(rig.data.bones), err))
arm = rig.data
for cname, pred in (("Fingers", lambda n: n.startswith("finger")), ("Twist", lambda n: "twist" in n), ("Toes", lambda n: n.startswith("toe"))):
    c = arm.collections.get(cname) or arm.collections.new(cname)
    for n in K.names:
        if pred(n): c.assign(arm.bones[n])
for i in range(19, len(K.names)):
    rig.pose.bones[K.names[i]].rotation_mode = "QUATERNION"

# ------------------------------------------------------------------ body
mats = [m for m in old.data.materials]
old_name = old.name; old.name = "UO_Body_v12"
me = bpy.data.meshes.new("UO_Body")
me.from_pydata(V.tolist(), [], [list(f) for f in S.faces]); me.update()
for p in me.polygons: p.use_smooth = True
body = bpy.data.objects.new("UO_Body", me)
for c in old.users_collection: c.objects.link(body)
body.parent = rig; body.matrix_parent_inverse = rig.matrix_world.inverted(); body.matrix_world = Matrix(np.eye(4).tolist())
for j, n in enumerate(K.names):
    g = body.vertex_groups.new(name=n)
    for vi in np.nonzero(K.SW[:, j] > 1e-4)[0]:
        g.add([int(vi)], float(K.SW[vi, j]), "REPLACE")
m = body.modifiers.new("Armature", "ARMATURE"); m.object = rig
# UVs (MakeHuman layout) + the v12 material with the v13 textures baked from the original frames
VT, FT = [], []; grp = None
for line in open(os.path.join(HERE, "base.obj")):
    if line.startswith("vt "): VT.append([float(x) for x in line.split()[1:3]])
    elif line.startswith("g "): grp = line.split()[1]
    elif line.startswith("f ") and grp == "body": FT.append([int(t.split("/")[1]) - 1 for t in line.split()[1:]])
uvl = me.uv_layers.new(name="UVMap")
for p, ft in zip(me.polygons, FT):
    for li, t in zip(p.loop_indices, ft):
        uvl.data[li].uv = VT[t]
if TEXDIR and mats:
    skin = mats[0]
    skin.name = "UO_Skin"
    for nd in skin.node_tree.nodes:
        if nd.type == "TEX_IMAGE" and nd.image and nd.image.name.startswith("UO_Body_"):
            tag = "all" if nd.image.name == "UO_Body_Texture" else nd.image.name.split("_")[-1]
            fn = os.path.join(TEXDIR, "UO_Body_Albedo_%s.png" % tag)
            old_img = nd.image; nm = old_img.name
            img = bpy.data.images.load(fn); img.colorspace_settings.name = old_img.colorspace_settings.name; img.pack()
            nd.image = img; bpy.data.images.remove(old_img); img.name = nm
    me.materials.append(skin)
else:
    skin = bpy.data.materials.get("UO_Skin_v13") or bpy.data.materials.new("UO_Skin_v13")
    skin.use_nodes = True; skin.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.62, 0.5, 1)
    me.materials.append(skin)
bpy.data.objects.remove(old, do_unlink=True)
for o in [o for o in bpy.data.objects if o.name.startswith("UO_Body_v13")]:
    bpy.data.objects.remove(o, do_unlink=True)

# ------------------------------------------------------------------ actions
L = Layout(K.names); fr_keys = {tuple(k): n for n, k in enumerate(r["keys"])}
acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
keyed = 0
for key, rec in P.items():
    a, i = map(int, key.split(",")); act = acts[a]; f = fr_keys[(a, i)]; frame = 1 + 3 * i
    x = np.array(rec["x"]); rr = x[:57].reshape(19, 3); dl = x[57:60]; g = x[L.o_g:L.o_e].reshape(-1, 2); e = x[L.o_e:]
    rig.animation_data.action = act
    for b in range(19):
        pb = rig.pose.bones[bones[b]]
        q = Matrix((qmat(r["quat"][f, b]) @ rotvec(rr[b])).tolist()).to_quaternion()
        if q.dot(Quaternion(r["quat"][f, b])) < 0: q.negate()
        pb.rotation_quaternion = q; pb.keyframe_insert("rotation_quaternion", frame=frame)
        if b == 0:
            pb.location = Vector(r["loc"][f, 0] + dl); pb.keyframe_insert("location", frame=frame)
    for k, bn in enumerate(GIRTH):
        pb = rig.pose.bones[bn]; pb.scale = (float(np.exp(g[k, 0])), 1.0, float(np.exp(g[k, 1])))
        pb.keyframe_insert("scale", frame=frame)
    ext = K.extra_bases({".L": e[0], ".R": e[1]}, {".L": e[2], ".R": e[3]}, {".L": e[4], ".R": e[5]})
    for bn, M in ext.items():
        pb = rig.pose.bones[bn]; pb.rotation_quaternion = Matrix(M.tolist()).to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    keyed += 1
# actions without refit frames (mounted, for now): fists, no girth
for a, act in acts.items():
    rig.animation_data.action = act
    for i in range(int(act["uo_frames"])):
        if "%d,%d" % (a, i) in P: continue
        ext = K.extra_bases({".L": 1.0, ".R": 1.0}, {".L": 1.0, ".R": 1.0}, {".L": 0.0, ".R": 0.0})
        for bn, M in ext.items():
            pb = rig.pose.bones[bn]; pb.rotation_quaternion = Matrix(M.tolist()).to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i)
# ------------------------------------------------------------------ cloth chain rigs + templates
from cloth13 import make_cloth, KINDS
from mathutils import Matrix as _M
tcoll = bpy.data.collections.get("Templates") or bpy.data.collections.new("Templates")
if tcoll.name not in [c.name for c in bpy.context.scene.collection.children]:
    bpy.context.scene.collection.children.link(tcoll)
for spec in CLOTHS:
    anim, fn = spec.split(":"); anim = int(anim); CFIT = json.load(open(fn))
    kind, zt, zh = KINDS[anim]
    crig, CV, CF, CW, top, par = make_cloth(K, V, kind, zt, zh, faces=S.faces)
    bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode="EDIT"); eb = rig.data.edit_bones
    for b, n in enumerate(crig.names):
        if n in eb: eb.remove(eb[n])
    for b, n in enumerate(crig.names):
        R = crig.R[b]; e = eb.new(n); e.head = Vector(R[:3, 3]); e.tail = Vector(R[:3, 3] + R[:3, 1] * crig.L[b]); e.align_roll(Vector(R[:3, 2]))
        e.parent = eb[par] if isinstance(crig.par[b], str) else eb[crig.names[crig.par[b]]]; e.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    c = arm.collections.get("Cloth") or arm.collections.new("Cloth")
    for n in crig.names:
        c.assign(arm.bones[n]); rig.pose.bones[n].rotation_mode = "QUATERNION"
    tname = "UO_Template_" + ("Cloak" if kind == "cloak" else "Skirt")
    if tname in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[tname], do_unlink=True)
    tm = bpy.data.meshes.new(tname); tm.from_pydata(CV.tolist(), [], CF.tolist()); tm.update()
    to = bpy.data.objects.new(tname, tm); tcoll.objects.link(to)
    to.parent = rig; to.matrix_parent_inverse = rig.matrix_world.inverted()
    for j, n in enumerate(crig.wnames):
        if not (CW[:, j] > 1e-4).any(): continue
        g = to.vertex_groups.new(name=n)
        for vi in np.nonzero(CW[:, j] > 1e-4)[0]: g.add([int(vi)], float(CW[vi, j]), "REPLACE")
    to.modifiers.new("Armature", "ARMATURE").object = rig
    to.hide_render = True; to.display_type = "WIRE"
    from cloth13 import rotxz
    for key, rec in CFIT.items():
        a, i = map(int, key.split(",")); rig.animation_data.action = acts[a]
        ang = np.array(rec["x"]).reshape(-1, 2)
        for b, n in enumerate(crig.names):
            pb = rig.pose.bones[n]; pb.rotation_quaternion = _M(rotxz(ang[b, 0], ang[b, 1]).tolist()).to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i)
    print("cloth", tname, len(crig.names), "bones,", len(CFIT), "frames keyed")
# ------------------------------------------------------------------ user scripts (v13-aware versions)
PIPE = os.path.join(HERE, "..", "")
for tn in ("render_uo_layer.py", "uo_bind_item.py", "uo_fit_item.py", "uo_transfer_corrections.py"):
    t = bpy.data.texts.get(tn) or bpy.data.texts.new(tn); t.from_string(open(PIPE + tn).read())
# example shirt: drop the v12 corrections, push it out of the new skin and bind it again
shirt = bpy.data.objects.get("Example_Shirt")
if shirt is not None:
    if shirt.data.shape_keys:
        shirt.shape_key_clear()
    rig.animation_data.action = None
    for o in bpy.context.selected_objects: o.select_set(False)
    shirt.select_set(True); bpy.context.view_layer.objects.active = shirt
    exec(compile(bpy.data.texts["uo_fit_item.py"].as_string(), "uo_fit_item.py", "exec"), {"__name__": "__main__"})
    src_ = bpy.data.texts["uo_bind_item.py"].as_string().replace('PART = "all"', 'PART = "chest"', 1)
    exec(compile(src_, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
rig.animation_data.action = acts[4] if 4 in acts else list(acts.values())[0]
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("built", out, "| keyed frames", keyed, "| body verts", len(V))
