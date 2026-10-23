# Put a cape sheet (uo_cape_sheet.py) on the UO body: the side with the clasps and the folds that run down from them faces OUT (away from the back), the middle of the cape lies on the back,
# the two clasps sit on the shoulders (a little behind them, CLASP) and are the only places that hold it (uo_cape_sim.py pins them); the whole cape is leaned a few degrees about the line of
# the clasps (the top towards the front, the hem back) and moved back until it clears the skin of the rest pose by CLEAR. Run in the rest pose with the cape selected; then
# uo_bind_item.py with PART = "cloak" (skin weights). The model is read in the file's own axes: x = width, y = depth (the clasps and folds are on the -y side), z = height.
import json
import bpy
import numpy as np
from mathutils import Matrix, Vector

SCALE = 0.586         # uniform scale: the clasps of the file are 0.58 m apart, the shoulders of the UO body carry them 0.34 m apart
TURN = 180.0          # deg about the vertical axis: the file's -y side (clasps + folds) goes to +y, the back of the UO body (it looks at -y)
TILT = 5.0            # deg: the top of the cape leans towards the front of the character, the hem goes back, about the line of the two clasps (a few degrees: "hangs from the back")
CLASP = (0.17, 0.17, 1.53)    # m: where each clasp sits on the body (x of the right one; the left is mirrored), y (back is +), z (height), rest pose
CLEAR = 0.02          # m: the cape is moved back until it is this far from the skin of the rest pose everywhere (None = as placed)
PIN_R = 0.050         # m (in the file's units): the vertices of the file within this distance of a clasp centre are the clasp, held by the pin of the simulation
TOP_BAND = 0.07       # m (file units): the clasp centre is the mean of the top vertices of each half within this band under the highest point

ob = next(o for o in bpy.context.selected_objects if o.type == "MESH")
bpy.context.view_layer.objects.active = ob
co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co); V = co.reshape(-1, 3).astype(np.float64)
Mw = np.array(ob.matrix_world); V = V @ Mw[:3, :3].T + Mw[:3, 3]

# the clasps of the file: the top vertices of each half (x < 0 / x > 0)
top = V[:, 2].max(); cen = []
for sgn in (-1, 1):
    m = (np.sign(V[:, 0]) == sgn) & (np.abs(V[:, 0]) > 0.12) & (V[:, 2] > top - TOP_BAND)
    cen.append(V[m].mean(0))
cen = np.array(cen)
pin = np.zeros(len(V), np.int8)                                           # 1 = left clasp (file x < 0), 2 = right clasp
for k in range(2):
    pin[np.linalg.norm(V - cen[k], axis=1) < PIN_R] = k + 1
print("uo_cape_place: clasps of the file at %s and %s, %d + %d vertices" % (np.round(cen[0], 3), np.round(cen[1], 3), int((pin == 1).sum()), int((pin == 2).sum())))

# turn, scale, tilt, place
R = Matrix.Rotation(np.radians(TURN), 4, "Z")
S = Matrix.Scale(SCALE, 4)
mid0 = (S @ R @ Vector(cen.mean(0)))                                      # middle of the clasps after the turn and the scale
Tl = Matrix.Rotation(np.radians(TILT), 4, "X")                            # +x rotation: points below the pivot go to +y (the hem goes back), the top goes to the front
place = Matrix.Translation(Vector((0.0, CLASP[1], CLASP[2]))) @ Tl @ Matrix.Translation(-Vector((mid0.x, mid0.y, mid0.z))) @ S @ R
ob.data.transform(ob.matrix_world @ Matrix())                            # bake the object's own transform into the mesh (it is identity after the import, kept for safety)
ob.matrix_world = Matrix.Identity(4)
ob.data.transform(place)
ob.data.update()
# the clasps should land at x = +-CLASP[0]: report the real spacing (the file's clasps are not exactly where the body's shoulders are)
W = np.array([(place @ Vector(p))[:] for p in cen])
print("uo_cape_place: scale %.3f, turn %.0f, tilt %.1f deg; clasps now at x %.3f / %.3f (wanted +-%.3f), y %.3f, z %.3f" % (SCALE, TURN, TILT, W[0, 0], W[1, 0], CLASP[0], W[:, 1].mean(), W[:, 2].mean()))

# clear of the body: the whole cape goes back (+y) until no vertex is closer to the skin of the rest pose than CLEAR (the clasps are held by the pin, the shoulders and the shoulder blades
# stick out further than the clasps of a shoulder line: the shape of the file does not know this body)
if CLEAR is not None:
    from mathutils.bvhtree import BVHTree
    body = bpy.data.objects["UO_Body"]; dg = bpy.context.evaluated_depsgraph_get(); eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles()
    bv = BVHTree.FromPolygons([eb.matrix_world @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()

    def worst(dy):
        co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co); X = co.reshape(-1, 3).astype(np.float64) + np.array([0.0, dy, 0.0])
        m = np.inf
        for p in X:
            loc, nrm, fi, dist = bv.find_nearest(Vector(p), 0.12)
            if loc is not None:
                m = min(m, dist if (Vector(p) - loc).dot(nrm) >= 0 else -dist)
        return m
    dy = 0.0
    while worst(dy) < CLEAR and dy < 0.10:
        dy += 0.004
    ob.data.transform(Matrix.Translation((0.0, dy, 0.0))); ob.data.update(); W[:, 1] += dy
    print("uo_cape_place: moved %.0f mm back to clear the skin by %.0f mm (clasps now at y %.3f)" % (1000 * dy, 1000 * CLEAR, W[:, 1].mean()))

# the clasp vertices and their rest positions for the simulation (pin group): vertex group "uo_clasp" + the two centres in the object's properties
att = ob.data.attributes.get("uo_clasp") or ob.data.attributes.new("uo_clasp", "INT", "POINT")
att.data.foreach_set("value", pin.astype(np.int32))
ob["uo_cape"] = json.dumps(dict(clasps=[[round(float(x), 4) for x in w] for w in W], pin_r=round(PIN_R * SCALE, 4), tilt=TILT, scale=SCALE))
for o in bpy.context.view_layer.objects:
    o.select_set(o == ob)
bpy.context.view_layer.update()
print("uo_cape_place: done")
