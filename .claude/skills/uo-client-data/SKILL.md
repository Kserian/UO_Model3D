---
name: uo-client-data
description: Pobieranie/rozpakowanie klienta UO (anim.mul, idx, tiledata), pliki .vd, mul2vd/vdtool, oryginalne klatki ciała. Użyj, gdy potrzebne są dane klienta lub pytanie, co wolno commitować.
---

- Dane tylko do użytku własnego (repo prywatne). Klient: `pip install gdown && mkdir -p uo_client && gdown 1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz -O uo_client/client_download` (2,6 GB; link: https://drive.google.com/file/d/1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz/view), potem tylko oficjalny `unrar` (RAR5): `cd uo_client && unrar x -y -idq client_download NelderimServUO/anim.idx NelderimServUO/anim.mul ...`. Nie wypakowuj ustawień ani wtyczek użytkownika.
- `uo_client/` jest w `.gitignore`; **nie commituj** `anim*.mul`, `*.idx`, `tiledata.mul` (limit 100 MB). Wyciągi: `client/extract/`.
- `.vd`: `python vdtool/mul2vd.py anim.idx anim.mul wyjscie <id>`; do PNG: `vdtool/vdtool.py extract`.
- Animacje Nelderim (`anim3`/`anim4`, np. 420, 422) zbędne; ubieralne w `anim2`/`anim4` to oryginały gry.
- **Nie usuwaj oryginalnych klatek ciała** (`client/body_0x190_frames/`, atlas w `.blend`): opiera się na nich `EXACT_BODY` i pomiary.
