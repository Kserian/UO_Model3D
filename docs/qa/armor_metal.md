# Zbroja metalowa (Quaternius, „Armor Metal”) – render (sesja 18)

Model: jeden obiekt `Armor_Metal2` (352 wierzchołki po sklejeniu, 1 materiał `LightSteel`, bez UV), czyli napierśnik + dwa naramienniki-kopuły (z płetwą). Plik `.glb` od użytkownika **nie jest w repo**
(licencja do potwierdzenia; Quaternius publikuje zwykle jako CC0). Przepis: `docs/qa/armor_metal_recipe.json`.

```
python pipeline/split_model.py armor.glb armor_metal_split.glb 0=0.57,0.63,0.9      # Part0 = napierśnik, Part1/2 = naramienniki
python pipeline/uo_make_item.py docs/qa/armor_metal_recipe.json --preview            # z katalogu, w którym leży armor_metal_split.glb
```

## Co było trzeba (i dlaczego)
| Problem (pomiar) | Rozwiązanie |
|---|---|
| Model to jedna siatka, napierśnik 0,99 × 0,76 m, czyli 2× za szeroki dla ciała UO (pierwsza próba: mediana odstępu 59 mm, naramienniki trzepotały jak skrzydła) | `split_model.py`: spawanie, podział na części, **nierówna skala napierśnika** 0,57 × 0,63 × 0,9; autofit potem robi jedną skalę (1,06, pokrycie skóry 96 %, mediana odstępu 33 mm przy celu 30) |
| Naramienniki wiązane jak skóra (`PART chest`) rozciągały się z ramieniem | osobne części; `cup` dopasowuje kulę kopuły do barku (promień skóry wokół kości + 35 mm), fit wypycha z ciała, potem `to_bone`: **sztywno na `upper_arm`** swojej strony (kula wokół stawu nie zmienia się przy obrocie; w pierwszej wersji 80 % wierzchołków kopuły było w ramieniu, teraz 0-10 %, do 3,7 cm) |
| Napierśnik z wagami `chest` unosił bok z ramieniem (pomarańczowe plamy skóry przy czarze) | `prepare.PART = "torso"`: tylko pelvis / spine / chest / neck; kończyny wypycha render (BODY_GAP), tułów nigdy nie zasłania (zero dziur) |
| Zbyt jasny wygląd (mediana 160 wobec 68 na oryginalnym plate 527) | `BRIGHTNESS 0.42`, `SPEC_STRENGTH 6.0`, `SPEC_POWER 19`, `SATURATION 0`, `METAL true` (model ma Metallic 0,4 < próg, więc bez tego byłby matowy); wynik: mediana 84, p95 191, p99 226 (oryginał 68 / 142 / 246) |

Nowe opcje przepisu części (`uo_make_item.py`): `cup`, `to_bone`, `scale`, `on_bone`, `clear_skin` (nieużywane w końcowym przepisie), `cut_below`, `arm_share`, `tune` per część; `uo_prepare_item.py`: `PART` (waga skinu inna niż domyślna dla slotu).

## Pomiary (`item_qa.py`, `item_thickness.py`, własny podział „w tułowiu / w kończynach”)
- Napierśnik w tułowiu (skóra tułowia przebija pancerz): stand 0 %, chód 0,8 %, atak 2,7 % (do 6,6 cm), jazda w biegu 1,7 %. Tułów nie zasłania pancerza w renderze, więc nie powstają dziury.
- Napierśnik w kończynach (uda, ręce przed klatką): 3-11 %, render wypycha je z ciała (BODY_GAP); to daje postrzępiony dół zbroi na jeździe w widoku od przodu (poniżej).
- Naramienniki w ciele: stand 0 %, atak 0,6-4,5 %, czar 3-10 % (do 3,8 cm), jazda 0-0,4 %. Odstęp od skóry p90 ok. 5 cm.
- Grubość na klatkach (stand, chód, bieg): 19 % pikseli poza sylwetką ciała, p50 2,8 cm, p90 6,2 cm; oryginalny plate 527: 14 %, 2,8 / 5,6 cm. Atak i czar: p90 8,3 cm.
- `ITEM_QA`: średnio 4,6 % wierzchołków w ciele, najgłębiej 10 cm (atak), odstęp p90 ≤ 7,2 cm.

## Czego nie rozwiązano
- Jazda, widok od przodu (kierunki 0-1): dół napierśnika między udami jest postrzępiony (cienkie ciemne paski, kawałki na udach). Przyczyna: uda zasłaniają dół (holdout) i wypychają go z ciała; w grze większość tego zakryje koń. Przycięcie dołu (`cut_below` 0,78 i 0,86 m) nie usunęło pasków, więc nie jest w przepisie.
- Skóra widoczna na szyi i nad naramiennikiem (kołnierz napierśnika jest niski): jak w ciele UO bez hełmu.
- Płetwy naramienników zostały spłaszczone przez limit grubości (`LIMIT` 4 cm).
- Pełny render `.vd` (35 akcji) nie był robiony: `python pipeline/uo_make_item.py docs/qa/armor_metal_recipe.json --vd`.

## Poprawka po uwagach użytkownika („kanciasta”, „przebija ramię”) i pełny `.vd`
- **Przyczyna skóry w napierśniku:** `split_model.py` eksportował siatkę z płaskim cieniowaniem, więc każda ścianka miała własne wierzchołki; zaokrąglające zagęszczenie (`uo_densify_item.py`, `SMOOTH` > 0) rozrywało takie wyspy, a w pancerzu powstawały szczeliny. Pomiar: klatek z dziurami w pancerzu (alfa 0 otoczona pancerzem) na stand + chód: 46 z 55 przy rozerwanej siatce, po naprawie 13 z 200 (zostają ramię i ręka przed klatką piersiową, 65-78 px).
  Teraz `split_model.py` domyślnie eksportuje gładkie normalne (siatka spawana: 204 wierzchołki napierśnika zamiast 1226); `--flat` przywraca stare zachowanie.
- **Kanciastość:** `smooth_shade` (gładkie normalne po zagęszczeniu) i `uo_densify_item.py` `SMOOTH 0.7` (zaokrąglenie jak Catmull-Clark; fit wypycha z ciała to, co się zapadło). Napierśnik: krawędź 2,2 cm, 4988 wierzchołków.
- **Ramię w napierśniku:** nowy krok `uo_pose_clear.py` (opcja części `pose_clear`): ramię (łopatka, przedramię, dłoń) przeciągane przez pozy stand / chód / bieg / combat idle / advance; wierzchołek bliżej skóry ramienia niż 12 mm jest wypychany po normalnej ramienia, a przesunięcie wraca do pozy spoczynkowej przez odwrotność macierzy skinningu wierzchołka (max 3 cm, wygładzone, 2 rundy), potem ponowne `uo_bind_item.py`. Pozy z ramieniem skrzyżowanym przez korpus (atak, czar) zostawione rendererowi (BODY_GAP).
  Napierśnik w kończynach: stand 2,9 → 1,2 %, chód 7,8 → 4,5 %, atak 6,0 → 6,0 %, czar 3,7 → 3,1 %, jazda w biegu 10,6 → 8,2 %. Naramienniki: w tułowiu i kończynach 0-5 %, do 3 cm (czar).
- Pełny `.vd`: 35 akcji × 5 kierunków = 1050 klatek, 724 KB, 6 minut (`uo_make_item.py docs/qa/armor_metal_recipe.json --vd`). Plik nie jest w repo (jak model).
- Odrzucone: wydłużony margines zasłaniania przez ciało (`HOLDOUT_MARGIN` 0,03 / 0,05) i `BODY_GAP` 0,02: bez wpływu na dziury (przyczyną były szczeliny siatki, nie zasłanianie).
