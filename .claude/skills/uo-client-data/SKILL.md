---
name: uo-client-data
description: Downloading/extracting the UO client (anim.mul, idx, tiledata), .vd files, mul2vd/vdtool, original body frames. Use when client data is needed or when unsure what may be committed.
---

- Client data is for the user's own use only (private repo). Download: `pip install gdown && mkdir -p uo_client && gdown 1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz -O uo_client/client_download` (2.6 GB; link: https://drive.google.com/file/d/1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz/view), then only the official `unrar` (RAR5): `cd uo_client && unrar x -y -idq client_download NelderimServUO/anim.idx NelderimServUO/anim.mul ...`. Do not extract the user's settings or plugins.
- `uo_client/` is in `.gitignore`; **never commit** `anim*.mul`, `*.idx`, `tiledata.mul` (GitHub 100 MB limit). Extracts go to `client/extract/`.
- `.vd`: `python vdtool/mul2vd.py anim.idx anim.mul out <id>`; to PNG: `vdtool/vdtool.py extract`.
- Nelderim-custom animations (`anim3`/`anim4`, e.g. 420, 422) are not needed; wearable animations in `anim2`/`anim4` are original game assets.
- **Keep the original body frames** (`client/body_0x190_frames/`, atlas in the `.blend`): `EXACT_BODY` and the measurements rely on them.
