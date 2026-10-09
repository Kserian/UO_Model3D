# Łokieć w czarze obszarowym (17_spell_area): pomiar, 2026-10-09

Zgłoszenie: przy czarowaniu, gdy postać unosi ręce, jedna ręka jest zgięta w łokciu nienaturalnie w dół. Wzorzec: oryginalne body 400 (`client/body_0x190_frames`, plik użytkownika `anim_0400.vd` jest z nim identyczny, 0 różnych klatek z 1050).

## Co jest
Kąt łokcia z kości (`upper_arm`/`forearm`, pozy wszystkich 35 akcji):
- `17_spell_area`, **lewa ręka**, klatki 0-4: **149 / 163 / 162 / 160 / 156°** (anatomicznie max ok. 145°). Klatka 2: bark z = 1,56 m, łokieć 1,80 m, nadgarstek **1,48 m**: ramię prosto w górę, przedramię złożone prosto w dół wzdłuż ramienia. Prawa ręka w tych samych klatkach: 45-70°, przedramię w górę (nadgarstek 1,81 m).
- Lewy bark jest też o 17 cm wyżej niż prawy (obojczyk podciągnięty), skręt tułowia kompensuje błąd ręki.
- Pojedyncze klatki z łokciem >160° poza czarem: `26_mounted_attack_1h` klatka 0 (prawa 162°), `29_mounted_attack_2h` klatka 1 (lewa 161°). Reszta ≤145°.
- Sylwetka vs oryginał (IoU, 5 kierunków): 16_spell_directed 0,86-0,93; 17_spell_area klatki 1-4 **0,79-0,84** (najgorsze w całym ciele). W nakładkach brakuje zaciśniętych pięści (czerwone plamy na końcach rąk) i dłoń lewej ręki wisi poniżej łokcia, tam gdzie oryginał ma pięść w górze (kierunki 1 i 3).

## Dlaczego tak wyszło
Sylwetka z jednej strony nie wyznacza zgięcia łokcia (raport, pkt „6 póz: łokcie i kolana różnią się o ok. 6 px”): złożone przedramię i wyprostowane w górę dają prawie tę samą sylwetkę przy rzucie z boku, a stare dopasowanie miało limit obrotów i wpadło w ten minimalnie lepszy lokalny kształt.

## Próby naprawy (nie wdrożone)
Narzędzia: `pipeline/arm_refit.py` (lokalne, losowe starty), `pipeline/arm_grid.py` (cała sfera kierunków ramienia × obrót × zgięcie 20-120°, potem dopracowanie). Cel: 1 − IoU sylwetki modelu vs sprite, 5 kierunków naraz, podwójna waga nad barkiem.

| klatka | koszt stary (łokieć ok. 160°) | koszt nowy, łokieć ≤120° | łokieć nowy |
|---|---|---|---|
| 1 | 0,381 | 0,357 | 64° |
| 2 | 0,363 | 0,368 | 104° |
| 3 | 0,407 | 0,414 | 111° |
| 4 | 0,391 | 0,354 | 74° |

Wniosek: **sylwetki akceptują łokieć anatomiczny tak samo dobrze jak złożony** (różnica ±0,006, w 2 klatkach lepiej), czyli złożony łokieć jest błędem dopasowania, nie wiedzą z oryginału. Ale same sylwetki nie wybierają sensownego rozwiązania: w klatkach 1-2 najlepsze „anatomiczne” przedramię zawija się nad głową w widoku od tyłu (kierunki 3-4), więc **żadnej pozy nie wgrano do `.blend`**. Zmieniona mierzona wielkość (koszt) jest za mało czuła na to, co widać na oko.

## Co dalej (propozycja)
1. Dopasować razem obie ręce, obojczyki i skręt tułowia (nie samą lewą rękę), z priorytetem symetrii z prawą ręką (w kierunku 0 oryginał jest prawie symetryczny) i cap łokcia 120°.
2. Dopiero po tym wymienić klucze akcji 17 (klatki 0-4) i 26/29 i zmierzyć `body_part_qa.py` (IoU 0,892 na 1050 klatkach nie może spaść) oraz `test_items.py` (0,718).
