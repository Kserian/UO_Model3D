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
- A classic harp with the pillar over the foot collides as little, but the pipeline would put the hand in the middle of the strings (foot 0.2 m off the grip line). The V frame with the foot in the middle needs no code change, but the user wants the harp held by its frame (pillar), not by a handle or foot. The worst actions are the same for every shape (18, 27 bow, 29 mounted 2H, 21 die forward: hands together or on the ground).

## The shape: the UO lap harp (user decision: held by the harp itself, no handle, no foot)

Reference: the client's `lap harp` (art 0x0EB2, 22x29 px; `standing harp` 0x0EB1 is the floor harp; no harp in tiledata is wearable, so there is no original animation to match). Read off the art:

- A V-shaped wooden frame (user decision, as in the art): wide at the top, narrowing to one softly rounded bottom tip, a little taller than wide (29:22 in the art). Left: a thick pillar bowed outward, curving down to the tip. Top: a neck rising to the right, ending in a small rolled scroll, the highest point. Right: a straight slim bar down to the same tip. **No soundbox**.
- About 6 vertical strings from the neck down to the bottom of the frame, with open gaps between them (drawn dark: the inside of the frame shows through).
- Light honey-tan wood with dark outlines; matte dark grey strings.
- For the pipeline: height ~0.6 m (22 px at 36 px/m), width ~0.45 m, depth 5-6 cm; every part of the frame >= 4-5 cm (1.5-2 px). The hand closes round the frame itself (the bowed pillar or the straight bar), so **the pipeline needs a grip offset before it can be built**: `uo_place_weapon.py` puts the middle of the cross-section on the grip line (the hand would be in the strings); the body of the harp should go to the free side (-X of `weapon1h.R`, > 0.45 m free in almost every action; +X has only 0.15-0.25 m). Not measured yet with the grip on the frame: measure (as above) before choosing the grip point and the side. Height:width is only ~1.3, so check that the long axis comes out along the height (else give the axis explicitly).
- Strings: a real string (2-8 mm) is 0.1-0.3 px and flickers from frame to frame; if they vanish in the render, `thicken` them after the import.

## meshy.ai (Text to 3D; prompt max 600 characters)

Prompt (552 characters; earlier prompts gave a big floor-standing harp and a soundbox: the UO harp has neither):

```
Small handheld lap harp, simple low-detail game prop, upright, strings facing the viewer. V-shaped wooden frame, wide at the top, narrowing down to one softly rounded bottom tip, a bit taller than wide: on the left a thick pillar bowed outward in a smooth curve down to the tip; on the right a straight slim bar down to the same tip; on top a neck rising to the right, ending in a small rolled scroll, the highest point. 6 vertical strings from neck to bottom with open see-through gaps. Light honey-tan wood, matte dark grey strings, smooth surfaces.
```

Negative prompt:

```
soundbox, box, floor harp, concert harp, pedal harp, large harp, flat bottom, U-shape, handle, foot, stand, base, ground plane, panel behind the strings, background, carvings, engravings, ornaments, knots, gems, tuning pins, tiny details, floating parts, hands, person, text, shiny metal, gold, black
```

Settings: symmetry off, triangle mesh, 10-30k polygons (the pipeline reduces to 30k), texture without metallic. Check before using: one piece, no handle or foot, no soundbox, no holes in the frame, strings separate with open gaps (no backing panel), not a mess of thin wires.

## Recipes (after the grip offset exists; the model kept outside the repo in `models/harp.glb`)

Like the horn: `"weapon": {"class": "mace", "part": "weapon1h" | "weapon.L", "length": 0.6, "tip": "+z"}`, `"decimate": 30000`, `"materials": {"METAL": null}`, plus the new grip offset onto the frame. Measure with `qa.json` (horn: 4.3 % inside the body).
