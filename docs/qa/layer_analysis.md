# Warstwy ubieralne z klienta: zasięg i odstęp od ciała (poza `stand`, 5 kierunków)

Źródło: `pipeline/layer_analysis.py` (anim, anim2, anim3, anim4, anim5; 385 animacji). 1 px = 2.78 cm. Szczegóły: `client/extract/layer_analysis.json`.

## Zasięg wysokości w pozie spoczynkowej (m, podłoga = 0)

| warstwa | animacji | dół: min / mediana / max | góra: min / mediana / max | przykłady |
|---|---|---|---|---|
| Arms | 14 | 0.02 / 0.89 / 0.93 | 1.31 / 1.65 / 1.69 | , Bracers_Turtle_H, Elven Arm Plate |
| Cloak | 5 | 0.10 / 1.04 / 1.24 | 1.56 / 1.68 / 1.75 | , M_Elven_Quiver, cloak |
| Earrings | 1 | 1.62 / 1.62 / 1.62 | 1.95 / 1.95 / 1.95 | Holiday_Gargoyle_ear |
| FacialHair | 8 | 1.46 / 1.52 / 1.61 | 1.68 / 1.72 / 1.73 | , Male_H_Beard_Hair_01, Male_H_Beard_Hair_02 |
| Gloves | 10 | -0.01 / 0.81 / 0.86 | 1.03 / 1.12 / 1.70 | , Elven Plate Gloves, Hide Gloves |
| Hair | 37 | 1.15 / 1.52 / 1.70 | 1.81 / 1.89 / 1.97 | , Elven_Hair, Elven_Hair01_BL_Mu |
| Helm | 59 | -0.01 / 1.52 / 1.71 | 1.86 / 1.92 / 2.48 | , 15AnnRobe EAST, 15AnnRobe SOUTH |
| InnerTorso | 28 | 0.56 / 0.90 / 1.12 | 1.61 / 1.64 / 2.10 | , Chest_Tiger_H_F, Chest_Tiger_H_M |
| MiddleTorso | 7 | 0.65 / 0.68 / 1.14 | 1.59 / 1.66 / 1.69 | Jin-Baori, body sash, doublet |
| Neck | 8 | 1.42 / 1.48 / 1.51 | 1.61 / 1.64 / 1.66 | , Collar_Tiger_H, Elven Plate Gorget |
| OneHanded | 52 | 0.41 / 0.84 / 0.95 | 1.03 / 1.28 / 1.59 | ,  wand, Assassin Spike |
| OuterLegs | 7 | 0.03 / 0.51 / 0.53 | 1.20 / 1.23 / 1.26 | Hakama, Kilt01, Kilt02 |
| OuterTorso | 26 | -0.68 / -0.01 / 0.68 | 1.47 / 1.87 / 3.58 | , 15AnnRobe EAST, 15AnnRobe SOUTH |
| Pants | 30 | -0.11 / 0.10 / 1.64 | 0.63 / 1.19 / 1.99 | , Elven Plate Legs, Elven_Pants |
| Shirt | 13 | 0.52 / 0.89 / 1.56 | 1.57 / 1.66 / 1.94 | ElvenShirt1_Male, ElvenShirt2_Male, FShirt1_Chest |
| Shoes | 10 | -0.09 / -0.07 / -0.05 | 0.20 / 0.44 / 0.86 | , Elven_Boot, Holiday_Boots_East |
| TwoHanded | 66 | -0.06 / 0.54 / 1.02 | 0.95 / 1.46 / 2.86 | , Chaos shield, Daisho |
| Waist | 8 | 0.42 / 0.74 / 1.00 | 1.13 / 1.19 / 1.25 | Belt_Dagger, Belt_Mace, Belt_Sword |

## Pokrycie części ciała (mediana po animacjach, udział pikseli części ciała zakrytych przez przedmiot)

| warstwa | head | neck | torso | upper_arm | forearm | hand | thigh | shin | foot |
|---|---|---|---|---|---|---|---|---|---|
| Arms | 0.02 | 0.03 | 0.18 | 0.79 | 0.65 | 0.01 | 0.00 | 0.00 | 0.00 |
| Cloak | 0.06 | 0.48 | 0.33 | 0.12 | 0.04 | 0.07 | 0.00 | 0.00 | 0.00 |
| Earrings | 0.68 | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| FacialHair | 0.25 | 0.18 | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Gloves | 0.00 | 0.00 | 0.01 | 0.00 | 0.28 | 0.54 | 0.01 | 0.00 | 0.00 |
| Hair | 0.59 | 0.38 | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Helm | 0.77 | 0.34 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| InnerTorso | 0.03 | 0.57 | 0.69 | 0.42 | 0.08 | 0.02 | 0.00 | 0.00 | 0.00 |
| MiddleTorso | 0.07 | 0.75 | 0.91 | 0.35 | 0.19 | 0.23 | 0.30 | 0.00 | 0.00 |
| Neck | 0.05 | 0.60 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| OneHanded | 0.00 | 0.00 | 0.02 | 0.01 | 0.05 | 0.37 | 0.00 | 0.00 | 0.00 |
| OuterLegs | 0.00 | 0.00 | 0.40 | 0.05 | 0.21 | 0.25 | 0.87 | 0.01 | 0.00 |
| OuterTorso | 0.81 | 0.90 | 0.98 | 0.95 | 0.80 | 0.29 | 0.99 | 1.00 | 0.61 |
| Pants | 0.00 | 0.00 | 0.34 | 0.03 | 0.13 | 0.22 | 0.96 | 0.84 | 0.03 |
| Shirt | 0.08 | 0.82 | 0.83 | 0.60 | 0.38 | 0.02 | 0.00 | 0.00 | 0.00 |
| Shoes | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.55 | 0.93 |
| TwoHanded | 0.00 | 0.00 | 0.05 | 0.05 | 0.11 | 0.23 | 0.07 | 0.01 | 0.00 |
| Waist | 0.00 | 0.00 | 0.19 | 0.03 | 0.07 | 0.04 | 0.06 | 0.00 | 0.00 |

## Wystawanie poza sylwetkę oryginalnego ciała (cm; p90 odległości pikseli przedmiotu od sylwetki, mediana po animacjach; tylko animacje z ≥ 5 pikselami poza sylwetką na kierunek)

To dolne oszacowanie odstępu od skóry (wewnątrz sylwetki ciało jest zasłonięte). `—` = przedmiot prawie nie wystaje.

| warstwa | head | neck | torso | upper_arm | forearm | hand | thigh | shin | foot |
|---|---|---|---|---|---|---|---|---|---|
| Arms | — | — | 10.1 | 4.7 | 3.9 | — | — | — | — |
| Cloak | — | — | 17.2 | 11.4 | — | — | — | — | — |
| Earrings | — | — | — | — | — | — | — | — | — |
| FacialHair | — | — | — | — | — | — | — | — | — |
| Gloves | — | — | 19.3 | — | 3.9 | 3.9 | — | — | — |
| Hair | 5.6 | — | 7.9 | — | — | — | — | — | — |
| Helm | 8.3 | — | 8.5 | 11.2 | — | — | — | — | — |
| InnerTorso | 8.1 | — | 5.6 | 6.2 | 3.9 | 5.6 | 5.6 | — | — |
| MiddleTorso | — | — | 3.9 | 5.6 | 2.8 | — | 3.9 | — | — |
| Neck | — | — | — | — | — | — | — | — | — |
| OneHanded | — | — | 23.6 | 16.2 | 11.0 | 38.5 | 11.1 | 35.2 | — |
| OuterLegs | — | — | 5.6 | — | — | — | 8.8 | 8.8 | — |
| OuterTorso | 5.6 | — | 5.9 | 3.9 | 3.9 | 5.6 | 8.3 | 8.7 | 8.2 |
| Pants | — | — | 2.8 | — | — | 5.6 | 3.9 | 3.9 | 6.9 |
| Shirt | — | — | 5.6 | 5.9 | 4.2 | — | 5.6 | — | — |
| Shoes | — | — | — | — | — | — | — | 3.3 | 2.8 |
| TwoHanded | 45.7 | — | 22.2 | 23.1 | 17.7 | 17.8 | 13.9 | 12.4 | 8.8 |
| Waist | — | — | 4.7 | — | — | — | 5.6 | — | — |
