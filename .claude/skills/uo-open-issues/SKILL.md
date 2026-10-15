---
name: uo-open-issues
description: Otwarte zagadnienia UO_Model3D (sloty, szata, peleryna, naramienniki, body 401, glb/fbx) i czego NIE robić. Użyj przy planowaniu pracy lub gdy nie wiesz, czy zmiana jest dozwolona.
---

**Nie rób:** korekt per klatka, dalszego strojenia replik `test_items`, dalszego dopasowywania sylwetki ciała, zmian kierunku/ambientu światła, AO i cienia na ziemi.

**Otwarte:**
- Fizyka szat skalibrowana na jednej szacie (469), sprawdzona na 447 i 970; brak testu na kilcie. Peleryna (`docs/qa/cloak_physics.md`) bez falowania boków i testu na prawdziwym modelu.
- Sloty `waist`, `vest` bez testu na prawdziwym modelu; brakuje Earrings, Ring, Bracelet, Talisman, Backpack (wykrywanie jednostek zakłada 0,15-3 m) i jednej tabeli slotów (`docs/AUDYT_2026-10-03.md`, pkt 5-6).
- Naramienniki w jednej siatce z korpusem rozciągają się w czarach; 3-4% wierzchołków zbroi w ciele w ruchu (`item_qa.py`); zmiany wag nie pomogły.
- Pierwszy prawdziwy darmowy model (np. włosy Curuaty CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c): użytkownik sam wrzuca glTF do repo; zapisz atrybucję.
- Body 401 (kobieta) w `anim.mul` ≈ kopia męskiego; sprawdź w grze przed pracą.
- `.glb`/`.fbx` nie ma w repo: `pipeline/export.py --blend model/UO_Body_0x190.blend`.
