# UO Body 0x190: a 3D model from Ultima Online animations

A naked male body (body 0x190 / 400) rebuilt in 3D from the UO client animation file `anim1_0x0190.vd`:
35 actions × 5 directions, 210 frames per direction, 1050 images in total. A realistic body (MakeHuman, CC0) in the
UO character's proportions, a 55-bone rig with fingers and cloth bone chains, and all 35 animations fitted to the
original frames. It is meant for designing new clothing, armour, hair, cloak and weapon layers: the `.blend` renders
new UO frames and writes them straight into a `.vd` file.

Polish version: [`README.md`](README.md).

**Contents**
1. [What's included](#1-whats-included)
2. [How the model works](#2-how-the-model-works)
3. [Modelling an item](#3-modelling-an-item)
4. [Rendering frames and the `.vd` file](#4-rendering-frames-and-the-vd-file)
5. [Cutting](#5-cutting)
6. [The `vdtool` tool](#6-the-vdtool-tool)
7. [Importing into the game](#7-importing-into-the-game)
8. [Accuracy](#8-accuracy)
9. [How the model was built](#9-how-the-model-was-built)
10. [Rebuilding the model (pipeline)](#10-rebuilding-the-model-pipeline)
11. [Limitations and common problems](#11-limitations-and-common-problems)
12. [Notes for AI assistants](#12-notes-for-ai-assistants)

---

## 1. What's included

| File / folder | What it is |
|---|---|
| `UO_Body_0x190.blend` | Main file (Blender 4.2+): body, rig, 35 actions, cloak and skirt templates, UO camera, clothing-layer scene, horse proxies, scripts. |
| `UO_Body_0x190.glb` | glTF 2.0: mesh + rig + animations + texture (Unity, Godot, three.js, Blender). |
| `UO_Body_0x190.fbx` | FBX: mesh + rig + animations (Maya, 3ds Max, Unreal, Unity). |
| `UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Albedo texture (grey like UO skin, lighting removed) and its variants for the 5 UO directions. |
| `compare/*.gif` | Top: original sprite; bottom: the model rendered through the UO camera (5 directions). |
| `example_clothing/` | Example layer (a shirt) in `Example_Shirt_layer.vd`, with a preview over the original body. |
| `vdtool/vdtool.py` | Tool to unpack and repack `.vd` files (section 6). |
| `pipeline/` | Scripts and data used to rebuild the model (section 10). |
| `pipeline/body400.vd`, `pipeline/horse200.vd` | Original client files: body 0x190 (`anim1_0x0190.vd`) and horse 0xC8. |
| `client/body_0x190_frames/`, `client/horse_0xC8_frames/` | Original body (1050) and horse (300) frames as PNG + `meta.json` (`vdtool extract`). |

**Original frames.** The `.blend` contains the original UO client body frames (for the exact modes,
section 2). It is for your own use only; do not share it publicly. A stripped copy (`strip_originals.py`) does not contain them.
To add them from your own client: copy `anim1_0x0190.vd` to `pipeline/body400.vd`, then run
`python build_originals.py` and `python pack_originals.py --blend ../model/UO_Body_0x190.blend` in `pipeline/`.

## 2. How the model works

**Mesh `UO_Body`**
- A realistic body based on MakeHuman (CC0): 13,380 vertices, UVs, fingers, toes, a face. Its proportions (arm, leg and
  torso girth, the head) are fitted to the original frames with anatomical constraints.
- Rest pose: A-pose. Units are metres, the character faces −Y, Z is up. **The floor is z = 0.**
- There are no shape corrections (shape keys): the bones alone set the silhouette in every frame, so an item simply
  follows the bones.

**Rig `UO_Rig`** (55 body bones + cloth chains, `.L`/`.R` suffixes):
- 19 UO bones: `pelvis → spine → chest → neck → head`, `chest → clavicle → upper_arm → forearm → hand`,
  `pelvis → thigh → shin → foot`. `pelvis` is the root and carries the character's translation. Clavicles raise the shoulder.
- `upper_arm_twist`, `forearm_twist` (arm twist), 15 finger bones per hand (`finger1-1` … `finger5-3`, `finger1` is the
  thumb), `toe`. Bone collections: *Fingers*, *Twist*, *Toes*, *Cloth*.
- Weights come from MakeHuman (smooth joints, no candy-wrapper elbows or shoulders).
- **Girth per frame:** the X/Z scale of `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1) makes a
  limb slightly thicker or thinner where the original needs it. The next bone of the chain does not inherit it
  (Inherit Scale = None), so limb lengths do not change. Items bound to these bones get thicker with the skin.
- **Fingers:** in every frame the hand is clenched like on the original (finger and thumb curl fitted to the frames).
- **Cloth chains:** `skirt_K_S` (8 chains × 3 bones around the pelvis) and `cloak_K_S` (7 × 4, down the back from the
  shoulders). Their motion is fitted to the original skirt (anim 449) and cloak (anim 468) frames from `anim.mul`,
  mounted actions included.

**Fitted to the frames.** The pose of each of the 210 frames is fitted to all 5 directions of the original at once
(1050 images), with no shape corrections. The right hand's rotation is also fitted to the original katana frames
(anim 627), so a weapon sits in the hand like in the game (the blade within 0.8 px on average).

**Animations.** Each UO action is a Blender action `NN_name` (with a fake user). 1 UO frame = 3 scene frames (24 fps),
with smooth interpolation. Walk and run loop. Action properties: `uo_action` (number) and `uo_frames` (frame count).

| # | action | # | action | # | action |
|---|---|---|---|---|---|
| 0 | walk_unarmed | 12 | attack_2h_bash | 24 | mounted_run |
| 1 | walk_armed | 13 | attack_2h_slash | 25 | mounted_stand |
| 2 | run_unarmed | 14 | attack_2h_pierce | 26 | mounted_attack_1h |
| 3 | run_armed | 15 | combat_advance | 27 | mounted_attack_bow |
| 4 | stand | 16 | spell_directed | 28 | mounted_attack_crossbow |
| 5 | fidget_1 | 17 | spell_area | 29 | mounted_attack_2h |
| 6 | fidget_2 | 18 | attack_bow | 30 | block |
| 7 | combat_idle_1h | 19 | attack_crossbow | 31 | punch |
| 8 | combat_idle_2h | 20 | get_hit | 32 | bow |
| 9 | attack_1h_slash | 21 | die_forward | 33 | salute |
| 10 | attack_1h_pierce | 22 | die_backward | 34 | eat |
| 11 | attack_1h_bash | 23 | mounted_walk | | |

Left and right match the original (limbs were never swapped). In the mounted actions the rider sits in the air,
because in UO the horse is a separate animation.

**The `UO_Camera`** sees exactly like the game camera.
- Orthographic, elevation 28.45°, 36 px/m, 136×120 image, anchor on the centre of pixel (68, 86). This is how the original body frames
  are stored. `render_uo_layer.py` renders on a bigger canvas (`CANVAS`, default 256×256 with anchor (128, 192), still 36 px/m),
  because 136×120 cuts off two-handed weapons, spears and tall headgear (chapter 4).
- The anchor is 7 cm above the floor (`uo_anchor_height`); all frames agree on this.
- The UO direction is the property `uo_direction` (0–4) on `UO_Rig`: 0 faces the camera, 2 is a profile facing left,
  4 faces away. Directions 5–7 are mirrors of 3–1, made by the client.

**Material and UO lighting.** The UO light (one light at the camera, almost frontal) was estimated from the frames and
separated from the body colour.
- `uo_look = 1` (default): the "UO look", albedo × (0.08 ambient + 0.92 UO light). Renders look like the game frames.
- `uo_look = 0`: plain PBR (Principled BSDF) for editing and game engines. The `.glb`/`.fbx` use this.
- The node group **`UO_Look`** gives items the same lighting. The "Skin hue" node optionally tints the skin.
- **Exact modes** (need the original frames in the file and the Cycles engine):
  - `EXACT_COLORS`: the body is painted with the original UO frame projected from the camera, so it has exactly the
    original colours.
  - `EXACT_BODY`: the body layer is identical to the original, and in a clothing layer the body hides the item exactly
    along the original outline.

**Horse (actions 23–29).** The `Horse_Proxy` collection holds an approximate horse volume (body 0xC8) for every mounted
frame. The volume decides **what** is behind the horse; **where** the horse is comes from the exact outline of its
frames (text `uo_horse_masks.json`). The horse therefore hides the rider and items to the pixel.

**Scripts inside the `.blend`** (Text Editor; pick them from the text list in the editor header):

| Text | Purpose |
|---|---|
| `render_uo_layer.py` | Renders a layer to frames and `.vd` (run with Alt+P). |
| `uo_fit_item.py` | Turns the selected item's sleeves onto the arms and pushes it out of the skin (before `uo_bind_item.py`, section 3). |
| `uo_bind_item.py` | Binds the selected item to the body in one run: parent, Armature and weights (section 3). |
| `uo_cloth_bake.py` | Cloth simulation for robes, dresses, skirts and cloaks, after `uo_bind_item.py` (section 3). |
| `uo_shield_keys.py` | Replaces the motion of the shield bone `shield.L` in an older file with the latest one (the shield and its binding stay). |
| `uo_weapon_bones.py` | Adds the left-hand weapon bones (`polearm.L`, `axe2h.L`, `bow.L`) and keys their motion from `weapon_motion.json` (already run in the file; to load the motion again). |
| `uo_place_weapon.py` | Puts the selected weapon (shaft along +Z, tip up) on the grip line of its class, before `uo_bind_item.py`. |
| `weapon_motion.json` | Data: grip (point, direction, butt position) and motion of the 3 left-hand weapon classes, 210 poses each. |
| `uo_place_shield.py` | Puts the selected shield on the left forearm as UO holds it and slides it onto the arm (before `uo_bind_item.py`, section 3). |
| `uo_vd_writer.py` | `.vd` writer used by the renderer (don't run it directly). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Data: horse outlines and original frames. |

The scripts live in the `.blend` file, not in objects. Always work in `UO_Body_0x190.blend` (File → Open) and bring your
items into it, not the other way round.

## 3. Modelling an item

1. **Open `UO_Body_0x190.blend`** and allow scripts: Preferences → Save & Load → *Auto Run Python Scripts*, or
   "Allow Execution" in the yellow bar.
2. **Rest pose:** select `UO_Rig` → Object Data Properties (stick-figure icon) → Pose → *Rest Position*. Model on the
   body in the A-pose, then switch back to *Pose Position*.
3. **Add the item:** model it or import it (File → Import / Append) and put it into the **`Clothing`** collection.
   Everything in this collection goes into the rendered layer. Delete `Example_Shirt` or disable it in renders.
4. **Clothing, armour, helmet, boots, gloves** (things that bend): the script **`uo_bind_item.py`**.
   1. Make every piece that is a separate item in the game (breastplate, pauldrons, gloves, boots, helmet) a separate
      object. A 136×120 px frame shows little detail, so up to about 20k vertices is plenty (reduce a dense mesh
      with a *Decimate* modifier).
   2. **Fit to the body** (optional, in Rest Position): select the item and run **`uo_fit_item.py`**. First the
      sleeves (`MATCH_ARMS`): if the item was made for arms held differently (lower, more forward, bent at the
      elbow), the script finds that pose and turns the sleeves onto the body's arms. Items without sleeves are left
      alone. Then parts closer to the skin than `MIN_GAP` (15 mm) or inside the body are pushed out. A push moves the
      whole area around it the same way and fades out smoothly over max(`RADIUS` = 4 cm, `SPREAD` × the push), so a
      sleeve widens or moves as a whole instead of getting bumps, and folds, rivets and reliefs go with it. Subdivide
      big faces first (Edit Mode, A, right click → Subdivide, Number of Cuts 2), as they can cut through the body
      between their corners. Running it again changes nothing. `MAX_GAP > 0` also pulls standing-off parts in
      (changes the look, off by default). Place and size the item yourself.
   3. Select the item, open the text **`uo_bind_item.py`**, set `PART` (the kind of item) and run it (Alt+P).
      Every item vertex follows the skin **right under it** (along its normal, `MAP = "under"`), and the weights
      are smoothed over the item (`SMOOTH = 4`).

      | `PART` | Item | What it follows |
      |---|---|---|
      | `"chest"` | breastplate, vest, tunic | skin under it; pauldron on the shoulder 80% on the collarbone, sleeve further down the arm follows the arm (smooth transition), bottom 70% on the pelvis |
      | `"torso"` | something on the torso only | pelvis, spine, chest, neck |
      | `"shoulders"` | pauldrons | chest, upper_arm |
      | `"arms"` | sleeves, arm armour | upper_arm, forearm |
      | `"gloves"` | gloves, gauntlets, bracers | forearm, hand |
      | `"legs"` | trousers, leg armour up to the waist | pelvis, thigh, shin |
      | `"boots"` | boots, greaves | shin, foot |
      | `"helm"` | helmet, hood, mask | head |
      | `"neck"` | gorget, collar | neck, chest, head |
      | `"all"` | full suit in one object | skin under it, every bone |
      | `"robe"` | robe, dress | top like the skin, from the waist down the skirt chains (35 cm smooth transition); sleeves always follow the arms |
      | `"skirt"` | skirt, kilt | the `skirt_*` chains (template `UO_Template_Skirt`) |
      | `"cloak"` | cloak, cape | the `cloak_*` chains + a yoke over the shoulders (template `UO_Template_Cloak`) |
      | `"hair"`, `"beard"`, `"hat"` | hair, beard, cap | rigid on `head` (UO hair and beards are rigid) |
      | `"weapon"` / `"weapon.L"` | 1H weapon | rigid on `hand.R` / `hand.L` (UO holds 1H weapons in the right hand) |
      | `"polearm"` (`"staff"`, `"weapon2h"`) | staff, spear, javelin, pitchfork, halberd, bardiche, crook | bone `polearm.L` on the left hand, motion fitted to the original weapons (0.6-1.1 px instead of 5-6 px); run `uo_place_weapon.py` first |
      | `"axe2h"` | two-handed axe, hatchet / hammer in the left hand | bone `axe2h.L` (same, 1.2-1.7 px error) |
      | `"shield"` | shield | rigid on `shield.L` (shield bone on the forearm, moves like the UO shield) |
      | `"bow"` / `"crossbow"` | bow / crossbow | bone `bow.L` on the left hand (1.6-2.1 px error instead of 3 px) |
      | `"quiver"` | quiver | rigid on `chest` |

      Gloves (`"gloves"`) also follow the fingers, sleeves (`"arms"`) the twist bones, boots (`"boots"`) the toes.
      The cloth templates (collection *Templates*, hidden in renders) can be copied as a base for your own cloak or
      skirt: reshape them in Rest Position, then run `uo_bind_item.py` with `PART = "cloak"` / `"skirt"`.

      For `"chest"` the shoulder is set in that type's line: `"upper_arm": (0.2, 0.15, 0.45)` = 20% on the arm at the
      joint, 100% from 45% of the arm's length (the sleeve), smooth in between. `"thigh": (0.3, 0.1, 0.4)` likewise for the thighs.

   4. The script parents the item to `UO_Rig`, adds the *Armature* modifier and sets the weights, so the item moves
      with the skin under it. Run it again after every change to the item's shape (old weights are replaced).
   5. Manual way (your own weights): Ctrl+P → *Armature Deform → With Empty Groups*, paint the weights or copy them with
      a *Data Transfer* modifier (Vertex Groups, *Nearest Face Interpolated*) and delete the groups of bones the item
      does not cover.
   6. Skin poking a few mm through the item (in the 3D view) does not cut holes in the frames: when rendering, the body
      hides the item only where it is more than `HOLDOUT_MARGIN` (1 cm, section 4) in front of it.
   7. **Cloth** (optional: robe, dress, skirt, cloak). Select the bound item, save the file and run
      **`uo_cloth_bake.py`**. The lower part of the item (what `uo_bind_item.py` put on the cloth chains) becomes
      Blender cloth: it falls, swings and collides with the body. Shoulders, chest and sleeves stay pinned to the
      skeleton.
      - `GOAL` (0.5): how strongly the cloth is pulled towards the shape of the chains fitted to the original UO
        frames (0 = pure cloth, 1 = no cloth). `MATERIAL`: `silk`, `cotton`, `wool` or `leather`.
      - Every action is simulated on its own. The cloth first settles for `PREROLL` frames in the first pose.
        Actions the game loops (walk, run, stand) run `LOOP_CYCLES` times and the last cycle is kept, so the loop
        has no jump. In the mounted actions the horse of each frame (collection `Horse_Proxy`) is an obstacle too.
      - `CHAIN_SWING` (0.5): how much of the UO chains' swing the cloth follows; lower = calmer in fast actions
        (war walk, run).
      - After the simulation every frame is checked against the real body: parts inside the skin or closer
        than `FIX_GAP` (4 mm) are pushed out smoothly, so the skin never shows through the cloth.
      - The result goes to `uo_cloth/<item>.npz` next to the `.blend`. `render_uo_layer.py` uses it automatically,
        and after the bake playing an action in the 3D viewport shows the cloth too (after reopening the file run
        the script with `BAKE = False` to get that preview back).
      - Layers of the item (a coat over a tunic) collide with each other (`SELF_COLLISION`), so the inner one never
        shows through the outer one.
      - All actions take 30-60 minutes (less: lower `SIM_VERTS`, `QUALITY` or only some `ACTIONS`). Run it
        again after changing the item (shape, fit, weights); an outdated bake is skipped. `REMOVE = True` goes back
        to the plain bound item.
5. **Weapon, shield, hair** (rigid things): `uo_bind_item.py` with `PART = "weapon"`, `"shield"`, `"hair"` etc. (table
   above). Place a sword in Rest Position with the grip inside the clenched right hand and the blade on the thumb side:
   that is how weapons sit on the original UO frames. Stand a shield upright with its face towards the front view
   (Numpad 1), select it and run **`uo_place_shield.py`**: it goes onto the outside of the left forearm (like the UO
   heater shield) and slides onto the arm, `GAP` = 1 cm; then `PART = "shield"`. Render a shield with
   `BODY_GAP = 0` so it does not bend.
6. **Material:** Add → Group → **`UO_Look`**, and plug your colour or texture into its *Albedo* input. Make anything that
   should take a hue in-game in greyscale.
7. **Check the motion:** Dope Sheet → Action Editor → pick the `NN_name` actions and play (Space). Game-camera view:
   Numpad 0; change the direction with `uo_direction`.
8. **Tips:**
   - Make clothing about 1–2 cm above the skin.
   - Check attacks, spells and deaths in particular.
   - Bind skirts, robes and cloaks with the `"skirt"`, `"robe"`, `"cloak"` presets (they follow the cloth chains);
     `uo_cloth_bake.py` then gives the cloth natural motion (step 4.7).

## 4. Rendering frames and the `.vd` file

1. Render engine: **Cycles** (the script sets it itself, with 1 sample per pixel).
2. Open the text **`render_uo_layer.py`** and set the options at the top:
   ```python
   LAYER = "clothing"          # "clothing" = item layer, "body" = body, "all" = preview of both
   CANVAS = (256, 256)         # render size in px (width, height); the .vd crops every frame to its content anyway
   ANCHOR = (128, 192)         # anchor pixel inside the canvas. 256x256 / (128, 192) holds 444 of the 449 people and equipment
                               # animations of the Nelderim client (outside: a lantern, a parrot epaulet). Old size: (136, 120), (68, 86)
   ONLY = ["04_stand"]         # test one action; [] = all 35 actions
   OUTLINE = 0.38              # dark 1-px outline like UO art (1.0 = none)
   OUT_DIR = "//uo_render/"    # folder next to the .blend
   WRITE_VD = True
   VD_FILE = "//uo_render/%s.vd"
   HORSE_HOLDOUT = True        # mounted actions: the horse hides the item
   EXACT_BODY = True           # cut along the original body outline
   EXACT_COLORS = True         # body colours from the original (LAYER = "body" / "all")
   HOLDOUT_MARGIN = 0.01       # the body hides the item where it is > 1 cm in front of it (shallow skin pokes cut
                               # no holes); 0 = plain Cycles holdout
   OCCLUDERS = [...]           # body parts that may hide the item: arms, hands, head, legs; never the torso
                               # (items are worn over it)
   OWN_PARTS_NEVER_HIDE = True # body parts the item is skinned to (trousers: thighs, shins) never hide it: the item wraps
                               # them, and their skin in front of the shell cut 1-px strips off the sides
   DESPECKLE = 28              # single dark dots inside the item (deep details, rivets) take the colour around
                               # them (0 = off)
   FILL_HOLES = 4              # holes up to 4 px fully surrounded by the item are filled (0 = off)
   BODY_GAP = 0.006            # every frame, parts of the items closer than 6 mm to the arms, hands, legs or head are
                               # pushed out - an arm poking through a sleeve in motion cuts no hole (0 = off)
   MIN_PIECE = 8               # detached bits of the item under 8 px (a collar / cuff rim cut off by the head or a
                               # hand) are removed; the biggest piece always stays (0 = off)
   ```
3. Run **Run Script** (Alt+P). A full layer is 1050 frames, about 15–30 minutes on a CPU. A clothing layer is rendered
   without the body, and the script works out from depth what the body hides (with `HOLDOUT_MARGIN = 0` every frame
   is rendered twice: with and without the body).
4. Output in `uo_render/`:
   - `clothing/frames/NN_action/dirK/NN.png`: frames on a `CANVAS` canvas (256×256 by default),
   - `clothing/meta.json`: frame order and anchor,
   - **`clothing.vd`**: the finished file.

**Rendering in parts.** Runs into the same `OUT_DIR` add up. For example, set the weapon up for attacks and render
`ONLY = ["09_attack_1h_slash", ...]`, then change the placement and render the other actions. Every run writes a `.vd`
with all actions rendered so far. Delete the `uo_render/` folder to start from scratch.

**Cancelling a render:** create an empty file named `STOP` in the output folder (e.g. `uo_render/clothing/STOP`), or press
Ctrl+C in Blender's console (Window → Toggle System Console). Finished PNG frames are kept.

**Several items:** render each one separately. Keep one item in `Clothing` and change `VD_FILE`, e.g.
`"//uo_render/helm.vd"`.

## 5. Cutting

- **Hidden by the body:** a clothing layer contains only what the body does not hide, as in UO. With `EXACT_BODY = True`
  the cut follows the outline of the original body exactly. The 3D model only decides what is in front of or behind the
  body, so the item fits the original body to the pixel.
- **Horse:** in the mounted actions the horse hides the item, exactly along the outline from its frames.
- **UO look:** black under edges, 0/1 transparency (UO has no semi-transparency) and a dark 1-px outline (`OUTLINE`).
- **Cropping:** the `.vd` stores every frame cropped to its content, together with the anchor. The PNGs keep the full
  canvas on purpose so frames line up. `vdtool extract --raw` gives cropped PNGs.
- **`LAYER = "body"`:** with `EXACT_BODY = True` the body is identical to the original; with `False` it is the pure
  3D model (~98% agreement).

## 6. The `vdtool` tool

`vdtool/vdtool.py` (Python 3.8+, `pip install pillow numpy`) unpacks a `.vd` into PNGs and packs them back in the same
order (action → direction → frame). Unpacking and repacking without changes gives a byte-identical file. Its messages
are in Polish.

```bash
python vdtool.py info    file.vd                   # type, actions, frame counts
python vdtool.py extract file.vd work              # -> work/meta.json + work/frames/NN_action/dirK/NN.png
python vdtool.py extract file.vd work --raw        # frames cropped to their content
python vdtool.py pack    work new.vd               # PNG + meta.json -> .vd
python vdtool.py verify  file.vd new.vd            # what changed
python mul2vd.py anim.idx anim.mul out 701 468     # animations from the client files (e.g. hair 701, cloak 468) -> .vd
```

- **Canvas mode (default):** all frames have the same size and share the anchor (`meta.json → anchor`). When packing,
  each frame is cropped and its centre computed. Best for editing and drawing.
- **`--raw`:** original cropped sizes. Don't change sizes or frame counts; only for retouching pixels.

**Editing rules:**
1. Don't move the drawing relative to the canvas: 1 px on the canvas is 1 px in the game.
2. Transparency is 0/1: alpha ≥ 128 is visible, below that it is transparent.
3. Every block (action + direction) has one palette of 256 15-bit colours. With more than 256 colours the tool reduces the
   palette (median cut) and warns. Pure black becomes near-black, because `0x0000` means transparent.
4. Draw hue-able parts in grey (R = G = B).
5. You can add frames (next number) and remove them (from the end). All 5 directions of an action should have the same
   number of frames.
6. Don't rename folders or edit `meta.json`. An empty frame is allowed.

**`.vd` format** (little-endian):
```
int16 magic = 6, int16 animType = 0 (high, 22 actions) | 1 (low, 13) | 2 (people, 35)
index:  actions*5 entries {int32 lookup, int32 length, int32 extra} (-1 = empty); block = action*5 + direction
block:  uint16 palette[256] (RGB555), int32 frameCount, int32 frameOffset[frameCount] (from the frameCount position)
frame:  int16 centerX, centerY; uint16 width, height; runs {uint32 header, byte pixel[header & 0xFFF]}; 0x7FFF7FFF
header: bits 22..31 = (x - centerX) & 0x3FF, bits 12..21 = (y - centerY - height) & 0x3FF, bits 0..11 = run length
anchor inside the frame = (centerX, centerY + height)
```

## 7. Importing into the game

UOFiddler → **Animations → Animation Edit** → pick the animation file and the body or item ID → **Import from VD** →
choose the `.vd` → Save. The `.vd` must have the same type as the target (human bodies and their items are type 2,
people). Each item has its own animation ID.

## 8. Accuracy

- **Exact mode (`EXACT_BODY = True`):** the rendered body layer is identical to the original (all 1050 frames, checked
  with `vdtool verify`).
- **Pure 3D model (`EXACT_BODY = False`):** mean silhouette IoU **0.879** over 1050 frames, **with no shape
  corrections** (bones only). By direction: 0.876–0.893. Colours on overlapping pixels are exact with `EXACT_COLORS`.

| # | action | IoU | # | action | IoU | # | action | IoU |
|---|---|---|---|---|---|---|---|---|
| 0 | walk_unarmed | 0.905 | 12 | attack_2h_bash | 0.882 | 24 | mounted_run | 0.858 |
| 1 | walk_armed | 0.901 | 13 | attack_2h_slash | 0.887 | 25 | mounted_stand | 0.853 |
| 2 | run_unarmed | 0.896 | 14 | attack_2h_pierce | 0.872 | 26 | mounted_attack_1h | 0.853 |
| 3 | run_armed | 0.896 | 15 | combat_advance | 0.881 | 27 | mounted_attack_bow | 0.865 |
| 4 | stand | 0.912 | 16 | spell_directed | 0.879 | 28 | mounted_attack_crossbow | 0.852 |
| 5 | fidget_1 | 0.909 | 17 | spell_area | 0.851 | 29 | mounted_attack_2h | 0.830 |
| 6 | fidget_2 | 0.896 | 18 | attack_bow | 0.868 | 30 | block | 0.884 |
| 7 | combat_idle_1h | 0.882 | 19 | attack_crossbow | 0.887 | 31 | punch | 0.884 |
| 8 | combat_idle_2h | 0.878 | 20 | get_hit | 0.896 | 32 | bow | 0.892 |
| 9 | attack_1h_slash | 0.860 | 21 | die_forward | 0.855 | 33 | salute | 0.902 |
| 10 | attack_1h_pierce | 0.879 | 22 | die_backward | 0.857 | 34 | eat | 0.893 |
| 11 | attack_1h_bash | 0.882 | 23 | mounted_walk | 0.859 |  |  |  |

The differences are almost only 1-pixel bands along the edges (the original was drawn from a different 3D model).
There are no large errors such as an arm in a different place than on the original, so the cut-outs in items hit the
arm. For comparison: the previous model scored 0.880 without its 1254 corrections and 0.979 with them (but items had
to copy those corrections).

**UO items.** A test on real items from `anim.mul` (shirt, trousers, boots, gloves, helmet, plate armour): body-hugging
items rendered on this model reproduce the original frames (cut-outs for the arms included) as well as the previous
model with its corrections. **Cloth:** skirt IoU 0.83 (mounted 0.62), cloak 0.73 (mounted 0.67) against the original skirt and cloak frames.
**Weapons:** the blade in the hand is 0.8 px from the UO katana blade on average.

## 9. How the model was built

**The current body (MakeHuman).**
1. **Shape:** the MakeHuman mesh (CC0, male, muscle 0.6) moved onto the UO skeleton: every limb onto its bone (length and
   girth), the torso with a height map (width and depth at 7 levels), neck and head separately, blended with the
   MakeHuman weights. Girths fitted to the original frames with a penalty on unnatural shapes.
2. **Rig:** the 19 UO bones unchanged + arm twist, 15 finger bones per hand, toes; MakeHuman weights.
3. **Poses:** every frame fitted to all 5 directions at once (own fast rasteriser + LBS like Blender's), alternating with
   the shape; limb girth (bone X/Z scale) and the clench of the hands are fitted per frame too.
4. **Hand and weapon:** the sword grip calibrated on the original katana frames (anim 627), then the hand's rotation in
   every frame so that the blade covers the original. The shield: bone `shield.L` (child of `forearm.L`),
   its turn and shift fitted in every frame to the original shield (anim 582) in all 5 directions at once (IoU with
   the original 0.48 -> 0.76 on average); its face away from the body and its top up (two penalties in the fit),
   and it may move off the forearm where the model's arm moves differently from the UO shield.
5. **Mounted:** the rider is seen only where it is in front of the horse and must not enter the horse volume.
6. **Cloth:** the skirt and cloak bone chains fitted frame by frame to the original skirt (449) and cloak (468) frames,
   hidden by the body, without entering the legs or the horse.
7. **Texture:** colours from the original frames projected onto the MakeHuman UVs, the UO light removed (albedo),
   separately for the 5 directions.

**The first version of the model** (UO proportions and camera found from the frames; the current body builds on them):
1. **Decoding the `.vd`:** RGB555 palette, RLE frames, anchor point.
2. **The UO camera from the frames alone:** a joint fit of body proportions and camera to the silhouettes of all
   5 directions gave an orthographic projection, elevation 28.45°, 36 px/m, the anchor on the pixel centre and the
   floor 7 cm below it.
3. **Shape:** a parametric body turned into a quad mesh. Vertices fitted to the silhouettes of all frames (symmetry,
   smoothness), plus a 6.5 mm inflation that compensates the fitting bias.
4. **Rig:** bones at the fitted joints, bone-heat weights, clavicles.
5. **Poses (gradient-based, JAX):** every frame fitted on the skinned mesh (LBS like Blender's) in all 5 directions at
   once. Loss terms:
   - vertices inside the silhouette,
   - every edge pixel reached,
   - anatomical limits (swing and twist separately, hinge elbows and knees),
   - temporal smoothness,
   - a penalty for going below the floor.
   Fitting starts from the frame closest to a known pose, so limbs are never swapped.
6. **Escaping local minima:** a multi-start search (torso twist and lean, variants of arms, legs and body orientation).
   Candidates are always chosen by the true IoU of the rasterised mesh, then A→B→A jitter is smoothed out.
7. **Horse:** a visual hull from the 5 views of the horse frames, without the rider's volume, clipped by the exact
   horse outline.
8. **Per-frame corrections:** vertex offsets fitted with the renderer's own rule (a pixel counts when its centre is
   inside a triangle). Then every wrong pixel was attached to the triangle responsible, and a per-direction correction
   was added. Everything is stored as driven shape keys.
9. **Texture and UO look:** the UO light was estimated from the frames and divided out of the colour, giving the albedo.
   The UO post-process (black under edges, 0/1 alpha, 0.38 outline) was measured on the original.
10. **Exact modes:** the original frames are packed as an atlas; the material projects them from the UO camera, and the
    render script uses their outline for the body and for hiding clothing.
11. **Verification:** the Blender rig reproduces the fitted mesh to < 0.1 mm, and the rasteriser agrees with Cycles to
    within 1 pixel.

## 10. Rebuilding the model (pipeline)

**The current body** (folder `pipeline/body13/`, run from that folder; requirements: `numpy scipy numba pillow "bpy==4.2.*"`).
The saved results (`*.json`, `*.npz`) let you repeat any step. The MakeHuman data (CC0) is in `mh/`, the UO item frames
from `anim.mul` (skirt, cloak, katana, shield, shirt, trousers, boots, armour, helmet) in `mul/`.

| Stage | Scripts | Result |
|---|---|---|
| Data from the first version | `prep_views.py`, `dump_poses.py`, `dump_horse.py`, `dump_v12.py` | `views_*.npz`, `rig_poses.npz`, `horse.npz` |
| Shape | `shape13.py`, `fit_shape2.py` | `shape_r2.json` |
| 55-bone rig | `skel13.py` | (in memory, `build_v13.py`) |
| Poses | `run_poses13.py`, `views_from_poses13.py`, `run_mounted13.py` (+ `horse_sdf.py`) | `poses13_*.json` |
| Weapon and hand | `weaponfit.py`, `handfit.py`, `shieldfit.py` | `grip_katana2.json`, `poses13_r5.json`, `shield_heater.json` |
| Cloth | `cloth13.py`, `clothfit.py`, `run_cloth.py`, `run_cloth_mounted.py` | `cloth_449all.json`, `cloth_468all.json` |
| Texture | `bake13.py` | albedo for 5 directions |
| Building the file | `build_v13.py`, then `../export.py` | `.blend`, `.glb`, `.fbx` |
| Measurements and previews | `eval13.py`, `itemval.py`, `gen_items.py`, `make_gif.py` | IoU, random outfits, GIFs |

**The first version of the model** (scripts in `pipeline/`):

The scripts are in `pipeline/` and run from that folder. Requirements: Python 3.11,
`pip install numpy pillow scipy scikit-image jax optax "bpy==4.2.*"`. The client files are already in `pipeline/`: the
body `body400.vd` and the horse (0xC8) `horse200.vd`. The `*.pkl` files are saved results, so steps can be resumed.

| Stage | Scripts | Result |
|---|---|---|
| Proportions and camera | `run_shape.py` | `shape_fit.pkl` |
| Mesh, rig, scene | `build.py` (`basemesh.py`, `sdfmesh.py`, `rig.py`, `texbake.py`) | `.blend` |
| Shape from the frames | `refine_mesh.py`, `inflate_test.py` | `refine_mesh.pkl`, `refine_infl.pkl` |
| Lighting and texture | `delight_bake.py`, `perdir_bake.py` | albedo, `uo_light.pkl` |
| Poses on the mesh | `posefit_seq.py`, `posefit_search.py`, `posefit_polish.py`, `jitter_fix.py`, `reeval.py` | `final_poses_v10.pkl` |
| Horse | `horse_hull.py`, `add_horse_proxy.py` | horse volumes and outlines |
| Building a version | `patch_final.py` → `uo_layers_setup.py` → `add_horse_proxy.py` → `export.py` | `.blend`, `.glb`, `.fbx` |
| Shape corrections | `corr_fit.py` (stage 1), `corr_fit34.py` (pixels + directions), `add_exact.py` | shape keys in the `.blend` |
| Exact modes | `build_originals.py`, `add_exact.py`, `pack_originals.py`, `strip_originals.py` | final version |
| Measurements | `render_body_vd.py --pure`, `compare2.py`, `err_parts.py`, `gross.py`, `zoom.py` | IoU, GIFs |

Key settings: `UO_DELTA=refine_mesh.pkl` when fitting poses and `refine_infl.pkl` when evaluating and building;
`UO_CLAV=1` enables the clavicles.

## 11. Limitations and common problems

**Limitations**
- Muscle drawing is softer than on the sprites, because the texture averages many frames.
- Fingers and the face come from MakeHuman (they cannot be seen on ~60 px frames).
- The pure 3D model differs from the original mostly by 1-pixel bands along the edges (about 12% of the silhouette
  pixels). The exact modes (`EXACT_BODY`) remove this from renders: the body is always the original, the model only
  decides what is in front of it and what is behind.
- On horseback the lower part of a skirt or cloak may go into the horse: the horse hides it when rendering (like in UO).
- The horse is an approximate occluder, not a model for editing.

**Common problems**

| Problem | Fix |
|---|---|
| The Text Editor is empty | Pick a text from the list in the editor header. If the list is empty, open `UO_Body_0x190.blend` with File → Open (don't import the `.glb`/`.fbx` and don't append the body into another scene). |
| The body renders black or wrong | Enable *Auto Run Python Scripts* and reopen the file. Use Cycles. Check `LAYER`. |
| Exact modes change nothing | The file has no original frames: use the `.blend` from this repository or `pack_originals.py`. |
| The item cuts into the body | Run `uo_bind_item.py` with the right `PART`, and make the item slightly larger. |
| The item stretches after an arm or leg | It has weights of bones it does not cover. Run `uo_bind_item.py` with the right `PART`. |
| Blender freezes while the script runs | The item has too many vertices. Reduce it (*Decimate*). |
| The item stays in place | The *Armature* modifier or the weights are missing (section 3). |
| The character "jumps" in `vdtool` | The drawing moved relative to the anchor. |
| Jagged edges after import | Semi-transparent pixels: set alpha to 0 or 255. |
| UOFiddler rejects the file | Different animation type than the target (human bodies: type 2). |
| Rendering takes long | Test with `ONLY = ["04_stand"]`, and do the full render at the end. |

## 12. Notes for AI assistants

```
PURPOSE    : 3D model of UO body 0x190 (male, naked) rebuilt from anim1_0x0190.vd; used to author clothing layers (.vd).
VD FORMAT  : see section 6. Colour 0x0000 = transparent (remap real black to 1).
SPACE      : metres, Z up, character faces -Y, floor z = 0, UO anchor point = world (0, 0, 0.07).
CAMERA     : "UO_Camera", orthographic, elevation 28.45 deg, 36 px/m, 136x120 px, anchor on pixel (68, 86), +0.5 px in x.
DIRECTIONS : UO_Rig["uo_direction"] = d (0..4) rotates the rig by -45 deg * d; 0 = facing camera, 2 = profile facing
             left, 4 = facing away; 5..7 are mirrors of 3..1 made by the client.
RIG        : 55 bones: pelvis (root) spine chest neck head; clavicle/upper_arm/forearm/hand .L/.R; thigh/shin/foot .L/.R;
             upper_arm_twist/forearm_twist .L/.R; finger1-1..finger5-3 .L/.R (finger1 = thumb, local X = curl axis,
             Z to the palm); toe.L/R. Cloth chains skirt_K_S (8x3, parent pelvis), cloak_K_S (7x4, parent chest).
             Quaternion rotations, MakeHuman weights. Per-frame girth = pose-bone scale (x, 1, z) on upper_arm,
             forearm, hand, thigh, shin, foot, head; forearm/hand/shin/foot have Inherit Scale = None.
ACTIONS    : 35 Blender actions "NN_name", props uo_action (0..34) and uo_frames; UO frame i -> scene frame 1 + 3*i.
             Every action keys UO_Rig["uo_action_id"].
BODY       : UO_Body = MakeHuman mesh (13380 verts, UVs), no shape keys. Items: text "uo_bind_item.py" (PART preset ->
             allowed bones): nearest skin point restricted to body triangles whose dominant bone is allowed; MAP "under":
             skin hit along the item vertex normal (else nearest); weights = body weights there (allowed bones only,
             renormalised); SMOOTH passes of neighbour averaging over the item. Finger/twist/toe groups count as hand/
             arm/foot. RIGID presets (hair, beard, hat, weapon, shield, bow, crossbow, quiver): 100 % on one bone.
             CLOTH presets (skirt, cloak, robe): weights of the nearest point of UO_Template_Skirt / UO_Template_Cloak
             (robe: blended with the skin weights over 0.15 m below the template top).
HOLDOUT    : clothing layer = Cycles render without the body; own z-buffer raster of body and items; the body hides a
             pixel where depth_body < depth_item - HOLDOUT_MARGIN (0.01 m), using only body triangles whose dominant bone is
             in OCCLUDERS (no torso); transparent patches <= FILL_HOLES px fully
             surrounded by the item are filled (from the render without the body, else the neighbours' colour);
             8-connected pieces < MIN_PIECE px other than the biggest are cleared after the UO post-process.
BODY GAP   : per UO frame (once for all 5 directions) the posed bound items (welded nodes) are pushed BODY_GAP out of
             the posed OCCLUDERS triangles (BVH nearest, 12 rounds, displacement smoothed over the item edges) and shown
             through shape key 'uo_fix' with the Armature modifier off; removed again after the run (also on STOP).
BIND FOLD  : uo_bind_item PARTS[...][1] = share of a limb bone's weight kept; the rest moves to the parent bone
             (hand>forearm>upper_arm>clavicle, foot>shin>thigh>pelvis, head>neck); a tuple (share, t0, t1) ramps the share along the bone; "chest" =
             upper_arm (0.2, 0.15, 0.45), thigh (0.3, 0.1, 0.4).
MOUNTED    : horse = body 0xC8; rider->horse action pairing 23->0, 24->1, 25..29->2. Objects Horse_a{action}_f{frame}
             (holdout proxies, parented to UO_Rig) + text "uo_horse_masks.json" (key "action,frame,dir" ->
             base64(zlib(packbits(120x136 bool)))). Hiding happens only inside the horse silhouette.
EXACT      : image "UO_Original_Atlas" (1050 original frames, 35 cols x 30 rows of 136x120) + text
             "uo_original_frames.json" (tiles; base64(zlib(RGBA)) per "action,frame,dir"); scene props uo_tile_col,
             uo_tile_row, uo_exact drive the projection. Present in this repository's .blend; strip_originals.py removes them.
MATERIAL   : scene["uo_look"]: 1 = albedo * (0.08 + 0.92 * max(0, N.L)), light fixed to the camera; 0 = plain PBR.
RENDERING  : text "render_uo_layer.py": LAYER ("clothing" | "body" | "all"), ONLY, OUTLINE = 0.38, WRITE_VD, OUT_DIR,
             VD_FILE, HORSE_HOLDOUT, EXACT_BODY, EXACT_COLORS. Cycles, 1 sample, box filter 0.01. Post-process:
             premultiply over black, alpha threshold 0.5 -> 0/1, 1-px boundary outline * 0.38. Runs into the same
             OUT_DIR accumulate; a file named STOP in the output folder cancels.
             Output: frames/NN_action/dirK/NN.png + meta.json (vdtool layout) + <LAYER>.vd (anim_type 2, anchor 68,86).
QUALITY    : exact mode: identical to the original body; pure model (bones only): mean silhouette IoU 0.879.
RULES      : never swap left/right limbs relative to the original frames; new layers must keep the same 35 actions,
             5 directions and frame counts as the body; do not redistribute UO client files or this repository's .blend.
REBUILD    : Tools/UOModel3D/pipeline (section 10); the client .vd must be copied in as body400.vd, the horse as
             horse200.vd.
```
