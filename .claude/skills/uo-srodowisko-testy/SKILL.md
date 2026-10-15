---
name: uo-srodowisko-testy
description: Instalacja środowiska (Python, bpy), synchronizacja skryptów z plikiem .blend, uruchamianie testów (test_items, test_canvas, render headless) i znane pułapki. Użyj przed uruchomieniem skryptów z pipeline/, zmianą model/*.blend lub testowaniem.
---

# Środowisko, testy, pułapki

- Python 3.11: `pip install numpy pillow scipy "bpy==4.2.*"`. Blender nie jest potrzebny, wystarczy moduł `bpy`. **Plik `.blend` zapisuj `bpy 4.2`** (zapisany w 5.x nie otworzy się w 4.2; 5.2 czyta pliki 4.2).
- Potok przedmiotów (`uo_make_item.py`, symulacja, render) działa też na `bpy 5.2` (Python 3.13: `pip install "bpy==5.2.*" numpy scipy pillow`); `item.blend` zapisany w 5.2 otwiera się tylko w 5.x, model nadal synchronizuj w 4.2.
- `model/UO_Body_0x190.blend` jest binarny, a skrypty są w nim osadzone jako teksty. Źródłem są `pipeline/*.py`; do pliku wgrywa je `pipeline/sync_blend_scripts.py` (`--check` pokazuje różnice). W commicie opisz, który plik binarny się zmienił. Przed zmianą `model/` rób kopię poza repo (historia gita to trwały punkt wyjścia).
- Testy bez GUI: `run_render_headless.py` (render ze zmienionymi ustawieniami), `test_items.py` (ok. 4 min), `test_canvas.py` (ok. 2 min), `test_import_item.py`, `test_materials.py`. Szczegóły i opcje w nagłówkach skryptów i w README.

## Pułapki
- `pkill -f`/`pgrep -f` z wzorcem występującym we własnej komendzie zabija powłokę; używaj `ps -eo pid,args | grep "[w]zorzec"`.
- `BVHTree.FromObject` liczy w układzie lokalnym obiektu (`UO_Body` jest obracany per kierunek).
- `bpy.app.driver_namespace` w trybie tła powoduje segfault przy zamykaniu.
- Po usunięciu grup wag kości trzeba wagi renormalizować.
