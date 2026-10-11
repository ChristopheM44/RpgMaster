# Refonte visuelle des cartes — analyse, cible, plan (2026-10-11)

> Demande : « reprendre tous les graphismes des cartes, les indicateurs visuels,
> corriger les transitions entre zones ; escaliers dans le bon sens ».
> Ce document est le livrable d'analyse. Aucun code moteur n'a été modifié.
> Maquette interactive de la cible : https://claude.ai/artifact/6a1JMFX7qkhHBTchqB8Tnk
> (Three.js r184 + modèles du dépôt ; trémie, escalier montant, transition Jardin ↔ Caveau,
> désert de jour, vocabulaire d'indicateurs, région et ville cibles).

## 1. Constat (vérifié live le 2026-10-11 sur 3 sessions réelles)

| Session / scène | Ce qu'on voit | Cause racine |
|---|---|---|
| *Le Sanctuaire du Crépuscule* — « Le Jardin pétrifié » (dungeon, torchlit) | Boîte de briques vide, damier, « arbre pétrifié » = **caisses**, « fontaine tarie » = **tonneau**, danger = disque rouge plat, escalier « S'enfoncer vers le Caveau » rendu **montant** et penché hors du mur | voir §1.1 à §1.4 |
| *Le Mirage du Sable d'Or* — « L'Entrée de la Vallée aride » (desert, **day**) | Plateau quasi noir flottant dans le vide, 1 cactus, 2 rochers, sorties = anneaux dorés, aucun chemin ne sort de la carte | §1.2, §1.3 |
| *L'île* — « Bibliothèque de Dragon's Rest » | Salle vide bleu nuit : **aucune étagère** | §1.4 |
| Onglet Région | Carré de 360 px, étiquettes **qui se chevauchent**, nœuds = pastilles sans type | §1.5 |
| Onglet Ville | 3 rectangles vides sans nom | §1.5 |

### 1.1 Escaliers et transitions (bugs de correction)

1. **Un escalier « down » est un escalier « up » retourné.** `ProceduralFactory` (case `stairs`) et
   `stairs.glb` ne savent que *monter au-dessus du sol* ; `stairsRotationY`
   (`engine3d/layers/ElementsLayer.ts:334`) traite `down` en tournant la volée de 180°.
   Résultat : une rampe dont le haut pointe vers la salle. Une descente doit être une
   **trémie creusée dans le sol** (marches sous y=0).
2. **Les jetons sont surélevés sur une descente.** `buildElevationByCell`
   (`engine3d/adapters/sceneAdapter.ts:189`) applique `elevation + height` (+0,4 m) à tout
   escalier, quel que soit `verticalDirection`.
3. **Inférence d'orientation par sous-chaîne** (`backend/app/services/local_map_service.py`,
   `_infer_exit_facing` / `_infer_vertical_direction`) — sortie mesurée le 2026-10-11 :

   | Sortie (position, texte) | facing obtenu | vertical obtenu | Attendu |
   |---|---|---|---|
   | bord N, « Le passage **est** étroit » | `east` | level | north |
   | bord O, « Escalier vers le **haut** » | `north` | up | west / up |
   | bord E, « Escalier vers le **bas** » | `south` | down | east / down |
   | bord S, « **Remonter** à la surface… par les **égouts** » | south | `down` | south / **up** |
   | bord N, « **Bas**sin de **bas**alte » | `south` | `down` | north / level |
   | bord N, « Sentier fore**st**ier, chemin qui r**est**e » | `east` | level | north |

   Le texte est testé **avant** la position de bord ; « est » matche *c'est / reste / forestier* ;
   « haut/bas » (vertical) sont lus comme nord/sud ; les mots « descente » sont testés avant
   « montée ». Comme `_edge_access_geometry` place l'élément selon `facing`, l'escalier peut
   atterrir **sur un autre mur que la sortie**.
4. **Aucune continuité spatiale entre deux scènes.** On sort par le sud ou on descend un escalier :
   la scène suivante ne sait pas d'où l'on vient. `_minimal_scene_layout_action`
   (`game/action_pipeline.py:1315`) pose le retour en dur à `(6,11)` ; les autres producteurs
   (LLM `scene_layout`, `scene_builder` via `compose_scene`, `dungeon_generator`) n'ont aucune règle.
   Point de convergence unique : `GMResponseExecutor._apply_scene_layout`
   (`game/gm_response_executor.py:1100`), qui dispose déjà de `old_scene`.
5. **Changement de scène = coupe sèche** : `SceneRuntime.update` reconstruit dès que
   `frameKey` change, sans animation de sortie ni d'arrivée.

### 1.2 Lumière et sol (cause n°1 du rendu « sombre et terne »)

`BIOME_3D` (`engine3d/core/ThemeProvider.ts`) a été transposé depuis la palette **UI** sombre :
le sable du désert vaut `#1e1810`, la forêt `#16201a`, les plaines `#181c14` (albédo 2 à 8 %).
Même en plein jour, le sol est quasi noir ; les passes précédentes ont compensé par
l'exposition, l'ambient et un curseur de luminosité, sans traiter la cause.
S'y ajoutent : sol = un plan uni + damier, plateau qui **flotte dans le vide** (rien au-delà
de la grille), murs pleine hauteur côté caméra qui masquent l'intérieur.

### 1.3 Indicateurs

Vocabulaire hétérogène : anneaux (sorties), disques rouges (dangers), loupes en billboard
(indices), glyphes canvas basse résolution, légende codée (`E1`, `L12`, `D2`). Les sorties ne
montrent ni direction ni destination ; rien ne distingue « voyager » de « monter/descendre ».

### 1.4 Habillage (props)

Le backend choisit l'`asset_key` **au hasard dans le pack du thème** sans regarder le nom
(`engine/scene_builder.py:176` `_pick_asset`, `engine/theme_packs.py`) ; le frontend honore
`modelKey` avant sa propre heuristique. D'où « Arbre pétrifié » → `prop/crates_stacked`.
Densité très faible ; aucun habillage par type de lieu (bibliothèque sans étagères).

### 1.5 Cartes 2D

Région : cadre fixe 640×580 réduit à un carré, placement d'étiquettes sans anti-collision,
pas d'iconographie par type de nœud. Ville : bâtiments anonymes, pas de rues lisibles,
pas de position du groupe.

## 2. Cible (voir maquette)

- **Scène 3D** : sol à albédo naturaliste (dalles instanciées en intérieur, texture
  procédurale en extérieur), **terrain qui se prolonge au-delà de la grille** et se fond dans
  la brume, murs **en coupe** (côté caméra abaissés), ambiance portée par la lumière et la
  brume plutôt que par un sol noir. Grille masquée en exploration (survol de case seulement),
  affichée en combat.
- **Escaliers** : `up` = volée qui monte vers une ouverture du mur ; `down` = trémie creusée
  dans le sol, marches qui s'enfoncent, fond sombre et lueur. Le sens se lit sans légende.
- **Transitions** : la sortie empruntée est mémorisée ; la scène d'arrivée a une sortie
  retour **sur le bord opposé** (sortie est → arrivée ouest) et au **sens vertical inversé**
  (descendre → arriver par un escalier qui remonte), le groupe apparaît à côté. Animation :
  les jetons marchent vers la sortie, travelling caméra, fondu, puis arrivée cadrée sur
  l'accès d'entrée, bandeau « Vous arrivez de… ».
- **Indicateurs** : un vocabulaire unique (tableau dans la maquette) — anneaux de socle par
  rôle, losanges flottants pour les POI, décalques au sol pour les dangers, chevrons + bannière
  de destination pour les sorties (→ voyager, ↑ monter, ↓ descendre), étiquettes en DOM
  (polices du design system, nettes à tout zoom).
- **Région / Ville** : carte plein cadre sur parchemin sombre, pictos par type de lieu,
  étiquettes anti-collision, routes parcourue / connue / rumeur, échelle en jours de marche ;
  ville avec quartiers, rues, bâtiments nommés et position du groupe.

## 3. Plan

Chaque lot se valide **en live** sur les 3 mêmes scènes (Jardin pétrifié, Vallée aride,
Bibliothèque) avec captures avant/après, plus les tests existants (backend `pytest`,
frontend `vitest` + `type-check`).

### Lot 0 — Banc d'essai visuel (S)
- Fixtures figées des 3 scènes réelles + une scène « escaliers » (up/down sur les 4 bords).
- Route dev `/dev/map-lab` montant `Scene3DCanvas` sur ces fixtures, sans backend ni LLM.
- *Critère* : captures reproductibles à l'identique entre deux runs.

### Lot 1 — Escaliers et transitions (M, backend + frontend) — priorité demandée
1. Inférence : position de bord **d'abord** ; regex à **mots entiers** ; cardinal uniquement
   via nord/sud/est/ouest ; haut/bas → vertical seulement ; « remonter / surface » prioritaire
   sur « égout / cave » ; test paramétré avec le tableau §1.1.3.
2. Géométrie : `down` = trémie (cellules de sol retirées, marches sous y=0, parois, fond
   sombre) ; `up` = volée vers une ouverture de mur ; orientation dérivée du **bord** de la
   sortie. `buildElevationByCell` : une descente ne surélève plus (palier à 0, marches négatives).
3. Continuité : `last_exit_used {scene_id, exit_id, facing, vertical_direction}` posé au
   voyage (`travel_detection` / `action_pipeline`) ; normalisation dans `_apply_scene_layout`
   qui garantit la sortie retour (bord opposé, vertical inversé, `leads_to` = scène quittée)
   et place `party_positions` à côté. Supprimer le `(6,11)` en dur.
   Voyage en texte libre (« nous partons pour les ruines », aucun clic de sortie) : retrouver la
   sortie via `leads_to`/libellé dans les sorties de l'ancienne scène ; à défaut, aucune
   contrainte de bord (à vérifier dans `travel_detection`).
4. Animation : sortie (marche des jetons + travelling 400 ms + fondu 250 ms) puis arrivée
   cadrée sur l'accès d'entrée ; `prefers-reduced-motion` → simple fondu.
- *Critère* : 0 escalier à contresens sur la scène de test ; descendre puis remonter ramène
  au même accès ; tests backend sur les 4 producteurs de layout.

### Lot 2 — Lumière, sol, terrain (M, frontend + miroir des défauts backend)
- Recalage des 11 biomes en albédo naturaliste ; l'ambiance sombre passe par lumière/brume.
- Sol : dalles instanciées (donjon/ville/caverne), texture procédurale seedée (extérieurs).
- Terrain prolongé (anneau 3× la grille, relief/dunes/végétation hors jeu) fondu dans la brume.
- Murs en coupe selon l'azimut caméra.
- *Critère* : désert de jour lisible au curseur de luminosité neutre (1.0) ; aucune scène
  ne « flotte » ; fps ≥ 50 sur la machine de dev.

### Lot 3 — Langage visuel des indicateurs (M, frontend)
- Table de vocabulaire unique (maquette §3) implémentée dans `TokenLayer` / `OverlayLayer`.
- Étiquettes DOM projetées (remplacent les sprites canvas), anti-chevauchement simple.
- Dangers en décalque, sorties en chevrons + bannière, POI en losange avec état découvert.
- Légende en clair (libellés, plus de `E1/L12`).
- *Critère* : un joueur identifie sorties, dangers et interlocuteurs sans légende (test à 3).

### Lot 4 — Habillage sémantique (M, backend + frontend)
- `scene_builder._pick_asset` → choix par mots-clés (catalogue partagé front/back) ;
  pas de correspondance → **pas d'`asset_key`** (procédural neutre plutôt qu'un mauvais modèle).
- Variantes matériau (`tint` : pierre pétrifiée, bois mort, sable) pour réutiliser les modèles.
- Habillage par type de lieu (bibliothèque : étagères le long des murs + tables…).
- Créatures (pack CC0 Quaternius) : lot séparé, déjà identifié.
- *Critère* : 0 contresens sémantique sur les 3 scènes de test.

### Lot 5 — Cartes Région et Ville (M, frontend + légère extension backend du typage des nœuds)
- Région plein cadre, pictos par type, étiquettes anti-collision, routes typées, brouillard,
  échelle, centrage sur le nœud courant.
- Ville : quartiers, rues, bâtiments nommés + pictos, position du groupe, sorties de ville.
- *Critère* : aucune étiquette chevauchante sur la région de la session « Sanctuaire ».

## 4. Décisions (validées le 2026-10-11)

1. Étiquettes en **DOM** projeté (nettes, design system) — pas de sprites WebGL.
2. Post-traitement (SSAO / outline) : **hors plan** ; à rouvrir après le Lot 2.
3. Murs en coupe **automatiques** selon l'azimut caméra.

## 5. Avancement

### Lot 0 — LIVRÉ (branche `map-refonte-lot0-1`)
- `backend/scripts/export_map_lab_fixtures.py` → `frontend/src/dev/mapLab/fixtures.generated.ts` :
  Jardin pétrifié, Vallée aride, Bibliothèque (figés depuis la base), Caveau du Codex
  (synthétique, arrivée via la continuité), Banc escaliers (un accès par bord, pipeline réel).
- Route `/dev/map-lab` (`views/dev/MapLabView.vue`), absente du build de production
  (vérifié) ; `?scene=<id>` pour un lien direct ; changer de scène rejoue la transition.

### Lot 1 — LIVRÉ
1. Inférence (`local_map_service`) : regex à mots entiers, position de bord d'abord,
   « est » seulement sous la forme « l'est »/« plein est », haut/bas → vertical seulement,
   verbes (monter/descendre) avant lieux (égout, surface). `test_exit_orientation.py` (21 cas).
2. Géométrie (frontend) : escaliers **100 % procéduraux** (`adapters/stairs.ts` +
   `ProceduralFactory`) ; montée vers `facing` avec palier ; descente = trémie (cellules
   retirées du sol via `GroundSpec.holes`, marches sous le sol, pente ~30° pour rester lisible
   depuis la caméra par défaut). `buildElevationByCell` : jeton sur la 1re marche (négatif).
   Jupe sombre sous le plateau. `stairs.glb` n'est plus utilisé.
3. Continuité (`services/scene_continuity.py`, branché dans `_apply_scene_layout`) :
   sortie retour sur le bord opposé, sens vertical inversé, groupe placé à côté,
   `layout.arrival` ; départ mémorisé au voyage (`pending_departure`, hors payload public) ;
   l'exécuteur conserve désormais `facing`/`vertical_direction`/`kind` des sorties.
4. Transition (`Scene3DCanvas`) : marche des héros vers la sortie + travelling, fondu 260 ms,
   arrivée cadrée sur l'accès puis recul, bandeau « Arrivée » ; jetons recréés au
   changement de scène ; `prefers-reduced-motion` → fondu seul.

Durcissements après relecture : un accès de BORD mène toujours vers son bord (valeur
stockée incohérente ignorée, back et front) ; quand la continuité déplace une sortie d'un
layout déjà enrichi (salles de donjon), l'ancien accès et les murs d'enceinte auto sont
retirés puis reconstruits (pas d'orphelin ni de brèche) ; `pending_departure` est oublié à
toute action sans voyage. Tests : aller-retour Jardin → Caveau → Jardin (retour sur
`exit_2`, sud, descente), scène de repli, salles de donjon, ordonnancement de la transition
(`Scene3DCanvas.test.ts`, minuteries simulées). Scan de la base : aucune orientation
d'accès erronée dans les scènes sauvegardées.

Vérifié : backend 2126 ✓, frontend 172 ✓, type-check ✓, build ✓ (banc absent du bundle),
rendu live (banc + écran de jeu réel « Jardin pétrifié »).

Limites connues : l'ouverture du mur au-dessus d'une trémie reste pleine hauteur (porte) ;
l'anneau doré de sortie recouvre encore la trémie (traité au Lot 3) ; les scènes déjà en
base ne gagnent la continuité qu'au prochain déplacement.
