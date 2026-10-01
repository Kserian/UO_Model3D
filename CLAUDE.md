# UO_Model3D

Model 3D ciała Ultima Online (body 0x190) do generowania animacji ubrań, zbroi i broni jako plików `.vd`.

**Cel nadrzędny:** nasze body ma odwzorowywać body z UO tak, żeby przedmioty zrobione na naszym modelu pasowały na oryginalny model UO.
Oceniaj tym każdą zmianę.

**Na początku każdej sesji przeczytaj `SESSION_HANDOFF.md`**: zawiera zasady pracy, decyzje, stan prac i następne kroki.
**Na końcu sesji zaktualizuj `SESSION_HANDOFF.md`** (sekcje: decyzje, plan i status, dziennik, następne kroki, pytania otwarte),
zrób commit i `git push origin main`. Bez tego następna sesja zaczyna w ciemno. Jeśli zmieniłeś zasady pracy, popraw też ten plik.

- Rozmowa po polsku. Commity po angielsku: `UOModel3D: <co i po co>`.
- Pracujemy na `main`. Wszystko przetestowane i działające wrzucaj na `main` (`git push origin main`) bez dopytywania; nietestowanego nie wrzucaj. Nie wypychaj na gałąź `claude/friendly-knuth-44xtfw` (kopia zapasowa stanu `ea55c0b`).
- Dokumentacja użytkownika: `README.md` (PL), `README_EN.md` (EN). Raport z analizy: `docs/RAPORT_model3D_UO.txt`.
