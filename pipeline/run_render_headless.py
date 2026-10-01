"""Run render_uo_layer.py headless (bpy module) on a .blend with some settings overridden.

    python run_render_headless.py <file.blend> <out_dir> [--script render_uo_layer.py] [NAME=<python literal> ...]
    python run_render_headless.py ../model/UO_Body_0x190.blend /tmp/out LAYER='"body"' ONLY='["04_stand"]' CANVAS='(136,120)' ANCHOR='(68,86)'
    --pre file.py runs a script (with bpy) after the .blend is opened and before the render, e.g. to add a test object.

The script text comes from the given file (default: render_uo_layer.py next to this one), not from the text embedded in the
.blend, so a change in pipeline/ can be tested without touching the .blend. Output goes to <out_dir>/<LAYER>/ and <out_dir>/<LAYER>.vd.
The .blend is only read, never saved. Needs: pip install numpy "bpy==4.2.*"
"""
import os, re, sys

import bpy

args = sys.argv[1:]
blend, out_dir = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_uo_layer.py")
pre = None
while args and args[0] in ("--script", "--pre"):
    flag = args.pop(0)
    if flag == "--script":
        script = os.path.abspath(args.pop(0))
    else:
        pre = os.path.abspath(args.pop(0))
over = dict(a.split("=", 1) for a in args)
over.setdefault("OUT_DIR", repr(out_dir + "/"))
over.setdefault("VD_FILE", repr(out_dir + "/%s.vd"))

text = open(script).read()
for k, v in over.items():
    text, n = re.subn(r"^%s\s*=.*$" % re.escape(k), "%s = %s" % (k, v), text, count=1, flags=re.M)
    if n != 1:
        sys.exit("setting %s not found in %s" % (k, script))

bpy.ops.wm.open_mainfile(filepath=blend)
if pre:
    exec(compile(open(pre).read(), pre, "exec"), {"__name__": "__pre__", "bpy": bpy})
exec(compile(text, script, "exec"), {"__name__": "__main__", "__file__": script})
