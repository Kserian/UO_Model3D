"""Copy the keys of bow.L (pose.bones["bow.L"]) of some actions from one item.blend into another (bpy).
The clearance search of uo_bow_hold.py (CONE_BY) depends on the vertices of the bow: a denser mesh of the same bow gave other tilts in 16 / 17 / 30. The bone and the mesh stay
the same within 3 mm, so a pose that was approved on one build is carried over to the other and only rendered again.

    ACTS=7,8,16,17,30 python copy_bow_poses.py SOURCE.blend TARGET.blend OUT.blend
"""
import os, sys
import bpy

src, dst, out = sys.argv[-3:]
acts_keep = {int(x) for x in os.environ.get("ACTS", "7,8,16,17,30").split(",")}
bpy.ops.wm.open_mainfile(filepath=src)
S = {a.name: [(f.data_path, f.array_index, [(k.co[0], k.co[1], k.interpolation) for k in f.keyframe_points])
              for f in a.fcurves if 'pose.bones["bow.L"]' in f.data_path] for a in bpy.data.actions if a.get("uo_action") in acts_keep}
bpy.ops.wm.open_mainfile(filepath=dst)
for a in bpy.data.actions:
    if a.name in S:
        for f in [f for f in a.fcurves if 'pose.bones["bow.L"]' in f.data_path]:
            a.fcurves.remove(f)
        for dp, idx, kps in S[a.name]:
            f = a.fcurves.new(dp, index=idx, action_group="bow.L")
            f.keyframe_points.add(len(kps))
            for k, (x, y, ip) in zip(f.keyframe_points, kps):
                k.co = (x, y); k.interpolation = ip
            f.update()
        print("copy_bow_poses: %s, %d curves" % (a.name, len(S[a.name])))
bpy.ops.wm.save_as_mainfile(filepath=out)
