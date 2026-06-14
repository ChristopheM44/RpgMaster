# Catalogue des modèles 3D — où tout consulter

> Le **catalogue + les règles de mapping** font foi dans
> [`src/engine3d/assets/manifest.ts`](../../src/engine3d/assets/manifest.ts).
> Ce fichier en est le résumé lisible. Les `.glb` servis vivent ici, sous
> `public/models/`. Sources & licences (CC0) : [`CREDITS.md`](./CREDITS.md).
> Un test (`engine3d/__tests__/manifest.test.ts`) garantit que **chaque entrée du
> manifest a son fichier** sur le disque (anti-régression).

**État : 58 modèles, ~4,7 Mo** — 5 aventuriers, 4 squelettes, 22 donjon,
27 nature (16 Kenney + 11 KayKit Forest).

## Comment un modèle est choisi (3 familles)

| Famille | Couche | Fonction de mapping | Repli |
|---|---|---|---|
| Personnages (héros / PNJ / ennemis) | `TokenLayer` | `modelForClass` / `modelForNpc` / `modelForMonster` | pion (`buildPawn`) |
| Éléments (mur, porte, mobilier, décor…) | `ElementsLayer` | `modelForElement` (kind + mots-clés) | volume procédural |
| POI (marqueurs) | `TokenLayer.buildPoi` | *(aucun modèle — icône flottante)* | — |

---

## Personnages — `adventurers/`
KayKit Adventurers (riggés, anim Idle/Walk).

| Modèle | Classes (`modelForClass`) | Mots-clés PNJ (`modelForNpc`) |
|---|---|---|
| `knight` | fighter, paladin, cleric | garde, soldat, chevalier, capitaine, paladin, officier, guerrier… |
| `barbarian` | barbarian, monk | brute, colosse, forgeron, gladiateur, bûcheron… |
| `mage` | wizard, sorcerer, warlock | mage, sorcier, prêtre, alchimiste, oracle, guérisseur… |
| `rogue` | rogue, bard | marchand, aubergiste, villageois, noble, dame, femme, vieux, barde… |
| `rogue_hooded` | ranger, druid | encapuchonné, voleur, assassin, chasseur, rôdeur, moine, cultiste… |

**PNJ sans rôle reconnaissable → défaut « quidam » déterministe** (hash) parmi
`rogue` / `rogue_hooded` — **plus jamais de pion** pour un PNJ. (cf. `COMMONER_MODELS`.)

## Monstres — `skeletons/`
KayKit Skeletons (riggés). `modelForMonster` (le rôle de lanceur prime sur l'espèce) :

| Modèle | Déclencheurs |
|---|---|
| `skeleton_mage` | liche, nécromant, chamane, cultiste, squelette mage |
| `skeleton_warrior` | squelette, mort-vivant, orc, ogre, troll, gnoll |
| `skeleton_minion` | gobelin, kobold, diablotin |
| `skeleton_rogue` | assassin, éclaireur, spectre, ombre |

> **Bêtes & monstres non-humanoïdes (loup, araignée, dragon…) → pion** : aucun
> modèle de créature n'existe encore (voir « Ajouter des modèles » → Phase créatures).

## Props de donjon — `dungeon/`
KayKit Dungeon Remastered. `modelForElement` (kind `furniture`/`cover`/`decor`/`light`/`door`) :

| Modèle | Mots-clés / règle |
|---|---|
| `table_medium` / `table_long` / `table_small` | table, comptoir, autel, établi — **variante selon l'empreinte** |
| `chair` / `stool` | chaise, banc, fauteuil, trône / tabouret |
| `barrel_small` / `barrel_large` | tonneau, baril — variante selon l'empreinte |
| `keg`, `crates_stacked` | keg / caisse, cageot (+ repli `cover`) |
| `chest` / `chest_gold` | coffre, malle / **coffre doré, au trésor, royal** |
| `shelf_large` / `shelf_small` | étagère, bibliothèque, armoire — variante empreinte |
| `bed_frame` | lit, couchette, paillasse, grabat |
| `pillar` | pilier, colonne, poteau |
| `rubble_large` | gravats, débris, éboulis |
| `door` (`wall_doorway`) | kind `door` |
| `torch_lit` / `torch_mounted` | torche, brasero, flambeau / torche **murale**, applique |
| `stairs` | *(non utilisé : les escaliers sont procéduraux, intégrés à l'élévation)* |

## Nature & décor — `nature/`
**KayKit Forest** (`nature/forest/`, scatter tempéré) + **Kenney Nature Kit** (reste — pas
d'équivalent KayKit Forest). Scatter (`SCATTER_MODELS`, semé par biome) + props de décor :

- **Scatter KayKit Forest** (`nature/forest/`) : `tree_pine_a/b` (`Tree_4_A`/`Tree_4_B`),
  `tree_dark` (`Tree_Bare_1_A`), `bush`/`bush_large` (`Bush_1_A`/`Bush_2_A`),
  `grass_large`/`grass_small` (`Grass_1_A`/`Grass_2_A`), `rock_large_a/b`
  (`Rock_1_A`/`Rock_3_A`), `rock_small_a/b` (`Rock_2_A`/`Rock_2_B`).
- **Scatter Kenney** : `tree_palm_tall/bend`, `flower_purple/yellow`, `mushroom_red/tan`,
  `stump`, `log`, `cactus_short/tall`, `lily`.
- **Props de décor** (`modelForElement`) :

| Modèle | Mots-clés |
|---|---|
| `rock_large_a` (KayKit `Rock_1_A`) | rocher, caillou, boulder, stalagmite, **érodé** (avant le repli `cover`) |
| `campfire` | feu de camp, foyer, bivouac, brasier (+ kind `light` → vraie lumière) |
| `tent` | tente, pavillon, abri, campement |
| `pot` | jarre, vase, amphore, poterie, cruche |
| `statue` ¹ | statue, idole, effigie, buste, monument |
| `obelisk` ¹ | obélisque, stèle, menhir, monolithe |

¹ **Props verticaux** : instanciés à une **hauteur intrinsèque** (`PROP_TARGET_HEIGHT_M`,
statue 2,2 m / obélisque 2,8 m) au lieu d'être ajustés à l'empreinte — sinon écrasés
par le plafond dérivé du défaut `decor` (0,6 m). C'est le mécanisme à réutiliser pour
mettre à l'échelle les futures créatures (rat ↔ dragon).

> `wall.glb`, `wall_corner.glb` sont présents mais **non mappés** : les murs sont rendus
> de façon procédurale (creux pour la lisibilité, cf. moteur).
>
> `nature/forest/*.gltf` sont au format glTF + `.bin` + texture partagée `forest_texture.png`
> (seul format livré par ce pack) au lieu du `.glb` unique habituel — `GLTFLoader` résout les
> fichiers liés par URI relative, donc aucune conversion n'a été nécessaire (cf. `CREDITS.md`).

---

## Ajouter des modèles

Tout passe par **`scripts/fetch_3d_assets.sh`** (script de maintenance, pas un build) :
il télécharge les packs CC0, extrait, et copie le sous-ensemble utilisé. Pour ajouter
un modèle : décommenter/ajouter une ligne `copy_model`, relancer le script, puis ajouter
l'entrée dans `MODEL_MANIFEST` + son mot-clé.

**Réserve disponible : ~530 modèles dans les packs sources, ~58 utilisés.** Les packs
complets se re-téléchargent dans le cache (`/tmp/rpgmaster_3d_packs/` par défaut). Pistes
à fort intérêt encore non stagées : bannières, bougies/candélabres, coffres-malles,
ponts, clôtures, falaises (donjon/nature) ; et surtout — **créatures** (bêtes & monstres),
absentes des packs KayKit/Kenney : source CC0 à évaluer = **Quaternius** (animaux & monstres
animés), avec une revue de cohérence de style (KayKit est low-poly « chunky »).

Les personnages (`adventurers/`, `skeletons/`, futur `creatures/`) sont **allégés** par
`scripts/prune_3d_animations.mjs` (ne garde que Idle/Walk/Death) — penser à y ajouter tout
nouveau dossier de personnages animés.
