# Roll broni (obrót wokół własnej osi) — wszystkie animacje broni z `anim`..`anim5`

Pomiar: `pipeline/weapon_roll_fit.py` (opis metody w nagłówku pliku). `zysk` = o ile mniej niezgodności ze sprite'ami daje roll klasy (jeden na pozę) niż najlepszy stały roll; `offset` = stały obrót tej broni względem rollu klasy (stopnie, głowica leży w płaszczyźnie wyznaczonej przez linię klasy i `Rot(phi+offset) e1`).

| id | nazwa | plik:id | klasa | chamfer linii [px] | wynik | zysk | offset |
|---|---|---|---|---|---|---|---|
| 464 | Wakizashi | anim4:429 | weapon1h.R | 1.01 | okrągła głowica / mały zysk (1%) | 1% | 339 |
| 467 | Bokuto | anim4:430 | weapon1h.R | 1.19 | okrągła głowica / mały zysk (0%) | 0% | 5 |
| 470 | Daisho | anim4:431 | weapon1h.R | 3.47 | linia klasy słaba (3.5 px): roll niepewny | 9% | 355 |
| 500 | lantern | anim:500 | bow.L | 3.33 | nie broń (light): własna kość |  |  |
| 501 | torch | anim:501 | bow.L | 3.37 | nie broń (light): własna kość |  |  |
| 502 | candle | anim:502 | bow.L | 3.05 | nie broń (light): własna kość |  |  |
| 503 | lantern | anim:503 | bow.L | 3.34 | nie broń (light): własna kość |  |  |
| 504 | torch%es% | anim:504 | bow.L | 2.38 | nie broń (light): własna kość |  |  |
| 505 | candle%s% | anim:505 | bow.L | 2.95 | nie broń (light): własna kość |  |  |
| 519 | No-Dachi | anim4:444 | weapon1h.R | 1.66 | roll zmierzony | 14% | 8 |
| 520 | Tessen | anim4:445 | axe2h.L | 4.99 | linia klasy słaba (5.0 px): roll niepewny | -0% | 25 |
| 526 | Lajatang | anim4:446 | weapon1h.R | 1.70 | roll zmierzony | 13% | 181 |
| 532 | Fukiya | anim4:447 | weapon1h.R | 1.15 | okrągła głowica / mały zysk (1%) | 1% | 163 |
| 533 | Tekagi | anim4:448 | bow.L | 4.99 | linia klasy słaba (5.0 px): roll niepewny | -4% | 247 |
| 535 | Kama | anim4:450 | polearm.L | 4.02 | linia klasy słaba (4.0 px): roll niepewny | 0% | 343 |
| 536 | Nunchaku | anim4:451 | weapon1h.R | 1.69 | roll zmierzony | 23% | 163 |
| 537 | Sai | anim4:452 | axe2h.L | 3.73 | linia klasy słaba (3.7 px): roll niepewny | 0% | 25 |
| 575 | Yumi | anim4:466 | polearm.L | 3.15 | linia klasy słaba (3.2 px): roll niepewny | 1% | 188 |
| 576 | metal shield | anim:576 | bow.L | 3.36 | nie broń (shield): własna kość |  |  |
| 577 | bronze shield | anim:577 | bow.L | 3.57 | nie broń (shield): własna kość |  |  |
| 578 | wooden shield | anim:578 | bow.L | 3.10 | nie broń (shield): własna kość |  |  |
| 579 | buckler | anim:579 | bow.L | 3.06 | nie broń (shield): własna kość |  |  |
| 580 | kite shield | anim:580 | bow.L | 3.58 | nie broń (shield): własna kość |  |  |
| 581 | kite shield | anim:581 | bow.L | 2.83 | nie broń (shield): własna kość |  |  |
| 582 | heater shield | anim:582 | bow.L | 3.11 | nie broń (shield): własna kość |  |  |
| 583 | Tetsubo | anim4:467 | weapon1h.R | 1.76 | roll zmierzony | 27% | 185 |
| 605 | scale shield | anim5:522 | bow.L | 5.91 | nie broń (shield): własna kość |  |  |
| 611 | large battle axe | anim:611 | axe2h.L | 1.67 | roll zmierzony | 27% | 5 |
| 612 | two handed axe | anim:612 | axe2h.L | 1.36 | roll zmierzony | 42% | 1 |
| 613 | executioner's axe | anim:613 | axe2h.L | 1.17 | roll zmierzony | 24% | 5 |
| 614 | bardiche | anim:614 | polearm.L | 1.07 | roll zmierzony | 30% | 1 |
| 615 | hatchet | anim:615 | axe2h.L | 0.98 | roll zmierzony | 22% | 12 |
| 616 | heavy crossbow | anim:616 | bow.L | 2.13 | roll nieokreślony (łuki: brak pomiaru) | -3% | 262 |
| 617 | black staff | anim:617 | polearm.L | 0.68 | roll zmierzony | 13% | 178 |
| 618 | broadsword | anim:618 | weapon1h.R | 0.77 | roll zmierzony | 20% | 346 |
| 619 | cleaver | anim:619 | weapon1h.R | 1.12 | roll zmierzony | 28% | 181 |
| 620 | club | anim:620 | weapon1h.R | 0.84 | roll zmierzony | 11% | 344 |
| 621 | shepherd's crook | anim:621 | polearm.L | 0.95 | roll zmierzony | 22% | 181 |
| 622 | dagger | anim:622 | weapon1h.R | 0.72 | roll zmierzony | 14% | 355 |
| 623 | cutlass | anim:623 | weapon1h.R | 1.10 | roll zmierzony | 22% | 2 |
| 624 | halberd | anim:624 | polearm.L | 0.95 | roll zmierzony | 30% | 360 |
| 625 | hammer pick | anim:625 | weapon1h.R | 0.89 | roll zmierzony | 12% | 353 |
| 626 | javelin | anim:626 | polearm.L | 0.67 | okrągła głowica / mały zysk (10%) | 10% | 169 |
| 627 | katana | anim:627 | weapon1h.R | 0.66 | roll zmierzony | 17% | 351 |
| 628 | gnarled staff | anim:628 | polearm.L | 0.67 | roll zmierzony | 14% | 189 |
| 629 | butcher knife | anim:629 | weapon1h.R | 0.77 | roll zmierzony | 17% | 172 |
| 630 | kryss | anim:630 | weapon1h.R | 0.85 | roll zmierzony | 11% | 347 |
| 631 | mace | anim:631 | weapon1h.R | 1.05 | okrągła głowica / mały zysk (1%) | 1% | 202 |
| 633 | maul | anim:633 | weapon1h.R | 0.86 | okrągła głowica / mały zysk (6%) | 6% | 346 |
| 634 | double axe | anim:634 | axe2h.L | 1.57 | roll zmierzony | 49% | 189 |
| 635 | pickaxe | anim:635 | weapon1h.R | 1.29 | okrągła głowica / mały zysk (9%) | 9% | 359 |
| 636 | pitchfork | anim:636 | polearm.L | 0.89 | roll zmierzony | 20% | 191 |
| 637 | scimitar | anim:637 | weapon1h.R | 0.89 | roll zmierzony | 21% | 1 |
| 638 | skinning knife | anim:638 | weapon1h.R | 0.80 | okrągła głowica / mały zysk (5%) | 5% | 323 |
| 639 | short spear | anim:639 | weapon1h.R | 0.59 | roll zmierzony | 12% | 349 |
| 640 | sledge hammer | anim:640 | weapon1h.R | 0.92 | roll zmierzony | 16% | 179 |
| 641 | Long Spear | anim:641 | polearm.L | 0.69 | roll zmierzony | 11% | 171 |
| 642 | war mace | anim:642 | weapon1h.R | 1.55 | roll zmierzony | 19% | 161 |
| 643 | viking sword | anim:643 | weapon1h.R | 0.68 | roll zmierzony | 22% | 348 |
| 644 | war axe | anim:644 | weapon1h.R | 1.03 | okrągła głowica / mały zysk (8%) | 8% | 187 |
| 645 | war fork | anim:645 | weapon1h.R | 1.33 | okrągła głowica / mały zysk (2%) | 2% | 135 |
| 646 | war hammer | anim:646 | axe2h.L | 0.90 | roll zmierzony | 11% | 188 |
| 648 | quarter staff | anim:648 | polearm.L | 0.60 | roll zmierzony | 13% | 179 |
| 649 | bow | anim:649 | bow.L | 1.73 | roll nieokreślony (łuki: brak pomiaru) | -12% | 67 |
| 651 | crossbow | anim:651 | bow.L | 1.60 | roll nieokreślony (łuki: brak pomiaru) | -9% | 238 |
| 653 | axe | anim:653 | axe2h.L | 1.29 | roll zmierzony | 24% | 2 |
| 877 | Spell weaving book | anim4:661 | weapon1h.R | 1.86 | nie broń (book): własna kość |  |  |
| 878 | book of ninjitsu | anim4:662 | weapon1h.R | 2.42 | nie broń (book): własna kość |  |  |
| 879 | book of bushido | anim4:663 | weapon1h.R | 1.82 | nie broń (book): własna kość |  |  |
| 880 | spellbook | anim4:664 | weapon1h.R | 2.17 | nie broń (book): własna kość |  |  |
| 882 | necromancer book | anim4:666 | weapon1h.R | 2.30 | nie broń (book): własna kość |  |  |
| 883 | book of arms | anim4:667 | weapon1h.R | 2.40 | nie broń (book): własna kość |  |  |
| 884 | paladin spellbook | anim4:668 | weapon1h.R | 2.27 | nie broń (book): własna kość |  |  |
| 888 | (bez nazwy) | anim4:670 | bow.L | 3.27 | linia klasy słaba (3.3 px): roll niepewny | -7% | 26 |
| 930 | scythe | anim3:930 | polearm.L | 2.15 | okrągła głowica / mały zysk (1%) | 1% | 161 |
| 931 | bone harvester | anim3:931 | weapon1h.R | 1.39 | roll zmierzony | 11% | 185 |
| 932 | scepter | anim3:932 | weapon1h.R | 0.85 | okrągła głowica / mały zysk (4%) | 4% | 341 |
| 933 | bladed staff | anim3:933 | polearm.L | 2.07 | okrągła głowica / mały zysk (1%) | 1% | 338 |
| 934 | pike | anim3:934 | polearm.L | 1.85 | okrągła głowica / mały zysk (3%) | 3% | 338 |
| 935 | double bladed staff | anim3:935 | polearm.L | 1.62 | okrągła głowica / mały zysk (3%) | 3% | 338 |
| 936 | lance | anim3:936 | weapon1h.R | 0.97 | okrągła głowica / mały zysk (9%) | 9% | 166 |
| 937 | crescent blade | anim3:937 | polearm.L | 1.78 | okrągła głowica / mały zysk (6%) | 6% | 358 |
| 938 | composite bow | anim3:938 | polearm.L | 2.08 | okrągła głowica / mały zysk (7%) | 7% | 159 |
| 939 | repeating crossbow | anim3:939 | bow.L | 2.21 | linia klasy słaba (2.2 px): roll niepewny | 2% | 14 |
| 940 | paladin sword | anim3:940 | weapon1h.R | 0.81 | roll zmierzony | 27% | 182 |
| 950 | Elven Composite Lo | anim5:600 | bow.L | 2.62 | linia klasy słaba (2.6 px): roll niepewny | -4% | 71 |
| 951 | Magical Shortbow | anim5:601 | bow.L | 2.14 | roll nieokreślony (łuki: brak pomiaru) | -9% | 77 |
| 952 | Elven Spellblade | anim5:602 | weapon1h.R | 1.52 | roll zmierzony | 26% | 164 |
| 953 | Assassin Spike | anim5:603 | weapon1h.R | 1.06 | okrągła głowica / mały zysk (7%) | 7% | 154 |
| 954 | Leafblade | anim5:604 | weapon1h.R | 0.86 | roll zmierzony | 15% | 168 |
| 955 | War Cleaver | anim5:605 | weapon1h.R | 1.07 | roll zmierzony | 15% | 15 |
| 956 | Diamond Mace | anim5:606 | weapon1h.R | 1.17 | okrągła głowica / mały zysk (-1%) | -1% | 122 |
| 957 | Wild Staff | anim5:607 | weapon1h.R | 1.53 | okrągła głowica / mały zysk (8%) | 8% | 346 |
| 958 | Rune Blade | anim5:608 | axe2h.L | 3.77 | linia klasy słaba (3.8 px): roll niepewny | -0% | 28 |
| 959 | Radiant Scimitar | anim5:609 | weapon1h.R | 1.21 | roll zmierzony | 15% | 190 |
| 960 | Ornate Axe | anim5:610 | weapon1h.R | 1.55 | roll zmierzony | 29% | 176 |
| 961 | (bez nazwy) | anim5:611 | weapon1h.R | 0.83 | roll zmierzony | 16% | 171 |
| 972 | fishing pole | anim:972 | weapon1h.R | 0.78 | roll zmierzony | 14% | 138 |
| 980 | wand | anim:980 | weapon1h.R | 1.71 | okrągła głowica / mały zysk (8%) | 8% | 358 |
| 981 | wand | anim:981 | weapon1h.R | 1.90 | okrągła głowica / mały zysk (4%) | 4% | 0 |
| 982 | wand | anim:982 | weapon1h.R | 1.82 | okrągła głowica / mały zysk (6%) | 6% | 4 |
| 983 | wand | anim:983 | weapon1h.R | 1.98 | okrągła głowica / mały zysk (4%) | 4% | 357 |
| 984 | spellbook | anim:984 | weapon1h.R | 2.28 | nie broń (book): własna kość |  |  |
| 992 | Order shield | anim:992 | bow.L | 3.11 | nie broń (shield): własna kość |  |  |
| 993 | Chaos shield | anim:993 | bow.L | 3.45 | nie broń (shield): własna kość |  |  |
| 1062 | Bard Spell Book | anim3:941 | weapon1h.R | 4.13 | nie broń (book): własna kość |  |  |
| 1263 | Shield_Vice | anim3:434 | bow.L | 3.97 | nie broń (shield): własna kość |  |  |
| 1265 | Shield_Virtue | anim3:435 | bow.L | 3.93 | nie broń (shield): własna kość |  |  |
| 1486 | Barbed Whip | anim2:556 | weapon1h.R | 2.29 | linia klasy słaba (2.3 px): roll niepewny | 20% | 182 |
| 1515 | Weapon_Bottle | anim3:590 | bow.L | 1.53 | roll nieokreślony (łuki: brak pomiaru) | 30% | 2 |
| 1529 | Shield_Pirate | anim3:604 | bow.L | 3.17 | nie broń (shield): własna kość |  |  |
| 1543 | wand | anim3:618 | bow.L | 1.69 | roll nieokreślony (łuki: brak pomiaru) | 6% | 215 |
| 1544 | Lantern_on | anim3:619 | bow.L | 2.61 | nie broń (light): własna kość |  |  |
| 1545 | Lantern_off | anim3:620 | bow.L | 2.51 | nie broń (light): własna kość |  |  |
| 1550 | Orb | anim3:625 | bow.L | 2.83 | nie broń (light): własna kość |  |  |
| 1554 | candycane_staff | anim3:629 | weapon1h.R | 3.29 | linia klasy słaba (3.3 px): roll niepewny | 8% | 343 |
| 1571 | Shield_Hildebrandt | anim3:646 | bow.L | 3.34 | nie broń (shield): własna kość |  |  |
