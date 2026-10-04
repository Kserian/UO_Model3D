# Peleryna (Cloak): ruch z klatek oryginału 468

Oryginalna peleryna (anim.mul, body 468, 35 akcji × 5 kierunków) nie wisi nieruchomo: w biegu **leci poziomo za plecami**, w jeździe galopem też, w chodzie i staniu wisi.
Powłoka nóg z szat (`cloth_lib.hull_push`) nic tu nie daje (IoU 0,395 -> 0,393), bo nogi prawie nie dotykają peleryny. Kluczowe jest **pochylenie peleryny do tyłu wokół linii ramion** w funkcji akcji.

## Pomiar (`pipeline/cloak_fit_frames.py`)

Replika peleryny (szeroka rura od ramion do łydek: półszerokość 0,33 m, głębokość 0,30 m, łuk ±75°, rąbek 0,30 m; kształt z przeszukania siatki kilku wartości na stand, chodzie, biegu,
ataku, jeździe), ułożona z szkieletu (`pose_capture.py`), zgięta wokół ramion: kąt `phi0` na ramionach i `phi1` na rąbku (tył = +, środek peleryny jest całką kąta, więc tkanina się wygina, nie obraca jak deska).
Dla **każdej klatki każdej akcji** szukamy (`phi0`, `phi1`) o największym IoU z duszkiem 468 poza sylwetką ciała, po wszystkich 5 kierunkach naraz (kąt nie zależy od kierunku).

| akcja | zmiana względem stand: ramiona / rąbek (stopnie) |
|---|---|
| stand (punkt odniesienia: 20° / 0°) | 0 / 0 |
| walk | 0 / −10…−2 (rąbek odrobinę do przodu) |
| run | +35…+68 / +25…+55 (leci za plecami; fala w rytmie kroku) |
| mounted walk / run | +52…+65 / +2…+8 / +25…+38 |
| atak 1H | 0…+15 / 0…+8 |
| czar | −8…+20 / −10…+5 |
| upadek | +10…+28 / −10…+25 |
| get hit | +12…+38 / +10…+18 |

IoU na klatkę (średnia po 35 akcjach): z najlepszym kątem 0,604; stała pozycja stand daje 0,396 (bieg 0,17, jazda 0,2).
Tabela jest wygładzona (3 klatki) i zapisana w `pipeline/cloak_pitch.json` (osadzona w `.blend`). Jest **względna do stand**: przedmiot z własnym kształtem spoczynkowym (wiszący inaczej niż replika) dostaje tylko zmianę.

## Wdrożenie

`PART cloak` w `uo_bind_item.py` (wagi jak szata: wisi od klatki piersiowej, reszta za miednicą) + `uo_cloth` typu `cloak` (linia ramion = góra przedmiotu, wysokość rąbka).
`render_uo_layer.py` (`cloth_push`, stała `CLOAK_SWING`, 0 = bez ruchu) zgina siatkę wg tabeli dla akcji i klatki (`cloth_lib.cloak_bend`), potem zwykłe wypchnięcie z ciała (`BODY_GAP`).
Slot `cloak` w `uo_prepare_item.py` / `uo_make_item.py` (`"kind": "cloak"`): autodopasowanie z krawędzią górną na 1,52 m (na duszku góra wygląda na 1,6, bo tył jest rzutowany wyżej).

## Test (`pipeline/test_cloak.py`, w `run_qa.py`)

Replika peleryny z `cloak_fit_frames.bent_cape` związana `PART cloak`, pełny render, IoU sylwetki z duszkiem 468 (230 klatek):

| | bez ruchu (`CLOAK_SWING=0`) | z tabelą |
|---|---|---|
| wszystkie | 0,376 | **0,507** |
| stand / walk | 0,56 / 0,54 | 0,56 / 0,54 |
| run | 0,21 | **0,49** |
| mounted run | 0,18 | **0,51** |
| atak / czar / upadek | 0,45 / 0,47 / 0,32 | 0,50 / 0,53 / 0,43 |

## Czego nie ma

Falowania boków (tkanina nie jest sztywną rurą), bezwładności między klatkami (tabela jest funkcją akcji i klatki), kaptura. Jedna oryginalna peleryna (468): nie wiadomo, czy inne mają inny trzepot.
Nie sprawdzone na prawdziwym darmowym modelu peleryny (test na replice i na syntetycznej pelerynie z glb).
