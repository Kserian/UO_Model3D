# Jakość tekstur przedmiotów (2026-10-14)

Zgłoszenie: kolega użytkownika renderował maskę (model z WoW, tekstura 64 x 64) z własnymi ustawieniami i miał wyraźnie lepszą teksturę.
Jego zmiany w `render_uo_layer.py`: Khronos PBR Neutral zamiast Standard, 512 próbek zamiast 1, `OUTLINE` 0,9 zamiast 0,38, `DESPECKLE` / `FILL_HOLES` / `MIN_PIECE` 0
(jego shader krawędzi „VRARK edges” nie działał: podpięty do Principled BSDF, który nie trafia na wyjście materiału).

## Co która zmiana robi (pomiar na jego masce i naszym cepie)
- **1 próbka szumiała**: `UO_Look` ma część Principled (połysk metalu), Cycles próbkuje ją losowo. 512 vs 1 próbka: inne 78 % pikseli maski, 61 % cepa (bez alfy w teksturze);
  64 próbki vs 512: 2 %. Założenie „cieniowanie UO nie szumi” było prawdziwe tylko bez metalu.
- **`DESPECKLE` 28** czyścił ten szum, ale zjadał ciemne detale tekstury (17 % pikseli maski). `FILL_HOLES` / `MIN_PIECE`: 2,7 % pikseli, zostają.
- **Obwódka**: oryginały UO mają krawędź / piksel głębiej = 0,40 (ciało), 0,33-0,43 (17 przedmiotów `body13/mul`, hełm 563: 0,37). Stałe `OUTLINE` 0,38 dawało na masce 0,23
  (za ciemno, tekstura znikała), na naszym ciele 3D 0,48, cep z `uo_outline` 0,7: 0,66; u kolegi (0,9) 0,53. Stała wartość nie pasuje do wszystkich przedmiotów.
- **Khronos PBR Neutral**: inna krzywa tonów (mediana jasności maski 70 -> 52), nasze światło jest zmierzone na oryginałach przy Standard: nie przejęte.

## Wdrożone (`render_uo_layer.py`)
- `SAMPLES` 512, próbkowanie adaptacyjne z progiem 0,002 i min. 64 próbkami (filtr piksela dalej 0,01 px = środek piksela, bez rozmycia). Próg domyślny (0,01) zostawiał
  3,9 % pikseli > 2 poziomy różnicy między płótnami; 0,002: 0,47 %, jak stałe 512 (0,56 %), a od stałego 512 różni się 0,03 % pikseli; czas 17-23 s zamiast 73 s (2 akcje cepa),
  wobec 11 s przy 1 próbce. Warstwa ciała: 1 próbka (kolory z oryginałów).
- `DESPECKLE` domyślnie 0 (per przedmiot: `uo_despeckle`).
- `OUTLINE_TARGET` 0,38: dla warstwy `clothing` bez własnego `uo_outline` jedna siła obwódki na cały render, tak by krawędź / piksel głębiej = 0,38 (liczone ze wszystkich klatek,
  nakładane przed zapisem `.vd`; siła per klatka skakała do 0,17 między klatkami). Maska: 0,65 przed obwódką -> współczynnik 0,58 -> 0,38.
- Testy: `test_items` 0,722 -> 0,723 (kawałki i kolory bez zmian), `test_canvas` 16/16 (test porównuje ze starym skryptem, więc włącza w bieżącym stary wygląd: 1 próbka,
  stała obwódka, `DESPECKLE` 28). Czas renderu przedmiotu ok. 2,5 x dłuższy.
