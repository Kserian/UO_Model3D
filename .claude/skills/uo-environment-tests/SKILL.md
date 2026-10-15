---
name: uo-environment-tests
description: Środowisko (Python, bpy), synchronizacja skryptów z .blend, uruchamianie testów i pułapki. Użyj przed uruchomieniem pipeline/, zmianą model/*.blend lub testowaniem.
---

- `pip install numpy pillow scipy "bpy==4.2.*"` (Python 3.11; Blender zbędny). `.blend` zapisuj w bpy 4.2 (z 5.x nie otworzy się w 4.2). Potok przedmiotów działa też na bpy 5.2 (Py 3.13), ale `item.blend` z 5.2 otwiera tylko 5.x; model synchronizuj w 4.2.
- `model/UO_Body_0x190.blend` jest binarny, skrypty osadzone; źródło to `pipeline/*.py`, wgrywa je `pipeline/sync_blend_scripts.py` (`--check` = różnice). W commicie napisz, który binarny plik się zmienił; przed zmianą `model/` zrób kopię poza repo.
- Testy bez GUI: `run_render_headless.py`, `test_items.py` (~4 min), `test_canvas.py` (~2 min), `test_import_item.py`, `test_materials.py`. Opcje w nagłówkach skryptów.
- Pułapki: `pkill/pgrep -f` z wzorcem z własnej komendy zabija powłokę (użyj `ps -eo pid,args | grep "[w]zorzec"`); `BVHTree.FromObject` liczy w układzie lokalnym (`UO_Body` obracany per kierunek); `bpy.app.driver_namespace` w tle = segfault przy zamknięciu; po usunięciu grup wag renormalizuj wagi.
