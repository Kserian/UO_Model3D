# Warstwy ubieralne z klienta: zasięg i odstęp od ciała (poza `stand`, 5 kierunków)

Źródło: `pipeline/layer_analysis.py` (anim, anim3, anim5 = oryginalne animacje; 272 animacji). 1 px = 2.78 cm. Szczegóły: `client/extract/layer_analysis.json`.

## Zasięg wysokości w pozie spoczynkowej (m, podłoga = 0)

| warstwa | animacji | dół: min / mediana / max | góra: min / mediana / max | przykłady |
|---|---|---|---|---|
| Arms | 9 | 0.88 / 0.89 / 0.93 | 1.31 / 1.63 / 1.69 | Bracers_Turtle_H, Elven Arm Plate, Hide Paldrons |
| Cloak | 3 | 0.10 / 1.03 / 1.24 | 1.56 / 1.64 / 1.68 | M_Elven_Quiver, cloak, elegant quarter cloa |
| FacialHair | 4 | 1.47 / 1.51 / 1.54 | 1.73 / 1.73 / 1.73 | , long beard, short beard |
| Gloves | 6 | 0.80 / 0.82 / 0.86 | 1.03 / 1.08 / 1.27 | Elven Plate Gloves, Hide Gloves, Leather Gloves |
| Hair | 21 | 1.29 / 1.54 / 1.66 | 1.86 / 1.89 / 1.97 | , Elven_Hair, Elven_Hair01_BL_Mu |
| Helm | 39 | -0.01 / 1.52 / 1.71 | 1.86 / 1.92 / 2.48 | 15AnnRobe EAST, 15AnnRobe SOUTH, Hat_Bake Kitsune_Eas |
| InnerTorso | 21 | 0.56 / 1.02 / 1.12 | 1.61 / 1.64 / 1.81 | Chest_Tiger_H_F, Chest_Tiger_H_M, Chest_Turtle_H_F |
| MiddleTorso | 6 | 0.65 / 0.68 / 1.14 | 1.59 / 1.66 / 1.69 | body sash, doublet, full apron |
| Neck | 7 | 1.42 / 1.47 / 1.51 | 1.62 / 1.64 / 1.66 | Collar_Tiger_H, Elven Plate Gorget, Hide Gorget |
| OneHanded | 41 | 0.41 / 0.84 / 0.95 | 1.03 / 1.30 / 1.59 | ,  wand, Assassin Spike |
| OuterLegs | 6 | 0.03 / 0.52 / 0.53 | 1.20 / 1.23 / 1.26 | Kilt01, Kilt02, Kilt03 |
| OuterTorso | 16 | -0.14 / 0.01 / 0.49 | 1.47 / 1.79 / 1.93 | , 15AnnRobe EAST, 15AnnRobe SOUTH |
| Pants | 20 | -0.11 / 0.09 / 0.73 | 0.63 / 1.18 / 1.23 | Elven Plate Legs, Elven_Pants, Hide Pants |
| Shirt | 10 | 0.52 / 0.89 / 1.00 | 1.62 / 1.66 / 1.69 | ElvenShirt1_Male, ElvenShirt2_Male, FShirt1_Chest |
| Shoes | 6 | -0.08 / -0.07 / -0.05 | 0.26 / 0.46 / 0.86 | Elven_Boot, Shoes_Jester, boots |
| TwoHanded | 55 | -0.06 / 0.54 / 1.02 | 0.95 / 1.48 / 2.86 | Chaos shield, Elven Composite Lo, Elven Spellblade |
| Waist | 6 | 0.42 / 0.65 / 0.90 | 1.13 / 1.17 / 1.25 | Belt_Dagger, Belt_Mace, Belt_Sword |

## Pokrycie części ciała (mediana po animacjach, udział pikseli części ciała zakrytych przez przedmiot)

| warstwa | head | neck | torso | upper_arm | forearm | hand | thigh | shin | foot |
|---|---|---|---|---|---|---|---|---|---|
| Arms | 0.01 | 0.03 | 0.20 | 0.82 | 0.72 | 0.00 | 0.00 | 0.00 | 0.00 |
| Cloak | 0.06 | 0.50 | 0.45 | 0.30 | 0.01 | 0.11 | 0.00 | 0.00 | 0.00 |
| FacialHair | 0.28 | 0.18 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Gloves | 0.00 | 0.00 | 0.01 | 0.00 | 0.20 | 0.54 | 0.01 | 0.00 | 0.00 |
| Hair | 0.54 | 0.38 | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Helm | 0.81 | 0.30 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| InnerTorso | 0.04 | 0.59 | 0.66 | 0.46 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 |
| MiddleTorso | 0.08 | 0.75 | 0.93 | 0.46 | 0.22 | 0.16 | 0.36 | 0.00 | 0.00 |
| Neck | 0.06 | 0.64 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| OneHanded | 0.00 | 0.00 | 0.02 | 0.01 | 0.05 | 0.35 | 0.00 | 0.00 | 0.00 |
| OuterLegs | 0.00 | 0.00 | 0.42 | 0.05 | 0.17 | 0.28 | 0.83 | 0.01 | 0.00 |
| OuterTorso | 0.51 | 0.95 | 0.98 | 0.96 | 0.83 | 0.36 | 1.00 | 1.00 | 0.57 |
| Pants | 0.00 | 0.00 | 0.33 | 0.03 | 0.14 | 0.23 | 0.96 | 0.85 | 0.05 |
| Shirt | 0.09 | 0.82 | 0.83 | 0.66 | 0.45 | 0.02 | 0.00 | 0.00 | 0.00 |
| Shoes | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.66 | 0.97 |
| TwoHanded | 0.00 | 0.00 | 0.06 | 0.05 | 0.12 | 0.23 | 0.08 | 0.01 | 0.00 |
| Waist | 0.00 | 0.00 | 0.19 | 0.02 | 0.10 | 0.07 | 0.12 | 0.00 | 0.00 |

## Wystawanie poza sylwetkę oryginalnego ciała (cm; p90 odległości pikseli przedmiotu od sylwetki, mediana po animacjach; tylko animacje z ≥ 5 pikselami poza sylwetką na kierunek)

To dolne oszacowanie odstępu od skóry (wewnątrz sylwetki ciało jest zasłonięte). `—` = przedmiot prawie nie wystaje.

| warstwa | head | neck | torso | upper_arm | forearm | hand | thigh | shin | foot |
|---|---|---|---|---|---|---|---|---|---|
| Arms | — | — | — | 3.6 | 3.9 | — | — | — | — |
| Cloak | — | — | — | 9.9 | — | — | — | — | — |
| FacialHair | — | — | — | — | — | — | — | — | — |
| Gloves | — | — | — | — | 3.9 | 3.3 | — | — | — |
| Hair | 4.6 | — | — | — | — | — | — | — | — |
| Helm | 7.7 | — | 8.5 | 11.2 | — | — | — | — | — |
| InnerTorso | 7.9 | — | 5.6 | 6.2 | 3.9 | — | 5.6 | — | — |
| MiddleTorso | — | — | 3.9 | 5.6 | 2.8 | — | 3.9 | — | — |
| Neck | — | — | — | — | — | — | — | — | — |
| OneHanded | — | — | 30.6 | 16.2 | 19.7 | 41.9 | 11.1 | 35.2 | — |
| OuterLegs | — | — | 8.2 | — | — | — | 9.8 | 9.4 | — |
| OuterTorso | 5.6 | — | 8.3 | 3.9 | 5.6 | 5.6 | 10.0 | 10.2 | 8.8 |
| Pants | — | — | 4.2 | — | — | — | 3.4 | 3.9 | 6.9 |
| Shirt | — | — | 5.6 | 5.9 | 4.2 | — | 5.6 | — | — |
| Shoes | — | — | — | — | — | — | — | 3.9 | 2.8 |
| TwoHanded | 47.6 | — | 21.8 | 22.9 | 16.9 | 17.1 | 13.9 | 12.4 | 8.8 |
| Waist | — | — | 4.7 | — | — | — | 5.6 | — | — |
