# Harp (instrument) for the right and the left hand: design for a generated model

Not built yet: no model file. This is the shape the model must have so that the item pipeline (`uo_orient_weapon.py` -> `uo_place_weapon.py` -> `uo_bind_item.py`, part `weapon1h` / `weapon.L`, like the horn) puts it in the hand well, and the meshy.ai prompt to generate it.

## What the pipeline does with a held item (why the shape is what it is)

- The long axis of the mesh (principal axis) becomes the shaft, the widest side the flat (+X), the thinnest side +Y. **The bounding-box middle of the cross-section goes onto the grip line**: the hand holds the item in the middle of its width, never on one side. So the part held in the hand must sit at the bottom, in the middle of the width.
- In the stand pose bone `weapon1h.R` holds the item like a sword: shaft forward at hip height (0.92 m), flat plane vertical. In profile (directions 1-3) the camera sees the whole face of the harp, in direction 0 its edge.
- Free room around the shaft over all 35 actions (closest body part 2 cm, the hand itself left out): towards -X and +Y almost always > 0.45 m; towards +X and -Y only 0.15-0.25 m in walk, run, 1H slash / pierce, fidget 2. Anything 0.15 m below the hand touches the body in nearly every action.

## Measured candidate shapes (point clouds of a triangular frame + string plane on `weapon1h.R`, all 35 actions, every frame)

Share of the item inside the body (grip zone of 6 cm left out); the same metric gives a horn-like column 1.45 % (butt -0.04) and 9.4 % (butt -0.19, the class default the horn uses):

| shape | butt -0.04 | butt -0.10 | butt -0.19 |
|---|---|---|---|
| V frame, foot in the middle, H 0.65, W 0.40 | 0.92 % | 3.1 % | 6.4 % |
| V frame, foot in the middle, H 0.65, W 0.30 | 0.98 % | 3.1 % | 6.1 % |
| classic triangle, pillar over the foot (foot off-centre) H 0.65, W 0.40 | 0.88 % | 1.2 % | 2.1 % |
| classic triangle, soundbox over the foot, H 0.65, W 0.40 | 2.2 % | 4.1 % | 7.1 % |

- **Nothing below the hand** matters most: butt -0.04 is 3-7x better than the default -0.19.
- Width 0.30 or 0.40 hardly changes anything; taller is a little better (0.75: 0.80 %).
- A classic harp with the pillar over the foot collides as little, but the pipeline would put the hand in the middle of the strings (foot 0.2 m off the grip line). The **V frame with the foot (and the handle) in the middle** is the shape that needs no code change. The worst actions are the same for every shape (18, 27 bow, 29 mounted 2H, 21 die forward: hands together or on the ground).

## The shape

- Total height **0.65 m** (23 px at 36 px/m), width **~0.35 m** (13 px), depth 5-6 cm (2 px edge-on); height:width about 1.9:1 so the long axis is unambiguous.
- Bottom: a round handle Ø 3-4 cm, ~10 cm long (1/6 of the height), with a ball pommel; the harp foot starts right above the fist.
- V frame from the foot: a slim straight **pillar** (>= 4 cm) on one side, a thicker tapered **soundbox** (>= 7 cm) on the other; on top a thick S-curved **neck** (>= 5 cm). Every part >= 1.5-2 px wide (a 3 cm part is 1 px: `thicken` exists, but better the model has it).
- Strings: no thin cords (1 px or less: they flicker from frame to frame); a thin flat panel inside the frame with 5-6 thick raised strings, lighter than the frame, reads as the strings area.
- Colour: warm, medium (honey-brown) wood and pale gold strings; no black, no shiny metal (UO light darkens, `METAL` null); no carvings, knots, gems, tuning pins.

## meshy.ai (Text to 3D; prompt max 600 characters)

Prompt (556 characters):

```
Stylized low-poly fantasy lap harp game prop, standing upright, front view, strings facing the viewer. V-shaped wooden frame almost twice as tall as wide: a slim straight pillar on the left and a thicker tapered soundbox on the right meet at the bottom in one narrow foot, joined on top by a thick, gently S-curved neck. Under the foot a short round wooden handle with a ball pommel, one sixth of the height. Strings: a thin flat panel filling the frame with 6 thick raised vertical strings. Chunky smooth shapes, warm honey-brown wood, pale gold strings.
```

Negative prompt:

```
carvings, engravings, filigree, celtic knots, gems, inlays, ornaments, tiny details, many thin strings, tuning pins, fragile thin parts, floating parts, stand, pedestal, base, ground plane, hands, person, text, black, dark wood, shiny metal, glass, transparency
```

Settings: symmetry off (pillar and soundbox differ), triangle mesh, 10-30k polygons (the pipeline reduces to 30k), texture without metallic. Check before using: one piece, the handle at the bottom in the middle of the width, no holes in the frame, strings not a mess of thin wires.

## Recipes (when the model exists; kept outside the repo in `models/harp.glb`)

```
{"name": "harp_R", "file": "models/harp.glb", "weapon": {"class": "mace", "part": "weapon1h", "length": 0.65, "tip": "+z", "butt": -0.05}, "decimate": 30000, "materials": {"METAL": null}}
{"name": "harp_L", "file": "models/harp.glb", "weapon": {"class": "mace", "part": "weapon.L", "length": 0.65, "tip": "+z", "butt": -0.05}, "decimate": 30000, "materials": {"METAL": null}}
```

`tip` = the model axis of the top (the neck); check with `--preview` (and `--list`) and change it if the import turns the model. Measure with `qa.json` (horn: 4.3 % inside the body).
