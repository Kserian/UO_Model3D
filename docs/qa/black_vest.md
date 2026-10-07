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
| Autodopasowanie wzięło plik za metry i przeskalowało kamizelkę do wysokości 1,2 m (do ud), z „skrzydłami” na ramionach (otwory na ręce mniejsze niż nasze ramiona, fit wypychał brzegi) | `ITEM_QA`: średnio 3,3% wierzchołków w ciele, 12 cm głęboko, odstęp p90 10 cm | `stretch_glb.py`: skala 0,3 do metrów i nierówne rozciągnięcie szerokość x0,8, głębokość x1,25, wysokość x0,77 (kamizelka z manekina była szersza i płytsza niż tułów: tułów ciała 0,36 x 0,28 m, kamizelka po skali do 0,55 x 0,22) |
| Wiązanie `chest` ciągnęło boki z ramieniem | skóra tułowia w kamizelce | `prepare.PART = "torso"` (pelvis, spine, chest, neck) |
| Ramiona w kamizelce w pozach animacji | w kończynach 3-5% wierzchołków, do 8 cm | `pose_clear` (ramiona + tułów, 9 akcji, 3 rundy, `GAP` 12 mm, `CAP` 5 cm); kończyny dodatkowo wypycha render (`BODY_GAP`) |
| Poza inna niż spoczynek: skóra tułowia (pierś, brzuch) w kamizelce mimo „inside 0” w pozie spoczynkowej | 4% wierzchołków w tułowiu we wszystkich akcjach, do 56 mm | odstęp od skóry 35 mm zamiast 20 (`MIN_GAP`, `GAP` w `tune`): 0,4-1,0% i do 35-50 mm; 5 cm dawało prawie 0, ale kamizelka jest wtedy za gruba |
| Czubki kołnierza i paski nad barkiem (czarne „rogi”, uderzały w żuchwę) | wierzchołki z > 1,6 m w głowie | `move` -8,5 cm i `cut_above` 1,60 m (nowa opcja części przepisu) |
| **Tylny panel widać przez dekolt V** (warstwa przedmiotu idzie na oryginalne ciało, tułów niczego nie zasłania) | skóra w obrębie kamizelki na klatkach (ciało „all” jasne, kamizelka ciemna): **5,6% pikseli** | `behind_torso` (nowa opcja części przepisu, ta sama co dla pasa): tułów zasłania to, co jest >= 12 cm za nim: **1,22%** |

## Wynik (pełny `.vd`, 35 akcji x 5 kierunków = 1050 klatek, 517 KB; w repo go nie ma)
- Skóra widoczna w obrębie kamizelki (`skinshow`: piksel ciała jaśniejszy niż 95 tam, gdzie warstwa przedmiotu ma kamizelkę, a kamizelka jest ciemna): **1,32% pikseli ogółem**, najgorsze akcje: 29_mounted_attack_2h 2,33%, 17_spell_area 2,24%, 22_die_backward 2,11%; reszta to pojedyncze piksele przy krawędzi ramienia.
- `ITEM_QA` (siatka, poza renderem): średnio 1,9% wierzchołków w ciele, najgłębiej 76 mm (czar). Tułów: 0,4-1,0% wierzchołków, do 35 mm (atak 50 mm); kończyny: 0,5-1,3%, wypycha je render.
- Grubość: p50 3,9 cm, p90 8,3 cm (oryginalna koszula 3,9, płytówka 5,6): p90 to czubki pasków na barkach i szeroki dół; dekolt V odsłania ciało tak jak w modelu.
- Sprawdzone: żadna z 1050 klatek nie jest pusta ani nie dotyka krawędzi płótna.

## Nowe w narzędziach
`pipeline/stretch_glb.py` (skala i rozciąganie pliku), `uo_import_item.py` `STRETCH` (recepta jednej siatki: `"stretch": [sx, sy, sz]`), opcje części w `uo_make_item.py`: `cut_above`, `behind_torso`; `uo_pose_clear.py`: `AVOID` może być listą (z przepisu), a lista części do omijania obejmuje tułów.
Wniosek ogólny: **pas, kamizelka i każda odzież obejmująca tułów** (pierścień, V-dekolt) potrzebuje `uo_behind_torso`, inaczej klient rysuje tylny panel na piersi.

## Otwarte
- Czubki pasków na barkach nadal lekko sterczą ponad linię barku w kilku klatkach (tułów w pozie ma inną linię barku niż model).
- Resztki skóry przy krawędzi ramienia (1-2% pikseli) i do 5 cm w tułowiu w ataku/czarze na kilku wierzchołkach.
- Dekolt V i brak rękawów: skóra jest tam odsłonięta zgodnie z modelem, nie jest błędem.
