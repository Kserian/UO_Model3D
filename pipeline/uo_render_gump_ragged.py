"""Paperdoll gumps (male / female) and the item icon (art) of the torn robe (docs/qa/robe_ragged.md): a plain grey robe with holes on purpose, a hood lying on the back, no gold.

    PD_OUT=DIR PD_REF_MALE=50469.png PD_REF_FEMALE=60469.png PD_BODY_MALE=12.png PD_BODY_FEMALE=13.png PD_ART_REF=7939.png \
        python run_script_in_blend.py ITEM.blend uo_render_gump_ragged.py

The FIT is that of uo_render_gump_fit.py (its definitions are loaded from that file, its own main part is not run and the file is not changed): per gender the scale x (shoulders / hem) and y
to the silhouette of the original robe's gump (50469 / 60469) without the sleeves' region, the woman's torso narrowed to the drawn body 13 (FIT_TORSO, the upper sleeve 0.7 wide), each upper
arm along shoulder -> elbow of the drawn body (JOINTS of gumps 12 / 13) and each forearm aimed until the sleeve's mouth ends on the drawn wrist.
The LOOK is this robe's own (that script's compose / sym_trims / smooth_cloth / texture_cloth are made for a robe with gold bands and a standing collar, and they fill every hole):
  - the textured render with the body as a holdout (holes over the body are transparent: the paperdoll body shows through them, as in the animation), box-filtered from SS x SS;
  - the grey mapped to the original gump's levels (p5 / p50 / p95 of its luminance: the standard robe grey that takes a hue);
  - dark specks and slits darker than DARK of the cloth around (the inside of the robe seen through a hole where no body is behind) kept: they read as the holes; single dark pixels evened;
  - the body gump's skin within COVER_PX of the robe taken in (a bare shoulder / forearm next to the sleeve), not inside the robe's holes, not the hands, head, feet;
  - a line where a sleeve meets the torso (a render of the uo_region labels, like render_uo_layer.py INNER_LINE), the outline 1 px darker (OUTLINE_K), 1-px spikes of the ragged hem cut.
Art: the robe laid flat (arms out ART_ARMS, front view), turned ART_TURN, stretched into the box of the original icon (PD_ART_REF), the same look; the mirrored icon too.
Writes gump_male.png, gump_female.png, art.png, art_mirror.png (and the same as .bin: a Gumpart.mul / art.mul entry), fit.json in PD_OUT.
"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get("__file__") or sys.argv[2])))
import uo_gump_art as ga
HERE = os.path.dirname(os.path.abspath(globals().get("__file__") or sys.argv[2]))   # run_script_in_blend.py passes no __file__: the script is its second argument
_src = open(os.path.join(HERE, "uo_render_gump_fit.py"), encoding="utf-8").read()
exec(compile(_src[:_src.index("\nreport = {}")], "uo_render_gump_fit.py", "exec"), globals())   # settings, scene setup and the fit functions only

LINE_K = float(os.environ.get("PD_LINE_K", "0.75"))      # the sleeve / torso line (render_uo_layer.py INNER_LINE of this robe: 0.75)
OUTLINE_K = float(os.environ.get("PD_OUTLINE_K", "0.55"))
DARK = float(os.environ.get("PD_DARK", "0.3"))           # pixels darker than this share of the cloth's median are a hole's inside: kept dark (not evened away)
ART_ARMS = float(os.environ.get("PD_ART_ARMS", "0"))      # deg the arms are raised for the laid robe: 0 = as at rest (40 deg from the vertical); 15 spread them wide (icon IoU 0.67, at 0: 0.74)
ART_MIRROR = os.environ.get("PD_ART_MIRROR", "0") == "1"   # 1 = the icon mirrored (a model laid the other way round)
HOLE_TOP = int(os.environ.get("PD_HOLE_TOP", "120"))     # gump row: gaps in the robe above it are filled (shoulders / sleeve roots), below it the rips stay open
SHOULDER_ROWS, SHOULDER_PX = (84, 104), 10                # gump rows of the shoulders and how far from the robe their skin is covered
NECK_X, NECK_HALF = 92, 7                                  # the drawn neck (bodies 12 / 13: columns 85-97 / 86-94): its skin stays (the V-neck)
SPECK_K = 0.6                                              # single pixels darker than this share of their neighbours: evened


def region_labels(w, h, ppm, cx, cz, holdout):
    """per pixel: 1 = a sleeve of the robe (uo_region 1-4), 0 = its torso part, -1 = no robe (a render of the labels, flat emission)"""
    obs = [o for o in items if "uo_region" in o.data.attributes]
    if not obs:
        return None
    m = bpy.data.materials.new("pd_region"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = "uo_region"
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(at.outputs["Fac"], em.inputs["Strength"]); em.inputs["Color"].default_value = (0.25, 0.25, 0.25, 1); nt.links.new(em.outputs[0], out.inputs["Surface"])
    keep = {o.name: [sl.material for sl in o.material_slots] for o in obs}
    for o in obs:
        for sl in o.material_slots:
            sl.material = m
    try:
        a = render(tmp, w, h, ppm, cx, cz, items, holdout)
    finally:
        for o in obs:
            for sl, mt in zip(o.material_slots, keep[o.name]):
                sl.material = mt
    lab = np.full(a.shape[:2], -1, np.int8); on = a[..., 3] > 0.5
    lab[on] = (a[..., 0][on] > 0.12).astype(np.int8)            # 0.25 x label 0..4 in Standard view: the torso 0, a sleeve >= 0.25
    return lab


def holes_of(m):
    return ndimage.binary_fill_holes(m) & ~m


def finish(a, ref, lab=None):
    """levels, specks, sleeve line, ragged edge, outline (a: RGBA float on the target grid; lab: region labels on the same grid)"""
    m = a[..., 3] > 0
    lv, _ = match_levels(a, ref); out = lv
    lum = lv[..., :3] @ LW; med = np.median(lum[m])
    hole_dark = m & (lum < DARK * med)                                       # the inside of the robe seen through a hole: stays
    for _ in range(3):                                                       # single dark pixels (the texture's grain at the gump scale)
        out, n = despeckle1(out, SPECK_K)
        if not n:
            break
    out[hole_dark, :3] = lv[hole_dark, :3]
    if lab is not None:                                                      # a sleeve over the torso: the torso pixels next to it darker
        line = m & (lab == 0) & ndimage.binary_dilation(m & (lab == 1), iterations=1)
        out[line, :3] *= LINE_K
    m2 = (ndimage.binary_opening(m, iterations=1) | ndimage.binary_erosion(m, iterations=1)) & m   # 1-px spikes of the ragged hem cut off
    out[..., 3] = m2
    edge = m2 & ~ndimage.binary_erosion(m2, iterations=1, border_value=0)
    out[edge, :3] *= OUTLINE_K
    return out


def cover_skin(a, body_png, ref, joints):
    """cover_body() of uo_render_gump_fit.py, but the robe's holes stay open (the body shows through them on purpose)"""
    m = a[..., 3] > 0; hl = holes_of(m)
    up = hl.copy(); up[HOLE_TOP:] = False                                    # above the waist the robe has no holes (closed on import): a gap there is where the sleeve
    if up.any():                                                             # leaves the torso in the gump's arm pose -> the cloth around
        _, (iy, ix) = ndimage.distance_transform_edt(~m, return_indices=True)
        a = a.copy(); a[up, :3] = a[iy[up], ix[up], :3]; a[up, 3] = 1.0; hl &= ~up
    out, n, left = cover_body(a, body_png, ref, joints, neck=False)
    back = hl & (out[..., 3] > 0) & ~(a[..., 3] > 0)
    out[back, 3] = 0.0
    bb = np.asarray(Image.open(body_png).convert("RGBA"))[..., 3] > 0      # the shoulders: the drawn body (13) is broader there than the robe -> its skin up to SHOULDER_PX
    m2 = out[..., 3] > 0; d, (iy, ix) = ndimage.distance_transform_edt(~m2, return_indices=True)   # from the robe, outside the neck, taken in
    Y, X = np.mgrid[0:GH, 0:GW]
    sh = bb & ~m2 & (d <= SHOULDER_PX) & (Y >= SHOULDER_ROWS[0]) & (Y <= SHOULDER_ROWS[1]) & (np.abs(X - NECK_X) > NECK_HALF)
    out[sh, :3] = out[iy[sh], ix[sh], :3]; out[sh, 3] = 1.0
    return out, n - int(back.sum()) + int(sh.sum()), left - int(sh.sum())


report = {}
tmp = os.path.join(OUT, "_tmp.png")
for gender, refp in REFS.items():
    if not refp:
        continue
    ref = np.asarray(Image.open(refp).convert("RGBA")); refm = ref[..., 3] > 0
    TORSO.clear(); pose_arms(0, 0); before = iou(raster(to_gump(flat_tris(items), (1, 1, 1, 0, 0)), GW, GH, 1), refm)
    r = fit_body(refm); kxt, kxb, ky, dx, dy = r.x; P = tuple(r.x); torso = None
    if FIT_TORSO.get(gender) and BODIES.get(gender):                        # the woman: the torso fitted to the drawn body 13, the scale / shift again, the torso once more
        P = (min(kxt, 1.0), kxb, ky, dx, dy); fit_torso(BODIES[gender], P)
        r = fit_body(refm, 1.0); kxt, kxb, ky, dx, dy = r.x; P = tuple(r.x); torso = fit_torso(BODIES[gender], P)
    uw = UPPER_W.get(gender, 1.0)
    wr, ce, gp, ov = fit_cuffs(JOINTS[gender], P, BODIES[gender], refm, uw)
    arms = pose_arms_to(JOINTS[gender], P, wr, uw)
    k0 = min(kxt, kxb, ky); W, H = GW * SS, GH * SS
    cxw = (GW / 2 - GX0) / PXM; czw = (GY_FEET - GH / 2) / PXM
    a = render(tmp, W, H, PXM * SS * k0, cxw / k0, czw / k0, items, True)
    lab = region_labels(W, H, PXM * SS * k0, cxw / k0, czw / k0, True)
    Yo, Xo = np.mgrid[0:H, 0:W].astype(np.float64) + 0.5                    # world (x, z) -> gump with kx(z), ky, the shift (as uo_render_gump_fit.py)
    z = (SS * (GY_FEET + dy) - Yo) / (SS * PXM * ky); xw = (Xo - SS * (GX0 + dx)) / (SS * PXM * kx_at(z, kxt, kxb))
    Yi, Xi = SS * GY_FEET - z * SS * PXM * k0 - 0.5, SS * GX0 + xw * SS * PXM * k0 - 0.5
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    wa = np.stack([ndimage.map_coordinates(pm[..., c], [Yi, Xi], order=1, mode="constant", cval=0.0) for c in range(4)], -1).astype(np.float32)
    wa[..., :3] /= np.maximum(wa[..., 3:], 1e-6)
    res = box_down(wa, SS)
    labg = None
    if lab is not None:
        lw = ndimage.map_coordinates(lab.astype(np.float32), [Yi, Xi], order=0, mode="constant", cval=-1)
        h_, w_ = GH, GW; lb = lw[:h_ * SS, :w_ * SS].reshape(h_, SS, w_, SS)
        labg = np.where((lb == 1).mean((1, 3)) >= 0.5, 1, np.where((lb == 0).mean((1, 3)) > 0, 0, -1)).astype(np.int8)
    res, covered, skin_left = cover_skin(res, BODIES[gender], refm, JOINTS[gender])
    res = finish(res, ref, labg)
    Image.fromarray(to8(res)).save(os.path.join(OUT, "gump_%s.png" % gender))
    data, extra = ga.encode_gump(to8(res)); open(os.path.join(OUT, "gump_%s.bin" % gender), "wb").write(data)    # a Gumpart.mul entry (Gumpidx.mul extra = width << 16 | height)
    m = res[..., 3] > 0
    report[gender] = dict(kx_top=round(kxt, 3), kx_hem=round(kxb, 3), ky=round(ky, 3), dx=round(dx, 1), dy=round(dy, 1), torso=torso, arms_deg=arms, forearm_target=wr, cuff_error_px=ce,
                          forearm_bare_px=gp, hand_covered_px=ov, covered_px=covered, skin_left_px=skin_left, holes_px=int(holes_of(m).sum()),
                          iou_rest=round(before, 3), iou_render=round(iou(m, refm), 3))
    print("GUMP %s: %s" % (gender, report[gender]), flush=True)

if ART_REF:                                  # the robe laid flat, turned, fitted to the box of the original icon
    ref = np.asarray(Image.open(ART_REF).convert("RGBA")); ys, xs = np.nonzero(ref[..., 3] > 0)
    rb = (xs.min(), ys.min(), xs.max(), ys.max()); AW, AH = ref.shape[1], ref.shape[0]
    TORSO.clear(); pose_arms(ART_ARMS, 0, 1.0)
    tr = flat_tris(items); lo = tr.reshape(-1, 2).min(0); hi = tr.reshape(-1, 2).max(0)
    ppm = 400.0; w, h = int((hi[0] - lo[0]) * ppm) + 8, int((hi[1] - lo[1]) * ppm) + 8
    a = render(tmp, w, h, ppm, (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, items, False)
    S4 = 4; bw, bh = (rb[2] - rb[0] + 1) * S4, (rb[3] - rb[1] + 1) * S4
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    im = Image.fromarray(np.clip(pm * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").rotate(ART_TURN, resample=Image.BICUBIC, expand=True)
    rot = np.asarray(im, np.float32) / 255.0; yy, xx = np.nonzero(rot[..., 3] > 0.5); rot = rot[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    rs = np.stack([np.asarray(Image.fromarray(rot[..., c]).resize((bw, bh), Image.BILINEAR)) for c in range(4)], -1)
    rs[..., :3] /= np.maximum(rs[..., 3:], 1e-6)
    big = np.zeros((AH * S4, AW * S4, 4), np.float32); big[rb[1] * S4:rb[1] * S4 + bh, rb[0] * S4:rb[0] * S4 + bw] = rs
    art = finish(box_down(big, S4), ref)
    if ART_MIRROR:
        art = art[:, ::-1].copy()
    Image.fromarray(to8(art)).save(os.path.join(OUT, "art.png"))
    Image.fromarray(to8(art[:, ::-1])).save(os.path.join(OUT, "art_mirror.png"))
    for nm, im_ in (("art", art), ("art_mirror", art[:, ::-1])):                # art.mul entries
        open(os.path.join(OUT, nm + ".bin"), "wb").write(ga.encode_art(to8(im_)))
    report["art"] = dict(turn=ART_TURN, box_ref=[int(v) for v in rb], iou=round(iou(art[..., 3] > 0, ref[..., 3] > 0), 3))
    print("ART: %s" % report["art"], flush=True)
json.dump(report, open(os.path.join(OUT, "fit.json"), "w"), indent=1, default=str)
if os.path.exists(tmp):
    os.remove(tmp)
