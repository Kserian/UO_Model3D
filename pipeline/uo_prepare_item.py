# One step from an imported item to a skinned one, with the settings of its SLOT: uo_autofit_item.py -> uo_densify_item.py -> uo_fit_item.py -> uo_bind_item.py.
# Select the item (after uo_import_item.py), set KIND (the slot) and run (Alt+P). What each slot gets, and why:
#   mesh density   uo_densify_item.py EDGE_BY_KIND: a low-poly item is subdivided (shape unchanged) to the mean edge length the slot needs, so that it
#                  bends smoothly at elbows / knees / hips and no face is bigger than the gap to the skin. Rigid slots (hair, beard, hat) are not densified:
#                  they do not bend.
#   distance       uo_fit_item.py GAP_BY_KIND: how far from the skin (tight cloth 1.5 cm, armour / helmets / sleeves 3 cm).
#   skinning       uo_bind_item.py PART: which bones the item follows (and RIGID presets: hair on the head).
# The settings are measured where noted in the scripts (docs/qa/slot_geometry.md); weights stay "as the skin under the item" (SMOOTH 4, STIFF 1): the originals
# do not tell another policy from it (docs/qa/bind_sweep.json: SMOOTH 0..12 and STIFF 0.5..4 change the IoU with the sprites by +-0.002 at most).
import json
import os
import re
import bpy

KIND = "shirt"        # slot: shirt, plate, arms, pants, legs, boots, gloves, helm, neck, hair, beard, hat, robe, skirt, harness, waist, vest, quiver
AUTOFIT = True        # first uo_autofit_item.py: units, size and place from the skin the slot covers (False: the item already stands where it should)
DENSIFY = True        # False: keep the mesh as it is
FIT = True            # False: skip uo_fit_item.py (the item already sits right)

# KIND -> (PART of uo_bind_item.py, densify?, class). class: "tight" (cloth / leather close to the skin), "hard" (armour, thick: keeps its distance, 3 cm),
# "rigid" (one bone). Same parts as EXTENTS of uo_import_item.py.
SLOTS = {
    "shirt":  ("chest", True, "tight"), "pants": ("legs", True, "tight"), "boots": ("boots", True, "tight"), "gloves": ("gloves", True, "tight"),
    "plate":  ("chest", True, "hard"),  "arms":  ("arms", True, "hard"),  "legs":  ("legs", True, "hard"),   "helm":   ("helm", True, "hard"),
    "neck":   ("neck", True, "hard"),
    "robe":   ("robe", True, "loose"), "skirt": ("skirt", True, "loose"), "cloak": ("cloak", True, "loose"),
    "waist":  ("torso", True, "tight"), "vest": ("chest", True, "tight"),   # belt / sash (Waist), waistcoat / doublet (MiddleTorso): measured ranges, settings by analogy (docs/qa/autofit.md)
    "harness": ("torso", True, "tight"),   # straps over the trunk (follow pelvis / spine / chest / neck only)
    "quiver": ("quiver", False, "rigid"),  # a quiver, a sword on the back: rigid on the chest (custom properties uo_no_body_gap, uo_behind_torso: render_uo_layer.py)
    "hair":   ("hair", False, "rigid"), "beard": ("beard", False, "rigid"), "hat":   ("hat", False, "rigid"),
}


def source(name):
    """the script's text: from the folder UO_SCRIPTS when that is set (development, tests, uo_make_item.py), else the copy inside the .blend, else ../pipeline"""
    env = os.environ.get("UO_SCRIPTS")
    if env and os.path.exists(os.path.join(env, name)):
        return open(os.path.join(env, name), encoding="utf-8").read()
    t = bpy.data.texts.get(name)
    if t is not None:
        return t.as_string()
    here = env or os.path.dirname(os.path.abspath(bpy.data.filepath)) + "/../pipeline"
    return open(os.path.join(here, name), encoding="utf-8").read()


EXTRA = json.loads(os.environ.get("UO_PREPARE_EXTRA", "{}"))     # {"uo_fit_item.py": {"MIN_GAP": 0.02}, ...}: settings for the steps (uo_make_item.py "tune")


def run(name, **over):
    over = dict(EXTRA.get(name, {}), **over)
    text = source(name)
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % k, "%s = %r" % (k, v), text, count=1, flags=re.M)
        assert n == 1, (name, k)
    exec(compile(text, name, "exec"), {"__name__": "__main__"})


if KIND not in SLOTS:
    raise ValueError("KIND must be one of %s" % list(SLOTS))
_part, _dens, _cls = SLOTS[KIND]
print("uo_prepare_item: KIND %s -> PART %s, class %s" % (KIND, _part, _cls))
try:
    import scipy                                      # noqa: F401
    _scipy = True
except ImportError:
    _scipy = False
if AUTOFIT and not _scipy:
    print("uo_prepare_item: scipy is not installed in this Python: no fit to the skin (uo_autofit_item.py); the item stays where uo_import_item.py put it")
elif AUTOFIT:
    run("uo_autofit_item.py", KIND=KIND)
if DENSIFY and _dens:
    run("uo_densify_item.py", KIND=KIND)
if FIT:
    run("uo_fit_item.py", KIND=KIND)
run("uo_bind_item.py", PART=_part)
# Cloth and leather keep the dark details of their texture (laces, buttons, stitches): the renderer's DESPECKLE (single dark pixels inside the item) is meant for sculpted
# armour (rivets, deep folds) and removed the front closure of a gambeson. Hard items keep it; "tune": {"scene": {"uo_despeckle": 0}} in a recipe overrides.
_dsp = EXTRA.get("scene", {}).get("uo_despeckle", 0 if _cls in ("tight", "loose") else None)
if _dsp is not None:
    _sc = bpy.context.scene
    _sc["uo_despeckle"] = min(int(_dsp), int(_sc["uo_despeckle"])) if "uo_despeckle" in _sc else int(_dsp)
    print("uo_prepare_item: renderer DESPECKLE %d (scene property uo_despeckle)" % _sc["uo_despeckle"])
