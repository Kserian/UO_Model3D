---
name: uo-klient-dane
description: Pobieranie i rozpakowywanie klienta UO (anim.mul, anim.idx, tiledata), pliki .vd, mul2vd/vdtool, oryginalne klatki ciała w client/. Użyj, gdy potrzebne są dane z klienta, konwersja animacji lub pytanie czy coś wolno commitować.
---

# Klient UO i dane

- Dane klienta tylko do użytku własnego, repo jest prywatne. Klient (Google Drive, link publiczny): https://drive.google.com/file/d/1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz/view?usp=drive_link
  `pip install gdown && mkdir -p uo_client && gdown 1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz -O uo_client/client_download` (2,6 GB), potem tylko oficjalny `unrar` (RAR5):
  `apt-get install -y unrar && cd uo_client && unrar x -y -idq client_download NelderimServUO/anim.idx NelderimServUO/anim.mul ...`. Nie wypakowuj ustawień ani wtyczek użytkownika.
- `uo_client/` jest w `.gitignore`. **Nie commituj** surowych `anim*.mul`, `*.idx`, `tiledata.mul` (limit GitHuba 100 MB). Wyciąg potrzebnych rzeczy idzie do repo: `client/extract/` (opis w jego README).
- Pliki `.vd` pojedynczych animacji: `vdtool/mul2vd.py` (`python vdtool/mul2vd.py anim.idx anim.mul wyjscie <id>`), rozpakowanie do PNG: `vdtool/vdtool.py extract`.
- Animacje własne Nelderim (`anim3`/`anim4`, np. 420, 422) nie są potrzebne; ubieralne animacje w `anim2`/`anim4` to oryginały gry.
- **Oryginalne klatki ciała zostają** (`client/body_0x190_frames/`, atlas oryginałów w `.blend`): na nich opiera się `EXACT_BODY` i pomiary. Nie usuwaj ich.
