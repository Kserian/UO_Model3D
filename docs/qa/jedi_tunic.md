# Biała tunika z „Jedi robes” (darmowy model, slot `shirt`)

Model: „Jedi robes” (plik `Jedi robes.glb` w zipie od użytkownika, źródło i licencja nieznane; pliku nie ma w repo). 9 siatek: buty, pas wewnętrzny i zewnętrzny, klamra, brązowa koszula spodnia, płaszcz z kapturem, **biała tunika (`Outer tunic`)**, tabard, spodnie.
Zlecenie: zostawić tylko koszulę (białą tunikę), bez paska; dopasować do ciała tak, żeby skóra nie przebijała materiału w żadnej akcji (materiał w minimalnej odległości od ciała) i żeby materiał nie rozciągał się dziwnie; przy czarowaniu nie może przesuwać się za jedną ręką.
Tunika: jedna warstwa, 13 084 wierzchołki, 4 panele (przód i tył, lewy i prawy, każdy z połową rękawa), brzegi: dół, kołnierz, 2 mankiety. Dół na 0,75 m (ok. 10 cm poniżej krocza UO).

```
python pipeline/uo_make_item.py docs/qa/jedi_tunic_recipe.json --preview      # z katalogu z jedi.glb (= "Jedi robes.glb"); --vd = pełny render
```

## Co nie działało (zmierzone, nie powtarzać)
| Próba | Wynik |
|---|---|
| Zwykły potok `kind shirt` (autofit, `uo_fit_item`, `uo_bind_item`) | rękawy 9-18 cm nad rękami UO i obrócone o 10,5°, `MATCH_ARMS` ich nie rozpoznał; w ruchu ręce wychodzą obok rękawów; tułów UO przebija przód i tył tuniki (model z węższego manekina), push przesuwał części o 21 cm; rozciągnięcie krawędzi p99 do 5,0 (skóra 2,3) |
| Wagi dokładnie ze skóry pod spodem + odsuwanie w kształcie spoczynkowym dla wszystkich póz | bez wyrównania rękawów nie zbiega się (wąskie ręce przechodzą przez szerokie rękawy, dół łokcia) |
| Wagi z inpaintingiem (Abdrashitov 2023) | rozciąganie mniejsze (p99 5,0 -> 2,0), ale kształt nadal zły: rękawy obok rąk |
| Rzut na najbliższą skórę (anchor + normalna × h) | dziury na barkach: wierzchołki zbijają się po jednej stronie wypukłego barku, duże trójkąty przecinają ciało; szczeliny na szwie pachy (najbliższy punkt skacze między klatką a ramieniem) |
| Membrana bez ograniczenia rozciągania | pojedyncze wierzchołki „odlatują” (krawędzie 24 cm przy pachach i kołnierzu); szew pod pachą zostaje w ramieniu UO blisko kości, a najbliższa skóra bywa po złej stronie |
| Statyczne odsuwanie kształtu pod wszystkie pozy (6 rund) | 6000 wierzchołków odsuniętych o maks. 9 cm: tunika w bryłach (`look_conf14`) |
| Tułów tuniki bez wagi ramienia (20%) z ostrym przejściem do rękawa | szczeliny na szwie barku (także w staniu od tyłu) |

## Metoda (`pipeline/uo_conform_item.py`, przepis: `"conform": {...}`)
1. **Rękawy na ręce:** oś rękawu (środki przekrojów, PCA części dalszej) obrócona i przesunięta na oś ręki UO (bark -> nadgarstek); ruch narasta przez 10 cm od nasady rękawu i gaśnie poza promieniem „rury” rękawu (bok tułowia pod pachą zostaje). Tunika najpierw w dół o 7 cm (`MOVE`): siedziała za wysoko (kołnierz przy twarzy), po tym rękawy są 4,2 cm od osi ręki zamiast 8,7.
2. **Owinięcie jak membrana:** cel h = GAP 1,5 cm + 25% luzu modelu (maks. 3 cm) + fałdy (maks. 2 cm). Ściąganie wzdłuż normalnej materiału (odległość od skóry jest ciągła, więc nic się nie rwie), wypychanie ze skóry wzdłuż normalnej skóry (wewnątrz ręki: od kości), maks. 1 cm na przebieg, wygładzanie (równe wierzchołki, zagłębienia jak pacha przykryte mostem), krawędź rozciągnięta maks. 1,25×. Obrys (dół, kołnierz, mankiety) i UV zostają z modelu. Panele obrócone tak, żeby normalne patrzyły na zewnątrz.
   Poniżej krocza dół wisi (kształt modelu, poza nogami o GAP) i podąża za miednicą; nogi pchają go w renderze (`uo_cloth`, jak szata).
3. **Wagi:** jak skóra pod materiałem (SMOOTH 4, dłonie -> przedramię), ale materiał dalej niż 2 cm od skóry ręki (przód i tył piersi) zostawia tylko **35% wagi ramienia** (`TORSO_ARM`), reszta idzie na klatkę (zob. „Poprawka po uwagach”). Skóra UO na górze piersi i barku ma 30-90% wagi ramienia, więc tunika jechała za uniesioną ręką.
4. **Render pilnuje odstępu w każdej klatce** (`render_uo_layer.py` + `cloth_lib.conform_push`, własność `uo_conform`, atrybut `uo_region`): każdy wierzchołek trzymany 8 mm od skóry swojej strefy, wypychany i wygładzany po siatce (jak `BODY_GAP`, który jest dla kończyn). Strefy: tułów tuniki od tułowia, nóg, głowy i obu rąk; rękaw od swojej ręki z dłonią; nasada rękawu (≥ 10% wagi tułowia) od swojej ręki i od tułowia. Rękaw nie patrzy na tułów: ręka przyciśnięta do boku jest w rękawie.

## Wynik (35 akcji, 210 klatek, `pipeline/item_clearance.py`, po pchnięciu renderu)
| | zwykły potok | ta metoda |
|---|---|---|
| wierzchołki w skórze własnej strefy, średnio / najgorsza klatka | 0,35% / 2,69% | **0,03% / 0,33%** |
| najgłębiej | 124,6 mm | 29,0 mm (fałd skóry w barku przy kuszy z konia; w renderze niewidoczne: ciało zasłania przedmiot dopiero, gdy jest > 1 cm przed nim, a ręce, do których tunika jest przypięta, nie zasłaniają jej wcale) |
| w nogach (dół) | 0,89% (70 mm) | 0,02% (26 mm) |
| dłonie i głowa w materiale | 1,03% | 0,02% |
| rozciągnięcie krawędzi p99 (skóra pod spodem) | 5,01 (2,31) | 3,09 (2,80) |
| przesunięcie barków względem klatki, czar 17, najgorsza klatka (L / P) | 14,6 / 14,1 cm | **4,9 / 3,9 cm** (bez `TORSO_ARM` 12,7 / 10,1) |
| odstęp od skóry w spoczynku p50 / p90 / maks. | | 1,7 / 3,6 / 7,3 cm (oryginalne koszule UO p90 3,9 cm) |
Miara zwykłego potoku nie łapie ręki wychodzącej obok rękawu (to nie jest przebicie); widać to na podglądzie. Podgląd 3D (skóra na czerwono) i klatki UO: czar 16 i 17 we wszystkich 5 kierunkach czyste, poza dłońmi, głową i nogami pod dołem.
Miara „odkrytej skóry” (promień ze skóry nie trafia w materiał) odrzucona: skóra pachy wchodzi w pozach w tułów i liczyła się jako odkryta.

## Otwarte
- Dzwonowy mankiet przy uniesionym przedramieniu wygląda jak prostokątny płat (kształt modelu, luz rękawu ograniczony do 3 cm ponad GAP).
- Rozciągnięcie p99 nieco wyższe niż skóry (3,1 vs 2,8): pchnięcie w klatce i mniejsza waga ramienia na barku.
- Kolor materiału z tekstury modelu (kremowy, w świetle UO lekko różowawy); kropki 1 px zasłaniania przez dłonie i głowę w warstwie przedmiotu.

## Poprawka po uwagach użytkownika (przebicia przy czarach, nowy model czaru 17)
Niebieska tunika i kolorowe części ciała na podglądzie `all` (render ciała i przedmiotu razem w 3D, `pre_parts`: dłonie czerwone, głowa zielona, ręce żółte, tułów fioletowy, nogi turkusowe) pokazały,
czego warstwa `clothing` nie pokazuje (tam przedmiot zasłania ciało, a te same piksele w podglądzie są skórą):
1. **Okno na ramieniu przy ręce uniesionej nad głowę:** nasada rękawu miała obniżoną wagę ramienia (`TORSO_ARM` z przejściem wygładzanym w głąb rękawu), zostawała w tyle, ręka przechodziła przez tylną
   ścianę, a pchnięcie w renderze przenosiło ją na drugą stronę ręki. Teraz pełną wagę ramienia ma materiał do 2 cm od skóry ręki (`TORSO_ARM_NEAR`), przejście do 35% przez 6 cm (`TORSO_ARM_FADE`).
   Dalsze obniżanie (np. 0 / 4 cm) od razu otwiera okno.
2. **Pchnięcie w renderze od całej skóry:** każda część przedmiotu trzyma 8 mm od tułowia, nóg, głowy, obu rąk i dłoni (wcześniej rękaw tylko od swojej ręki: ręka przyciśnięta do boku i druga
   ręka przechodziły przez rękaw); wierzchołek głęboko w kończynie (< 7 cm od kości) jest wypychany od kości, nie do najbliższej skóry (`cloth_lib.conform_push`, `limbs`).
3. **Czar 17 w starym modelu** miał lewe przedramię zwisające z łokcia uniesionego nad głowę (oryginał: obie dłonie w górze); poprawione na `main` w innej sesji (`docs/qa/elbow_spell.md`). To też była
   przyczyna „tunika przesuwa się za jedną ręką”: barki względem klatki w czarze 17 na nowym modelu 12,5 / 12,6 cm (symetrycznie).

Wynik na nowym modelu (35 akcji × 5 kierunków, 1050 klatek podglądu `all`, piksele czystych kolorów, bez mieszanych z krawędzi dłoni): **ręka 29 px, tułów 11 px, w 19 klatkach**
(łuk 15 px przy nadgarstku naciągającym cięciwę, upadek do przodu 12 px: miednica pod dołem tuniki). Czar 17: ręka 93 -> 3 px po zmianach (stary model 40 px po p. 1). `item_clearance.py`:
własna strefa 0,085% (najgorsza klatka 0,45%), najgłębiej 20,7 mm, styk z inną strefą 0,37% -> 0,11%, rozciągnięcie p99 3,65 (skóra 2,80). `test_items` 0,718, `test_canvas` OK.
