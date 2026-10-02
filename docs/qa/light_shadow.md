# Światło i cienie w sprite'ach UO (sesja 10)

Pomiar na oryginalnych klatkach: 880 klatek ciała 400 (akcje 0-22 i 30-34, 5 kierunków; jazda konna pominięta, bo koń zasłania ciało) i 393 animacje
ubieralne z klienta (`anim`..`anim5`, warstwy < 25). Geometria z naszego ciała 3D (IoU sylwetki ok. 0,895), więc wnioski dotyczą **postaci** oświetlenia,
nie dokładnych liczb.

Narzędzia: `pipeline/light_raster.py` (normalne, pozycje, UV, cień własny i AO na piksel), `light_data.py` (złączenie z klatkami oryginału),
`light_fit.py` (dopasowania, wynik w `light_fit.txt`), `light_items.py` (statystyka wszystkich animacji ubieralnych, wynik `client/extract/light_items.json`).
Model: `światło(piksel) = albedo[teksel UV] * S(piksel)`, albedo na teksel (96x96) wyeliminowane, `S = otoczenie + (1 - otoczenie) * max(n·L, 0)`.

## Wyniki

| Pytanie | Wynik |
|---|---|
| Domena | Światło działa w **świetle liniowym** (sRGB zdekodowane): Lambert tłumaczy 27,2% wariancji w domenie liniowej i tylko 4,4% w sRGB. Nasz potok (emisja liniowa, wyjście sRGB) jest zgodny. |
| Kierunek światła | Dopasowane swobodnie: L = (0,011; -0,787; 0,617), nasze (0,001; -0,757; 0,653): **różnica 2,9°**. Osobno na każdy kierunek postaci: x od -0,05 do +0,08, y -0,75..-0,79, z 0,62..0,66, bez trendu. **Światło jest stałe w układzie kamery**, nie obraca się z postacią (zgodnie z tym, że klient robi kierunki 5-7 lustrem 3-1). |
| Otoczenie | Nie da się go zmierzyć: 0 daje rms 0,1051, 0,0798 (nasze) 0,1048, swobodne 0,046 daje 0,1047. Zostaje 0,0798. |
| Kształt oświetlenia | Lambert wykładnik 1 jest najlepszy (0,5 → 0,1095, 2 → 0,1084 wobec 0,1048). Światło owijające (wrap), półkula (góra jaśniejsza) pogarszają. |
| Ambient occlusion | **Brak.** Stosunek oryginał/model w miejscach zamkniętych (otwartość < 0,5) 1,007, w otwartych 1,008. |
| Cień własny (promień do światła zablokowany przez ciało) | **Jest.** Piksele zacienione: stosunek 0,50 (mediana, n = 16 462) wobec 1,02 w oświetlonych. Mocno we wszystkich akcjach (mediany 0,38-0,62). Cień jest **częściowy**: najlepsze `S = otoczenie + (1 - otoczenie) * c * s` przy **s = 0,4** (rms 0,1048 → 0,1022). Dotyczy ud, goleni, miednicy, tułowia (ręka przed tułowiem, noga przed nogą). 3,3% pikseli. |
| Cień w warstwach przedmiotów | Cień ciała widać też w przedmiotach: stosunek światła w cieniu / w świetle (184 animacje przylegające) mediana **0,69**, kwartyle 0,51-0,98, 67% animacji poniżej 0,9. Sprite'y przedmiotów były więc renderowane z ciałem w scenie. |
| Metal | Krzywa światła względem n·L: tkanina/skóra (87 animacji) ≈ Lambert (1,48 na górze wobec 1,44). Przedmioty o metalowych nazwach (41): 2,03 na górze, najjaśniejsza ćwiartka (płyta, hełmy, 12) 3,13. Dopasowanie `albedo * k * c^n`: wszystkie 41 metalowych nazw k = 0,7, n = 11; najjaśniejsza ćwiartka (płyta, hełmy) k = 2,0, n = 19; tkanina k = 0,28 i niewiele lepiej niż nic. |

## Co z tego wynika dla renderu

1. **Światło i kierunek są dobre**, nic nie zmieniać. Ambient zostaje.
2. **Odblask metalu** (zrobione): `uo_materials.py` dodaje `SPEC_STRENGTH * albedo * max(n·L,0)^SPEC_POWER`, domyślnie 1,0 i 16. Stare wartości (0,5 absolutne, bez albedo) były za słabe dla płyty i za mocne dla jasnych albedo. Płyta i hełmy: 2,0 / 19, metal ogólnie (kolczuga itp.): 0,7 / 11.
3. **Cień własny nie jest odtwarzany w naszym renderze** (UO_Look to emisja, nie dostaje cieni). Efekt na ciało jest mały (rms -2,5%), na przedmioty potencjalnie większy (mediana 0,69). Zrobić go w Cycles można jako: emisja `s * c` bez cienia + diffuse od słońca `L` z cieniem `(1 - s) * c`, s = 0,4; wymaga sprawdzenia, czy ciało-holdout rzuca cień na przedmiot. Niezrobione (czeka na decyzję).
4. Brak AO i brak cienia na ziemi w sprite'ach: nie dodawać.

## Ograniczenia

- Normalne pochodzą z naszego ciała 3D (nie z oryginału), a albedo jest uśrednione w teksel 96x96: Lambert tłumaczy tylko 27% wariancji, reszta to błąd kształtu/pozy i malowane detale (dłonie rel. rms ok. 1,0). Wnioski dotyczą postaci zależności, nie ostatniej cyfry.
- Dla przedmiotów normalna ciała jest zastępnikiem normalnej przedmiotu: dobra dla koszul, spodni, butów, zbroi przylegających; zła dla luźnych (szata, płaszcz, włosy, broń, tarcza: R² ujemne). Dlatego liczby przedmiotów to mediany po setkach animacji, nie pomiar jednej.
- Flaga cienia liczona na ciele, nie na przedmiocie; pokrywa się z cieniem przedmiotu tylko tam, gdzie przedmiot przylega.
- Podział „metal / tkanina” po słowach w nazwie (plate, chain, mail, helm, bascinet, gorget, gauntlet...) jest przybliżony.
