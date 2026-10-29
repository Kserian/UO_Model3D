# Drum on a sash: paperdoll gumps and item art

Made from the 3D drum of the animation (`Drum_meshy_sash.vd`) and the ORIGINAL body sash of the client (anim 490, item 0x1541 / 0x1542), by `pipeline/uo_render_drum_gump.py`:

| File | Size | Where it goes |
|---|---|---|
| `gump_male.png` | 260 x 237 | gump 50490 (50000 + anim 490), over the body gump 12 |
| `gump_female.png` | 260 x 237 | gump 60490 (60000 + anim 490), over the body gump 13 |
| `art.png` | 45 x 32 | item art 0x1541 (5441) |
| `art_mirror.png` | 45 x 32 | item art 0x1542 (5442), the mirror (the client's sash comes as a pair) |
| `preview.png` | | the two gumps on the drawn bodies, 3x |
| `preview_art.png` | | the two arts, 8x |

**Gump.** The original sash of the client is kept pixel for pixel (it already fits the drawn bodies: from the left shoulder across the chest to the right waist, 7-9 px wide). A strap of the same grey continues from its lower end in the direction in which the sash arrives (measured on the client's gumps) to the rim of the drum, where a small brass ring sits. The drum is the 3D model (orthographic front view, 90.5 px/m like the body gump: head top y 54, feet y 221; UO light, own shadow, 4 x 4 supersampling, edge pixels x 0.5): it hangs at the right hip (the left of the picture), **lower and nearer the legs than on the animation** (there it rides on the chest), its axis tilted so that the head looks up, out and to the front, centre at gump pixel (70, 157) male / (70, 152) female (the waist of the body gump 13 is ca. 7 px higher). Brightness x 0.8, no channel above 215 (the UO light from the front lit the white head to white).
**Art.** The drum lying on the ground (the head up, towards a camera 55 degrees above the horizon, a little turned), the strap as a loop attached to its right rim like a handle; 56 px/m (the drum 23 px); the second art is the mirror.
**Colours.** The strap is grey (R = G = B) like the original sash: it takes the hue of a dye. The drum is red / cream: set the tiledata flag PartialHue (0x00040000) of the item so that only the grey pixels are dyed (`uo_hue_preview.py` shows both).
**Rebuild.** The originals: `python pipeline/uo_gump_art.py gump CLIENT_DIR 12|13|50490|60490 OUT.png` into one folder (`gump12.png`, `gump13.png`, `gump50490.png`, `gump60490.png`), then `PD_OUT=DIR PD_GUMPS=THAT_FOLDER python pipeline/run_script_in_blend.py ITEM.blend pipeline/uo_render_drum_gump.py` (ITEM.blend: the item of `drum_only.json` built by `uo_make_item.py`). Position, tilt, brightness: the settings at the top of the script. The client data are not in the repo (see the skill uo-client-data); the gump PNGs of the client are not committed.
