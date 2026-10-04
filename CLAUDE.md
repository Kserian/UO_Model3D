# UO_Model3D

Model 3D ciała Ultima Online (body 0x190) do generowania animacji ubrań, zbroi i broni jako plików `.vd`.

**Cel nadrzędny:** nasze body ma odwzorowywać body z UO tak, żeby przedmioty zrobione na naszym modelu pasowały na oryginalny model UO.
Oceniaj tym każdą zmianę.

- Rozmowa po polsku. Commity po angielsku: `UOModel3D: <co i po co>`. Użytkownik prosi o krótkie komunikaty: wynik, blokada, decyzja.
- Pracujemy na `main`. Wszystko przetestowane i działające wrzucaj na `main` (`git push origin main`) bez dopytywania; nietestowanego nie wrzucaj.
  Jeśli zadanie sesji narzuca inną gałąź, wypchnij na nią, a po przetestowaniu także `git push origin HEAD:main`. Pull requesta nie twórz bez prośby.
  **Nie wypychaj na gałąź `claude/friendly-knuth-44xtfw`** (kopia zapasowa stanu `ea55c0b`).
- Dokumentacja: `README.md` (PL), `README_EN.md` (EN). Raport z analizy: `docs/RAPORT_model3D_UO.txt`, audyt: `docs/AUDYT_2026-10-03.md`, pomiary: `docs/qa/` (autodopasowanie: `autofit.md`, szaty i spódnice: `robe_physics.md`, broń z darmowych modeli: `weapons_free_models.md`).
  Nie ma pliku przekazania między sesjami: stan jest w kodzie, w `docs/` i w historii gita. Zasady i decyzje są poniżej; jeśli je zmieniasz, popraw ten plik.
- **Mierz, nie ufaj.** Liczby, na których opierasz decyzję, mają pochodzić z własnego pomiaru na plikach (przed i po zmianie). Główna miara celu:
  `pipeline/test_items.py` (przedmiot na naszym ciele vs oryginalny sprite; baseline w `docs/qa/items_after_fingers.json`: średnia 0,718),
  sylwetka ciała: `body_part_raster.py` + `body_part_qa.py` (IoU 0,892 na 1050 klatkach).

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
| Szkielet (sesja 14) | **19 kości UO** (pelvis, spine, chest, neck, head, clavicle ×2, upper_arm, forearm, hand, thigh, shin, foot ×2) **+ 30 kości palców** (przywrócone po prośbie użytkownika, pozy dopasowane do klatek UO; `rig_restore_fingers.py`). **+ 5 kości ruchu broni i tarczy** (`polearm.L`, `axe2h.L`, `bow.L`, `weapon1h.R`, `shield.L`; przywrócone, zależą tylko od dłoni i przedramienia; `rig_restore_weapons.py`, kalibracja: `weapon_*.py`, `docs/qa/weapon_roll.md`, `weapons_*_hand.json`). Bez skrętu, palców stóp i łańcuchów materiału (decyzja użytkownika). Szata i spódnica (sesja 15, prośba użytkownika): `PART robe`/`skirt` = wisi od miednicy, nogi wypychają tkaninę per klatka (`cloth_lib.py`, powłoka nóg, bez symulacji i bez łańcuchów; kalibracja na oryginale 469, `docs/qa/robe_physics.md`); peleryna: `PART cloak` (pochylenie do tyłu per akcja, `cloak_pitch.json`). Włosy są sztywne na głowie (`uo_bind_item.py`, `RIGID`). Pomiar bez palców: IoU sylwetki 0,8922 -> 0,8882, `test_items` 0,718 -> 0,710 (`docs/qa/items_after_slim_rig.json`); po przywróceniu palców: patrz `docs/qa/items_after_fingers.json`. Poprzedni stan: commit `b86c314` |
| Barki i ramiona | Barki −1 cm, ramiona ×0,95 (prośba użytkownika; pomiar pokazał, że model zgadzał się z oryginałem ±1 px). Nie zwężaj dalej bez prośby |
| Światło UO | Zostaje `UO_Look`: Lambert, L = (0,0012; −0,7572; 0,6532), ambient 0,0798 (zmierzone na 880 klatkach ciała i 393 animacjach). Odblask tylko na metalu (`uo_materials.py`). Brak AO i cienia na ziemi |
| Cień własny | Odłożony na później (decyzja użytkownika); sprite'y mają częściowy cień własny (s = 0,4), nasz render nie |
| Gęstość siatki i wagi | Przedmiot low-poly zagęszczany (`uo_densify_item.py`), wagi jak skóra pod spodem (SMOOTH 4, STIFF 1): sprite'y nie odróżniają polityk wag (±0,002) |
| Przedmioty | Użytkownik używa darmowych modeli 3D. Jedno polecenie: `python pipeline/uo_make_item.py przepis.json --preview` (przepis: `file`, `kind` albo `weapon`, `skip`/`keep`; `--list` pokazuje siatki pliku). Łańcuch: `uo_import_item.py` (`PLACE = wrap`) -> `uo_materials.py` -> `uo_prepare_item.py` (**`uo_autofit_item.py`** skala/miejsce z kształtu skóry, densify, fit z miękkim limitem grubości `LIMIT`, bind) -> `render_uo_layer.py`. Broń: `uo_orient_weapon.py` -> `uo_place_weapon.py` -> `uo_bind_item.py`. Pomiary: `docs/qa/autofit.md`. Skala z jednej wysokości na slot (`PLACE = height`) jest tylko dla przedmiotów podobnych do wzorca |

Gotowe sketche użytkownika do testów leżą poza repo (licencje nieznane); nie commituj ich ani wyników renderu bez zgody.

Czego nie robić: korekt per klatka, dalszego strojenia replik `test_items`, dalszego dopasowywania sylwetki ciała (granica ok. 0,90), zmian kierunku/ambientu światła, AO i cienia na ziemi.

## Otwarte

- Fizyka luźnych ubrań (sesja 15) jest skalibrowana na jednej oryginalnej szacie (469) i sprawdzona na 447 i 970; brak testu na prawdziwym darmowym modelu szaty i kiltu. Peleryna: `PART cloak`, pochylenie per akcja z oryginału 468 (`docs/qa/cloak_physics.md`), bez falowania boków i bez testu na prawdziwym modelu (`docs/qa/robe_physics.md`, „Czego model nie robi").
- Sloty `waist` i `vest` (MiddleTorso) dodane z zakresów oryginałów, ustawienia przez analogię, bez testu na prawdziwym modelu; nadal brakuje Earrings, Ring, Bracelet, Talisman, Backpack (małe przedmioty: wykrywanie jednostek zakłada 0,15-3 m).
- Naramienniki jako jedna ciągła siatka z korpusem rozciągają się z ramieniem w czarach (wagi „jak skóra"); `item_qa.py` pokazuje 3-4% wierzchołków zbroi w ciele w ruchu (do 11 cm przy ataku, wypychane przez `BODY_GAP`), warianty wag (`FOLLOW` barku, `STIFF` 2) nic nie poprawiły.
- Pierwszy prawdziwy darmowy model (np. włosy Curuaty, CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c: użytkownik sam pobiera glTF i wrzuca do repo, zapisz atrybucję autora).
- Brakujące sloty (Waist, MiddleTorso, Earrings, Ring, Bracelet, Talisman, Backpack) i jedna tabela slotów: `docs/AUDYT_2026-10-03.md`, pkt 5-6.
- Body 401 (kobieta) w `anim.mul` jest prawie kopią męskiego; sprawdzić w grze przed pracą nad ciałem kobiecym.
- `.glb`/`.fbx` nie ma w repo (były nieaktualne): `pipeline/export.py --blend model/UO_Body_0x190.blend` generuje je na żądanie.
