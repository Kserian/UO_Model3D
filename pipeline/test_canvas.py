"""Regression test of the CANVAS / ANCHOR parameters of render_uo_layer.py.

For every test case the frames are rendered with (a) the reference script (default: the version of commit ea55c0b, 136x120 with
anchor (68, 86) hard-wired), (b) the current script with CANVAS=(136,120) - must be pixel-identical to (a), and (c) the current
script on other canvases - inside the area of the original 136x120 frame (anchors aligned) they must have the same silhouette
and colours within 1 level of (a) (float rounding), and everywhere else the frame must be transparent (the test items fit into
the old canvas). (a) is the old script plus `dither_intensity = 0`: Blender's 8-bit dither is position dependent noise.

    python test_canvas.py [--blend ../model/UO_Body_0x190.blend] [--ref ref_render_uo_layer.py] [--tmp DIR] [--quick]
"""
import argparse, os, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = {      # name: (settings, actions)
    "clothing": ('LAYER="clothing"', ["04_stand", "25_mounted_stand", "09_attack_1h_slash"]),
    "body_model": ('LAYER="body"; EXACT_BODY=False', ["04_stand", "25_mounted_stand"]),   # atlas colours through UOX_* nodes
    "body_exact": ('LAYER="body"; EXACT_BODY=True', ["04_stand", "00_walk_unarmed"]),
    "all": ('LAYER="all"', ["04_stand", "25_mounted_stand"]),
}
CANVASES = [((136, 120), (68, 86)), ((256, 256), (128, 192)), ((200, 180), (90, 130)), ((100, 100), (40, 70))]


def render(blend, script, out, case, actions, canvas=None):
    sets = dict(s.split("=", 1) for s in CASES[case][0].split("; "))
    sets["ONLY"] = repr(actions)
    if "OWN_PARTS_NEVER_HIDE" in open(script).read():      # the reference (commit ea55c0b) has no such rule: switch it off, this test only checks the canvas
        sets["OWN_PARTS_NEVER_HIDE"] = "False"
    if canvas:
        sets["CANVAS"], sets["ANCHOR"] = repr(canvas[0]), repr(canvas[1])
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, out, "--script", script] + ["%s=%s" % kv for kv in sets.items()]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("render failed (%s):\n%s\n%s" % (" ".join(cmd[-6:]), r.stdout[-1500:], r.stderr[-1500:]))
    return os.path.join(out, sets["LAYER"].strip('"'), "frames")


def frames(root):
    for dp, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            if f.endswith(".png"):
                yield os.path.relpath(os.path.join(dp, f), root), np.array(Image.open(os.path.join(dp, f)).convert("RGBA"))


def compare(ref_root, new_root, canvas):
    (W, H), (ax, ay) = canvas
    dx, dy = ax - 68, ay - 86
    ref = dict(frames(ref_root)); new = dict(frames(new_root))
    assert ref.keys() == new.keys(), "different frame lists"
    bad_in = bad_out = 0
    for k, a in ref.items():
        b = new[k]
        assert b.shape == (H, W, 4), (k, b.shape)
        full = np.zeros_like(b)
        y0, y1, x0, x1 = max(dy, 0), min(dy + 120, H), max(dx, 0), min(dx + 136, W)
        full[y0:y1, x0:x1] = a[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        inside = np.zeros((H, W), bool); inside[y0:y1, x0:x1] = True
        diff = np.abs(b.astype(int) - full.astype(int))
        d = diff.max(-1) > (0 if (dx, dy) == (0, 0) and (W, H) == (136, 120) else 1)   # identity canvas: exact; others: 1 level of float rounding
        d |= diff[..., 3] > 0                                                           # the silhouette must always be identical
        bad_in += int((d & inside).sum()); bad_out += int((diff.max(-1) > 0)[~inside].sum())
    return len(ref), bad_in, bad_out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--ref", help="reference script (default: pipeline/test_data/ref_render_uo_layer_ea55c0b.py.txt, the script of commit ea55c0b)")
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--quick", action="store_true", help="only 04_stand")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_canvas_")
    os.makedirs(tmp, exist_ok=True)
    blend = os.path.abspath(a.blend)
    ref = a.ref or os.path.join(tmp, "ref_render_uo_layer.py")
    if not a.ref:                      # the old script plus the one line that turns the position-dependent 8-bit dither off
        old = open(os.path.join(HERE, "test_data", "ref_render_uo_layer_ea55c0b.py.txt"), encoding="utf-8").read()
        assert "sc.render.resolution_percentage = 100\n" in old
        open(ref, "w").write(old.replace("sc.render.resolution_percentage = 100\n", "sc.render.resolution_percentage = 100\nsc.render.dither_intensity = 0.0\n", 1))
    fail = 0
    for case, (_, actions) in CASES.items():
        actions = actions[:1] if a.quick else actions
        ref_root = render(blend, ref, os.path.join(tmp, "ref_" + case), case, actions)
        for canvas in CANVASES:
            root = render(blend, os.path.join(HERE, "render_uo_layer.py"), os.path.join(tmp, "%s_%dx%d" % ((case,) + canvas[0])), case, actions, canvas)
            n, bi, bo = compare(ref_root, root, canvas)
            ok = bi == 0 and bo == 0
            fail += not ok
            print("%-11s canvas %-9s anchor %-10s %3d frames | px off inside the old area: %5d | outside: %5d | %s" % (
                case, "%dx%d" % canvas[0], canvas[1], n, bi, bo, "OK" if ok else "FAIL"))
    print("output in", tmp)
    sys.exit(1 if fail else 0)
