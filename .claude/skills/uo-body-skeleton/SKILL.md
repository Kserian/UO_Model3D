---
name: uo-body-skeleton
description: Ustalone decyzje o ciele i szkielecie (kości, palce, broń, szaty/peleryna, czar akcja 17, obrót głowy, barki/ramiona, płótno). Użyj przed zmianą rigu, póz, kluczy animacji, proporcji lub dopasowania sylwetki.
---

Decyzje użytkownika; nie zmieniaj bez prośby.

- Rozwijamy UO_Model3D (nie budujemy od nowa; granica sylwetki ok. 0,88-0,90 IoU). Płótno `CANVAS` 256×256, zaczep (128,192), 36 px/m.
- **Zero korekt kształtu per klatka** (v12): ciało poprawiamy w modelu. Nie dopasowuj dalej sylwetki (granica ~0,90).
- Szkielet: 19 kości UO + 30 palców (`rig_restore_fingers.py`) + 5 kości broni/tarczy (`polearm.L`, `axe2h.L`, `bow.L`, `weapon1h.R`, `shield.L`; `rig_restore_weapons.py`, kalibracja `weapon_*.py`, `docs/qa/weapon_roll.md`). Bez skrętu, palców stóp, łańcuchów materiału. Włosy sztywne na głowie (`uo_bind_item.py`, `RIGID`). Poprzedni stan: `b86c314`.
- Szata/spódnica (`PART robe`/`skirt`): wiszą od miednicy, nogi wypychają tkaninę; symulacja tkaniny Blendera `uo_cloth_sim.py` (cel = powłoka nóg `cloth_lib.py`, bez łańcuchów kości; `docs/qa/robe_physics.md`). Peleryna `PART cloak`: pochylenie per akcja (`cloak_pitch.json`).
- Czar obszarowy (akcja 17): ręce symetryczne (lewa = odbicie prawej), tułów bez skrętu, tylko pochylenie (`arm_sym_fit.py --torso upper`, `arm_mirror_action.py`; `docs/qa/elbow_spell.md`). Wspólna poza palców (zgięcie 20-35°, skala dłoni 1,045). Nie wracaj do starej pozy.
- Ręce (i część miednicy/nóg) dopasowane z sylwetek w ~150 klatkach (`arm_joint_fit.py`, `docs/qa/arm_poses.md`); IoU ciała 0,9001 → 0,8991 po wygładzeniu głowy.
- **Obrót głowy gładki w czasie:** nie dopasowuj go do sylwetek bez członu gładkości (zygzak 10-26° skakał hełmem).
- Barki −1 cm, ramiona ×0,95; nie zwężaj dalej.
- Cień własny sprite'ów (s=0,4) odłożony; nasz render go nie ma.
