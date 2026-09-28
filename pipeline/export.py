import bpy, sys, os
blend = sys.argv[sys.argv.index("--blend") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
base = os.path.splitext(os.path.abspath(blend))[0]
arm = bpy.data.objects["UO_Rig"]
arm.animation_data.action = bpy.data.actions.get("04_stand") or arm.animation_data.action
# exporters understand a plain Principled BSDF with a base-colour texture: bypass the "UO look" mix for export
for m in bpy.data.materials:
    if m.use_nodes:
        nodes = m.node_tree.nodes
        out = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if out and bsdf:
            m.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
body = bpy.data.objects["UO_Body"]
if body.data.shape_keys:                    # per-frame corrective keys only serve the UO renders inside Blender
    body.shape_key_clear()
bpy.ops.object.select_all(action="DESELECT")
for name in ("UO_Rig", "UO_Body"):          # the body model only (no example clothing, camera or lights)
    bpy.data.objects[name].select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects["UO_Rig"]
bpy.ops.export_scene.gltf(
    filepath=base + ".glb", export_format="GLB", use_selection=True,
    export_animations=True, export_animation_mode="ACTIONS", export_skins=True,
    export_texcoords=True, export_normals=True, export_materials="EXPORT",
    export_cameras=False, export_lights=False, export_yup=True, export_apply=False,
    export_force_sampling=True, export_optimize_animation_size=False)
bpy.ops.export_scene.fbx(
    filepath=base + ".fbx", use_selection=True, object_types={"ARMATURE", "MESH"},
    add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
    path_mode="COPY", embed_textures=True, primary_bone_axis="Y", secondary_bone_axis="X",
    use_armature_deform_only=False, mesh_smooth_type="FACE")
print("exported", base + ".glb", base + ".fbx")
