"""Blender version differences used by the pipeline scripts (4.2 ... 5.2).

    from bpy_compat import action_fcurves, find_fcurve, clear_fcurves, new_fcurve, eevee_engine

Blender 5.0 removed the direct Action.fcurves (an action has slots, layers and strips now: the curves of a slot live in a
"channelbag"). The helpers give the same code one answer on both sides of that change. Blender 5.0 also renamed the engine
'BLENDER_EEVEE_NEXT' back to 'BLENDER_EEVEE'.
"""
import bpy


def _bags(action, create=False):
    """channelbags of an action in 5.x (one per slot); create=True makes slot / layer / strip when the action is empty"""
    if create:
        if not action.slots:
            action.slots.new(id_type="OBJECT", name="Legacy Slot")
        if not action.layers:
            action.layers.new("Layer")
        layer = action.layers[0]
        if not layer.strips:
            layer.strips.new(type="KEYFRAME")
        strip = layer.strips[0]
        return [strip.channelbag(action.slots[0], ensure=True)]
    return [cb for layer in action.layers for strip in layer.strips if strip.type == "KEYFRAME" for cb in strip.channelbags]


def action_fcurves(action):
    """list of all F-curves of the action (a live collection before 5.0, a list of the channelbag curves from 5.0)"""
    if hasattr(action, "fcurves"):
        return action.fcurves
    return [fc for cb in _bags(action) for fc in cb.fcurves]


def find_fcurve(action, data_path, index=0):
    for fc in action_fcurves(action):
        if fc.data_path == data_path and fc.array_index == index:
            return fc
    return None


def clear_fcurves(action, data_path=None):
    """remove every F-curve of the action (or only those with the given data path)"""
    if hasattr(action, "fcurves"):
        for fc in [fc for fc in action.fcurves if data_path is None or fc.data_path == data_path]:
            action.fcurves.remove(fc)
        return
    for cb in _bags(action):
        for fc in [fc for fc in cb.fcurves if data_path is None or fc.data_path == data_path]:
            cb.fcurves.remove(fc)


def new_fcurve(action, data_path, index=0):
    if hasattr(action, "fcurves"):
        return action.fcurves.new(data_path, index=index)
    return _bags(action, create=True)[0].fcurves.new(data_path, index=index)


def eevee_engine():
    """identifier of the EEVEE render engine of this Blender"""
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    return "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in ids else "BLENDER_EEVEE"
