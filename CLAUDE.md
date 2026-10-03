# UO_Model3D

Model 3D ciała Ultima Online (body 0x190) do generowania animacji ubrań, zbroi i broni jako plików `.vd`.

**Cel nadrzędny:** nasze body ma odwzorowywać body z UO tak, żeby przedmioty zrobione na naszym modelu pasowały na oryginalny model UO.
Oceniaj tym każdą zmianę.

- Rozmowa po polsku. Commity po angielsku: `UOModel3D: <co i po co>`. Użytkownik prosi o krótkie komunikaty: wynik, blokada, decyzja.
- Pracujemy na `main`. Wszystko przetestowane i działające wrzucaj na `main` (`git push origin main`) bez dopytywania; nietestowanego nie wrzucaj.
  Jeśli zadanie sesji narzuca inną gałąź, wypchnij na nią, a po przetestowaniu także `git push origin HEAD:main`. Pull requesta nie twórz bez prośby.
  **Nie wypychaj na gałąź `claude/friendly-knuth-44xtfw`** (kopia zapasowa stanu `ea55c0b`).
- Dokumentacja: `README.md` (PL), `README_EN.md` (EN). Raport z analizy: `docs/RAPORT_model3D_UO.txt`, audyt: `docs/AUDYT_2026-10-03.md`, pomiary: `docs/qa/`.
  Nie ma pliku przekazania między sesjami: stan jest w kodzie, w `docs/` i w historii gita. Zasady i decyzje są poniżej; jeśli je zmieniasz, popraw ten plik.
- **Mierz, nie ufaj.** Liczby, na których opierasz decyzję, mają pochodzić z własnego pomiaru na plikach (przed i po zmianie). Główna miara celu:
  `pipeline/test_items.py` (przedmiot na naszym ciele vs oryginalny sprite; baseline po uproszczeniu szkieletu w `docs/qa/items_after_slim_rig.json`),
  sylwetka ciała: `body_part_raster.py` + `body_part_qa.py` (IoU 0,888 na 1050 klatkach).

## Środowisko

- Python 3.11: `pip install numpy pillow scipy "bpy==4.2.*"`. Blender nie jest potrzebny, wystarczy moduł `bpy`. **Plik `.blend` zapisuj `bpy 4.2`** (zapisany w 5.x nie otworzy się w 4.2; 5.2 czyta pliki 4.2).
- `model/UO_Body_0x190.blend` jest binarny, a skrypty są w nim osadzone jako teksty. Źródłem są `pipeline/*.py`; do pliku wgrywa je `pipeline/sync_blend_scripts.py`
  (`--check` pokazuje różnice). W commicie opisz, który plik binarny się zmienił. Przed zmianą `model/` rób kopię poza repo (historia gita to trwały punkt wyjścia).
- Testy bez GUI: `run_render_headless.py` (render ze zmienionymi ustawieniami), `test_items.py` (ok. 4 min), `test_canvas.py` (ok. 2 min), `test_import_item.py`, `test_materials.py`.
  Szczegóły i opcje w nagłówkach skryptów i w README.
- Pułapki: `pkill -f`/`pgrep -f` z wzorcem występującym we własnej komendzie zabija powłokę (używaj `ps -eo pid,args | grep "[w]zorzec"`); `BVHTree.FromObject` liczy w układzie lokalnym obiektu
  (`UO_Body` jest obracany per kierunek); `bpy.app.driver_namespace` w trybie tła powoduje segfault przy zamykaniu; po usunięciu grup wag kości trzeba wagi renormalizować.

## Klient UO i dane

- Dane klienta tylko do użytku własnego, repo jest prywatne. Klient (Google Drive, link publiczny): https://drive.google.com/file/d/1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz/view?usp=drive_link
  `pip install gdown && mkdir -p uo_client && gdown 1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz -O uo_client/client_download` (2,6 GB), potem tylko oficjalny `unrar` (RAR5):
  `apt-get install -y unrar && cd uo_client && unrar x -y -idq client_download NelderimServUO/anim.idx NelderimServUO/anim.mul ...`. Nie wypakowuj ustawień ani wtyczek użytkownika.
- `uo_client/` jest w `.gitignore`. **Nie commituj** surowych `anim*.mul`, `*.idx`, `tiledata.mul` (limit GitHuba 100 MB). Wyciąg potrzebnych rzeczy idzie do repo: `client/extract/` (opis w jego README).
  Pliki `.vd` pojedynczych animacji: `vdtool/mul2vd.py` (`python vdtool/mul2vd.py anim.idx anim.mul wyjscie <id>`), rozpakowanie do PNG: `vdtool/vdtool.py extract`.
  Animacje własne Nelderim (`anim3`/`anim4`, np. 420, 422) nie są potrzebne; ubieralne animacje w `anim2`/`anim4` to oryginały gry.
- **Oryginalne klatki ciała zostają** (`client/body_0x190_frames/`, atlas oryginałów w `.blend`): na nich opiera się `EXACT_BODY` i pomiary. Nie usuwaj ich.

## Decyzje (ustalone z użytkownikiem)

| Temat | Decyzja |
|---|---|
| Rozwijać czy budować od nowa | Rozwijać UO_Model3D (raport: czysty szkielet daje granicę sylwetki ok. 0,88-0,90 IoU, nowy model trafiłby w tę samą) |
| Płótno renderu | `CANVAS` 256×256, zaczep (128, 192), 36 px/m (mieści 444 z 449 animacji ludzi/ekwipunku) |
| Korekty kształtu per klatka (v12) | **NIE.** Ciało poprawiamy w modelu, nie maskujemy. Nie wracaj bez prośby |
| Szkielet (sesja 14) | **Tylko 19 kości UO** (pelvis, spine, chest, neck, head, clavicle ×2, upper_arm, forearm, hand, thigh, shin, foot ×2). Bez palców, skrętu, palców stóp, łańcuchów materiału, kości broni i tarczy (decyzja użytkownika). Broń, tarcza i włosy są sztywne na kości dłoni/przedramienia/głowy (`uo_bind_item.py`, `RIGID`). Szata, spódnica i płaszcz nie mają już presetów ani symulacji tkaniny. Pomiar: IoU sylwetki 0,8922 -> 0,8882, `test_items` 0,718 -> 0,710 (`docs/qa/items_after_slim_rig.json`; rękawice 0,557 -> 0,519, reszta ±0,01). Poprzedni stan: commit `b86c314` |
| Barki i ramiona | Barki −1 cm, ramiona ×0,95 (prośba użytkownika; pomiar pokazał, że model zgadzał się z oryginałem ±1 px). Nie zwężaj dalej bez prośby |
| Światło UO | Zostaje `UO_Look`: Lambert, L = (0,0012; −0,7572; 0,6532), ambient 0,0798 (zmierzone na 880 klatkach ciała i 393 animacjach). Odblask tylko na metalu (`uo_materials.py`). Brak AO i cienia na ziemi |
| Cień własny | Odłożony na później (decyzja użytkownika); sprite'y mają częściowy cień własny (s = 0,4), nasz render nie |
| Gęstość siatki i wagi | Przedmiot low-poly zagęszczany (`uo_densify_item.py`), wagi jak skóra pod spodem (SMOOTH 4, STIFF 1): sprite'y nie odróżniają polityk wag (±0,002) |
| Przedmioty | Użytkownik używa darmowych modeli 3D. Łańcuch: `uo_import_item.py` -> `uo_materials.py` -> `uo_prepare_item.py` (densify + fit + bind) -> `render_uo_layer.py` |

Czego nie robić: korekt per klatka, dalszego strojenia replik `test_items`, dalszego dopasowywania sylwetki ciała (granica ok. 0,90), zmian kierunku/ambientu światła, AO i cienia na ziemi.

## Otwarte

- Pierwszy prawdziwy darmowy model (np. włosy Curuaty, CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c: użytkownik sam pobiera glTF i wrzuca do repo, zapisz atrybucję autora).
- Brakujące sloty (Waist, MiddleTorso, Earrings, Ring, Bracelet, Talisman, Backpack) i jedna tabela slotów: `docs/AUDYT_2026-10-03.md`, pkt 5-6.
- Body 401 (kobieta) w `anim.mul` jest prawie kopią męskiego; sprawdzić w grze przed pracą nad ciałem kobiecym.
- `.glb`/`.fbx` nie ma w repo (były nieaktualne): `pipeline/export.py --blend model/UO_Body_0x190.blend` generuje je na żądanie.
