"""Compare / copy the scripts of pipeline/ with the texts embedded in a .blend (the .blend runs ITS OWN copy of a script).

    python sync_blend_scripts.py <file.blend> --check            # which embedded texts differ from the files of pipeline/
    python sync_blend_scripts.py <file.blend> render_uo_layer.py  # copy the given scripts into the .blend and save it
Only the named texts are replaced. Everything else in the .blend stays as it is. Needs: pip install "bpy==4.2.*" (a file saved by Blender 5.x does not open in 4.2: sync with 4.2 to keep both working), or run it inside Blender 5.x with --background --python.
"""
import os, sys
if "--" in sys.argv:                                     # run inside Blender: blender -b --python this.py -- <arguments>
    sys.argv = sys.argv[:1] + sys.argv[sys.argv.index("--") + 1:]

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
blend = os.path.abspath(args.pop(0))
check = args == ["--check"]
bpy.ops.wm.open_mainfile(filepath=blend)
names = [t.name for t in bpy.data.texts if os.path.exists(os.path.join(HERE, t.name))] if check else args
changed = 0
for name in names:
    src = os.path.join(HERE, name)
    new = open(src, encoding="utf-8").read()
    t = bpy.data.texts.get(name)
    old = t.as_string() if t else None
    state = "missing in the .blend" if t is None else ("identical" if old == new else "DIFFERENT (%d -> %d chars)" % (len(old), len(new)))
    print("%-28s %s" % (name, state))
    if not check and old != new:
        t = t or bpy.data.texts.new(name)
        t.clear(); t.write(new); changed += 1
if not check and changed:
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("saved", blend)
