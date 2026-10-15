# UO_Model3D

Model 3D ciała UO (body 0x190) do animacji ubrań/zbroi/broni jako `.vd`. **Cel:** nasze body odwzorowuje body UO tak, by przedmioty z naszego modelu pasowały na oryginał. Oceniaj tym każdą zmianę.

- Rozmowa po polsku; commity po angielsku: `UOModel3D: <co i po co>`. Krótkie komunikaty: wynik, blokada, decyzja.
- Przetestowane wrzucaj na `main` bez dopytywania (`git push origin main`; przy narzuconej gałęzi sesji: na nią, potem `git push origin HEAD:main`). Nietestowanego nie wrzucaj. PR tylko na prośbę. **Nie pushuj na `claude/friendly-knuth-44xtfw`.**
- **Mierz, nie ufaj:** decyzje opieraj na własnych pomiarach przed/po. Miary: `pipeline/test_items.py` (baseline `docs/qa/items_after_fingers.json`, 0,718), `body_part_raster.py` + `body_part_qa.py` (IoU 0,892).
- Szkice użytkownika (poza repo) i wyników ich renderu nie commituj.
- Docs: `README.md`, `docs/PRZEKAZANIE.md` (stan między sesjami), `docs/qa/`. Szczegóły w skillach `.claude/skills/uo-*` (środowisko, klient, ciało, przedmioty, otwarte/zakazy); zmieniając zasady, popraw skill.
