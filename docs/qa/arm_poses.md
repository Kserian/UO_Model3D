# Ułożenie rąk poza czarem obszarowym: śmierć (21, 22), ataki (9, 14, 18), blok (30); 2026-10-09

Zgłoszenie użytkownika: złe ułożenie rąk w akcji 17 (naprawione wcześniej, `elbow_spell.md`) i w „śmierci do tyłu”, trzeba przejrzeć inne akcje (ręce, barki, ciało).
Uwaga o nazwach: w kliencie akcja 21 to „Die Backward” (postać pada na plecy), 22 to „Die Forward” (pada twarzą w dół); w `meta.json` i w `.blend` nazwy są zamienione (`21_die_forward`, `22_die_backward`).
Wzorzec: oryginalne klatki body 400 (`client/body_0x190_frames`), 5 kierunków naraz.

## Pomiar: gdzie są ręce źle
Nowe narzędzia (nie zmieniają `.blend`):
- `pipeline/action_overlay.py` — arkusz nakładek model / sprite jednej akcji (szary = oba, zielony = tylko sprite, czerwony = tylko model),
- `pipeline/arm_mismatch.py` — ranking klatek wg pikseli niezgodnych w okolicy ręki (piksele modelu z częścią `upper_arm`/`forearm`/`hand`/`clavicle` poza sprite'em + piksele sprite'a najbliższe części ręki),
- `pipeline/iou_action.py` — IoU sylwetki per klatka akcji.
Przed zmianą (średnia niezgodność ręki 163,8 px na klatkę): najgorsze 21 kl. 5 (406 px), 21 kl. 4 (402), 17 kl. 3-5 (373 / 340 / 314), 29 (jazda; część niezgodności to maska konia), 9 kl. 1 i 6, 22 kl. 2-5, 18 kl. 5.
Akcja 21 klatki 4-5 (oglądane nakładki 5 kierunków): prawe przedramię model unosi pionowo w górę (czerwony słupek poza sprite'em w 4 z 5 kierunków), oryginał ma rękę rozłożoną przy ciele; łokieć R 97° / 92° przy lewej ręce prostej (4° / 15°), IoU klatek 0,803 / 0,805 (akcja 0,8516).
Poprzednia notatka sesji 19 („oryginał ma ręce płasko na ziemi”) była nieprecyzyjna: w sprite'ach klatki 4 ręce są wzniesione bokiem (d2, d3), więc to nie sama pozycja, tylko długość / kierunek przedramienia.

## Metoda: `pipeline/arm_joint_fit.py`
Dotychczasowe `arm_grid.py` / `arm_refit.py` dopasowywały jedną rękę przy drugiej złej, a `arm_sym_fit.py` wymusza symetrię (dobrą w czarze, złą w upadku: odbicie lewej ręki akcji 21 na prawą daje koszt 1,244 wobec 1,197 klucza).
`arm_joint_fit.py`: obie ręce niezależnie (obojczyk, ramię, przedramię = zawias + skręt, dłoń: 11 parametrów na rękę), opcjonalnie wolny obrót kręgosłupa i klatki piersiowej (`--torso 1`, kara 0,05), limit zgięcia łokcia (`--flex`, tu 130°),
cel jak w `arm_sym_fit.py` (1 − IoU całości + 1 − IoU nad linią barków, średnia z 5 kierunków), kary za odejście od klucza; starty: klucz, 3 zgięcia, losowe kierunki; najpierw każda strona osobno, potem wspólne dopracowanie 2×2 najlepszych par (Powell). Klatka na raz, ok. 15-30 min na rdzeń.
Zapis: `arm_sym_fit.py --apply` (te same klucze `rotation_quaternion`; zapis `bpy 4.2`).
Wynik dla klatki jest wdrażany tylko, gdy IoU sylwetki w tej klatce nie spadło (klatka 1 akcji 21: koszt 0,786 -> 0,709, ale IoU 0,844 -> 0,833, więc **zostawiona stara**).

## Wdrożone (klucze w `model/UO_Body_0x190.blend`)
| akcja | klatki | IoU akcji przed -> po | uwagi |
|---|---|---|---|
| 21 (pada na plecy) | 2, 3, 4, 5 | 0,8516 -> **0,8633** | kl. 4 samo ręce (łokieć R 97 -> 88°), kl. 2, 3, 5 z kręgosłupem / klatką; kl. 5: łokieć R 124° |
| 22 (pada na twarz) | 1-5 | 0,8578 -> **0,8686** | wszystkie klatki lepsze |
| 9 (cięcie 1H) | 1, 4, 5, 6 | 0,8762 -> **0,8843** | |
| 18 (łuk) | 4, 5 | 0,8893 -> **0,8939** | |
| 14 (pchnięcie 2H) | 6 | 0,8887 -> **0,8896** | |
| 30 (blok) | 3 | 0,8952 -> **0,8974** | |
Sylwetka ciała 1050 klatek: 0,8922 -> **0,8934** (`body_parts_after_arms.json`); pozostałe akcje bez zmian co do liczby (porównanie krzywych per akcja). Ruch dłoni między klatkami (krok nadgarstka) bez nowych skoków (akcja 21 prawa ręka kl. 3->4: 0,79 -> 0,42 m, 22 i pozostałe zmiany ≤ 0,15 m różnicy).
Nie ruszone: akcja 17 (symetria rąk to decyzja użytkownika, kl. 3-5 nadal mają 314-373 px niezgodności ręki), jazda (23-29: dopasowanie nie zna maski konia, niezgodność to w dużej części koń).

## Czego sylwetka nie rozstrzyga
Przy leżącej postaci zgięcie łokcia i kierunek przedramienia w kierunku patrzenia są niejednoznaczne; dopasowania dają zysk 0,01-0,03 IoU na klatkę, nie rozwiązanie „idealne” (kl. 4 akcji 21 nadal ma 299 px niezgodności ręki, kl. 5 265 px). Jeśli użytkownik widzi w konkretnej klatce i kierunku inne ułożenie, trzeba je ustawić ręcznie wg tej klatki (narzędzia: `action_overlay.py`, `arm_joint_fit.py --frame`).

## Runda 2 (2026-10-10, prośba użytkownika: „model ma się pokrywać idealnie”)
Najpierw sprawdzona skala (1050 klatek, skalowanie maski modelu wokół zaczepu): obecny model 0,894; ×0,98 / ×1,02 0,862 / 0,872; sama szerokość ×0,97 / ×1,03 0,890 / 0,891; sama wysokość ×0,98 / ×1,02 0,862 / 0,872; najlepsza skala per klatka 0,895. Powierzchnia modelu / sprite'a 1,004. **Skala jest optymalna, przeskalowanie pogarsza.**
Skąd niezgodności: 90,7% pikseli różnicy leży 1 px od krawędzi drugiej sylwetki (obwódka innego renderera, 1 px = 2,8 cm), 7,6% 2 px, 1,6% dalej; po pominięciu obwódki 1 px IoU = 0,990. Prawdziwe błędy pozy (≥ 2 px): 3746 px w 1050 klatkach, w 34 klatkach ≥ 40 px (suma 5 kierunków), głównie ręce (dłoń / przedramię / ramię 2656 z 3746), w jeździe (23-29) ok. 40%.
Zmiany w `arm_joint_fit.py`: maska konia w koszcie (jazda), `TOP_W`, `EDGE_W` (kara za piksele ≥ 2 px), powrót do klucza gdy żaden start nie jest lepszy (wcześniej `x = 0` prostował przedramię).
Kryterium wgrania klatki: IoU klatki rośnie **i** liczba pikseli ≥ 2 px nie rośnie. Akcja 17 pominięta (symetria rąk, decyzja użytkownika).
Wynik: 31 klatek dopasowanych, 23 wgrane (9 kl. 2, 6; 14 kl. 4, 6; 16 kl. 4; 18 kl. 2; 21 kl. 5; 22 kl. 4; 23 kl. 0, 2; 24 kl. 1-4; 26 kl. 0, 3; 28 kl. 1, 6; 29 kl. 0-3; 34 kl. 0), odrzucone 9/5, 18/5, 21/1, 21/4, 23/3.
Najwięcej: 9/2 błędy ≥ 2 px 43 -> 5, 16/4 43 -> 6, 18/2 46 -> 13, 23/2 42 -> 13, 28/1 42 -> 11, 34/0 59 -> 23, 29/1 167 -> 95.
Ciało 1050 klatek IoU 0,8934 -> **0,8947**, błędy ≥ 2 px 3746 -> **3282**; akcje: 29 0,8194 -> 0,8295, 26 0,8564 -> 0,8647, 23 0,8577 -> 0,8644, 24 0,8587 -> 0,8648, 34 0,9079 -> 0,9122, 9 0,8843 -> 0,8875 (`body_parts_after_arms2.json`); `test_items` 0,720 (`items_after_arms2.json`), `test_canvas` 16/16 OK.
Dalej: runda 3 z `EDGE_W = 1`, zgięcie łokcia do 145°, na 34 klatkach z ≥ 30 px błędu.
