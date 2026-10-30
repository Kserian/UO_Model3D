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

## The shape (user decision: held by the harp itself, no handle, no foot)

- A realistic small handheld (bard's) lap harp, not a floor harp: soundbox wide at the bottom, narrowing to the top, S-curved neck; the hand closes round the **front pillar** (straight, smooth, round, Ø 3-4 cm, full height), the harp body hangs to one side of the hand. Height 0.65 m (23 px at 36 px/m), width ~0.38 m, height:width ~1.7 so that the long axis is the pillar; depth 5-6 cm (2 px edge-on).
- **Needs a pipeline change before it can be built**: `uo_place_weapon.py` puts the middle of the cross-section on the grip line (the hand would be in the strings). It needs an offset that puts the pillar on the grip line, and the body of the harp on the free side (-X of `weapon1h.R`, > 0.45 m free in almost every action; +X has only 0.15-0.25 m). Not measured yet with the grip on the pillar: measure (as above) before choosing the grip height and the side.
- Soundbox >= 7 cm, neck >= 5 cm; every part >= 1.5-2 px wide (a 3 cm part is 1 px).
- Strings (user decision): like a real harp, 10 separate strings with open see-through gaps, no panel, a soft rounded bottom. A real string (2-8 mm) is 0.1-0.3 px and flickers from frame to frame: ask for slightly thick strings, and if they still vanish in the render, `thicken` them after the import.
- Colour: warm, medium (honey-brown) wood and pale gold strings; no black, no shiny metal (UO light darkens, `METAL` null); no carvings, knots, gems, tuning pins.

## meshy.ai (Text to 3D; prompt max 600 characters)

Prompt (535 characters; "lap harp" alone gave a big floor-standing harp: the size and "handheld" must be said, and floor / concert / pedal harp excluded):

```
Small handheld medieval bard's lap harp, about 60 cm tall, light enough to carry in one hand, realistic simple wooden game prop, shown upright, strings facing the viewer. Compact triangle about 1.7 times as tall as wide: a straight smooth round front pillar, a slim soundbox slanting up on the other side, slightly wider at the bottom, and a gently S-curved neck. Soft rounded bottom corner. 10 separate taut strings, slightly thick, with open see-through space between them. Smooth surfaces, warm honey-brown wood, pale gold strings.
```

Negative prompt:

```
floor harp, concert harp, pedal harp, large standing harp, pedals, column base, crown, handle, pommel, foot, stand, base, ground plane, panel behind the strings, background, cartoon, carvings, engravings, filigree, knots, gems, ornaments, tiny details, tuning pins, pointed bottom, floating parts, hands, person, text, black, shiny metal
```

Settings: symmetry off, triangle mesh, 10-30k polygons (the pipeline reduces to 30k), texture without metallic. Check before using: one piece, no handle or foot, the pillar straight and free of ornaments, no holes in the frame, strings separate with open gaps (no backing panel), not a mess of thin wires.

## Recipes (after the grip offset exists; the model kept outside the repo in `models/harp.glb`)

Like the horn: `"weapon": {"class": "mace", "part": "weapon1h" | "weapon.L", "length": 0.65, "tip": "+z"}`, `"decimate": 30000`, `"materials": {"METAL": null}`, plus the new grip offset onto the pillar. Measure with `qa.json` (horn: 4.3 % inside the body).
