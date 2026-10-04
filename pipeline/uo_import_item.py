# Bring a model from outside (a free 3D model: .glb / .gltf / .fbx / .obj / .dae / .stl / .ply) onto the UO body, ready for uo_fit_item.py and
# uo_bind_item.py. Foreign models come in any size, any place, often with their own skeleton and weights; this script does the dull part:
# 1. imports the file and bakes every mesh as it looks now (its own armature / modifiers applied; shape keys, vertex groups, parents and
#    the armature, empties, lights, cameras of the file are dropped: uo_bind_item.py makes the skin weights from the UO body),
# 2. joins the meshes into one object (JOIN) and puts it in the collection "Clothing", selected,
# 3. scales it (uniformly) and moves it so that its height lands where the ORIGINAL UO item of the same KIND stands on the body: the lowest
#    and highest point of the original sprites in the rest pose (EXTENTS, measured from anim 431, 434, 449, 468, 477, 527, 528, 529, 530,
#    563; hair, beard, hat, neck: medians of the whole layer). Sideways and front-back it is centred on the body at that height. Tell it SCALE = a number to scale yourself instead.
# Then: check that the FRONT of the item looks at the camera of the front view (Numpad 1) - if it is the other way round, set TURN = 180 and
# run again - run uo_fit_item.py, and uo_bind_item.py with the PART of the table below. Work in Rest Position (UO_Rig > Pose > Rest Position).
# Run from Blender's Text Editor (Alt+P) in UO_Body_0x190.blend, or headless: UO_IMPORT_FILE=... UO_IMPORT_KIND=... (see pipeline/test_import_item.py).
# A file often holds more than the item (the model's body, eyes, helper shapes): the meshes are listed, name the ones to leave out in SKIP.
# Remember to keep the item under ~20k vertices (Decimate modifier) and to check the licence of the model you use.
import os
import bpy
import bmesh
import numpy as np
from mathutils import Matrix

FILE = ""             # path of the model to import ("" = take the SELECTED mesh objects instead, e.g. something you appended yourself)
KIND = "shirt"        # shirt, plate, arms, pants, legs, boots, gloves, helm, neck, hair, beard, hat ("" = do not scale or move; only clean + join)
SCALE = 0.0           # > 0: uniform scale you give (the item is then only moved), 0 = from the height of KIND
PLACE = "wrap"        # "wrap": the item is only cleaned, joined and reduced here, its units, size and place are found from the skin by uo_autofit_item.py (called by uo_prepare_item.py);
                      # "height": the old way, one height per KIND (EXTENTS below) - right only for items shaped like the typical original (docs/qa/autofit.md)
TURN = 0              # deg around the vertical axis (180 when the item came in back to front)
JOIN = True           # one object out of all the meshes of the file (False: they stay separate objects, each scaled alike)
KEEP = ()             # names (parts of names, any case; "=name" = exactly that mesh) of the meshes to keep; everything else is left out (empty = all that SKIP does not exclude)
SKIP = ()             # names (parts of names, any case) of meshes of the file to leave out: eyes, the model's body, helper shapes, collision meshes
DROP_MATERIALS = ()   # names (parts of names, any case) of MATERIALS whose faces are cut out of the model: a belt, a buckle, a bag that is one mesh with the robe
ARMS_DOWN = 0.0       # deg: a model in a T-pose (arms out) has its sleeves turned down by this much about the shoulders (80-90 for a T-pose, 0 = leave); the sleeves are the faces of ARM_MATERIALS, the
                      # item around the shoulders follows them over ARM_BLEND m of the arm (uo_fit_item.py MATCH_ARMS only finds up to MAX_TURN deg, and a T-pose is beyond it)
ARM_MATERIALS = ("sleeve",)   # names (parts of names, any case) of the materials of the sleeves (a trim of the sleeves too: "sleeve" matches TrimSleeve)
ARM_BLEND = 0.12      # m: the width of the shoulder over which the turn fades from the sleeve into the body
NAME = ""             # name of the result ("" = file name)
DECIMATE_TO = 30000   # a model with more vertices than this is reduced (collapse, UVs and materials kept) - a 144k-vertex scan costs minutes in every later step; uo_densify_item.py adds
                      # vertices back where the item has to bend. 0 = never
SMOOTH_SHADE = True   # smooth shading on every face (UO art is shaded smoothly; a decimated or scanned model with flat faces turns into noise at 36 px/m)
PERCENT = 0.5         # the height is measured between the PERCENT and 100 - PERCENT percentile of the vertices (a stray spike does not count)

# measured on the original sprites (stand, mean of the 5 directions): z of the lowest and highest point of the item in the rest pose, m
# (the ground is z = 0), and the PART of uo_bind_item.py that belongs to the KIND
EXTENTS = {"shirt": (0.999, 1.656, "chest"), "plate": (0.651, 1.643, "chest"), "arms": (0.929, 1.694, "arms"), "pants": (0.057, 1.170, "legs"),
           "legs": (-0.107, 1.138, "legs"), "boots": (-0.069, 0.563, "boots"), "gloves": (0.797, 1.245, "gloves"), "helm": (1.504, 1.903, "helm"),
           # medians over the original animations of the layer (docs/qa/layer_analysis.md, pipeline/layer_analysis.py).
           # hair / beard / hat: the TOP is reliable (hair 1.88-1.93 m for 80 % of the 37 hairstyles), the bottom depends on the style (hair 1.34-1.64):
           # for a long hairstyle give SCALE yourself instead of letting the height decide
           "hair": (1.52, 1.89, "hair"), "beard": (1.52, 1.72, "beard"), "hat": (1.52, 1.92, "hat"), "neck": (1.48, 1.64, "neck")}

body = bpy.data.objects["UO_Body"]
UO_NAMES = {"UO_Body", "UO_Rig", "UO_Camera", "UO_Sun"}


def named(o, keys):
    """is the mesh `o` named by one of `keys`: a part of the name, any case; "=name" = exactly that name (a model whose meshes are all called defaultMaterial.NNN)"""
    n = o.name.lower()
    return any((n == k[1:].lower()) if k.startswith("=") else (k.lower() in n) for k in keys)


def import_file(path):
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".dae":
        bpy.ops.wm.collada_import(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    else:
        raise ValueError("unsupported file type %r (use .glb .gltf .fbx .obj .dae .stl .ply)" % ext)
    return [o for o in bpy.data.objects if o not in before]


def bake(ob):
    """a new mesh object with the geometry of `ob` as it is evaluated now, in world space (own armature, modifiers applied)"""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    me.transform(ob.matrix_world)
    bm = bmesh.new(); bm.from_mesh(me)
    for lay in list(bm.verts.layers.deform):         # weights of the file's own skeleton: uo_bind_item.py makes its own
        bm.verts.layers.deform.remove(lay)
    bm.to_mesh(me); bm.free()
    return bpy.data.objects.new(ob.name, me)


def arms_down(n):
    """turn the sleeves of a T-pose model down about the shoulders (see ARMS_DOWN): per side the pivot is the inner end of the sleeve faces; vertices turn by ARMS_DOWN times a weight that is 1 on the
    sleeve and fades to 0 over ARM_BLEND towards the body"""
    me = n.data
    mats = {i for i, m in enumerate(me.materials) if m and any(k.lower() in m.name.lower() for k in ARM_MATERIALS)}
    if not mats:
        print("uo_import_item: ARMS_DOWN: no material of %s in %s" % (list(ARM_MATERIALS), n.name)); return
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    sl = np.zeros(len(co), bool)
    for p in me.polygons:
        if p.material_index in mats:
            sl[list(p.vertices)] = True
    th = np.radians(ARMS_DOWN)
    for sg in (1.0, -1.0):
        side = sl & (co[:, 0] * sg > 0)
        if not side.any():
            continue
        xin = np.percentile(np.abs(co[side, 0]), 2)                             # the inner end of the sleeve
        ring = side & (np.abs(co[:, 0]) < xin + 0.03)
        pv = co[ring].mean(0)
        w = np.clip((np.abs(co[:, 0]) - (xin - ARM_BLEND)) / ARM_BLEND, 0, 1) * (co[:, 0] * sg > 0)
        w = np.where(sl & (co[:, 0] * sg > 0), 1.0, w * (np.abs(co[:, 2] - pv[2]) < 0.2))   # the body fades in only at the height of the arm opening (not the chest, not the skirt)
        a = sg * th * w                                                          # positive a turns the +X side down (z' = -dx sin a + dz cos a)
        dx, dz = co[:, 0] - pv[0], co[:, 2] - pv[2]
        co[:, 0] = np.where(w > 0, pv[0] + dx * np.cos(a) + dz * np.sin(a), co[:, 0])
        co[:, 2] = np.where(w > 0, pv[2] - dx * np.sin(a) + dz * np.cos(a), co[:, 2])
        print("uo_import_item: ARMS_DOWN %.0f deg, side %+d: pivot %s, %d sleeve vertices" % (ARMS_DOWN, sg, np.round(pv, 3), int(side.sum())))
    me.vertices.foreach_set("co", co.ravel()); me.update()


def run():
    if FILE:
        everything = import_file(FILE)
        meshes = [o for o in everything if o.type == "MESH"]
        print("uo_import_item: meshes in the file (name, vertices, size in the file's units):")
        for o in meshes:
            d = np.array(o.dimensions)
            print("   %-30s %7d  %.3f x %.3f x %.3f%s" % (o.name, len(o.data.vertices), *d, "   <- SKIP" if named(o, SKIP) else ""))
        src = [o for o in meshes if not named(o, SKIP) and (not KEEP or named(o, KEEP))]
        imported = True
    else:
        src = [o for o in bpy.context.selected_objects if o.type == "MESH" and o.name not in UO_NAMES]
        imported = False
    if not src:
        raise RuntimeError("no mesh to work on (FILE is empty and nothing is selected, or the file has no mesh)")
    bpy.context.view_layer.update()
    clo = bpy.data.collections.get("Clothing") or bpy.data.collections.new("Clothing")
    if clo.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(clo)
    news = []
    for o in src:
        n = bake(o)
        clo.objects.link(n)
        news.append(n)
    if ARMS_DOWN:
        for n in news:
            arms_down(n)
    if DROP_MATERIALS:
        import bmesh
        for n in news:
            drop = {i for i, m in enumerate(n.data.materials) if m and any(k.lower() in m.name.lower() for k in DROP_MATERIALS)}
            if not drop:
                continue
            bm = bmesh.new(); bm.from_mesh(n.data)
            faces = [f for f in bm.faces if f.material_index in drop]
            bmesh.ops.delete(bm, geom=faces, context="FACES")
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
            print("uo_import_item: DROP_MATERIALS %s: %d faces cut out of %s" % (sorted(DROP_MATERIALS), len(faces), n.name))
            bm.to_mesh(n.data); bm.free(); n.data.update()
    for o in (everything if imported else src):      # drop what the file brought (meshes, armature, empties, lights, cameras)
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for n in news:
        n.select_set(True)
    bpy.context.view_layer.objects.active = news[0]
    if JOIN and len(news) > 1:
        bpy.ops.object.join()
        news = [bpy.context.view_layer.objects.active]
    for k, n in enumerate(news):
        n.name = (NAME or os.path.splitext(os.path.basename(FILE))[0] or "Item") + ("" if len(news) == 1 else "_%d" % k)
        n.data.name = n.name
    if DECIMATE_TO > 0:
        total = sum(len(n.data.vertices) for n in news)
        if total > DECIMATE_TO:
            ratio = DECIMATE_TO / total
            for n in news:
                md = n.modifiers.new("uo_decimate", "DECIMATE"); md.ratio = ratio
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            for n in news:
                me = bpy.data.meshes.new_from_object(n.evaluated_get(dg))
                n.modifiers.clear(); old = n.data; n.data = me; bpy.data.meshes.remove(old)
            print("uo_import_item: %d vertices -> %d (DECIMATE_TO %d)" % (total, sum(len(n.data.vertices) for n in news), DECIMATE_TO))
    if SMOOTH_SHADE:
        for n in news:
            n.data.polygons.foreach_set("use_smooth", [True] * len(n.data.polygons))
            n.data.update()
    verts = np.concatenate([np.array([v.co[:] for v in n.data.vertices]) for n in news])
    if TURN:
        R = np.array(Matrix.Rotation(np.radians(TURN), 3, "Z"))
        c0 = np.array([(verts[:, 0].min() + verts[:, 0].max()) / 2, (verts[:, 1].min() + verts[:, 1].max()) / 2, 0])
        for n in news:
            n.data.transform(Matrix.Translation(c0) @ Matrix.Rotation(np.radians(TURN), 4, "Z") @ Matrix.Translation(-c0))
        verts = np.concatenate([np.array([v.co[:] for v in n.data.vertices]) for n in news])
    info = "%d mesh object(s), %d vertices, size %.3f x %.3f x %.3f (as imported)" % (len(news), len(verts), *(verts.max(0) - verts.min(0)))
    if KIND and PLACE == "wrap":
        print("uo_import_item: PLACE = wrap: size and place are left to uo_autofit_item.py (uo_prepare_item.py runs it)")
    elif KIND:
        if KIND not in EXTENTS:
            raise ValueError("KIND must be one of %s" % list(EXTENTS))
        zlo, zhi, part = EXTENTS[KIND]
        lo, hi = np.percentile(verts[:, 2], [PERCENT, 100 - PERCENT])
        s = SCALE if SCALE > 0 else (zhi - zlo) / max(hi - lo, 1e-9)
        # sideways / front-back: the middle of the item on the middle of the body between the same heights
        bz = np.array([v.co[:] for v in body.data.vertices])
        bz = (np.array(body.matrix_world)[:3, :3] @ bz.T).T + np.array(body.matrix_world)[:3, 3]
        near = bz[(bz[:, 2] > zlo) & (bz[:, 2] < zhi) & (np.abs(bz[:, 0]) < 0.25)]
        tx, ty = (np.median(near[:, 0]), (near[:, 1].min() + near[:, 1].max()) / 2) if len(near) else (0.0, 0.0)
        ix, iy = [(np.percentile(verts[:, a], PERCENT) + np.percentile(verts[:, a], 100 - PERCENT)) / 2 for a in (0, 1)]
        T = Matrix.Translation((tx, ty, zlo)) @ Matrix.Diagonal((s, s, s, 1.0)) @ Matrix.Translation((-ix, -iy, -lo))
        for n in news:
            n.data.transform(T)
        info += "; KIND %s: scale %.4f (height %.3f -> %.3f m), moved onto the body; PART for uo_bind_item.py: %r" % (KIND, s, hi - lo, zhi - zlo, part)
        if not 0.3 < s < 3 and SCALE <= 0:
            info += "\n  WARNING: scale %.2f is far from 1: check the model's units, or that KIND is the right one" % s
    nv = sum(len(n.data.vertices) for n in news)
    if nv > 20000:
        info += "\n  WARNING: %d vertices: add a Decimate modifier (about 20k are enough for a 136x120 frame)" % nv
    for n in news:
        n.matrix_world = Matrix.Identity(4)
        n.select_set(True)
    bpy.context.view_layer.objects.active = news[0]
    print("uo_import_item: " + info)
    return news


try:
    import scipy                                      # noqa: F401  (uo_autofit_item.py needs it)
except ImportError:
    if PLACE == "wrap" and KIND:
        PLACE = "height"
        print("uo_import_item: WARNING - scipy is not installed in this Python, so the size and place come from ONE HEIGHT per KIND (PLACE = height), which only suits items shaped like the "
              "typical original (docs/qa/autofit.md). For the fit to the skin install scipy into Blender's Python or run  python pipeline/uo_make_item.py recipe.json  outside the window.")
FILE = os.environ.get("UO_IMPORT_FILE", FILE)
KIND = os.environ.get("UO_IMPORT_KIND", KIND)
SKIP = [k for k in os.environ.get("UO_IMPORT_SKIP", "").split(",") if k] or SKIP
ARMS_DOWN = float(os.environ.get("UO_IMPORT_ARMS_DOWN", ARMS_DOWN))
DROP_MATERIALS = [k for k in os.environ.get("UO_IMPORT_DROP_MATERIALS", "").split(",") if k] or DROP_MATERIALS
_result = run()
