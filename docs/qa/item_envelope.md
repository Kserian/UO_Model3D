# Envelope of the originals per slot (`item_envelope_qa.py`, Phase 3, measure only)

Share of an item's pixels that lie outside the union of the originals of its slot (same action / direction / frame, canvas 256x256, anchor 128,192), and outside what at least 3 originals cover. Originals = the `layer_priors.py` set. It is a measure for the human, not a trigger for a correction. Run: `python pipeline/item_envelope_qa.py uo_client/NelderimServUO <layer> --render RENDER_DIR | --vd item.vd | --anim <id> [--loo]`.

## Control 1: a real original against the OTHER originals of its layer (leave-one-out; mean over all 35 actions x 5 directions x frames per item; spread between the items of the layer)

| layer | originals | outside union: median | p90 | max | outside < 3: median | p90 |
|---|---|---|---|---|---|---|
| Shirt | 13 | 0.001 | 0.094 | 0.812 | 0.040 | 0.377 |
| InnerTorso | 26 | 0.000 | 0.015 | 0.843 | 0.011 | 0.129 |
| Pants | 30 | 0.000 | 0.022 | 0.996 | 0.010 | 0.088 |
| Shoes | 10 | 0.015 | 0.145 | 0.332 | 0.078 | 0.323 |
| Gloves | 9 | 0.050 | 0.271 | 0.956 | 0.313 | 0.681 |
| Helm | 58 | 0.000 | 0.017 | 0.702 | 0.001 | 0.081 |
| Arms | 14 | 0.002 | 0.052 | 0.812 | 0.033 | 0.127 |
| OuterTorso | 24 | 0.001 | 0.006 | 0.230 | 0.006 | 0.044 |
| Hair | 37 | 0.001 | 0.040 | 0.124 | 0.019 | 0.135 |

## Control 2: wrong slot

Shirt envelope: robe 469 0.420 / 0.609, long pants 431 0.448 / 0.764 (outside union / outside < 3). Pants envelope: shirt 434 0.722 / 0.776, robe 469 0.443 / 0.570. Right slot: 0.001-0.10 / 0.03-0.39 (shirts), 0.000 / 0.007-0.009 (pants). The measure separates a garment of the right slot from a wrong one.

## The six replicas of `test_items` (default 6 actions, 160 frames each, IoU 0.723) and the example item

| replica | layer | originals | outside union | outside < 3 | worst frame (action,dir,frame: outside union) |
|---|---|---|---|---|---|
| shirt | Shirt | 13 | 0.004 | 0.033 | 21,0,4: 0.057 |
| plate | InnerTorso | 26 | 0.008 | 0.027 | 21,0,5: 0.117 |
| pants | Pants | 30 | 0.009 | 0.016 | 21,4,2: 0.286 |
| boots | Shoes | 10 | 0.013 | 0.183 | 16,0,2: 0.068 |
| gloves | Gloves | 9 | 0.138 | 0.429 | 0,1,6: 0.459 |
| helm | Helm | 58 | 0.000 | 0.001 | 0,0,0: 0.000 |
| `model/example_clothing/Example_Shirt_layer.vd` | Shirt | 13 | 0.008 | 0.060 | 21,1,4: 0.125 |

Reading: the replicas (body shells) lie inside the union of the originals of their slot (<= 1.3 %) except the gloves (13.8 %; 9 originals, the control p90 is 27 %: the glove envelope is thin). The worst frames are mostly action 21 (die_forward), where the body is lying and few originals cover the same pixels. First values, informational; promote to a threshold only after they proved stable on foreign items (none in the repo yet: `model/items` has only the horn).
