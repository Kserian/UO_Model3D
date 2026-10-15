---
name: uo-otwarte-zakazy
description: Lista otwartych zagadnień projektu UO_Model3D (sloty, szata, peleryna, naramienniki, body 401, eksport glb/fbx) oraz czego NIE robić (korekty per klatka, strojenie replik, światło, AO). Użyj przy planowaniu następnej pracy lub gdy wahasz się, czy zmiana jest dozwolona.
---

# Czego nie robić

Korekt per klatka, dalszego strojenia replik `test_items`, dalszego dopasowywania sylwetki ciała (granica ok. 0,90), zmian kierunku/ambientu światła, AO i cienia na ziemi.

# Otwarte

- Fizyka luźnych ubrań (sesja 15) jest skalibrowana na jednej oryginalnej szacie (469) i sprawdzona na 447 i 970; prawdziwy darmowy model szaty: `docs/qa/robe_black.md` (sesja 21; symulacja z sesji 16 nie trzymała celu, naprawione), brak testu na kilcie. Peleryna: `PART cloak`, pochylenie per akcja z oryginału 468 (`docs/qa/cloak_physics.md`), bez falowania boków i bez testu na prawdziwym modelu (`docs/qa/robe_physics.md`, „Czego model nie robi").
- Sloty `waist` i `vest` (MiddleTorso) dodane z zakresów oryginałów, ustawienia przez analogię, bez testu na prawdziwym modelu; nadal brakuje Earrings, Ring, Bracelet, Talisman, Backpack (małe przedmioty: wykrywanie jednostek zakłada 0,15-3 m).
- Naramienniki jako jedna ciągła siatka z korpusem rozciągają się z ramieniem w czarach (wagi „jak skóra"); `item_qa.py` pokazuje 3-4% wierzchołków zbroi w ciele w ruchu (do 11 cm przy ataku, wypychane przez `BODY_GAP`), warianty wag (`FOLLOW` barku, `STIFF` 2) nic nie poprawiły.
- Pierwszy prawdziwy darmowy model (np. włosy Curuaty, CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c: użytkownik sam pobiera glTF i wrzuca do repo, zapisz atrybucję autora).
- Brakujące sloty (Waist, MiddleTorso, Earrings, Ring, Bracelet, Talisman, Backpack) i jedna tabela slotów: `docs/AUDYT_2026-10-03.md`, pkt 5-6.
- Body 401 (kobieta) w `anim.mul` jest prawie kopią męskiego; sprawdzić w grze przed pracą nad ciałem kobiecym.
- `.glb`/`.fbx` nie ma w repo (były nieaktualne): `pipeline/export.py --blend model/UO_Body_0x190.blend` generuje je na żądanie.
