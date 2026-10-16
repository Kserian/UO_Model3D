---
name: uo-environment-tests
description: Environment setup (Python, bpy), syncing scripts into the .blend, running tests, known pitfalls. Use before running pipeline/ scripts, changing model/*.blend, or testing.
---

- `pip install numpy pillow scipy "bpy==4.2.*"` (Python 3.11; Blender itself not needed); optional `numba` makes the numpy rig raster of `pose_lib.py` ~7x faster (pose fitting). Save `.blend` files with bpy 4.2 (a file saved in 5.x does not open in 4.2). The item pipeline also runs on bpy 5.2 (Python 3.13), but an `item.blend` saved in 5.2 opens only in 5.x; sync the model in 4.2.
- `model/UO_Body_0x190.blend` is binary with scripts embedded as texts. Source of truth is `pipeline/*.py`; `pipeline/sync_blend_scripts.py` copies them in (`--check` shows differences). Say in the commit which binary changed; back up `model/` outside the repo before changing it.
- Headless tests: `run_render_headless.py`, `test_items.py` (~4 min), `test_canvas.py` (~2 min), `test_import_item.py`, `test_materials.py`. Options are in the script headers.
- Pitfalls: `pkill/pgrep -f` with a pattern present in your own command kills the shell (use `ps -eo pid,args | grep "[p]attern"`); `BVHTree.FromObject` works in the object's local space (`UO_Body` is rotated per direction); `bpy.app.driver_namespace` in background mode segfaults on exit; renormalise weights after deleting bone vertex groups.
