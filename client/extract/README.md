# Wyciąg z klienta Nelderim (sprzed zmian)

Źródło: archiwum klienta (link i polecenia pobrania w `CLAUDE.md`). Surowe `anim*.mul`, `*.idx`, `tiledata.mul` NIE są w repo
(pobieraj do `uo_client/`, w `.gitignore`). Tu jest tylko wyciąg potrzebny do pracy.

| Plik | Co to jest | Skąd / jak powstał |
|---|---|---|
| `defs/Body.def`, `defs/Bodyconv.def`, `defs/Equipconv.def`, `defs/mobtypes.txt` | Konwersje ciał i ekwipunku klienta | kopia z klienta (stan z 2026-09-24 / 2026-09-18) |
| `defs/Bodyconv.def.bak-vd2anim2` | Starsza wersja `Bodyconv.def` (2026-09-09) | kopia z klienta |
| `equipment_extent.json` | Zasięg klatek każdej animacji ludzi / ekwipunku (`anim`, `anim2`..`anim5`, ID lokalne w pliku) względem zaczepu: `left`, `right`, `up`, `down` w px, z uwzględnieniem lustra kierunków 5–7 | `pipeline/measure_equipment_extent.py` |
| `layer_analysis.json` | Analiza A: zasięg wysokości, pokrycie części ciała i wystawanie poza sylwetkę ciała dla 385 oryginalnych animacji (`anim`..`anim5`) ubieralnych (`stand`) | `pipeline/layer_analysis.py` (tabele: `docs/qa/layer_analysis.md`, `pipeline/layer_analysis_report.py`) |
| `item_animations.json` | Przedmioty ubieralne z `tiledata.mul` (animacja, warstwa, nazwa) połączone przez `Bodyconv.def` z plikiem animacji i zasięgiem; statystyki per warstwa | `pipeline/extract_tiledata.py` |

Odtworzenie (z katalogu repo, klient w `uo_client/NelderimServUO/`):
```
python pipeline/measure_equipment_extent.py uo_client/NelderimServUO client/extract/equipment_extent.json 128,128,192,64
python pipeline/extract_tiledata.py uo_client/NelderimServUO/tiledata.mul uo_client/NelderimServUO/Bodyconv.def \
       client/extract/equipment_extent.json client/extract/item_animations.json
```
Archiwum klienta to RAR5. W kontenerze działa `apt-get install unrar` (UNRAR 7.00 z multiverse). `unar` i `7zip` z Debiana
psują większe pliki lub nie obsługują RAR5.

Fakty o kliencie (zmierzone): `anim.mul` i `anim.idx` są bajt w bajt identyczne z kopiami `*_BACKUP_przed_vd`
(md5 `b1efc293…` / `ca8a8f91…`), więc ciało 400 i ekwipunek w `anim.mul` są oryginalne. `anim2`, `anim4` mają zmiany z 2026-09, ale animacje ubieralne w nich to oryginały gry (potwierdził użytkownik, sesja 8); własne animacje Nelderim (np. 420, 422) są osobno. Animacje w `anim`..`anim5`: 449 z klatkami (417 kompletnych 35×5); 613 ID ubieralnych w `tiledata`,
392 z klatkami.
