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
STRETCH = (1.0, 1.0, 1.0)   # (width, depth, height) factors about the centre of the model, before the fit: a model made on a mannequin with other proportions than the UO body (a vest much wider and shallower than the
                      # torso: (0.8, 1.25, 1.0)). Recipe of uo_make_item.py: "stretch": [0.8, 1.25, 1.0]
TURN = 0              # deg around the vertical axis (180 when the item came in back to front)
JOIN = True           # one object out of all the meshes of the file (False: they stay separate objects, each scaled alike)
KEEP = ()             # names (parts of names, any case; "=name" = exactly that mesh) of the meshes to keep; everything else is left out (empty = all that SKIP does not exclude)
SKIP = ()             # names (parts of names, any case) of meshes of the file to leave out: eyes, the model's body, helper shapes, collision meshes
DROP_MATERIALS = ()   # names (parts of names, any case) of MATERIALS whose faces are cut out of the model: a belt, a buckle, a bag that is one mesh with the robe
ARMS_DOWN = 0.0       # deg: a model in a T-pose (arms out) has its sleeves turned down by this much about the shoulders (80-90 for a T-pose, 0 = leave); the sleeves are the faces of ARM_MATERIALS, the
                      # item around the shoulders follows them over ARM_BLEND m of the arm (uo_fit_item.py MATCH_ARMS only finds up to MAX_TURN deg, and a T-pose is beyond it)
ARM_MATERIALS = ("sleeve",)   # names (parts of names, any case) of the materials of the sleeves (a trim of the sleeves too: "sleeve" matches TrimSleeve)
ARM_BLEND = 0.12      # m: the width of the shoulder over which the turn fades from the sleeve into the body
OUTER_SHELL = False   # a model that is a CLOSED SOLID cloth (a cloth simulator exports garments ~1.5 cm thick: outer layer + inner layer): only the outer layer is kept, before the reduction. Reducing the
                      # solid pastes the two layers into each other (cracks, torn patches, the inner lining showing through); a single sheet reduces cleanly and fits to the skin. Recipe: "outer_shell": true
OUTER_REMESH = 0.0    # m: > 0 (0.006) = before OUTER_SHELL the solid is rebuilt by Blender's voxel remesh: a garment exported as separate panels (sewing patterns that only touch, 284 of them
                      # in docs/qa/robe_black.md) becomes ONE continuous sheet, so the seams cannot open when the sleeves are turned onto the arms or the item is wrapped. The UVs are lost:
                      # the texture is baked from the original (BAKE_TEXTURE, 2048 when not given). Recipe: "outer_shell": 0.006
NAME = ""             # name of the result ("" = file name)
BAKE_TEXTURE = 0      # > 0 (px, 2048 is plenty): the reduced model gets a NEW UV map and a texture BAKED from the original: a reduction drags the UVs of a model with a sculpted detail / an embroidery into
                      # streaks (the cloth turns into smeared noise). Needs the Cycles engine of Blender. Recipe: "bake_texture": 2048
BAKE_RAY = 0.04       # m: how far from the reduced surface the original is looked for in the bake (layers closer to each other than this, e.g. a robe over a tunic, are not mixed up if they are further apart)
WELD = 1e-6           # m: vertices closer than this are merged before the reduction (seams of the glTF import; 0 = off)
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


def pose_own_arms(everything):
    """a model that came with its own skeleton (a Daz / Genesis rig: lShldrBend, ...) in a T-pose: the shoulder bones are turned down by ARMS_DOWN about the front-back axis, so that the sleeves and the
    shoulders deform with the weights the author made (bake() then takes the posed mesh). True if there was a skeleton with shoulders."""
    import re
    from mathutils import Matrix, Vector
    arms = [o for o in everything if o.type == "ARMATURE"]
    if not arms:
        return False
    arm = arms[0]; done = 0
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        nm = pb.name.lower()
        if not re.search(r"(shldr|shoulder|upperarm|upper_arm|uparm)", nm) or re.search(r"(twist|collar|clav|handle)", nm):
            continue
        if pb.parent is not None and re.search(r"(shldr|shoulder|upperarm|upper_arm|uparm)", pb.parent.name.lower()) and not re.search(r"collar|clav", pb.parent.name.lower()):
            continue                                                     # the lower segment of the same arm follows its parent
        head = arm.matrix_world @ pb.head; tail = arm.matrix_world @ pb.tail
        sg = 1.0 if head.x > 0 else -1.0                                 # which side the arm is on (the bone itself may point anywhere: Daz bones point up)
        R = Matrix.Rotation(sg * np.radians(ARMS_DOWN), 4, "Y")           # about +Y: the +X arm goes down
        T = Matrix.Translation(head)
        Rw = T @ R @ T.inverted()
        pb.matrix = arm.matrix_world.inverted() @ Rw @ (arm.matrix_world @ pb.matrix)
        bpy.context.view_layer.update()
        done += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    print("uo_import_item: ARMS_DOWN %.0f deg: %d shoulder bone(s) of the model's own skeleton turned" % (ARMS_DOWN, done))
    return done > 0


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


def outer_shell(n, rays=8, reach=1.5, partner_max=0.06, smooth=8, min_island=0.002):
    """keep only the outer layer of a thick closed garment. Every face looks at the sky through a hemisphere of `rays` rays (an inner face sees mostly cloth: the other side of the robe, the sleeve);
    its partner is the face hit under it (-normal, up to partner_max m = the other layer); the face that sees more sky is the outer one. The votes are smoothed over the neighbouring faces
    (the two layers meet only at the hem and the cuffs) and the inner layer is deleted."""
    import time
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    t0 = time.time(); me = n.data; me.calc_loop_triangles()
    tri = [t.vertices[:] for t in me.loop_triangles]
    if len(tri) != len(me.polygons):
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free(); me.update(); me.calc_loop_triangles(); tri = [t.vertices[:] for t in me.loop_triangles]
    bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], tri)
    i = np.arange(rays) + 0.5; z = 1 - i / rays; r = np.sqrt(1 - z * z); ph = i * 2.399963
    D = np.c_[r * np.cos(ph), r * np.sin(ph), z]
    npoly = len(me.polygons); sky = np.zeros(npoly); partner = -np.ones(npoly, int)
    for k, p in enumerate(me.polygons):
        nr = p.normal; c = p.center
        a = Vector((1, 0, 0)) if abs(nr.x) < 0.9 else Vector((0, 1, 0))
        u = nr.cross(a).normalized(); w = nr.cross(u); o = c + nr * 1e-3; esc = 0
        for d in D:
            if bvh.ray_cast(o, u * d[0] + w * d[1] + nr * d[2], reach)[0] is None:
                esc += 1
        sky[k] = esc / rays
        h = bvh.ray_cast(c - nr * 1e-4, -nr, partner_max)
        if h[0] is not None:
            partner[k] = h[2]
    vote = np.zeros(npoly); has = np.nonzero(partner >= 0)[0]; vote[has] = sky[has] - sky[partner[has]]
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    A, B = [], []
    for e in bm.edges:
        f = e.link_faces
        if len(f) == 2:
            A.append(f[0].index); B.append(f[1].index)
    A = np.array(A); B = np.array(B); deg = np.maximum(np.bincount(np.r_[A, B], minlength=npoly), 1)
    for _ in range(smooth):
        acc = np.zeros(npoly); np.add.at(acc, A, vote[B]); np.add.at(acc, B, vote[A]); vote = 0.5 * vote + 0.5 * acc / deg
    drop = np.nonzero(vote < 0)[0]
    bmesh.ops.delete(bm, geom=[bm.faces[k] for k in drop], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.faces.ensure_lookup_table(); seen = np.zeros(len(bm.faces), bool); bits = []      # bits of the inner layer left alone by the vote (a few faces): removed
    for f in bm.faces:
        if seen[f.index]:
            continue
        st = [f]; seen[f.index] = True; isl = [f]
        while st:
            g = st.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if not seen[h.index]:
                        seen[h.index] = True; st.append(h); isl.append(h)
        if len(isl) < min_island * len(bm.faces):
            bits += isl
    if bits:
        bmesh.ops.delete(bm, geom=bits, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    nv0 = len(me.vertices); bm.to_mesh(me); bm.free(); me.update()
    print("uo_import_item: OUTER_SHELL %s: %d of %d faces kept (outer layer; %d faces of small pieces removed), %d -> %d vertices, %.0f s" % (n.name, npoly - len(drop) - len(bits), npoly, len(bits), nv0, len(me.vertices), time.time() - t0))


def bake_texture(lo, hi, px):
    """texture of the original `hi` baked onto the reduced `lo` (new smart-projected UVs, one image `px` x `px`, a Principled material with it)"""
    import math, tempfile, time
    t0 = time.time(); sc = bpy.context.scene
    for u in list(lo.data.uv_layers):
        lo.data.uv_layers.remove(u)
    lo.data.uv_layers.new(name="UVMap")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    lo.select_set(True); bpy.context.view_layer.objects.active = lo
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("uo_baked_" + lo.name, px, px, alpha=False)
    mat = bpy.data.materials.new("uo_baked_" + lo.name); mat.use_nodes = True; nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]; tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"]); nt.nodes.active = tex
    lo.data.materials.clear(); lo.data.materials.append(mat)
    for i in range(len(lo.data.polygons)):
        lo.data.polygons[i].material_index = 0
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1
    b = sc.render.bake
    b.use_selected_to_active = True; b.max_ray_distance = BAKE_RAY; b.cage_extrusion = BAKE_RAY; b.margin = 8; b.margin_type = "EXTEND"
    b.use_pass_direct = False; b.use_pass_indirect = False; b.use_pass_color = True
    hi.select_set(True); lo.select_set(True); bpy.context.view_layer.objects.active = lo
    bpy.ops.object.bake(type="DIFFUSE")
    f = os.path.join(tempfile.mkdtemp(prefix="uo_bake_"), "baked.png"); img.filepath_raw = f; img.file_format = "PNG"; img.save(); img.pack()
    print("uo_import_item: BAKE_TEXTURE %s: %d x %d px from %s, %d vertices, %.0f s" % (lo.name, px, px, hi.name, len(lo.data.vertices), time.time() - t0))


def run():
    if FILE:
        everything = import_file(FILE)
        meshes = [o for o in everything if o.type == "MESH"]
        print("uo_import_item: meshes in the file (name, vertices, size in the file's units):")
        for o in meshes:
            d = np.array(o.dimensions)
            print("   %-30s %7d  %.3f x %.3f x %.3f%s" % (o.name, len(o.data.vertices), *d, "   <- SKIP" if named(o, SKIP) else ""))
        posed_own = bool(ARMS_DOWN) and pose_own_arms(everything)             # T-pose + own skeleton: pose it before the meshes are baked
        src = [o for o in meshes if not named(o, SKIP) and (not KEEP or named(o, KEEP))]
        imported = True
    else:
        src = [o for o in bpy.context.selected_objects if o.type == "MESH" and o.name not in UO_NAMES]
        imported = False; posed_own = False
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
    if ARMS_DOWN and not posed_own:
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
    bake_px = BAKE_TEXTURE or (2048 if OUTER_SHELL and OUTER_REMESH > 0 else 0)
    originals = {}
    if bake_px > 0:                                       # the original (with its texture) stays hidden until the reduced / rebuilt model has its baked texture
        for n in news:
            hi = n.copy(); hi.data = n.data.copy(); hi.name = n.name + "_original"; clo.objects.link(hi); originals[n] = hi
    if OUTER_SHELL:
        for n in news:
            if OUTER_REMESH > 0:
                import time
                t0 = time.time(); k0 = len(n.data.vertices)
                md = n.modifiers.new("uo_remesh", "REMESH"); md.mode = "VOXEL"; md.voxel_size = float(OUTER_REMESH); md.adaptivity = 0.0
                bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
                me = bpy.data.meshes.new_from_object(n.evaluated_get(dg)); n.modifiers.clear(); old = n.data; n.data = me; bpy.data.meshes.remove(old)
                print("uo_import_item: OUTER_REMESH %s: voxels %.1f mm, %d -> %d vertices (one continuous solid), %.0f s" % (n.name, 1000 * OUTER_REMESH, k0, len(me.vertices), time.time() - t0))
            outer_shell(n)
    if DECIMATE_TO > 0:
        total = sum(len(n.data.vertices) for n in news)
        if total > DECIMATE_TO:
            if WELD > 0:                                  # a glTF import splits the vertices on every UV / normal seam: the halves of a seam move apart in the reduction (cracks); the UVs stay with the faces
                import bmesh
                for n in news:
                    bm = bmesh.new(); bm.from_mesh(n.data); k = len(bm.verts)
                    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD); bm.to_mesh(n.data); bm.free(); n.data.update()
                    print("uo_import_item: WELD %s: %d -> %d vertices" % (n.name, k, len(n.data.vertices)))
                total = sum(len(n.data.vertices) for n in news)
            ratio = DECIMATE_TO / total
            for n in news:
                md = n.modifiers.new("uo_decimate", "DECIMATE"); md.ratio = ratio
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            for n in news:
                me = bpy.data.meshes.new_from_object(n.evaluated_get(dg))
                n.modifiers.clear(); old = n.data; n.data = me; bpy.data.meshes.remove(old)
            print("uo_import_item: %d vertices -> %d (DECIMATE_TO %d)" % (total, sum(len(n.data.vertices) for n in news), DECIMATE_TO))
    for n, hi in originals.items():
        bake_texture(n, hi, int(bake_px))
        bpy.data.objects.remove(hi, do_unlink=True)
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
    if tuple(STRETCH) != (1.0, 1.0, 1.0):
        c0 = (verts.min(0) + verts.max(0)) / 2
        for n in news:
            n.data.transform(Matrix.Translation(c0) @ Matrix.Diagonal((*[float(k) for k in STRETCH], 1.0)) @ Matrix.Translation(-c0))
        verts = np.concatenate([np.array([v.co[:] for v in n.data.vertices]) for n in news])
        print("uo_import_item: STRETCH %s about the centre" % (tuple(STRETCH),))
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
