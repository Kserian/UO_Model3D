# UO Body 0x190: a 3D model from Ultima Online animations

A naked male body (body 0x190 / 400) rebuilt in 3D from the UO client animation file `anim1_0x0190.vd`:
35 actions × 5 directions, 210 frames per direction, 1050 images in total. A realistic body (MakeHuman, CC0) in the
UO character's proportions, a 54-bone rig (19 UO bones plus the fingers and weapon bones), and all 35 animations fitted to the
original frames. It is meant for designing new clothing, armour, hair and weapon layers: the `.blend` renders
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
| `UO_Body_0x190.blend` | Main file (Blender 4.2 – 5.2): body, rig, 35 actions, UO camera, clothing-layer scene, horse proxies, scripts. |
| `UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Albedo texture (grey like UO skin, lighting removed) and its variants for the 5 UO directions. |
| `example_clothing/` | Example layer (a shirt) in `Example_Shirt_layer.vd`, with a preview over the original body. |
| `vdtool/vdtool.py` | Tool to unpack and repack `.vd` files (section 6). |
| `pipeline/` | Pipeline scripts: render, item fitting, tests, measurements (section 10). |
| `pipeline/body400.vd`, `pipeline/horse200.vd` | Original client files: body 0x190 (`anim1_0x0190.vd`) and horse 0xC8. |
| `client/body_0x190_frames/`, `client/horse_0xC8_frames/` | Original body (1050) and horse (300) frames as PNG + `meta.json` (`vdtool extract`). |

**Original frames.** The `.blend` contains the original UO client body frames (for the exact modes,
section 2). It is for your own use only; do not share it publicly.
To add them from your own client: copy `anim1_0x0190.vd` to `pipeline/body400.vd`, then run
`python build_originals.py` and `python pack_originals.py --blend ../model/UO_Body_0x190.blend` in `pipeline/`.

## 2. How the model works

**Mesh `UO_Body`**
- A realistic body based on MakeHuman (CC0): 13,380 vertices, UVs, fingers, toes, a face. Its proportions (arm, leg and
  torso girth, the head) are fitted to the original frames with anatomical constraints.
- Rest pose: A-pose. Units are metres, the character faces −Y, Z is up. **The floor is z = 0.**
- There are no shape corrections (shape keys): the bones alone set the silhouette in every frame, so an item simply
  follows the bones.

**Rig `UO_Rig`** (54 bones: 19 UO bones, 30 fingers and 5 weapon and shield bones, `.L`/`.R` suffixes; only bones that move the character):
- `pelvis → spine → chest → neck → head`, `chest → clavicle → upper_arm → forearm → hand`, `pelvis → thigh → shin → foot`.
  `pelvis` is the root and carries the character's translation. Clavicles raise the shoulder; they do not deform the mesh (Deform off).
- `finger1-1` … `finger5-3` (15 bones per hand, `finger1` is the thumb, bone X = curl axis). In every frame the hand is clenched like on the original
  (finger and thumb curl fitted to the UO frames). Gloves (`"gloves"`) follow the fingers.
- Item-motion bones: `polearm.L`, `axe2h.L`, `bow.L` (children of `hand.L`), `weapon1h.R` (child of `hand.R`), `shield.L` (child of `forearm.L`), keyed in the 35 actions
  (restored at the user's request; they depend only on the hand and forearm, so the fingers do not change them).
- There are no twist, toe or cloth-chain bones (removed in session 14; the weights of the toes went to the foot).
  Before the simplification (commit `b86c314`) the rig had 112 bones.
- Weights come from MakeHuman (smooth joints, no candy-wrapper elbows or shoulders).
- **Girth per frame:** the X/Z scale of `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1) makes a
  limb slightly thicker or thinner where the original needs it. The next bone of the chain does not inherit it
  (Inherit Scale = None), so limb lengths do not change. Items bound to these bones get thicker with the skin.

**Fitted to the frames.** The pose of each of the 210 frames is fitted to all 5 directions of the original at once
(1050 images), with no shape corrections. Weapons, shields and hair are rigid on the hand, forearm and head bones.

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
- `uo_look = 0`: plain PBR (Principled BSDF) for editing and game engines. `export.py` uses this (it creates `.glb`/`.fbx` on demand; they are not in the repo).
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
| `uo_materials.py` | Puts the materials of a foreign model (PBR, textures) into the UO look: wires the colour (texture, colour, colour attribute) into the `UO_Look` node, keeps transparency (alpha >= 0.5 = pixel in the sprite), drops PBR parameters (roughness, normal maps, environment reflections), but **metal gets a UO-style highlight** (measured on the plate and helm sprites: `SPEC_STRENGTH` 1.0 × albedo, `SPEC_POWER` 16; plate 2.0/19, mail 0.7/11, see `docs/qa/light_shadow.md`); `SATURATION = 0` gives a grey item for in-game dyeing. Run it after `uo_import_item.py`. |
| `uo_import_item.py` | Brings a foreign (e.g. free) model (`.glb` `.fbx` `.obj` `.dae`…) onto the body: bakes the mesh without the file's skeleton and weights, scales it and puts it at the height of the original UO item of that kind (`KIND`), in `Clothing` (before `uo_fit_item.py`, section 3). |
| `uo_fit_item.py` | Turns the selected item's sleeves onto the arms and pushes it out of the skin (before `uo_bind_item.py`, section 3). |
| `uo_densify_item.py` | Densifies the mesh of the selected item (subdivision without changing the shape, optional `SMOOTH`), so a low-poly item bends smoothly at elbows, knees and hips instead of folding along a few long edges; the target edge length depends on the slot (`EDGE_BY_KIND`, gloves 2 cm, the rest 3-5 cm). Before `uo_fit_item.py`. |
| `uo_prepare_item.py` | One step for a slot (`KIND`): `uo_densify_item.py` -> `uo_fit_item.py` -> `uo_bind_item.py` with that slot's settings (table `SLOTS`). Results and reasons: `docs/qa/slot_geometry.md`. |
| `uo_autofit_item.py` | Units, size and place of the selected item from the shape of the skin of its slot (not from one height per slot): `docs/qa/autofit.md`. Called by `uo_prepare_item.py` (`AUTOFIT`). |
| `uo_orient_weapon.py` | Stands a foreign weapon upright (tip up, flat side on +X, class length: sword 1 m, musket 1.3 m...), before `uo_place_weapon.py`. |
| `cloth_lib.py` | Loose garments (robe, skirt): a hull of the legs and a tent from the waist, per frame, numpy (`docs/qa/robe_physics.md`); used by `render_uo_layer.py` for items with the `uo_cloth` property. |
| `uo_bind_item.py` | Binds the selected item to the body in one run: parent, Armature and weights (section 3). |
| `uo_weapon_bones.py` | Adds the weapon bones (left hand: `polearm.L`, `axe2h.L`, `bow.L`; right hand: `weapon1h.R`) and keys their motion from `weapon_motion.json` (already run in the file; to load the motion again). |
| `uo_place_weapon.py` | Puts the selected weapon (shaft along +Z, tip up) on the grip line of its class, before `uo_bind_item.py`. Model the head (blade, axe) as a flat plate in the XZ plane, wide side on +X; the script turns the weapon about its shaft like the original weapon `REF_ANIM` (e.g. 624 halberd, 613 executioner's axe, 623 cutlass) and the bone then turns it by the measured roll (`weapon_motion.json`, field `roll`). Bows: roll undetermined. |
| `weapon_motion.json` | Data: grip (point, direction, butt position) and motion of the 4 weapon classes (3 in the left hand, 1H in the right), 210 poses each. |
| `uo_place_shield.py` | Puts the selected shield on the left forearm as UO holds it and slides it onto the arm (before `uo_bind_item.py`, section 3). |
| `uo_shield_keys.py` | Replaces the motion of the shield bone `shield.L` in an older file with the latest one (the shield and its binding stay). |
| `weapon_roll_fit.py`, `weapon_roll_lib.py`, `weapon_roll_apply.py`, `weapon_classify.py`, `test_weapon_roll.py` | Measure the roll (turn about the weapon's own axis) of all original weapons of `anim`..`anim5`, classify weapons to bones, write into `weapon_motion.json`, render test of a plate against the sprite. Results: `docs/qa/weapon_roll.md`. |
| `uo_vd_writer.py` | `.vd` writer used by the renderer (don't run it directly). |
| `uo_job.py` | Runs long scripts (render) step by step from a modal operator, so Blender's window does not freeze (progress in the status bar, ESC cancels). Used by `render_uo_layer.py` and `uo_cloth_bake.py` (don't run it directly). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Data: horse outlines and original frames. |

Tool scripts outside the file (`pipeline/`): `uo_make_item.py` (a free model -> an item in one command, section 3a), `item_sheet.py` / `arm_mirror_action.py` / `arm_sym_fit.py` / `arm_refit.py` / `arm_grid.py` (left arm of an action as the mirror of the right one, fit of an arm to the original frames; `docs/qa/elbow_spell.md`), `item_gif.py` (a contact sheet of frames and an animated GIF of an item on the original body), `item_qa.py` (clipping and thickness of an item in motion), `uo_conform_item.py` / `item_clearance.py` (a shirt as a shell of the body and the clipping in every frame, `docs/qa/jedi_tunic.md`), `item_thickness.py` (stand-off on frames vs the original sprites), `pose_capture.py` / `robe_calib.py` / `cloak_calib.py` / `cloak_fit_frames.py` (calibration of the physics of loose garments on the originals, `docs/qa/robe_physics.md`), `test_autofit.py` / `test_robe.py` / `test_cloak.py` / `run_qa.py` (tests of the autofit and of robes, and one regression with thresholds: `python pipeline/run_qa.py [--quick]`), `sync_blend_scripts.py` (copy scripts into the `.blend`), `run_render_headless.py` (render without GUI), `test_*.py` (tests), `body_part_raster.py` / `body_part_qa.py` (body silhouette vs the original), `light_*.py`, `layer_analysis*.py`, `slot_dynamics.py` (analyses of client frames), `build_originals.py` / `pack_originals.py` (original frames into the `.blend`), `export.py` (glb/fbx), `rig_simplify.py`, `rig_restore_fingers.py`, `rig_restore_weapons.py` (one-off rig changes), `weapon_*.py` and `test_weapons.py` / `test_weapon_roll.py` (weapon calibration and tests; they need sprites from the client, only the katana 627 is in the repo).

The scripts live in the `.blend` file, not in objects. Always work in `UO_Body_0x190.blend` (File → Open) and bring your
items into it, not the other way round.

## 3. Modelling an item

1. **Open `UO_Body_0x190.blend`** and allow scripts: Preferences → Save & Load → *Auto Run Python Scripts*, or
   "Allow Execution" in the yellow bar.
2. **Rest pose:** select `UO_Rig` → Object Data Properties (stick-figure icon) → Pose → *Rest Position*. Model on the
   body in the A-pose, then switch back to *Pose Position*.
3. **Add the item:** model it or import it (File → Import / Append) and put it into the **`Clothing`** collection.
   **A model from outside (e.g. a free one):** in the text **`uo_import_item.py`** set `FILE` (path to a `.glb`, `.fbx`, `.obj`,
   `.dae`…) and `KIND` (`shirt`, `plate`, `arms`, `pants`, `legs`, `boots`, `gloves`, `helm`, `neck`, `hair`, `beard`, `hat`) and run it
   (Alt+P). It bakes the mesh (without the file's skeleton and weights), throws away everything but the mesh, scales and
   places the item so that its height matches the original UO item of that kind on the body (ranges from the original
   sprites), and prints the `PART` for `uo_bind_item.py`. The meshes in the file are listed: leave out eyes, the model's body
   and helper shapes with `SKIP`. If the item faces backwards set `TURN = 180`. Then **`uo_materials.py`** (the foreign materials into the UO look; without it the model's shiny metal renders about 55/255 off the UO light; metal gets a UO-style highlight), `uo_fit_item.py` and `uo_bind_item.py`
   (below). Check the model's licence. Tests: `pipeline/test_import_item.py` (foreign file), `pipeline/test_materials.py` (materials).
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
      | `"chest"` | breastplate, vest, tunic | skin under it; thigh near the hip 70% on the pelvis, sleeves on the arms |
      | `"torso"` | something on the torso only | pelvis, spine, chest, neck |
      | `"shoulders"` | pauldrons | chest, upper_arm |
      | `"arms"` | sleeves, arm armour | upper_arm, forearm |
      | `"gloves"` | gloves, gauntlets, bracers | forearm, hand |
      | `"legs"` | trousers, leg armour up to the waist | pelvis, thigh, shin |
      | `"boots"` | boots, greaves | shin, foot |
      | `"helm"` | helmet, hood, mask | head |
      | `"neck"` | gorget, collar | neck, chest, head |
      | `"all"` | full suit in one object | skin under it, every bone |
      | `"cloak"` | cloak | hangs from the chest and **swings back about the shoulders** per action (run, riding: streams out behind; table from the original 468, `docs/qa/cloak_physics.md`) |
      | `"robe"`, `"skirt"` | robe, dress, skirt, kilt | like the skin down to the hips; below, the **pelvis**, and the legs push the cloth out per frame (`cloth_lib.py`, property `uo_cloth`; `docs/qa/robe_physics.md`) |
      | `"hair"`, `"beard"`, `"hat"` | hair, beard, cap | rigid on `head` (UO hair and beards are rigid) |
      | `"weapon1h"` | sword, mace, hammer, 1H axe, kryss, pickaxe | bone `weapon1h.R` on the right hand, motion fitted to 13 original weapons (0.7-1.3 px instead of 1.4-2.1 px); run `uo_place_weapon.py` with `PART = "weapon1h"` first |
      | `"weapon"` / `"weapon.L"` | uncalibrated weapon | rigid on `hand.R` / `hand.L` |
      | `"polearm"` (`"staff"`, `"weapon2h"`) | staff, spear, javelin, pitchfork, halberd, bardiche, crook | bone `polearm.L` on the left hand, motion fitted to the original weapons (0.6-1.1 px instead of 5-6 px); run `uo_place_weapon.py` first |
      | `"axe2h"` | two-handed axe, hatchet / hammer in the left hand | bone `axe2h.L` (same, 1.2-1.7 px error) |
      | `"shield"` | shield | rigid on `shield.L` (shield bone on the forearm, moves like the UO shield) |
      | `"bow"` / `"crossbow"` | bow / crossbow | bone `bow.L` on the left hand (1.6-2.1 px error instead of 3 px) |
      | `"quiver"` | quiver | rigid on `chest` |

      For `"chest"` the line of that type sets how much of a bone's weight stays on it: `"thigh": (0.3, 0.1, 0.4)` = 30% on the thigh
      at the hip (the rest on the pelvis), 100% from 40% of the thigh length, smooth in between.

   4. The script parents the item to `UO_Rig`, adds the *Armature* modifier and sets the weights, so the item moves
      with the skin under it. Run it again after every change to the item's shape (old weights are replaced).
   5. Manual way (your own weights): Ctrl+P → *Armature Deform → With Empty Groups*, paint the weights or copy them with
      a *Data Transfer* modifier (Vertex Groups, *Nearest Face Interpolated*) and delete the groups of bones the item
      does not cover.
   6. Skin poking a few mm through the item (in the 3D view) does not cut holes in the frames: when rendering, the body
      hides the item only where it is more than `HOLDOUT_MARGIN` (1 cm, section 4) in front of it.
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
   - Shirts, tunics, jackets made on another mannequin (sleeves beside the UO arms, the body through the front): `"conform": {...}` in a `uo_make_item.py` recipe (`pipeline/uo_conform_item.py`): sleeves moved onto the arm axes, the item wrapped like a membrane 1.5 cm off the skin (the model's folds and UVs kept), weights as the skin under it but the front and back of the chest (more than 2 cm from the arm's skin) keep 35% of the arm's weight, and the render keeps it 8 mm off all the skin in every frame (`cloth_lib.conform_push`). Measure: `pipeline/item_clearance.py` (skin through the item after the render's push, stretch), `docs/qa/jedi_tunic.md`.
   - Robes, dresses and skirts: `PART = "robe"` / `"skirt"` (the cloth hangs from the pelvis and the legs push it out, and Blender's cloth simulation with collision against the body runs on top: `pipeline/uo_cloth_sim.py`, on by default in `uo_make_item.py` for `robe` / `skirt`, `--no-sim` turns it off; no bone chains). Cloaks: `PART = "cloak"` (`kind: cloak`), swung back per action and frame from the table `cloak_pitch.json` (IoU with the original 468: 0.376 -> 0.507, `docs/qa/cloak_physics.md`); no waving of the sides.
   - A robe from a cloth simulator (a closed solid ~1.5 cm thick made of separate panels, hundreds of thousands of vertices; `docs/qa/robe_black.md`): `"outer_shell": 0.006` (a 6 mm voxel remesh fuses the panels into one sheet, the outer layer is kept, the texture is baked from the original: otherwise the reduction pastes the layers together and the seams open under the arms), `"prepare": {"HEM": 0.15}` (a robe longer than the body: the lower part shortened, the hem above the feet), `"HEM_BAND": {"height": 0.15, "skip_front": 20}` (a continuous gold band along the hem where the embroidery of the model has gaps; not across the front opening), `"conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "SPACE_SMOOTH": 0.04}` (wrapped round the body, the legs covered in the whole stride, flaps and collar moved together), `"sim": {"arm_goal": 0.95, "smooth": 0.04}` (pleats do not cut through each other), `"materials": {"GREY_CLOTH": {...}}` (the cloth grey like the UO robes, the gold kept), `"scene": {"uo_outline": 0.6, "uo_hide_erode": 1, "uo_legs_under": 1}` (a softer outline, the hand / head do not cut the sleeve and collar, the legs always under the robe). The measure of what the client shows (the clothing layer over the original body 400): `pipeline/item_body_holes.py`. The cloth simulation works in Blender 5.2 and 4.2 (the target of every frame as animated shape keys; before, the pin stayed on the first frame).

## 3a. The fast path: a free model -> an item in one command

No Blender window (`pip install numpy pillow scipy "bpy==4.2.*"`), from the repo folder:

```
python pipeline/uo_make_item.py --list model.glb            # what is in the file: meshes, vertices, size (to choose "skip" / "keep")
python pipeline/uo_make_item.py recipe.json --preview       # item.blend + preview.png (6 actions x 3 directions x 3 moments of the animation)
python pipeline/uo_make_item.py recipe.json --vd            # the same + all 35 actions into clothing.vd (15-30 min)
```

The recipe (`file` and `kind` are required; every field is described in the header of `pipeline/uo_make_item.py`):

```json
{"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt", "skip": ["guy"]}
{"name": "sword", "file": "models/miecz.glb", "weapon": {"class": "sword", "part": "weapon1h"}}
```

What happens (the same scripts as in the Blender window): import (drops the meshes of `skip`, keeps `keep`, reduces a mesh over 30k vertices, smooth shading) -> `uo_materials.py` (UO look) ->
`uo_prepare_item.py` = **`uo_autofit_item.py`** (units, size and place from the shape of the skin, not from one height per slot; short jackets and wide pauldrons are not stretched; `docs/qa/autofit.md`) ->
densify (dense meshes, so that it bends smoothly) -> `uo_fit_item.py` (pushed out of the skin, **soft thickness limit** `LIMIT`: pauldrons and collars are no thicker than the original UO items) -> `uo_bind_item.py`.
Weapon (`weapon`): `uo_orient_weapon.py` stands it upright (tip up, flat side on +X, class length), then `uo_place_weapon.py` and `uo_bind_item.py`.
Next to `item.blend` there is `qa.json` (`pipeline/item_qa.py`, a few seconds): how many vertices are inside the body in motion (clipping before the render pushes them out of the body) and how far the item stands off the skin (thickness). The report says `AMBIGUOUS` when two solutions (e.g. front / back) fit almost equally well: check `preview.png` and set `turn` or `scale` in the recipe.

In the Blender window `uo_autofit_item.py` needs `scipy` (Blender does not ship it): `import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'scipy'])` in Blender's Python console, or simply run `uo_make_item.py` from outside. Without scipy `uo_import_item.py` falls back to the old placement from one height per slot (with a warning) and `uo_prepare_item.py` skips the fit.

A model of several items with its mannequin in the file (e.g. a harness with a sword on the back): `"reference": {"keep": ["=mannequin mesh name"], "kind": "shirt"}` fits the mannequin to the body and every one of `"parts"` gets its transform
(`{"name": "straps", "keep": [...], "kind": "harness"}`, `{"name": "sword", "keep": [...], "rigid": "quiver"}`; `=name` = the exact mesh name). Rigid things on the back get the properties `uo_behind_torso` (the torso hides them from the front) and `uo_no_body_gap` (they are not bent away from limbs).

**Loose garments (`kind`: `robe`, `skirt`).** The cloth hangs from the pelvis and the legs **push it out to where they reach** (a hull of the legs, a tent from the waist, one frame at a time with no memory: no jumps, no clipping),
5 cm past the legs and 0.8 of the way, as in the original UO robes. Measured on the original 469: lower-body IoU 0.641 -> 0.757 (`docs/qa/robe_physics.md`). The `uo_cloth` property is set by `uo_bind_item.py` (`PART` `robe` / `skirt`) and applied by `render_uo_layer.py`.

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

**Cancelling a render:** press **ESC** in Blender's window (progress is in the status bar at the bottom; the window does not freeze,
but other input is blocked while it renders). In background mode (`blender -b`, the `bpy` module) create an empty file named `STOP`
in the output folder (e.g. `uo_render/clothing/STOP`) or press Ctrl+C. Finished PNG frames are kept.

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
- **Pure 3D model (`EXACT_BODY = False`):** mean silhouette IoU **0.892** over 1050 frames (`body_part_qa.py`), **with no shape
  corrections** (bones only). IoU per action: `docs/qa/body_parts_after_fingers.json`. Colours on overlapping pixels are exact with `EXACT_COLORS`.

The differences are almost only 1-pixel bands along the edges (the original was drawn from a different 3D model).
There are no large errors such as an arm in a different place than on the original, so the cut-outs in items hit the
arm. For comparison: the previous model scored 0.880 without its 1254 corrections and 0.979 with them (but items had
to copy those corrections).

**UO items.** A test of replicas of items from `anim.mul` (`test_items.py`: shirt, plate, trousers, boots, gloves, helmet) on the current rig:
mean IoU with the original frames **0.718** (shirt 0.714, plate 0.690, trousers 0.800, boots 0.768, gloves 0.557, helmet 0.781; `docs/qa/items_after_fingers.json`).
Hand shape error against the original (model pixels outside the sprite per frame): 3.9 -> 1.4 (left) and 4.3 -> 2.0 (right) after the fingers came back.
There are no skirt, cloak or weapon tests any more (their bones were removed).

## 9. How the model was built

The body is a MakeHuman mesh (CC0, male) moved onto the UO skeleton; the UO camera (orthographic, elevation 28.45°, 36 px/m, anchor in the pixel centre,
floor 7 cm below it) and 210 poses × 5 directions were fitted to the 1050 original frames (own rasteriser + skinning like Blender's), then the mesh shape
was fitted to the outlines of all frames, and the shoulders and arms were narrowed slightly at the user's request. The UO light (one light near the
camera, Lambert) was derived from the frames and removed from the colour, giving the albedo. The original frames are packed in the `.blend` as an atlas for the exact modes.
In session 14 the rig was reduced to 19 bones (see section 2). Measurements and decisions: `docs/RAPORT_model3D_UO.txt`, `docs/AUDYT_2026-10-03.md`, `docs/qa/`.

## 10. Rebuilding and tools

The scripts that built the body (versions 1-13: pose, shape and correction fitting, cloth, weapons, shield) were removed from the repository together with their intermediate data:
they are in git history up to commit `b86c314` (`git show b86c314:pipeline/body13/build_v13.py`). The current `.blend` is the source of truth; changes are made on it
(e.g. `pipeline/rig_simplify.py`) and described in the commit. Input data that remain: the original client files `pipeline/body400.vd`, `pipeline/horse200.vd`,
the frames in `client/`, item sprites `pipeline/body13/mul/` (from `anim.mul`), the client extract `client/extract/`.

To restore the original frames in the `.blend`: `python build_originals.py`, then `python pack_originals.py --blend ../model/UO_Body_0x190.blend` (in `pipeline/`).
Measurements: `body_part_raster.py` + `body_part_qa.py` (body silhouette), `test_items.py` (items), `test_canvas.py` (canvas), `layer_analysis.py`, `light_*.py`, `slot_dynamics.py`.

## 11. Limitations and common problems

**Limitations**
- Muscle drawing is softer than on the sprites, because the texture averages many frames.
- Fingers and the face come from MakeHuman (they cannot be seen on ~60 px frames).
- The pure 3D model differs from the original mostly by 1-pixel bands along the edges (about 12% of the silhouette
  pixels). The exact modes (`EXACT_BODY`) remove this from renders: the body is always the original, the model only
  decides what is in front of it and what is behind.
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
RIG        : 54 bones: pelvis (root) spine chest neck head; clavicle/upper_arm/forearm/hand .L/.R; thigh/shin/foot .L/.R
             (clavicles do not deform); finger1-1..finger5-3 .L/.R (finger1 = thumb, local X = curl axis). Item bones polearm.L axe2h.L bow.L (hand.L), weapon1h.R (hand.R), shield.L (forearm.L). No twist, toe or cloth-chain bones.
             Quaternion rotations, MakeHuman weights. Per-frame girth = pose-bone scale (x, 1, z) on upper_arm,
             forearm, hand, thigh, shin, foot, head; forearm/hand/shin/foot have Inherit Scale = None.
ACTIONS    : 35 Blender actions "NN_name", props uo_action (0..34) and uo_frames; UO frame i -> scene frame 1 + 3*i.
             Every action keys UO_Rig["uo_action_id"].
BODY       : UO_Body = MakeHuman mesh (13380 verts, UVs), no shape keys. Items: text "uo_bind_item.py" (PART preset ->
             allowed bones): nearest skin point restricted to body triangles whose dominant bone is allowed; MAP "under":
             skin hit along the item vertex normal (else nearest); weights = body weights there (allowed bones only,
             renormalised); SMOOTH passes of neighbour averaging over the item. RIGID presets (hair, beard, hat, weapon, shield, bow,
             crossbow, quiver): 100 % on one bone (hand.R / hand.L / forearm.L / head / chest).
HOLDOUT    : clothing layer = Cycles render without the body; own z-buffer raster of body and items; the body hides a
             pixel where depth_body < depth_item - HOLDOUT_MARGIN (0.01 m), using only body triangles whose dominant bone is
             in OCCLUDERS (no torso); transparent patches <= FILL_HOLES px fully
             surrounded by the item are filled (from the render without the body, else the neighbours' colour);
             8-connected pieces < MIN_PIECE px other than the biggest are cleared after the UO post-process.
BODY GAP   : per UO frame (once for all 5 directions) the posed bound items (welded nodes) are pushed BODY_GAP out of
             the posed OCCLUDERS triangles (BVH nearest, 12 rounds, displacement smoothed over the item edges) and shown
             through shape key 'uo_fix' with the Armature modifier off; removed again after the run (also on STOP).
BIND FOLD  : uo_bind_item PARTS[...][1] = share of a limb bone's weight kept; the rest moves to the parent bone
             (hand>forearm>upper_arm>chest, foot>shin>thigh>pelvis, head>neck); a tuple (share, t0, t1) ramps the share along the bone; "chest" =
             thigh (0.3, 0.1, 0.4).
MOUNTED    : horse = body 0xC8; rider->horse action pairing 23->0, 24->1, 25..29->2. Objects Horse_a{action}_f{frame}
             (holdout proxies, parented to UO_Rig) + text "uo_horse_masks.json" (key "action,frame,dir" ->
             base64(zlib(packbits(120x136 bool)))). Hiding happens only inside the horse silhouette.
EXACT      : image "UO_Original_Atlas" (1050 original frames, 35 cols x 30 rows of 136x120) + text
             "uo_original_frames.json" (tiles; base64(zlib(RGBA)) per "action,frame,dir"); scene props uo_tile_col,
             uo_tile_row, uo_exact drive the projection. Present in this repository's .blend.
MATERIAL   : scene["uo_look"]: 1 = albedo * (0.08 + 0.92 * max(0, N.L)), light fixed to the camera; 0 = plain PBR.
RENDERING  : text "render_uo_layer.py": LAYER ("clothing" | "body" | "all"), ONLY, OUTLINE = 0.38, WRITE_VD, OUT_DIR,
             VD_FILE, HORSE_HOLDOUT, EXACT_BODY, EXACT_COLORS. Cycles, 1 sample, box filter 0.01. Post-process:
             premultiply over black, alpha threshold 0.5 -> 0/1, 1-px boundary outline * 0.38. Runs into the same
             OUT_DIR accumulate; a file named STOP in the output folder cancels.
             Output: frames/NN_action/dirK/NN.png + meta.json (vdtool layout) + <LAYER>.vd (anim_type 2, anchor 68,86).
QUALITY    : exact mode: identical to the original body; pure model (bones only): mean silhouette IoU 0.888.
RULES      : never swap left/right limbs relative to the original frames; new layers must keep the same 35 actions,
             5 directions and frame counts as the body; do not redistribute UO client files or this repository's .blend.
REBUILD    : the .blend is the source of truth; build scripts are in git history (commit b86c314), see section 10.
```
