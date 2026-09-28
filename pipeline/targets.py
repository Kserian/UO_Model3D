import numpy as np
from vd import read_vd, ACTIONS_PEOPLE
from body import CANVAS_W, CANVAS_H, ANCHOR_X, ANCHOR_Y

_cache = {}


def load(path="body400.vd"):
    if path not in _cache:
        _cache[path] = read_vd(path)
    return _cache[path]


def frame_canvas(f):
    """Place a decoded frame on the fixed canvas with its anchor at (ANCHOR_X, ANCHOR_Y)."""
    rgba = np.zeros((CANVAS_H, CANVAS_W, 4), np.uint8)
    x0 = ANCHOR_X - f["cx"]
    y0 = ANCHOR_Y - (f["cy"] + f["h"])
    img = f["img"]
    h, w = img.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    ex, ey = min(w, CANVAS_W - x0), min(h, CANVAS_H - y0)
    assert sx0 == 0 and sy0 == 0 and ex == w and ey == h, "frame exceeds canvas"
    rgba[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex] = img[sy0:ey, sx0:ex]
    return rgba


def targets(action, frame=None, path="body400.vd"):
    """Returns array (F,5,H,W,4) uint8 for all frames (or one) of an action."""
    _, _, anims = load(path)
    n = len(anims[(action, 0)])
    idx = range(n) if frame is None else [frame]
    return np.stack([[frame_canvas(anims[(action, d)][i]) for d in range(5)] for i in idx])
