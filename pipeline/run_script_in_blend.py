"""python run_script_in_blend.py <file.blend> <script.py>: open the .blend (bpy module) and run the script with bpy in its globals (the .blend is not saved)."""
import sys, os
if "--" in sys.argv:                                     # run inside Blender: blender -b --python this.py -- <arguments>
    sys.argv = sys.argv[:1] + sys.argv[sys.argv.index("--") + 1:]
import bpy
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(sys.argv[1]))
sc = os.path.abspath(sys.argv[2])
exec(compile(open(sc).read(), sc, "exec"), {"__name__": "__main__", "bpy": bpy})
sys.stdout.flush(); sys.stderr.flush()
os._exit(0)                                           # the bpy module can segfault while it shuts down, after the work is done
