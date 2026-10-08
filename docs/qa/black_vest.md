# Czarna kamizelka garniturowa (darmowy model, slot `vest` / MiddleTorso)

Model: „Black Suit Vest” (prestonboy132, https://sketchfab.com/3d-models/black-suit-vest-cbc97be2ca064abfb190b8090b37d233), **CC BY 4.0**. Plik `.glb` (2,2 MB) nie jest w repo.
Jedna siatka (11 331 wierzchołków, 1 materiał, tekstura), rozmiar w jednostkach pliku 1,61 x 0,70 x 1,99 (kamizelka ma ok. 0,6 m wysokości, czyli plik jest 3,3 razy za duży).

```
python -I pipeline/stretch_glb.py black_suit_vest.glb black_suit_vest_pre.glb 0.3 0.8,1.25,0.77
python pipeline/uo_make_item.py docs/qa/black_vest_recipe.json --preview          # z katalogu z black_suit_vest_pre.glb; --vd = pełny render
```

## Co było trzeba (i dlaczego), z pomiarami
| Problem | Pomiar | Rozwiązanie |
|---|---|---|
| Autodopasowanie wzięło plik za metry i przeskalowało kamizelkę do wysokości 1,2 m (do ud), z „skrzydłami” na ramionach | `ITEM_QA`: średnio 3,3% wierzchołków w ciele, 12 cm głęboko, odstęp p90 10 cm | `stretch_glb.py`: skala 0,3 do metrów i nierówne rozciągnięcie szerokość x0,8, głębokość x1,25, wysokość x0,77 (kamizelka z manekina była szersza i płytsza niż tułów: tułów ciała 0,36 x 0,28 m, kamizelka po skali do 0,55 x 0,22) |
| Wiązanie `chest` ciągnęło boki z ramieniem | skóra tułowia w kamizelce | `prepare.PART = "torso"` (pelvis, spine, chest, neck) |
| Poza inna niż spoczynek: skóra tułowia w kamizelce mimo „inside 0” w pozie spoczynkowej | 4% wierzchołków w tułowiu we wszystkich akcjach, do 56 mm | odstęp od skóry 35 mm zamiast 20 (`MIN_GAP`, `GAP` w `tune`); 5 cm dawało prawie 0, ale kamizelka jest wtedy za gruba |
| Czubki kołnierza i paski nad barkiem (czarne „rogi”) | wierzchołki z > 1,6 m uderzały w żuchwę | `move` -8,5 cm i `cut_above` 1,60 m |
| Tylny panel widać przez dekolt V (warstwa przedmiotu idzie na oryginalne ciało, tułów niczego nie zasłania) | skóra w obrębie kamizelki na klatkach: 5,6% pikseli | `behind_torso` (ta sama opcja co dla pasa): 1,2% |
| **Poszarpane krawędzie, ostre odłamki, nierówna powierzchnia** (uwaga użytkownika) | siatka w pozie spoczynkowej po `pose_clear` rozerwana na kolce przy otworach na ręce (wypchnięcia o 8-14 cm bez wygładzenia); w sprite'ach czarne kolce na ramionach i szyi | **`pose_clear` odrzucony** (ani na ramiona, ani na tułów; nawet łagodny, CAP 12 mm, SMOOTH 25, zostawia zmarszczki), `smooth_mesh` (4 przebiegi Laplace'a, brzegi i wagi bez zmian) i `no_body_gap` (renderer nie gnie kamizelki wokół ramion klatka po klatce: ramię w klatce ją zasłania) |
| (próba odrzucona) wycięcie otworów na ręce tam, gdzie ramiona przemiatają pozy | zaznaczało 49% siatki (boczne panele leżą dokładnie w strefie ramion): zostawały tylko przód i tył | usunięte z repo (`uo_arm_cut.py`); nie powtarzać |

## Wynik (pełny `.vd`, 35 akcji x 5 kierunków = 1050 klatek, 513 KB; w repo go nie ma)
- Skóra widoczna w obrębie kamizelki (piksel ciała jaśniejszy niż 95 tam, gdzie warstwa przedmiotu ma kamizelkę): **1,02% pikseli ogółem** (poprzednia wersja 1,32%), najgorsze akcje: 17_spell_area 2,08%, 29_mounted_attack_2h 2,00%, 22_die_backward 1,82%; reszta to pojedyncze piksele przy krawędzi ramienia.
- Siatka (poza renderem): tułów w kamizelce 0-0,3% wierzchołków (stand 0, chód 0,3% do 26 mm, atak 0,15% do 80 mm, czar 0,12%). **Ramiona w bocznych panelach: 16-18% wierzchołków w stand / chodzie** (do 7 cm): kamizelki nie wypychamy i nie wycinamy, bo ramię ją tam zasłania w klatce (tak jak oryginalne rękawy); to też powód, że `ITEM_QA` pokazuje teraz średnio 5,6% w ciele (wcześniej 1,9% z wypychaniem, które rwało siatkę).
- Grubość (odstęp od sylwetki ciała): **p50 2,8 cm, p90 6,2 cm** (wcześniej 3,9 / 8,3; oryginalna koszula 3,9, płytówka 5,6).
- Obrys: kolce i rogi przy szyi i ramionach zniknęły (zestawienie klatek przed / po w opisie sesji); kawałków na klatkę 1,19, drobnych pyłków (< 12 px) 0,04.
- Sprawdzone: żadna z 1050 klatek nie jest pusta ani nie dotyka krawędzi płótna.

## Nowe w narzędziach
`pipeline/stretch_glb.py` (skala i rozciąganie pliku), `uo_import_item.py` `STRETCH` (recepta jednej siatki: `"stretch": [sx, sy, sz]`), opcje części w `uo_make_item.py`: `cut_above`, `behind_torso`, `no_body_gap`, `smooth_mesh`; `uo_pose_clear.py`: `AVOID` może być listą (z przepisu).
Wniosek ogólny: **pas, kamizelka i każda odzież obejmująca tułów** (pierścień, V-dekolt) potrzebuje `uo_behind_torso`, inaczej klient rysuje tylny panel na piersi.

## Otwarte
- Drobne kępki czarnych pikseli przy barku w kilku klatkach (linia barku ciała w pozie inna niż w modelu).
- Resztki skóry przy krawędzi ramienia (ok. 1% pikseli) i na kilku wierzchołkach tułowia do 8 cm w ataku.
- Dekolt V i brak rękawów: skóra jest tam odsłonięta zgodnie z modelem, nie jest błędem.
