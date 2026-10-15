---
name: uo-projekt-zasady
description: Cel nadrzędny, język, commity, praca na main i spis dokumentacji projektu UO_Model3D. Wczytaj na początku każdej sesji w tym repo, przed commitem/pushem lub gdy trzeba ocenić zmianę względem celu.
---

# UO_Model3D: zasady ogólne

Model 3D ciała Ultima Online (body 0x190) do generowania animacji ubrań, zbroi i broni jako plików `.vd`.

**Cel nadrzędny:** nasze body ma odwzorowywać body z UO tak, żeby przedmioty zrobione na naszym modelu pasowały na oryginalny model UO. Oceniaj tym każdą zmianę.

## Praca
- Rozmowa po polsku. Commity po angielsku: `UOModel3D: <co i po co>`. Użytkownik prosi o krótkie komunikaty: wynik, blokada, decyzja.
- Pracujemy na `main`. Wszystko przetestowane i działające wrzucaj na `main` (`git push origin main`) bez dopytywania; nietestowanego nie wrzucaj.
  Jeśli zadanie sesji narzuca inną gałąź, wypchnij na nią, a po przetestowaniu także `git push origin HEAD:main`. Pull requesta nie twórz bez prośby.
  **Nie wypychaj na gałąź `claude/friendly-knuth-44xtfw`** (kopia zapasowa stanu `ea55c0b`).
- **Mierz, nie ufaj.** Liczby, na których opierasz decyzję, mają pochodzić z własnego pomiaru na plikach (przed i po zmianie). Główna miara celu:
  `pipeline/test_items.py` (przedmiot na naszym ciele vs oryginalny sprite; baseline w `docs/qa/items_after_fingers.json`: średnia 0,718),
  sylwetka ciała: `body_part_raster.py` + `body_part_qa.py` (IoU 0,892 na 1050 klatkach).
- Gotowe sketche użytkownika do testów leżą poza repo (licencje nieznane); nie commituj ich ani wyników renderu bez zgody.

## Dokumentacja
- `README.md` (PL), `README_EN.md` (EN).
- Raport z analizy: `docs/RAPORT_model3D_UO.txt`; audyt: `docs/AUDYT_2026-10-03.md`.
- Pomiary w `docs/qa/`: autodopasowanie `autofit.md`, szaty i spódnice `robe_physics.md`, broń z darmowych modeli `weapons_free_models.md`, koszula jako powłoka ciała `jedi_tunic.md`, cep z łańcuchem `flail.md`, podarta szata z dziurami `robe_ragged.md`, suknia balowa z Meshy `dress_meshy.md`, jakość tekstur w renderze `render_quality.md`.
- Przekazanie między sesjami: `docs/PRZEKAZANIE.md` (co zrobiono, zmierzono, odrzucono, co dalej); poza tym stan jest w kodzie, w `docs/` i w historii gita.

## Gdzie są zasady
Zasady i decyzje są w skillach `.claude/skills/uo-*` (po usunięciu CLAUDE.md). Jeśli je zmieniasz, popraw odpowiedni skill:
- `uo-srodowisko-testy` (środowisko, testy, pułapki), `uo-klient-dane` (klient UO),
- `uo-ciało-szkielet` (decyzje o ciele i szkielecie), `uo-przedmioty-render` (przedmioty, render, światło),
- `uo-otwarte-zakazy` (otwarte zagadnienia i czego nie robić).
