# Analyse de fidélité — Chronique des Ruines Blanches (4ᵉ terrain, build récent)

> **Date** : 2026-06-04 · **Code lu** : `main` (working tree courant)
> **Objet** : confronter une **4ᵉ chronique réelle** (donjon « Les Ruines Blanches → Crypte du Cœur ») au code, distinguer ce qui **tient** de ce qui **casse encore**, et **amender le plan**. Aucune implémentation ici.
> **Particularité forte** : cette partie **n'a pas été jouée sur ce poste** (DB locale indisponible) — l'analyse se fonde sur le **texte de la chronique + lecture de code**, pas sur un état de session inspectable. **Build confirmé par l'utilisateur = récent** (inclut A/B/D/G/N1/E2-cheap des 3-4 juin) : les écarts ci-dessous sont donc des **trous live dans des lots livrés**, pas des comportements d'avant-correctif.
> **Composition de table** : Thorvald = **PC humain** (marqueur ◉, fautes de frappe, tranche les décisions) ; Elara / Shade / Solana = **compagnons IA** (◈). **Aucun PNJ en scène.**
> **Suite de** : [`reprise-fidelite-s3-2026-06.md`](reprise-fidelite-s3-2026-06.md), [`analyse-fidelite-dialogue-oasis-s3-2026-06.md`](analyse-fidelite-dialogue-oasis-s3-2026-06.md), [`analyse-croisee-fidelite-2026-06.md`](analyse-croisee-fidelite-2026-06.md).

## Légende des statuts

- 🟢 **Progrès confirmé** — un correctif antérieur tient, vérifié sur cette chronique.
- ✅ **Tracé au code** — symptôme suivi jusqu'à un mécanisme précis.
- 🔶 **Fork / hypothèse** — non clos par la seule lecture de code (ici, parce que la session n'est pas inspectable) ; à trancher par replay ou inspection d'une session équivalente.
- 🧩 **Décision de design** — déjà ouverte au plan, ré-éclairée par cette chronique.

---

## 1. Ce qui fonctionne maintenant (crédit avant critique)

Cette chronique **valide en conditions réelles** plusieurs acquis, et **désamorce en partie le doute central** (N3, « construction de l'aventure »).

- 🟢 **N3 ne se reproduit PAS — l'objectif a une route jouable ET une destination atteignable.** Le donjon enchaîne une vraie colonne vertébrale : Parvis → Arche Principale → Hall des Échos → (passage secret **ou** Cœur Violet) → Boyaux de Pierre → Crypte du Cœur → **Faille Planaire = la source, effectivement atteinte**. Contraste net avec le cul-de-sac de l'Oasis (la fissure pleine d'eau, sans nulle part où aller). Le doute « gros doute sur la construction de l'aventure » **ne se rejoue pas ici**. *(Cause de ce succès = 🔶 fork, cf. §3.1.)*
- 🟢 **Succès → prise jouable (l'objectif de F atteint organiquement).** Le **20** de Perception de Thorvald n'a pas produit qu'une jolie prose : il a surfacé un **passage secret** = une **nouvelle route réelle** + un **vrai dilemme** (passage prudent vs Cœur direct). Les compagnons débattent, l'humain tranche. C'est exactement ce que visait **F-visible** — obtenu ici sans panneau cliquable, par une prose nette.
- 🟢 **Compagnons IA crédibles ET déférents.** Voix distinctes (Elara = arcanes/érudition, Solana = foi martiale fonceuse, Shade = pragmatisme impatient). Surtout : ils **conseillent** mais **renvoient la décision à l'humain** — le MJ écrit explicitement « *le groupe attend désormais son signal pour trancher* ». C'est la dynamique de table idéale (le spotlight/E2-cheap tient).
- 🟢 **Pas de roll-spam / pas de saturation (vecteur E1 non déclenché).** Seuls **Thorvald (3 jets)** et **Elara (2 jets)** lancent, sur des **objets distincts** et des **compétences distinctes** ; Shade et Solana poussent l'action **sans jamais lancer**. Aucun « tout le monde enchaîne sur le même objet ». *(NB : favorable au scénario — 1 humain + 3 IA avec un enquêteur clair ; n'invalide pas E1 en général.)*
- 🟢 **Bonne facture d'aventure (Tchekhov posés).** La stèle (« *ce qui a été brisé ne peut être recousu que par le sang* » = présage de rituel/sacrifice) et la **relique qui résonne avec le Cœur** (artefact-boussole = une « clé » naturelle vers la source) sont des fusils de Tchekhov bien plantés — l'esprit même de « Forge-spine » émergeant tout seul.
- 🟢 **Ouverture : QUI + POURQUOI mieux ancrés que l'Oasis (progrès N6).** « *Votre employeur a été clair : pénétrer dans ces vestiges, identifier l'origine de l'énergie corruptrice… et récupérer tout artefact de valeur.* » L'**origine de la mission** (un commanditaire) et l'**objectif** sont **présents** — le trou N6 de l'Oasis (origine sous-surfacée) est nettement réduit. *(Résidu : cf. R4.)*

> Constat net : sur le **fond d'aventure** (le « doute »), cette chronique est **rassurante**. Les écarts ci-dessous sont des **coutures** (attribution, inventaire, arbitrage du monde) et un **résidu d'ouverture**, pas un effondrement de structure.

---

## 2. Constats tracés au code (build récent → trous live)

### R1 — Attribution de jet cassée sur le chemin **clic-POI** (« Système » / « — ») — famille **Q7**, **trou live dans le lot G** ✅

**Symptôme (relevé dans les en-têtes de jet)** :

| Jet | Action de Thorvald | Attribution affichée | Modificateur |
|---|---|---|---|
| 1 | « Je cherche à en savoir plus sur : *(passereau)* » | **Système** | 17 **+ −1** |
| 3 | « J'examine zone instable sans m'y engager. » | **—** (vide) | 17 **+ −1** |
| 4 | « je fouille la piece, a la recherche… » *(texte libre tapé main)* | **Thorvald** ✓ | 20 + 0 |

Le mod **−1 INT** des jets 1 et 3 = celui de Thorvald (≠ le +2 d'Elara) : ce sont **ses** jets, **mal attribués**. Le facteur distinctif : jets 1 et 3 = actions **clic-POI / interaction de scène** ; jet 4 = **texte libre**. C'est la **famille Q7** — que le **lot G** prétend close avec invariant testé (« *un ROLL_RESULT subi par un PJ n'est jamais attribué à Système* »).

**Cause racine, tracée de bout en bout** :

1. Le chemin clic-POI résout le jet via `_resolve_scene_interaction_roll` ([action_pipeline.py:1066](../backend/app/game/action_pipeline.py)) → `execute_roll_request`, qui **garantit bien** un `character_name` non vide ([roll_executor.py:100-103](../backend/app/game/roll_executor.py) — le **fix G**).
2. **Mais** l'event finalement **publié et persisté** n'est pas ce payload : c'est `roll_evt = _enrich_roll_event(_normalize_roll_event(roll_results), …)` ([action_pipeline.py:432-445](../backend/app/game/action_pipeline.py)).
3. `_normalize_roll_event`, branche `skill_check`, **reconstruit** le payload en conservant `character_id` ([action_mechanics.py:145](../backend/app/game/action_mechanics.py)) mais **en laissant tomber `character_name`** ([action_mechanics.py:132-147](../backend/app/game/action_mechanics.py)).
4. `_enrich_roll_event` pose `actor_name` mais **n'écrit jamais `character_name`** ([action_pipeline.py:1258-1262](../backend/app/game/action_pipeline.py)).
5. Résultat : le ROLL_RESULT du chemin clic-POI **n'a plus de `character_name`**. Le rendu de l'acteur lit `character_name` **en premier**, jamais `actor_name` :
   - **persist** → `persist_roll_result` retombe sur le speaker **« Système »** ([message_service.py:76](../backend/app/services/message_service.py) : `speaker = character_name or "Système"`).
   - **live** → l'adaptateur fait `who: r.character_name ?? entry.speaker ?? '—'` ([narrative.ts:49](../frontend/src/stores/narrative.ts)), affiché par [RollCard.vue:25](../frontend/src/components/exploration/RollCard.vue) (`DiceRollResult.vue` masque le nom si absent, [:14](../frontend/src/components/narrative/DiceRollResult.vue)).

   **« — » (jet 3) vs « Système » (jet 1) = même cause, deux rendus** : en **live**, `character_name` ET `speaker` absents → `'—'` ; au **reload**, la persistance a backfillé `speaker="Système"` → `character_name` absent + `speaker="Système"` → « Système ». **Porter `character_name` répare les deux** (il précède `speaker` dans `who`, et `message_service:76` le lit directement).

**Pourquoi le texte libre (jet 4) est correct** : il ne pré-résout pas via la scène — le MJ émet un `roll_request` exécuté **et publié** par `gm_response_executor` ([:167-174](../backend/app/game/gm_response_executor.py)) qui **publie directement le payload d'`execute_roll_request`**, **sans passer par `_normalize_roll_event`/`_enrich_roll_event`** (`character_name` intact) → « Thorvald ». Le discriminant est donc bien **quel chemin publie** (GM-roll_request brut vs scène pré-résolue re-normalisée), **pas** le `type` du jet. *(Les deux maillons — texte-libre hors normalize, et `who ← character_name` — sont vérifiés par lecture de code.)*

**Conclusion** : le lot G a colmaté la **source** (`execute_roll_request`) et l'espacement UI, mais **pas** le **round-trip `_normalize_roll_event` → `_enrich_roll_event`** sur une interaction de scène. L'invariant de test de G ne couvrait pas ce chemin.

**Fix (déterministe, à coder) — complet pour les deux rendus** : (a) propager `character_name` dans `_normalize_roll_event` (branche `skill_check` : `"character_name": raw.get("character_name")`) **et/ou** (b) le restaurer dans `_enrich_roll_event` (`enriched.setdefault("character_name", enriched.get("actor_name") or actor_name)`). Test de non-régression : un jet d'**interaction de scène** persiste un speaker = nom du PJ, **jamais** « Système » ni vide. *(Routage de l'acteur OK : le mod −1 = celui de Thorvald prouve qu'`execute_roll_request` a bien utilisé ses stats **et** posé son nom — donc `actor_id` était transmis et le fallback `roll_executor:50-55` n'est pas intervenu ; le **seul** défaut est le `character_name` jeté en aval.)*

**Rattachement backlog** : **G-bis** (généralisation de Q7 au chemin interaction-de-scène).

---

### R2 — Relique **ramassée sans déclaration** du joueur humain — **trou live dans E2-cheap + :116** ✅

**Symptôme** : Thorvald **examine** la « Relique brisée » (action déclarée). Puis **Shade (IA)** suggère « *ramasse ce truc si ça peut nous servir* ». Thorvald, lui, ne déclare **que** « Descente vers la Crypte. ». Au tour suivant, la relique est **dans sa besace** sans qu'il l'ait jamais ramassée : « *Le fragment de marbre dans la besace de Thorvald se met à vibrer…* ». Le MJ a donc **inféré une action signifiante du PC humain** (acquérir un artefact) **à partir d'une suggestion de compagnon**.

**Tracé** — **deux** règles existantes violées :
- [gm_narrate.txt:111](../backend/app/agents/prompts/gm_narrate.txt) (E2-cheap) : « *N'invente jamais [les] actions, décisions ou répliques [du PC humain]… Une action qu'un joueur humain a explicitement déclarée… se narre normalement.* » Ramasser la relique **n'a pas été déclaré** par Thorvald.
- [gm_narrate.txt:116](../backend/app/agents/prompts/gm_narrate.txt) : « *Ne transforme jamais « j'examine » en « je pose la main » ; demande une confirmation ou attends une action `use/custom`.* » L'examen est devenu une **prise en main + acquisition**.

Ce n'est pas un nouveau sous-système : c'est une **non-conformité** à deux consignes déjà en place. La suggestion d'un **compagnon** semble avoir suffi au modèle pour franchir la barrière d'agentivité du PC humain.

**Fix (prompt, cheap)** : durcir :111 pour couvrir explicitement l'**inventaire/acquisition** — « *ne place jamais un objet dans l'inventaire d'un PC humain, et ne narre jamais qu'il ramasse/empoche un objet, sans action déclarée par lui (ou un `loot_grant` canonique) — la suggestion d'un compagnon ne vaut pas action du PC humain.* »

**Rattachement backlog** : **E2-cheap (renfort)**.

---

### R3 — « L'entrée a disparu » : **assertion-monde non arbitrée** par le MJ, ratifiée par un compagnon ✅

**Symptôme** : Thorvald (humain) signale « *je ne vois plus l'arche par laquelle nous sommes arrivé si nous voulons revenir sur nos pas* ». **Shade (IA)** ratifie aussitôt comme un fait — « *L'entrée a disparu ? Parfait…* » — et le **MJ n'arbitre jamais** : l'arche est-elle réellement scellée (un *beat* : on est piégés) ou Thorvald a-t-il juste perdu l'orientation ? La question concrète « **peut-on faire demi-tour ?** » reçoit un **haussement d'épaules narratif**.

**Tracé** : c'est la règle **INTENTION ≠ FAIT** ([gm_narrate.txt:92](../backend/app/agents/prompts/gm_narrate.txt)) — une assertion du joueur sur l'**état du monde** (« l'entrée n'est plus là ») doit être **arbitrée** par le MJ (confirmer ou infirmer), pas accordée par défaut. Ici, c'est un **compagnon** qui a tranché à la place du monde, et le MJ a enchaîné. Moins « suivi spatial » que **assertion-monde non arbitrée + IA qui parle pour le monde**.

**Enjeu de fidélité** : « peut-on battre en retraite ? » touche directement l'**agentivité** ; le laisser ambigu (et délégué à un compagnon) érode la confiance dans la cohérence du lieu.

**Fix (prompt, cheap)** : quand un joueur **affirme ou interroge un état du monde** (une sortie disparue, un passage bloqué, un objet présent), le MJ **doit trancher explicitement** (confirmer le *beat* — « la paroi de marbre a coulissé, la voie est scellée » — **ou** infirmer — « l'arche est toujours là, derrière vous »), **sans** déléguer cet arbitrage à un compagnon IA. Recoupe la colonne vertébrale spatiale (N3 / Forge-spine : une sortie de retour devrait exister comme sortie persistée tant qu'aucun *beat* ne la ferme).

**Rattachement backlog** : **neuf (petit)** — « arbitrage des assertions-monde » ; recoupe **N3**.

---

### R4 — Ouverture : commanditaire **anonyme** + objectif en **liste** (résidu N6 / P3) ✅

**Symptôme** : l'ouverture ancre bien l'origine (« *Votre employeur a été clair : …* ») — progrès réel sur N6 — mais (a) le commanditaire reste **sans nom ni visage** (« votre employeur »), et (b) la suite « *: pénétrer…, identifier…, récupérer…* » est une **liste d'infinitifs** qui sent légèrement le **méta-objectif recopié**.

**Tracé** : tension connue entre [gm_open_scene.txt:27](../backend/app/agents/prompts/gm_open_scene.txt) (« *d'où vient la mission… et le PNJ commanditaire si le contrat ou le dossier l'établit* ») et [:33](../backend/app/agents/prompts/gm_open_scene.txt) (« *jamais d'étiquette… ne recopie pas l'objectif méta… réécris-le en enjeu concret* »). Le modèle a ancré l'origine (bien) mais **sans nommer** le commanditaire et **en listant** l'objectif plutôt qu'en le tissant.

**Fix (prompt léger, N6)** : nudge — « si le dossier établit un commanditaire, **nomme-le et donne-lui un visage** ; tisse l'objectif en une phrase d'enjeu, **jamais en liste d'objectifs** ». Vérifier d'abord que la **forge peuple un commanditaire concret** (sinon l'ouverture n'a rien à nommer → recoupe N3/forge).

**Rattachement backlog** : **N6** (déjà au plan).

---

## 3. Forks & hypothèses (non clos par lecture de code)

### 3.1 — 🔶 Pourquoi N3 marche ici (et pas à l'Oasis) : **hypothèse structurelle**, à vérifier

**Hypothèse** (non tracée — session non inspectable) : la différence n'est pas « la forge a mieux défini une destination », mais la **structure de scène**. Un **donjon** enchaîne des **salles-scènes** : chaque salle est un `scene_layout` avec ses **sorties**, et le MJ génère légitimement la salle suivante en franchissant une sortie (descente). La **source** se trouve au bout d'une chaîne de salles → **toujours atteignable** parce qu'il y a toujours « une sortie vers la salle suivante ». L'**Oasis**, à l'inverse, modélisait « la source » comme un **POI terminal bloqué** (fissure pleine d'eau) **sans sortie vers une scène plus profonde** → cul-de-sac.

**Conséquence pour le design N3 / Forge-spine** (sharpening, pas une preuve) : la cible concrète n'est pas « définir un nœud-destination » en l'air, c'est **garantir que le point d'aboutissement de l'objectif est atteignable comme une chaîne scène/sortie** (ou un POI portant une **« clé » de déblocage explicite**), **jamais** un POI terminal bloqué. Et **F-visible baisse en urgence** : la prose nette a suffi ici à transformer un succès en prise jouable — F-visible devient un **confort de fiabilité**, pas un déblocage structurel.

**Comment vérifier** : inspecter, sur une session équivalente jouable, (a) une campagne forgée **type donjon** (les salles sont-elles des nœuds/sorties chaînés ?) vs (b) un objectif **en scène ouverte** (la source est-elle un POI terminal ?) ; ou rejouer l'Oasis avec la consigne « la source est une sortie vers une scène, pas un POI bloqué ».

### 3.2 — ⚪ Labels d'interface dans la prose (famille Q1/A) — résidu mineur à vérifier

Quelques tournures sentent encore le label cliqué : « *Je me dirige vers L'Arche Principale* », « *Je m'arrête devant Relique brisée* » (article manquant), « *Descente vers la Crypte.* », « *Je cherche à en savoir plus sur : (description complète du POI)* ». Build récent ⇒ le **lot A** est censé naturaliser ces clics. À **confronter à la sortie réelle de A** (`scenePoiInteractions.ts`) : soit acceptable post-A, soit petit résidu de naturalisation. **Non confirmé comme régression** — réserve honnête faute de session inspectable.

---

## 4. Non exercés par cette chronique (pas de nouvelle preuve)

- **N1 / D** (double-réponse + parole PNJ) : **aucun PNJ en scène** → non testés ici. Statut inchangé (N1 livré 2026-06-04, D livré).
- **N5** (levier sur PNJ réticent) : pas de PNJ → non exercé.
- **N4** (fail-forward) : **aucun jet raté** (5 succès / 5) → l'économie d'indices sur échec n'est pas sollicitée. Statut inchangé.
- **E1** (plafond compagnons IA) : non déclenché (cf. §1) — ne confirme **ni n'infirme** le vecteur social broadcast non cappé.

---

## 5. Mapping au backlog & plan amendé

| Constat (Ruines Blanches) | Nature | Backlog | Priorité |
|---|---|---|---|
| **R1** attribution jet clic-POI « Système »/« — » | `character_name` jeté par `_normalize_roll_event`/`_enrich_roll_event` | **G-bis** (neuf, déterministe) | 🟠 **haut** (régression live d'un lot livré) |
| **R2** relique ramassée sans déclaration | non-conformité :111 + :116 | **E2-cheap (renfort)** | 🟡 |
| **R3** « l'entrée a disparu » non arbitrée | non-conformité :92 + IA parle pour le monde | **neuf (petit)** + recoupe N3 | 🟡 |
| **R4** commanditaire anonyme + objectif en liste | tension :27/:33 | **N6** | 🟡 |
| **N3** route/destination | **ne se reproduit pas** ; hypothèse structurelle | **🧩 Forge-spine (sharpened)** | 🟠 (design) |
| Labels d'interface | famille Q1/A | vérifier A | ⚪ |

**Séquence recommandée (amende le plan de la reprise)** :

1. **G-bis (R1)** — **nouveau top déterministe**. Cheap, testable, ferme une régression live d'un lot « livré » (Q7). Propager `character_name` dans `_normalize_roll_event` + `_enrich_roll_event` ; test de non-régression sur le chemin interaction-de-scène.
2. **N3 / Forge-spine** — *design* (déjà la prochaine étape). **Sharpening** : viser « point d'aboutissement atteignable comme chaîne scène/sortie ou POI à clé explicite, jamais POI terminal bloqué » ; **F-visible rétrogradé** en confort. Vérifier d'abord le fork §3.1 (donjon vs scène ouverte).
3. **Renforts prompt cheap, groupables** : **R2** (:111 inventaire/acquisition), **R3** (arbitrage des assertions-monde, pas de délégation à un compagnon), **R4/N6** (nommer le commanditaire, tisser l'objectif). Doser en replay.
4. **Inchangés** : N4, N5, E1 (non exercés) ; N1, D (pas de PNJ).

---

## 6. Qualité-modèle (priorité basse)

- **Prose riche mais lexique récurrent** : « violet / cristal / pulsation / cœur malade / organique / corruption » saturent ; le motif « cœur qui bat dans la pierre » revient. Moins répétitif que le « dread » de l'Oasis, mais rendement décroissant. Candidat nudge de variété — bas.
- **Pas de fuite d'anglais visible** dans cette chronique (≠ « own » de l'Oasis). Rien à signaler.
