# Densify the SELECTED item meshes before uo_fit_item.py / uo_bind_item.py, so that a low-poly item bends smoothly instead of
# folding along a few long edges when the arms and legs move (linear blend skinning can only bend where there are vertices), and so
# that no face is much bigger than the gap to the skin (uo_fit_item.py: "faces much bigger than the gap can cut through the skin").
# 1. Level: the number of subdivision steps is the smallest that brings the mean edge length to TARGET_EDGE or below (0..MAX_LEVEL),
#    lowered when the result would have more than MAX_VERTS vertices (uo_bind_item.py wants ~10k; the binding maps every vertex to the skin).
# 2. Shape: SMOOTH = 0 splits the faces without moving anything (rest shape exactly as modelled: armour, hard-surface parts);
#    SMOOTH = 1 rounds the rest shape like Catmull-Clark (cloth, leather, hair); in between blends the two. Catmull-Clark pulls the surface in
#    (it shrinks convex parts): run uo_fit_item.py afterwards, it pushes whatever got into the skin back out.
# Run it with the item(s) selected (Alt+P) BEFORE uo_fit_item.py. Meshes with shape keys or an Armature modifier are skipped (bind first = too late).
# Densify once: running it again subdivides again (only while the edges are still longer than TARGET_EDGE, so a dense item is left alone).
import bpy
import numpy as np

KIND = ""             # kind of item (as in uo_fit_item.py): picks TARGET_EDGE from EDGE_BY_KIND when TARGET_EDGE < 0 ("" = not given)
TARGET_EDGE = -1.0    # m, mean edge length to reach; < 0 = from KIND (EDGE_BY_KIND, else 0.03); 0 = off
# TARGET_EDGE by KIND. Measured (test_density.py, replicas decimated to 10 % and densified, IoU with the sprite and px/frame from the full-density
# render, `docs/qa/density.json`): shirt, pants, boots reach the full-density result at a mean edge <= 5 cm (no gain below), gloves need 2 cm (fingers; at 5 cm
# nothing is subdivided and the gloves stay 16 px/frame off, at 2 cm 4 px). The others are set by analogy (limbs bend like pants / shirt), NOT measured:
# 4 cm for limbs and trunk, 2 cm for small parts, 0 for what does not bend (helmets, rigid items ride on one bone; the push of uo_fit_item.py only needs faces
# not much bigger than the gap, 5 cm).
EDGE_BY_KIND = {"shirt": 0.04, "pants": 0.04, "legs": 0.04, "arms": 0.03, "plate": 0.04, "boots": 0.03, "gloves": 0.02, "neck": 0.02, "harness": 0.04,
                "helm": 0.05, "hair": 0.05, "beard": 0.03}
MAX_LEVEL = 3         # subdivision steps at most
MAX_VERTS = 30000     # vertices at most after densifying
SMOOTH = 0.0          # 0..1, see above


if TARGET_EDGE < 0:
    TARGET_EDGE = EDGE_BY_KIND.get(KIND, 0.03)


def mean_edge(me, mw):
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    co = co @ np.array(mw)[:3, :3].T
    e = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get("vertices", e); e = e.reshape(-1, 2)
    return float(np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1).mean()) if len(e) else 0.0


def level_for(me, mw):
    L, lv = mean_edge(me, mw), 0
    nv = len(me.vertices)
    while lv < MAX_LEVEL and L > TARGET_EDGE and nv * 4 <= MAX_VERTS:      # each step: ~4x the faces, ~4x the vertices of a closed surface
        lv += 1; L /= 2; nv *= 4
    return lv


def subdivided(ob, kind, level):
    md = ob.modifiers.new("uo_densify", "SUBSURF")
    md.subdivision_type = kind; md.levels = md.render_levels = level; md.boundary_smooth = "ALL"; md.use_creases = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(md)
    return new


def densify(ob):
    me = ob.data
    if me.shape_keys or any(m.type == "ARMATURE" for m in ob.modifiers):
        print("uo_densify_item: %s skipped (shape keys or Armature modifier)" % ob.name); return
    lv = level_for(me, ob.matrix_world) if TARGET_EDGE > 0 else 0
    if lv == 0:
        print("uo_densify_item: %s unchanged (mean edge %.1f cm)" % (ob.name, mean_edge(me, ob.matrix_world) * 100)); return
    before = (len(me.vertices), mean_edge(me, ob.matrix_world))
    simple = subdivided(ob, "SIMPLE", lv)
    new = simple
    if SMOOTH > 0:
        cc = subdivided(ob, "CATMULL_CLARK", lv)
        assert len(cc.vertices) == len(simple.vertices)
        a = np.empty(len(simple.vertices) * 3, np.float32); simple.vertices.foreach_get("co", a)
        b = np.empty_like(a); cc.vertices.foreach_get("co", b)
        simple.vertices.foreach_set("co", (a + SMOOTH * (b - a)).astype(np.float32)); simple.update()
        bpy.data.meshes.remove(cc)
    name, old = me.name, me
    ob.data = new; new.name = name + "_dense"
    if old.users == 0:
        bpy.data.meshes.remove(old)
    print("uo_densify_item: %s level %d, %d -> %d vertices, mean edge %.1f -> %.1f cm, SMOOTH %.2f" % (
        ob.name, lv, before[0], len(new.vertices), before[1] * 100, mean_edge(new, ob.matrix_world) * 100, SMOOTH))


for _ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    densify(_ob)
