**[Polska wersja (Polish version) → README_PL.md](README_PL.md)**

# UO Body 0x190: a 3D model from Ultima Online animations

A naked male body (body 0x190 / 400) rebuilt in 3D from the UO client animation `anim1_0x0190.vd`: 35 actions × 5 directions, 1050 images.
A realistic body (MakeHuman, CC0) in the UO character's proportions, a 54-bone rig and all 35 animations fitted to the original frames.
It is meant for designing clothing, armour, hair and weapon layers: the `.blend` renders new UO frames and writes them straight into a `.vd` file.

**Contents:** [1 Files](#1-files) · [2 The model](#2-how-the-model-works) · [3 Modelling an item](#3-modelling-an-item) · [3a Fast path](#3a-the-fast-path-a-free-model---an-item-in-one-command) · [4 Rendering](#4-rendering-frames-and-the-vd-file) · [5 Cutting](#5-cutting) · [6 vdtool](#6-the-vdtool-tool) · [7 Importing into the game](#7-importing-into-the-game) · [8 Accuracy](#8-accuracy) · [9 History and tools](#9-history-and-tools) · [10 Problems](#10-limitations-and-common-problems) · [11 Notes for AI assistants](#11-notes-for-ai-assistants)

---

## 1. Files

| File / folder | What it is |
|---|---|
| `model/UO_Body_0x190.blend` | Main file (Blender 4.2 – 5.2): body, rig, 35 actions, UO camera, clothing-layer scene, horse proxies, scripts. |
| `model/UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Albedo (grey like UO skin, lighting removed) and its variants for the 5 directions. |
| `model/example_clothing/` | Example layer (a shirt) as `.vd` with a preview over the original body. |
| `model/items/horn/` | Recipes of a horn item for the right and left hand. |
| `vdtool/` | `vdtool.py` unpacks and repacks `.vd` (section 6), `mul2vd.py` converts client `anim.mul`. |
| `pipeline/` | Render, item fitting, tests, measurements (section 9). `body400.vd`, `horse200.vd` = original client files (body 0x190, horse 0xC8). |
| `client/` | Original body (1050) and horse (300) frames as PNG + `meta.json`; `extract/` = data extracted from the client. |
| `docs/qa/` | `baselines.md` (QA thresholds and last values), measurement JSONs, reports on the robe variants (section 3a). |

**Original frames.** The `.blend` contains the original UO frames (for the exact modes, section 2). Own use only; do not share them. To add them from your client: copy `anim1_0x0190.vd` to `pipeline/body400.vd`, then in `pipeline/` run `python build_originals.py` and `python pack_originals.py --blend ../model/UO_Body_0x190.blend`.

## 2. How the model works

**Mesh `UO_Body`:** MakeHuman (CC0), 13,380 vertices, UVs, fingers, face; proportions fitted to the original frames. Rest pose: A-pose. Metres, the character faces −Y, Z up, **floor z = 0**. No shape keys: the bones alone set the silhouette in every frame, so an item simply follows the bones.

**Rig `UO_Rig`** (54 bones: 19 UO bones, 30 finger bones, 5 weapon / shield bones; `.L`/`.R`):
- `pelvis` (root, carries the translation) → `spine → chest → neck → head`; `chest → clavicle → upper_arm → forearm → hand`; `pelvis → thigh → shin → foot`. Clavicles raise the shoulder but do not deform the mesh; they have location keys only in 49 of 210 frames where the silhouette needs them.
- `finger1-1` … `finger5-3` (15 per hand, `finger1` = thumb, X = curl axis): the hand is clenched as on the original. Gloves follow the fingers.
- Item bones: `polearm.L`, `axe2h.L`, `bow.L` (on `hand.L`), `weapon1h.R` (on `hand.R`), `shield.L` (on `forearm.L`), keyed in all 35 actions.
- No twist, toe or cloth-chain bones. Weights from MakeHuman (no candy-wrapper joints).
- **Girth per frame:** X/Z scale of `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1, the next bone does not inherit it) makes a limb thicker or thinner where the original needs it; items bound to these bones follow. The head has one scale (1, 1, 0.942) in all frames, so a helmet does not pulse.

**Fitted to the frames.** The pose of each of the 210 frames is fitted to all 5 directions of the original at once, then re-fitted for **natural motion with the same silhouettes** (`pipeline/pose_natural_fit.py`): smooth in time, no head zig-zag, no twisting or sliding shoulder, elbow a hinge; no frame worse than before. In the area spell (action 17) the arms are symmetric and the torso only tilts. Weapons, shields and hair are rigid on hand, forearm and head.

**Animations.** Each UO action is a Blender action `NN_name` (fake user), properties `uo_action` and `uo_frames`; 1 UO frame = 3 scene frames (24 fps), smooth interpolation. Left and right match the original. In the mounted actions the rider sits in the air; the horse is a separate animation.

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

**`UO_Camera`** sees like the game camera: orthographic, elevation 28.45°, 36 px/m, original frames 136×120 with the anchor on pixel (68, 86), 7 cm above the floor. `render_uo_layer.py` renders on a bigger canvas (`CANVAS` 256×256, anchor (128, 192)), because 136×120 cuts off two-handed weapons, spears and tall headgear. Direction = property `uo_direction` (0–4) of `UO_Rig`: 0 faces the camera, 2 is a profile facing left, 4 faces away; 5–7 are mirrors of 3–1 made by the client.

**Material and UO light.** One light at the camera, estimated from the frames and separated from the body colour. `uo_look = 1` (default): albedo × (0.08 ambient + 0.92 UO light), looks like the game frames; `uo_look = 0`: plain PBR for editing and game engines (`export.py` makes `.glb`/`.fbx` on demand, not in the repo). The node group **`UO_Look`** gives items the same light; "Skin hue" tints the skin. **Exact modes** (need the original frames and Cycles): `EXACT_COLORS` paints the body with the original frame projected from the camera; `EXACT_BODY` makes the body layer identical to the original and lets the body hide an item exactly along the original outline.

**Horse (actions 23–29).** The `Horse_Proxy` collection holds an approximate volume of the horse (0xC8) per mounted frame; it decides **what** is behind the horse, while **where** the horse is comes from the exact outline of its frames (`uo_horse_masks.json`), so the horse hides the rider and items to the pixel.

**Scripts inside the `.blend`** (Text Editor, pick from the list in the header). Always work in `UO_Body_0x190.blend` and bring your items into it:

| Text | Purpose |
|---|---|
| `render_uo_layer.py` | Renders a layer to frames and `.vd` (Alt+P). |
| `uo_import_item.py` | Brings a foreign model (`.glb` `.fbx` `.obj` `.dae`) onto the body: bakes the mesh, scales it to the height of the original item of that `KIND`, puts it in `Clothing`. |
| `uo_materials.py` | Foreign materials into the UO look: colour into `UO_Look`, alpha >= 0.5 = pixel, PBR parameters dropped, **metal gets a UO-style highlight** (measured on plate and helm sprites); `SATURATION = 0` = grey item for in-game dyeing. After `uo_import_item.py`. |
| `uo_densify_item.py` | Subdivides the mesh without changing the shape so that a low-poly item bends smoothly (edge 2 cm gloves, 3-5 cm the rest). |
| `uo_autofit_item.py` | Units, size and place from the shape of the skin of the slot (needs `scipy`). |
| `uo_fit_item.py` | Turns sleeves onto the arms and pushes the item out of the skin. |
| `uo_prepare_item.py` | One step per slot (`KIND`): autofit → densify → fit → bind. |
| `uo_bind_item.py` | Binds the item to the body: parent, Armature, weights (section 3). |
| `uo_hood_cover.py` | Brings a hood onto the skull and the cowl onto the shoulders. |
| `cloth_lib.py` | Loose garments: hull of the legs and tent from the waist, per frame (numpy); leg push of the renderer and target of the cloth simulation. |
| `uo_orient_weapon.py`, `uo_place_weapon.py`, `uo_place_shield.py` | Stand a weapon upright, put it on the grip line of its class (turned about its shaft like the original `REF_ANIM`, then the bone turns it by the measured roll), put a shield on the left forearm. Before `uo_bind_item.py`. |
| `uo_weapon_bones.py`, `uo_shield_keys.py`, `weapon_motion.json` | Weapon bones and their motion (grip and 210 poses of 4 weapon classes); load the motion into an older file. |
| `uo_vd_writer.py`, `uo_job.py` | `.vd` writer and a runner that keeps Blender's window alive during long renders (not run directly). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Data: horse outlines and original frames. |

**Tools outside the file (`pipeline/`):**

| Group | Scripts |
|---|---|
| Item in one command | `uo_make_item.py` (3a), `vd_swap_action.py` (replace the frames of single actions in a finished `.vd` by freshly rendered ones: no full render), `uo_conform_item.py`, `uo_cloth_sim.py`, `uo_spikes.py` (bigger spikes of a spiked ball), `uo_twohand.py` (two-handed weapon carried by both hands), `item_gif.py` (frame sheet and GIF of an item on the original body), `item_sheet.py` |
| Item measurements | `item_qa.py` (clipping, thickness), `item_clearance.py`, `item_thickness.py`, `item_body_holes.py` (what the client shows over the original body 400), `item_skin_check.py` (skin through the item vs in holes, feet apart) |
| Body and poses | `pose_lib.py` (rig in numpy, pixel-identical to Blender; `qa`), `pose_natural_fit.py` + `apply_pose_keys.py`, `pose_naturalness.py`, `body_part_raster.py` + `body_part_qa.py`, `arm_*.py` (arm fit, mirror of the left arm in action 17) |
| Tests | `run_qa.py [--quick]` (regression with thresholds, `docs/qa/baselines.md`), `test_items.py`, `test_canvas.py`, `test_autofit.py`, `test_robe.py`, `test_cloak.py`, `test_materials.py`, `test_import_item.py`, `test_twohand.py`, `test_weapons.py`, `test_weapon_roll.py` (weapon tests need client sprites; only katana 627 is in the repo) |
| Calibration and analysis | `weapon_*.py`, `robe_calib.py`, `cloak_calib.py`, `cloak_fit_frames.py`, `layer_analysis*.py`, `light_*.py`, `slot_dynamics.py` |
| Environment | `sync_blend_scripts.py` (scripts into the `.blend`), `run_render_headless.py`, `build_originals.py` / `pack_originals.py`, `export.py`, `rig_*.py` (one-off rig changes) |

## 3. Modelling an item

1. **Open `UO_Body_0x190.blend`**, allow scripts (Preferences → Save & Load → *Auto Run Python Scripts*).
2. **Rest pose:** select `UO_Rig` → Object Data Properties → Pose → *Rest Position*; model on the A-pose, then back to *Pose Position*.
3. **Add the item** (model, or import / append) into the **`Clothing`** collection; everything in it is rendered. Delete `Example_Shirt` or disable it.
   **A foreign model:** in `uo_import_item.py` set `FILE` and `KIND` (`shirt`, `plate`, `arms`, `pants`, `legs`, `boots`, `gloves`, `helm`, `neck`, `hair`, `beard`, `hat`) and run it (Alt+P). It drops the file's skeleton and everything but the mesh (`SKIP` for eyes, the model's body, helpers; `TURN = 180` if it faces backwards), places the item at the height of the original UO item of that kind and prints the `PART`. Then `uo_materials.py` (without it shiny metal renders about 55/255 off the UO light), `uo_fit_item.py`, `uo_bind_item.py`. Check the licence.
4. **Things that bend (clothing, armour, helmet, boots, gloves):**
   1. Make every piece that is a separate game item a separate object. 136×120 px shows little detail: up to ~20k vertices is plenty (*Decimate*).
   2. **`uo_fit_item.py`** (optional, in Rest Position): turns the sleeves onto the arms (`MATCH_ARMS`) and pushes parts closer to the skin than `MIN_GAP` (15 mm) out. A push moves its neighbourhood the same way, fading over max(`RADIUS` 4 cm, `SPREAD` × push), so folds and rivets go with it. Subdivide big faces first. Running it again changes nothing; `MAX_GAP > 0` also pulls standing-off parts in.
   3. In **`uo_bind_item.py`** set `PART` and run it (Alt+P): every item vertex follows the skin right under it (`MAP = "under"`), weights smoothed (`SMOOTH = 4`). Run it again after every shape change.

      | `PART` | Item | What it follows |
      |---|---|---|
      | `"chest"` | breastplate, vest, tunic | skin under it; thigh near the hip 70% on the pelvis, sleeves on the arms |
      | `"torso"` | something on the torso only | pelvis, spine, chest, neck |
      | `"shoulders"` | pauldrons | chest, upper_arm |
      | `"arms"` | sleeves, arm armour | upper_arm, forearm |
      | `"gloves"` | gloves, gauntlets, bracers | forearm, hand |
      | `"legs"` | trousers, leg armour | pelvis, thigh, shin |
      | `"boots"` | boots, greaves | shin, foot |
      | `"helm"` | helmet, mask, stiff hood | head |
      | `"hood"` | hood with a cowl | hood: head, cowl: neck and chest; then `uo_hood_cover.py` (recipe `"hood_cover"`) |
      | `"neck"` | gorget, collar | neck, chest, head |
      | `"all"` | full suit in one object | skin under it, every bone |
      | `"cloak"` | cloak | hangs from the chest and **swings back about the shoulders** per action (table `cloak_pitch.json` from the original 468; no side waving) |
      | `"robe"`, `"skirt"` | robe, dress, skirt, kilt | skin down to the hips; below, the pelvis and the leg push (`cloth_lib.py`, property `uo_cloth`), then the cloth simulation (3a) |
      | `"hair"`, `"beard"`, `"hat"` | hair, beard, cap | rigid on `head` |
      | `"weapon1h"` | sword, mace, hammer, 1H axe, pickaxe | bone `weapon1h.R`, fitted to 13 original weapons (0.7-1.3 px error); run `uo_place_weapon.py` first |
      | `"weapon"` / `"weapon.L"` | uncalibrated weapon | rigid on `hand.R` / `hand.L`; `weapon.L` puts a 1H item (horn, lantern) in the left hand on the mirrored grip |
      | `"polearm"` (`"staff"`, `"weapon2h"`) | staff, spear, halberd | bone `polearm.L` (0.6-1.1 px); `uo_place_weapon.py` first |
      | `"axe2h"` | two-handed axe, hatchet in the left hand | bone `axe2h.L` (1.2-1.7 px) |
      | `"shield"` | shield | rigid on `shield.L` |
      | `"bow"` / `"crossbow"` | bow / crossbow | bone `bow.L` (1.6-2.1 px) |
      | `"quiver"` | quiver | rigid on `chest` |

      For `"chest"` a line like `"thigh": (0.3, 0.1, 0.4)` sets how much of a bone's weight stays on it: 30% on the thigh at the hip, 100% from 40% of its length.
   4. Manual way: Ctrl+P → *Armature Deform → With Empty Groups*, paint or copy weights (*Data Transfer*), delete groups of bones the item does not cover.
   5. Skin poking a few mm through the item in the 3D view cuts no holes: the body hides the item only where it is more than `HOLDOUT_MARGIN` (1 cm) in front of it.
5. **Weapon, shield, hair** (rigid): `uo_bind_item.py` with the matching `PART`. Put a sword in Rest Position with the grip inside the right hand and the blade on the thumb side (as on the original frames). Stand a shield upright, face to the front view (Numpad 1), run `uo_place_shield.py` (outside of the left forearm, `GAP` 1 cm), then `PART = "shield"`; render it with `BODY_GAP = 0`.
6. **Material:** Add → Group → **`UO_Look`**, plug the colour or texture into *Albedo*. Make anything that should take a hue in-game greyscale.
7. **Check the motion:** Dope Sheet → Action Editor → pick `NN_name` and play (Space); game view = Numpad 0, direction = `uo_direction`. Check attacks, spells and deaths in particular. Keep clothing 1-2 cm above the skin.

## 3a. The fast path: a free model -> an item in one command

No Blender window (`pip install numpy pillow scipy "bpy==4.2.*"`), from the repo folder:

```
python pipeline/uo_make_item.py --list model.glb            # meshes, vertices, size (to choose "skip" / "keep")
python pipeline/uo_make_item.py recipe.json --preview       # item.blend + preview.png (6 actions x 3 directions x 3 moments)
python pipeline/uo_make_item.py recipe.json --vd            # the same + all 35 actions into clothing.vd (15-30 min)
```

Recipe (`file` and `kind` required; every field is described in the header of `uo_make_item.py`):

```json
{"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt", "skip": ["guy"]}
{"name": "sword", "file": "models/miecz.glb", "weapon": {"class": "sword", "part": "weapon1h"}}
```

Steps (the same scripts as in the Blender window): import (drops `skip`, keeps `keep`, reduces over 30k vertices) → `uo_materials.py` → `uo_prepare_item.py` (**autofit**: units, size and place from the shape of the skin, short jackets and wide pauldrons not stretched; densify; `uo_fit_item.py` with a **soft thickness limit** `LIMIT`; bind). Weapon: `uo_orient_weapon.py` (tip up, flat side on +X, class length), `uo_place_weapon.py`, bind. Next to `item.blend` is `qa.json` (`item_qa.py`): vertices inside the body in motion and the stand-off from the skin. `AMBIGUOUS` means two solutions (front / back) fit almost equally well: check `preview.png`, set `turn` or `scale`. In the Blender window `uo_autofit_item.py` needs `scipy` (install it in Blender's Python console or run `uo_make_item.py` from outside); without it the old placement from one height per slot is used.

**Special recipe fields:**
- `"conform"` (`uo_conform_item.py`): shirts, tunics and jackets made on another mannequin: sleeves moved onto the arm axes, the item wrapped like a membrane 1.5 cm off the skin (folds and UVs kept), the render keeps it 8 mm off the skin in every frame. Measure with `item_clearance.py`.
- A model of several items with a mannequin: `"reference": {"keep": ["=mannequin mesh"], "kind": "shirt"}` fits the mannequin to the body and every entry of `"parts"` gets its transform (`{"name": "straps", "keep": [...], "kind": "harness"}`, `{"name": "sword", "keep": [...], "rigid": "quiver"}`; `=name` = exact mesh name). Things on the back get `uo_behind_torso` and `uo_no_body_gap`. Thin parts vanish at 36 px/m: `"widen": {"width": 0.07}` (straps), `"skin_wrap": {"GAP": 0.008}` (straps laid on the skin), `"thicken": {"width": 0.085}` (a flat scabbard seen edge-on).
- A two-handed weapon (mace, maul): `"weapon": {"class": "mace", "part": "polearm", "spikes": {"LENGTH": 1.6, "WIDTH": 3.0, "SHAFT": 0.0278}, "no_body_gap": true, "behind_torso": true}` + `"twohand": {...}`. `spikes` (`uo_spikes.py`) makes the spikes of the ball longer and thicker (`LENGTH`, `WIDTH`) and the shaft thicker (`SHAFT`, m of diameter; 0.0278 = 1 px); `twohand` (`uo_twohand.py`) re-keys the bone `polearm.L` from the posed fists instead of the halberd calibration: the shaft goes through **both** fists (the upper one `GRIP_BELOW` 0.14 m = 5 px under the ball, 0.12 m lower when mounted), the ball does not spin about the shaft, in the falls (21, 22) the shaft turns into the axis of the body, in the mounted actions it is moved to the nearest direction that clears the horse proxy and leans away from the horse. Details and settings in the header of `uo_twohand.py`; `test_twohand.py` checks it on a synthetic mace. `no_body_gap` (the renderer does not push the shaft out of the fists) and `behind_torso` (seen from the back the chest and neck hide what is in front of them; scene `uo_torso_margin` 0.04) are needed for a weapon held in front of the body.
- `"scene": {...}` = per-item render options (section 4), `"sim": {...}` = cloth simulation settings, `"prepare"`, `"materials"`, `"holes"`, `"bake_normal"` / `"bake_ao"` as in the header of `uo_make_item.py`.

**Loose garments (`kind`: `robe`, `skirt`).** The cloth hangs from the pelvis and Blender's cloth simulation (`pipeline/uo_cloth_sim.py`, on by default in `uo_make_item.py`; `"sim": {...}` = its settings, `--no-sim` = off) lets the legs push it out like real fabric. Every vertex is held by a weak spring (pin `goal`) to a kinematic target = the item as the skeleton skins it + `pushw` × the leg push (`cloth_lib.hull_push`); the cloth collides with the posed body; the result is stored as the difference to the full target (`cloth_sim.npz`) and added by `render_uo_layer.py`. The target need not match the original robe sprite 469: the judge is physics (collisions, hem) and the look. (The leg hull alone, one frame at a time, gave lower-body IoU 0.641 → 0.757 against the original 469.)

Settings that worked for a fine mesh (24k vertices; set **t1**, not yet the defaults of `uo_cloth_sim.py`, give them in `"sim"`): `mscale 0.0333 goal 0.2 pushw 0.5 gravity 1.5 in_max -1 max_move 0 smooth 0.04 arm_goal 0.95 preroll 20 cycles 2 thick 0.02 dist 0.005`; riding: `mounted 1 horse 1` (the horse proxy is a collider). Blender's mass and stiffness depend on the vertex count, so `mscale` scales the per-vertex mass to the mesh. A robe made by a cloth simulator (a closed solid of separate panels, hundreds of thousands of vertices) also needs `"outer_shell": 0.006` (voxel remesh fuses the panels), `"prepare": {"HEM": 0.15}` and `"HEM_BAND"` (hem above the feet, a continuous trim), `"conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "CLOTH_DROP": 0.3, "SLEEVE_CUFF": 0.05}` (wrapped round the body, hangs from a knee, bell sleeves narrowed so the hands show), `"sim": {"arm_goal": 0.95, "smooth": 0.04}`, `"materials": {"GREY_CLOTH": {...}}` (grey like UO robes), `"scene": {"uo_cloth_lie": 1.0, "uo_hide_erode": 1, "uo_legs_under": 1, "uo_outline": 0.6}`; a torn robe keeps the holes of the model (`"prepare": {"HEM_FLARE": {"factor": 0.65}}` narrows a strongly flared skirt).

| `fabric` | Mass | Bending | Damping | Run |
|---|---|---|---|---|
| `silk` | 0.15 | 0.05 | 1 | full 35 actions × 5 directions |
| `cotton` | 0.3 | 0.5 | 5 | full 35 actions × 5 directions |
| `wool` | 0.5 | 2 | 10 | full 35 actions × 5 directions |
| `denim` | 1.0 | 10 | 25 | not run |
| `leather` | 0.4 | 150 | 25 | not run |

In-plane stiffness (tension, compression, shear) is 5 for all fabrics: Blender's presets (15-80) are pulled up by the pin and the hem climbed (cotton +0.26 m, wool +0.47 m in the walk; at 5: +0.04 / +0.05 m, silk +0.04). Free cloth without the pin (goal 0) falls apart or lifts the hem; the collision margin 0.02 m (`thick`) is needed, 0.006 m lets the legs through (leg pixels through the cloth in walk + run, silk: 723 with t1 against 1862 thin). Reports: `docs/qa/robe_variants_2026-10.md` / `.pdf` (what was tried, with measurements), `docs/qa/robe_variants_screenshots_2026-10.pdf` (renders of every variant with its settings). Remaining: legs show in the falls (die forward), the skirt is about 1.7× wider at the hem than the original robe 469, sleeves about 10% thicker.

## 4. Rendering frames and the `.vd` file

1. Engine: **Cycles** (the script sets it: items 512 adaptive samples, body layer 1).
2. Open **`render_uo_layer.py`** and set the options at the top:
   ```python
   LAYER = "clothing"          # "clothing" = item layer, "body" = body, "all" = preview of both
   CANVAS = (256, 256)         # render size; the .vd crops every frame to its content anyway
   ANCHOR = (128, 192)         # anchor pixel (256x256 / (128, 192) holds 444 of 449 people and equipment animations; old size (136, 120), (68, 86))
   ONLY = ["04_stand"]         # test one action; [] = all 35
   OUTLINE = 0.38              # dark 1-px outline of the body (1.0 = none); items: OUTLINE_TARGET 0.38; scene property uo_outline overrides
   SAMPLES = 512               # Cycles samples for items; scene property uo_samples overrides
   EDGE_FLOOR = 0              # the outline of an item is never darker than this (0-255); scene property uo_edge_floor
   OUT_DIR = "//uo_render/"; WRITE_VD = True; VD_FILE = "//uo_render/%s.vd"
   HORSE_HOLDOUT = True        # mounted actions: the horse hides the item
   EXACT_BODY = True           # cut along the original body outline
   EXACT_COLORS = True         # body colours from the original
   HOLDOUT_MARGIN = 0.01       # the body hides the item where it is > 1 cm in front of it (0 = plain Cycles holdout)
   OCCLUDERS = [...]           # parts that may hide the item: arms, hands, head, legs; never the torso
   OWN_PARTS_NEVER_HIDE = True # parts the item is skinned to never hide it
   DESPECKLE = 0               # N > 0: single dark dots inside the item take the colour around them (erased texture detail: off)
   FILL_HOLES = 4              # holes up to 4 px surrounded by the item are filled
   BODY_GAP = 0.006            # every frame, item parts closer than 6 mm to arms, hands, legs, head are pushed out
   MIN_PIECE = 8               # detached bits under 8 px are removed; the biggest piece stays
   ```
3. **Run Script** (Alt+P). A full layer is 1050 frames, 15-30 minutes on a CPU. A clothing layer is rendered without the body; the script works out from depth what the body hides.
4. Output in `uo_render/`: `clothing/frames/NN_action/dirK/NN.png` (full canvas), `clothing/meta.json`, **`clothing.vd`**.

**Rendering in parts:** runs into the same `OUT_DIR` add up (e.g. `ONLY = ["09_attack_1h_slash", ...]`, change the placement, render the rest); every run writes a `.vd` of all actions so far. Delete `uo_render/` to start over. **Cancel:** ESC in Blender's window; in background mode create an empty file `STOP` in the output folder (e.g. `uo_render/clothing/STOP`) or press Ctrl+C; finished frames are kept. **Several items:** render each separately (one item in `Clothing`, change `VD_FILE`).

**Per-item render options** (scene properties; in a `uo_make_item.py` recipe under `"scene"`). They change one item, never the body or the light of other items:

| Option | Default | What it does | Measured effect |
|---|---|---|---|
| `uo_contrast` | 1 (off) | Contrast curve on the item's own pixels, after the outline: `rgb = pivot + k × (rgb - pivot)`. k > 1: darker creases, brighter lights; the item reads thinner and more painted, like the UO originals | Silk robe, sleeves in walk: brightness spread (std) 31 → 45 (k 1.5) → 52 (k 1.8); original robe 469: 54. Dark pixels around the hands 30% → 55-59% (469: 56%). Gold trim more saturated, mean brightness 109 → 98 (469: 113) |
| `uo_contrast_pivot` | 0.49 | The grey (0..1) unchanged by `uo_contrast` (about the median of a grey robe) | Raise it to keep the mean brightness higher |
| `uo_shade_sleeve` | 0 (off) | Smooth contact shadow where sleeve and torso meet (needs `conform`): the torso next to the arm and the inside of the sleeve darken by up to this share over `uo_shade_width` px, per frame, a gradient, no line | Reads as depth in side view and raised-arm spells; 0.6 slightly strong |
| `uo_shade_body` | 0 (off) | The same next to body parts that hide the item (hands, arms, head) | Very subtle at 0.6 |
| `uo_shade_width` | 3 | Width in px (1 px = 2.8 cm) of both gradients | 3-4 |
| `uo_outline` | auto (0.38) | Strength of the dark 1-px outline (1.0 = none) | Light grey robe: 0.6-0.8 |
| `uo_edge_floor` | 0 | The outline is never darker than this per channel | 24 = no pure black rim on a black item |
| `uo_outline_blend` | 0 (off) | Share of the colour of the item pixels next to the rim (inside it) mixed into the rim before `uo_outline` darkens it: the outline is a darker shade of its surroundings (grey of the steel, brown of the leather), not of the often black edge pixel | Spiked mace: `uo_outline` 0.7 + `uo_outline_blend` 0.6 = soft coloured rim, spikes and shaft no longer read as black lines |
| `uo_action_hide` | none | JSON string, per action: `{"29": {"legs_under": 1, "torso": 0}}` = in that action the legs never hide the item and the torso does not hide it / only the listed parts may hide it (`"occluders": "hand"`) / the horse does not hide it (`"horse": 0`) (a weapon whose holding hand is hidden behind the body looked detached from the hand: it is drawn in front of the leg and hip instead) | Mace, mounted attack 2H (29), frames 3-4 |
| `uo_fist_sprite` | none | Actions (`"23,24,..."`): the weapon is moved in the camera plane, per frame and direction, so that its grip lies on the hand SHOWN ON THE ORIGINAL SPRITE (our fitted fist is up to 4 px off it in the mounted walk/run/stand). The hand is found on the sprites where it stands free; its 3D offset gives the shift where it merges with the body; smoothed over the action. `uo_fist_manual` (JSON `{"action": {"dir": [dx, dy] or {"frame": [dx, dy]}}}`, px) overrides it where it cannot be found; `uo_fist_radius` / `uo_fist_edt` tune the search. With `uo_grip_cut_orig` the original hand's pixels cut the shaft. |
| `uo_grip_cut` | 0 (off) | Radius in px: an item with the property `uo_grips` (`uo_twohand.py`, `GRIP_CUT_ACTIONS`) is cut by the hands that hold it: item pixels within this radius of a grip that lie on our hand (fingers included) and on the original body sprite are removed, without a depth test | 3 for the mace: in the fall to the front and the mounted actions the 3D depth did not let the hand hide the shaft |
| `uo_torso_margin` | 0.12 | How far behind the chest (m) an item must be for the torso to hide it (items with `behind_torso`) | 0.04 for a weapon held in front of the body: from directions 3 and 4 the back, neck and head hide the shaft |
| `uo_samples` | 512 | Cycles samples | 1024 for metal gloss, dark leather |
| `uo_inner_line` | 0 | 1-px dark line between sleeve and torso (needs `conform`) | Spread 30 → 40 but reads as a drawn line: not recommended |
| `uo_hide_erode` | 0 | Hands and head hide the item 1 px less | 1 for robes: fewer skin holes at cuffs and collar |
| `uo_legs_under` | 0 | The legs never hide the item | 1 for a long robe |
| `uo_cloth_lie` | 0 | Falls (21, 22): share in which the robe lies along the legs; 0 = the simulation runs there | 1.0 = lies along the legs |

**Base look of a robe or skirt.** `uo_make_item.py` gives `"kind": "robe"` / `"skirt"` the scene `uo_shade_sleeve` 0.4, `uo_shade_width` 4, `uo_contrast` 1.5 unless the recipe's own `"scene"` says otherwise (`"scene": {"uo_contrast": 1}` turns the curve off). Silk robe in walk, sleeve zone: brightness spread 31 → 46 (469: 54), dark share around the hands 38% → 55% (469: 56%). The shadow needs `"conform"`; the contrast does not. Other kinds get nothing. Tried and not useful for sleeves and hands (silk robe, 2026-10): own shadow strength, normal map strength, texture contrast, occlusion shading (spread stays ~31), moving the UO light left, right or above (34-36 and a darker robe): the UO light sits almost on the camera axis, so thin arms get flat shading.

## 5. Cutting

- **Hidden by the body:** a clothing layer contains only what the body does not hide. With `EXACT_BODY = True` the cut follows the original outline; the 3D model only decides what is in front of or behind the body, so the item fits the original body to the pixel.
- **Horse:** in mounted actions the horse hides the item exactly along the outline from its frames.
- **UO look:** black under edges, 0/1 transparency (no semi-transparency), dark 1-px outline (`OUTLINE`).
- **Cropping:** the `.vd` stores every frame cropped with its anchor; the PNGs keep the full canvas so frames line up (`vdtool extract --raw` gives cropped PNGs).
- **`LAYER = "body"`:** `EXACT_BODY = True` = identical to the original; `False` = the pure 3D model (~98% agreement).

## 6. The `vdtool` tool

`vdtool/vdtool.py` (Python 3.8+, `pip install pillow numpy`; messages in Polish) unpacks a `.vd` into PNGs and packs them back in the same order; unpack + pack without changes gives a byte-identical file.

```bash
python vdtool.py info    file.vd                   # type, actions, frame counts
python vdtool.py extract file.vd work              # -> work/meta.json + work/frames/NN_action/dirK/NN.png
python vdtool.py extract file.vd work --raw        # frames cropped to their content
python vdtool.py pack    work new.vd               # PNG + meta.json -> .vd
python vdtool.py verify  file.vd new.vd            # what changed
python mul2vd.py anim.idx anim.mul out 701 468     # client animations (e.g. hair 701, cloak 468) -> .vd
```

- **Canvas mode (default):** all frames have one size and the anchor of `meta.json`; packing crops each frame. Best for editing. **`--raw`:** original cropped sizes; only for retouching pixels.
- **Rules:** don't move the drawing relative to the canvas (1 px = 1 px in game); transparency is 0/1 (alpha ≥ 128 visible); one palette of 256 15-bit colours per block (more colours: median-cut reduction with a warning; pure black becomes near-black, since `0x0000` is transparent); draw hue-able parts in grey (R = G = B); frames may be added at the end or removed from the end, all 5 directions of an action should have the same count; don't rename folders or edit `meta.json`.

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

UOFiddler → **Animations → Animation Edit** → pick the animation file and the body or item ID → **Import from VD** → the `.vd` → Save. The `.vd` must have the same type as the target (human bodies and their items: type 2, people). Each item has its own animation ID.

## 8. Accuracy

- **Exact mode (`EXACT_BODY = True`):** the body layer is identical to the original (1050 frames, `vdtool verify`).
- **Pure 3D model:** mean silhouette IoU **0.899** over 1050 frames (`body_part_qa.py`, per action in `docs/qa/body_parts_after_natural_fit.json`) with no shape corrections; 2049 pixels off by ≥ 2 px (real pose errors, `pose_lib.py qa`). The differences are almost only 1-px bands along the edges (the original was drawn from another 3D model), with no large errors such as an arm in another place, so cut-outs of items hit the arm. The previous model scored 0.880 without its 1254 corrections and 0.979 with them, but items had to copy them.
- **UO items:** replicas of items from `anim.mul` on the current rig (`test_items.py`): mean IoU **0.723** (shirt 0.715, plate 0.699, trousers 0.801, boots 0.771, gloves 0.572, helmet 0.782; `docs/qa/items_after_natural_fit.json`). Weapons, robes and cloaks have their own tests (`test_weapons.py`, `test_robe.py`, `test_cloak.py`; all thresholds and last values in `docs/qa/baselines.md`).

## 9. History and tools

The body is a MakeHuman mesh (CC0, male) moved onto the UO skeleton. The UO camera and 210 poses × 5 directions were fitted to the 1050 original frames (own rasteriser + skinning like Blender's), then the mesh was fitted to the outlines of all frames, and shoulders and arms were narrowed slightly at the user's request. The UO light was derived from the frames and removed from the colour, giving the albedo. The rig was reduced to 19 UO bones, then fingers and weapon bones came back (54); arms, legs and head were refitted per frame, and finally all poses for natural motion.

The scripts that built the body (versions 1-13) were removed together with their intermediate data; they are in git history up to commit `b86c314`. The current `.blend` is the source of truth: changes are made on it (e.g. `pipeline/rig_simplify.py`) and described in the commit. Remaining input data: `pipeline/body400.vd`, `horse200.vd`, `client/`, item sprites `pipeline/body13/mul/` (from `anim.mul`). Measurements: `body_part_raster.py` + `body_part_qa.py`, `test_items.py`, `test_canvas.py`, `run_qa.py`.

## 10. Limitations and common problems

**Limitations:** muscle drawing is softer than on the sprites (the texture averages many frames); fingers and face come from MakeHuman (invisible at ~60 px); the pure model differs from the original by 1-px edge bands (~12% of silhouette pixels), which the exact modes remove; the horse is an approximate occluder, not a model for editing.

| Problem | Fix |
|---|---|
| The Text Editor is empty | Pick a text from the list in the header. If it is empty, open `UO_Body_0x190.blend` with File → Open (don't import the `.glb`/`.fbx`, don't append the body into another scene). |
| The body renders black or wrong | Enable *Auto Run Python Scripts*, reopen the file, use Cycles, check `LAYER`. |
| Exact modes change nothing | The file has no original frames: use the `.blend` from this repo or `pack_originals.py`. |
| The item cuts into the body | `uo_bind_item.py` with the right `PART`; make the item slightly larger. |
| The item stretches after an arm or leg | It has weights of bones it does not cover: `uo_bind_item.py` with the right `PART`. |
| Blender freezes while the script runs | Too many vertices: *Decimate*. |
| The item stays in place | The *Armature* modifier or weights are missing (section 3). |
| The character "jumps" in `vdtool` | The drawing moved relative to the anchor. |
| Jagged edges after import | Semi-transparent pixels: alpha 0 or 255. |
| UOFiddler rejects the file | Different animation type than the target (human bodies: type 2). |
| Rendering takes long | Test with `ONLY = ["04_stand"]`, full render at the end. |

## 11. Notes for AI assistants

```
PURPOSE    : 3D model of UO body 0x190 (male, naked) rebuilt from anim1_0x0190.vd; authors clothing layers (.vd).
VD FORMAT  : section 6. Colour 0x0000 = transparent (remap real black to 1).
SPACE      : metres, Z up, character faces -Y, floor z = 0, UO anchor = world (0, 0, 0.07).
CAMERA     : "UO_Camera", orthographic, elevation 28.45 deg, 36 px/m, 136x120 px, anchor on pixel (68, 86), +0.5 px in x.
DIRECTIONS : UO_Rig["uo_direction"] = d (0..4) rotates the rig by -45 deg * d; 0 = facing camera, 2 = profile facing
             left, 4 = facing away; 5..7 are mirrors of 3..1 made by the client.
RIG        : 54 bones (section 2). Quaternion rotations, MakeHuman weights. Per-frame girth = pose-bone scale (x, 1, z) on
             upper_arm, forearm, hand, thigh, shin, foot, head; forearm/hand/shin/foot have Inherit Scale = None.
ACTIONS    : 35 Blender actions "NN_name", props uo_action (0..34), uo_frames; UO frame i -> scene frame 1 + 3*i;
             every action keys UO_Rig["uo_action_id"].
BODY       : UO_Body = MakeHuman mesh (13380 verts, UVs), no shape keys.
ITEMS      : text "uo_bind_item.py" (PART preset -> allowed bones): nearest skin point restricted to body triangles whose
             dominant bone is allowed; MAP "under": skin hit along the item vertex normal (else nearest); weights = body
             weights there (allowed bones, renormalised), SMOOTH passes of neighbour averaging. RIGID presets (hair, beard, hat,
             weapon, shield, bow, crossbow, quiver): 100 % on one bone. BIND FOLD: PARTS[...][1] = share of a limb bone's weight
             kept, the rest goes to the parent bone (hand>forearm>upper_arm>chest, foot>shin>thigh>pelvis, head>neck); a tuple
             (share, t0, t1) ramps along the bone.
HOLDOUT    : clothing layer = Cycles render without the body; own z-buffer raster of body and items; the body hides a pixel
             where depth_body < depth_item - HOLDOUT_MARGIN (0.01 m), using only body triangles whose dominant bone is in
             OCCLUDERS (no torso); transparent patches <= FILL_HOLES px surrounded by the item are filled; 8-connected pieces
             < MIN_PIECE px other than the biggest are cleared after the UO post-process.
BODY GAP   : per UO frame the posed bound items are pushed BODY_GAP out of the posed OCCLUDERS triangles (BVH nearest, 12 rounds,
             smoothed over item edges) via shape key 'uo_fix' with the Armature modifier off; removed after the run (also on STOP).
LOOSE CLOTH: items with property uo_cloth: leg push (cloth_lib.hull_push) + cloth_sim.npz from uo_cloth_sim.py (Blender cloth, pin to
             the kinematic target, collision with UO_Body); the render adds the delta, then BODY_GAP.
MOUNTED    : horse = body 0xC8; rider->horse action pairing 23->0, 24->1, 25..29->2. Objects Horse_a{action}_f{frame} (holdout
             proxies, parented to UO_Rig) + text "uo_horse_masks.json" (key "action,frame,dir" -> base64(zlib(packbits(120x136 bool)))).
EXACT      : image "UO_Original_Atlas" (1050 original frames, 35 cols x 30 rows of 136x120) + text "uo_original_frames.json"
             (base64(zlib(RGBA)) per "action,frame,dir"); scene props uo_tile_col, uo_tile_row, uo_exact drive the projection.
MATERIAL   : scene["uo_look"]: 1 = albedo * (0.08 + 0.92 * max(0, N.L)), light fixed to the camera; 0 = plain PBR.
RENDERING  : text "render_uo_layer.py" (options: section 4). Cycles, items 512 adaptive samples (body 1), box filter 0.01. Post-process:
             premultiply over black, alpha threshold 0.5 -> 0/1, 1-px boundary outline (items OUTLINE_TARGET 0.38). Runs into the
             same OUT_DIR accumulate; a file named STOP cancels. Output: frames/NN_action/dirK/NN.png + meta.json + <LAYER>.vd
             (anim_type 2, anchor 68,86).
QUALITY    : exact mode: identical to the original body; pure model (bones only): mean silhouette IoU 0.899.
RULES      : never swap left/right limbs relative to the original frames; new layers keep the same 35 actions, 5 directions and
             frame counts as the body; do not redistribute UO client files or this repository's .blend.
REBUILD    : the .blend is the source of truth; build scripts are in git history (commit b86c314), see section 9.
```
