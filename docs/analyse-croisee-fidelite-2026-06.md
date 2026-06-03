# Analyse croisée de fidélité — Oasis × Port d'Azur

> **Date** : 2026-06-02 · **Code lu** : `main`, HEAD `ec36179`
> **Objet** : confronter les deux analyses de terrain — [`analyse-fidelite-dialogue-2026-06.md`](analyse-fidelite-dialogue-2026-06.md) (Oasis, plan **P1–P6**) et [`analyse-fidelite-dialogue-port-azur-2026-06.md`](analyse-fidelite-dialogue-port-azur-2026-06.md) (Port d'Azur, plan **Q1–Q7**, lue **après** l'implémentation de P3) — pour : (1) **vérifier** chaque constat contre le code, (2) **réconcilier** les deux plans, (3) produire un **backlog unifié, dédupliqué et re-priorisé**.
> **Suite de** : [`suivi-tabletop-fidelity.md`](suivi-tabletop-fidelity.md) (lots 1→12), [`audit-data-flow-gm.md`](audit-data-flow-gm.md) (A1→A6).

## Légende des statuts

- ✅ **Confirmé** — symptôme tracé jusqu'à un mécanisme précis dans le code.
- 🟢 **Progrès confirmé** — un lot précédent fonctionne mieux, vérifié sur le terrain.
- 🔧 **Corrigé / affiné** — le diagnostic du document source est rectifié par lecture de code.
- ⚠️ **Partiel** — partiellement traité ; un résidu subsiste.
- 🔶 **Fork ouvert** — cause non close par la seule lecture de code ; à trancher par inspection d'état de session.

---

## 1. Vérification des constats contre le code

Chaque claim des deux documents a été suivi jusqu'à son site dans le code. Trois claims sont **rectifiés** (Q3, Q5, et le statut réel de P5).

| Claim | Statut | Preuve |
|---|---|---|
| **Q1** — les clics carte affichent des labels d'interface | ✅ confirmé | `ExplorationLayout.vue` (desktop V2) : `onAct` émet `Je me dirige vers ${poi.title}` pour une sortie et `J'examine : ${poi.title}` pour un POI ([:31-50](../frontend/src/components/exploration/ExplorationLayout.vue)), **sans** passer par `buildScenePoiInteractionPrompt` ([scenePoiInteractions.ts:54-78](../frontend/src/utils/scenePoiInteractions.ts)) qui produit des phrases naturelles. `onApproach` ([:52](../frontend/src/components/exploration/ExplorationLayout.vue)) est déjà naturel ; `onDecide` ([:64](../frontend/src/components/exploration/ExplorationLayout.vue)) émet `Le groupe décide : ${poi.title}`. |
| **Q2** — le label d'horloge interne fuit dans la narration | ✅ confirmé | `infer_clock_start_from_opening` crée automatiquement « Menace aux docks » dès que le texte contient docks/quai/entrepôt ([social_scene_state.py:646-675](../backend/app/game/social_scene_state.py)). `_default_clock_crisis_text` ([:924](../backend/app/game/social_scene_state.py)) injecte `{label}` verbatim + le placeholder « le personnage exposé » ; `_clock_roll_outcome_text` ([:932](../backend/app/game/social_scene_state.py)) idem côté résultat. `_default_clock_on_fill` ([:865](../backend/app/game/social_scene_state.py)) = DEX save Acrobatie DD14 par défaut. |
| **Q3** — « examiner » déclenche un DEX Save | 🔧 **corrigé** | L'inférence **par défaut est déjà correcte** : `infer_poi_interaction_mechanics` route `examine/search` sur un danger vers un **INT (Investigation)**, pas un DEX Save ([social_scene_state.py:380-389](../backend/app/game/social_scene_state.py)). Le DEX Save sur observation vient donc **en amont** : soit des `mechanics` **explicites** posées par le MJ (court-circuit en tête de fonction, [:343-345](../backend/app/game/social_scene_state.py)), soit d'un **intent mal routé** par le clic. → **Fork** : non clos par lecture de code. |
| **Q4** — parole PNJ et didascalie mélangées dans un seul champ | ✅ confirmé | `gm_npc_dialogue.txt` demande explicitement que `narration` contienne « la réplique du PNJ entre guillemets, avec au plus une courte réaction physique/émotionnelle » ([:51](../backend/app/agents/prompts/gm_npc_dialogue.txt)). Le sanitizer existant retire surtout les préfixes de speaker, pas les guillemets ni les didascalies longues. |
| **Q5** — « Vael, compagnon fantôme » | 🔧 **corrigé (erreur du document source)** | **Vael est un personnage joueur humain (`is_ai=False`), pas un compagnon IA.** Le diagnostic Port d'Azur §2.8 (via les réactions de compagnons IA) est donc **mal ciblé**. Un personnage n'est piloté par l'IA que si `is_ai=True` ([ai_player_manager.py:265-266](../backend/app/game/ai_player_manager.py)) ; `rebuild_ai_players` n'enregistre que ceux-là ([:319-338](../backend/app/game/ai_player_manager.py)) ; à la connexion, un PC humain est *désenregistré* de `ai_players` ([session.py:82-89](../backend/app/api/ws_handlers/session.py), `unregister_ai_player` = « passage sous contrôle humain »). Vael est un **slot PC humain sans humain connecté** → narré comme présent, mais sans aucune agentivité moteur. Les hooks de réaction IA cités par §2.8 ([narrative_flow_service.py:238/369/381](../backend/app/services/narrative_flow_service.py), cap=1, `order_companion_spotlight`) sont réels **mais ne le concernent pas**. |
| **Q7** — jet environnemental attribué à « Système » | ✅ confirmé (cas limite) | La persistance retombe sur speaker `"Système"` si `character_name` est vide ([message_service.py:73-74](../backend/app/services/message_service.py)). `execute_roll_request` prend le **1er personnage** si `target_id` est introuvable ([roll_executor.py:43-49](../backend/app/game/roll_executor.py)) et pose `character_name` à partir de là ([:94-105](../backend/app/game/roll_executor.py)). Les espacements (`OakenDEX Save`, `1d2018`) sont **en partie** un artefact de copier-coller à reproduire côté UI. |
| **P4** — l'indicateur d'attente est publié tard (chemin action) | ✅ **toujours ouvert** | `load_recent_messages` ([action_pipeline.py:303](../backend/app/game/action_pipeline.py)) et `_game_state_for_gm` ([:305](../backend/app/game/action_pipeline.py)) s'exécutent **avant** `thinking:True` ([:321](../backend/app/game/action_pipeline.py)). Non traité par P1/P2/P3 ; le silence de Port d'Azur sur la latence n'est **pas** une preuve de correction. |
| **P5** — plafond des réactions compagnons | ⚠️ **partiel** | Les chemins de **réaction** sont cappés (`max_reactors=1` explicite ; défaut `1 si open_scene sinon 2`, [ai_player_manager.py:603-605](../backend/app/game/ai_player_manager.py)). Mais le chemin **social broadcast** `_run_companion_responses` itère `target_ids` **sans aucun cap** (boucle [:484](../backend/app/services/narrative_flow_service.py), aucune limite jusqu'à la fin [:564](../backend/app/services/narrative_flow_service.py)), et `detect_audience` peuple `target_ids = list(companions)` — **tous** les compagnons — pour une adresse « party »/« mixed » ([:454/459/461](../backend/app/services/narrative_flow_service.py)). → **vecteur de saturation avéré** reproduisant le motif oasis (« tous réagissent sur une action »), **non corrigé**. *(L'attribution exacte à l'épisode oasis reste à confirmer en replay — le vecteur, lui, est vérifié ; d'où le gate replay sur E1.)* |

---

## 2. Synthèse croisée

### 2.1 🟢 Ce que Port d'Azur confirme : P1/P2/P3 tiennent

Le dialogue de Port d'Azur, joué **après** l'implémentation de P1/P2/P3, valide les trois correctifs en conditions réelles :
- **P1** (continuité PNJ) : Valerius suit jusqu'aux quais, refuse de descendre, et son arrêt devient une **décision fictionnelle** — il ne « disparaît » pas comme Khalid (Port d'Azur §2.7).
- **P2** (transitions) : les changements de scène ne cassent plus le PNJ accompagnant.
- **P3** (ouverture) : le contrat de quête affleure dans la fiction, sans labels « Accroche/Mission » collés (Port d'Azur §2.1). Résidu cosmétique : « Le contrat est clair » garde une légère odeur de fiche — relève du **thème unificateur** ci-dessous, pas d'un bug.

### 2.2 Le thème unificateur — « les coutures mécaniques transparaissent dans la fiction »

C'est la **généralisation de P3**. Le même défaut se rejoue sous plusieurs formes, à chaque fois qu'un artefact de la couche mécanique atteint la fiction lue par le joueur :

| Forme | Constat |
|---|---|
| Labels de fiche | P3 (« Accroche : ») — *corrigé* |
| Labels d'interface | Q1 (« Direction les Docks », « J'examine : … ») |
| Identifiants & placeholders d'horloge | Q2 (« Menace aux docks », « le personnage exposé ») |
| Champs de schéma rendus bruts | Q4 (parole + didascalie dans `narration`) |
| Acteur technique | Q7 (« Système » pour un jet subi par un PJ) |

→ Tous relèvent d'**une seule frontière de présentation/sanitisation** mal tenue entre la mécanique et la fiction. C'est l'angle qui fait de ce document une *analyse croisée* et non un simple cumul de tickets : **Q1, Q2, Q4, Q7 sont des instances d'un même problème**, et devraient partager une discipline commune (« aucun identifiant interne, label d'UI, nom de champ ou acteur technique ne doit apparaître dans un texte joueur — seulement dans un badge/élément d'UI dédié »).

### 2.3 Présence & agentivité de la table — deux problèmes **distincts** (correction)

Le document Port d'Azur (§2.8) traitait Vael comme un compagnon IA muet et le mettait dans la balance avec la saturation observée à l'oasis (§1.5 du doc Oasis). **C'est une erreur factuelle** : Vael est un **personnage joueur humain**, pas un compagnon IA. Les deux sujets doivent être **dé-fusionnés** :

- **Compagnons IA (héritage P5)** — vrai sujet de *dosage*. La saturation oasis (« Elara *puis* Solana *puis* Oaken » sur chaque action) a été **partiellement** corrigée : le cap est posé sur les chemins de *réaction*, mais le chemin **social broadcast** `_run_companion_responses` reste non cappé (cf. §1, P5). **Plafond à finir.** Ne concerne que les PC `is_ai=True`.
- **PC humain sans contrôleur (Vael)** — problème **séparé**, qui ne passe par **aucun** code de compagnon IA. Un slot de personnage joueur sans humain connecté est narré comme présent mais n'agit jamais. **Décision (2026-06-02) : hand-off / contrôle multi-personnage** — le joueur connecté peut piloter aussi ce personnage (ou un 2ᵉ joueur le rejoint) ; en attendant, le MJ ne le met pas en avant comme acteur tant qu'il n'est pas réclamé. **Pas de délégation à l'IA** (ce serait contraire à sa nature de personnage joueur).

### 2.4 Statut consolidé du plan P1–P6

| Lot d'origine | Statut | Note |
|---|---|---|
| **P1** continuité PNJ + anti-canon | ✅ livré & validé live | Confirmé par Valerius (Port d'Azur §2.7). |
| **P2** transition assistée | ✅ livré & validé live | P2-b (confirmation UI) toujours différée. |
| **P3** ouverture diégétique | ✅ livré & validé live | Résidu cosmétique → thème §2.2. |
| **P4** robustesse indicateur | ⏳ **ouvert** | Confirmé non corrigé ([action_pipeline.py:303/305/321](../backend/app/game/action_pipeline.py)). |
| **P5** spotlight / anti-saturation | ⚠️ **partiel** | Cap sur les réactions ; chemin social non cappé. |
| **P6** ancrage persona PNJ clés | ⏳ ouvert, **re-priorisé** | Sa justification d'origine (résistance à l'oubli, liée à P1) est désormais **couverte par P1**. Reste sa valeur propre (voix/savoir persistants) → bas/continu. |

### 2.5 Fork restant tenu honnête

- **Q3** : 1ʳᵉ étape = inspecter `current_scene.pois[].interactions` d'une session réelle pour déterminer si le DEX Save vient de `mechanics` explicites du MJ ou d'un intent mal routé. **Ne pas pré-trancher** la cause ni coder le champ `exposure` avant ce diagnostic. → **diagnostic réalisé le 2026-06-03, cf. §2.6** (les deux causes d'origine sont écartées ; cause de tête = crise d'horloge, corroborée par la session Port d'Azur).
- *(Q5 n'est plus un fork : cause établie — Vael est un PC humain.)*

### 2.6 Diagnostic Q3 (2026-06-03) — inspection d'état réel

Inspection en lecture seule de `current_scene.pois[].interactions` sur les 5 `game_states` de `backend/rpgmaster.db` (18 POI, 12 interactions) :

- **Distribution des intents** : `examine`×3, `search`×3, `talk`×4, `custom`×1, `use`×1.
- **Mécaniques explicites posées par le MJ** : 3 seulement, **toutes des checks INT/WIS** — Nature DD12 (« Analyser l'eau »), Perception DD13 (« Fouiller »), Arcana DD15 (« Désactiver »). **Zéro DEX Save sur un intent d'observation** (`examine/listen/search/approach`).

→ **Ce que le diagnostic clôt (prouvé par les données)** : le DEX Save sur « examiner » **ne vient ni** d'une mécanique explicite du MJ (aucune n'existe sur un intent d'observation) **ni** de l'inférence par défaut (qui route correctement `examine` sur un danger vers un INT Investigation, [social_scene_state.py:380-389](../backend/app/game/social_scene_state.py)). Les **deux** causes hypothétiques d'origine sont **écartées**.

→ **Hypothèse de tête, corroborée par la session Port d'Azur elle-même** : la session `c2a070a0` (« L'Éclat du Port d'Azur ») contient l'horloge `menace_aux_docks` **résolue** via un **DEX Acrobatie DD14** (`reason: scene_clock_crisis`, jet 18 vs 14 = succès), avec la narration **fuyante** persistée : « Menace aux docks atteint son point critique. […] le personnage exposé doit réagir immédiatement. » Le **seul** DEX Save de la scène est donc **la crise d'horloge**, déclenchée sur un tick `player_action` — qui a pu coïncider avec un clic d'observation, d'où la lecture « examiner → DEX Save ». Le **lot B rend cette crise lisible** (phénomène concret, plus de label ni de placeholder « personnage exposé ») ; ce DEX Save de crise n'est **pas** un jet d'observation.

→ **Vecteur non exclu (à garder pour le lot C)** : un intent `use`/`custom` sur un POI dangereux produit légitimement un DEX Save Acrobatie ([social_scene_state.py:357-367](../backend/app/game/social_scene_state.py)). Aucune occurrence dans les données inspectées, mais ce chemin reste un déclencheur possible d'un DEX Save « sur un danger » — à confirmer/infirmer en replay.

**Conséquence pour le lot C** : **ne pas** coder le champ `exposure` réflexivement. Priorité = (a) lot B (lisibilité de crise — **livré**), puis (b) éventuellement gating du DEX Save de crise d'horloge **ou** annonce de risque avant toute sauvegarde sur une intention d'observation — **à trancher en replay live**, pas par anticipation.

---

## 3. Backlog unifié amendé

Remplace P1–P6 + Q1–Q7. Ordre re-priorisé par *impact fidélité × déterminisme × coût*.

| Lot | Contenu | Origine | Priorité | Risque |
|---|---|---|---|---|
| **A ✅ — Clics carte naturalisés + diagnostic Q3** | **Livré 2026-06-03.** `cleanExitLabel` + `buildSceneExitPrompt` centralisés (`utils/scenePoiInteractions.ts`, design 3-branches à échec sûr), utilisés par `ExplorationLayout` desktop + chemin mobile ; `onAct` passe par `buildScenePoiInteractionPrompt`. Diagnostic Q3 consigné en **§2.6**. Vérif : type-check + 87 vitest + bundle Vite live. | Q1 (+ Q3 diag) | ✅ livré | faible |
| **B ✅ — Voix fictionnelle des horloges + dents** | **Livré 2026-06-03.** `_default_clock_crisis_text` / `_clock_roll_outcome_text` réécrits : phénomène concret par `kind(label)`/`severity`, label jamais rendu, « personnage exposé » supprimé, nom réel du PC, conséquence concrète **même sur succès**, clauses **neutres en genre**. Narration `on_fill` dé-bakée (recalcul à la résolution). Garde-test anti-fuite de label. | Q2 | ✅ livré | faible/moyen |
| **C — Contrat mécanique exposition/danger** | **⚠️ Re-cadré par le diag Q3 (§2.6)** : (a) et (b) **dissous** — aucun DEX Save explicite du MJ sur intention d'observation, et le routage par défaut est correct (`examine` danger → INT Investigation). Le vrai levier subsistant = **crise d'horloge** (désormais lisible via B) + éventuelle **annonce de risque avant sauvegarde**. **Replay-gated** : trancher en replay live ; **ne pas** coder le champ `exposure` réflexivement. | Q3 | 🟠 (replay-gated) | moyen |
| **D — Parole PNJ vs didascalie** | `gm_npc_dialogue.txt` : `narration` **sans** guillemets, 1–3 phrases, ≤1 didascalie. Idéalement schéma `spoken_text` + `stage_direction` (UI : parole en dialogue, didascalie atténuée) + sanitizer (retire guillemets englobants et préfixe « Le Maire Valerius… »). | Q4 | 🟠 | faible/moyen |
| **E1 — Plafond compagnons IA** | Capper `_run_companion_responses` (chemin social broadcast non cappé — source de la saturation oasis). Réutiliser `order_companion_spotlight` + cooldown. Concerne les PC `is_ai=True`. À doser en **replay live**. | P5 | 🟡 | moyen |
| **E2 — PC sans contrôleur : hand-off (Vael)** | **Cheap d'abord** : consigne MJ → ne pas mettre en avant un PC non piloté comme acteur actif. **Puis** : contrôle multi-personnage — le joueur connecté réclame/pilote un PC sans contrôleur (le WS clé déjà sur `character_id` ; à construire : sélection/ajout de perso piloté + état UI « sans contrôleur »). **Pas de délégation IA.** | Q5 (corrigé) | 🟠 | moyen |
| **F — Indices → options jouables** | Prompt MJ : après 2 indices convergents, émettre 2–4 approches via `scene_update`/interactions POI ; les faits découverts alimentent de nouvelles interactions concrètes, pas seulement la prose. | Q6 (lié lot 9) | 🟡 | faible/moyen |
| **G — Polish (parallèle)** | **P4** : publier `thinking:True` **avant** `load_recent_messages`/`_game_state_for_gm`. **Q7** : invariant — un `ROLL_RESULT` subi par un PJ est toujours attribué (jamais « Système ») ; espacement UI stable. | P4 ⊕ Q7 | 🟡 | faible |
| **H — Persona PNJ clés (optionnel/continu)** | `stub_then_enrich` + persist `played_canon.npc_personas` à l'intro d'un PNJ central. Justification réduite (P1 couvre l'oubli). | P6 | ⚪ | faible |

**Recommandation d'ordre** : ~~**A + B** en lot immédiat~~ → **livrés 2026-06-03**. **Prochain lot recommandé : D + G** (tous deux déterministes, prêts, indépendants) — **C** étant désormais *replay-gated* par le diagnostic Q3 (ne plus le traiter en tâche de code à l'aveugle). **E2** garde sa part *cheap* (consigne MJ) faisable tôt ; sa part UI ainsi que **E1** et **F** après un replay live. **H** continu.

---

## 4. Scénarios d'acceptation (harness live `test_tabletop_replay_live.py`)

Reprendre **4 des 5** scénarios proposés par Port d'Azur §6 :
1. **Clic sortie naturalisé** ✅ (A, 2026-06-03) — label `Direction les Docks` → action visible sans « vers Direction » ni doublon de préposition. *Couvert par `frontend/src/utils/__tests__/scenePoiInteractions.test.ts` sur les vrais libellés DB + bundle Vite live.*
2. **Horloge critique fictionnelle** ✅ (B, 2026-06-03) — une horloge atteint son max → narration = phénomène concret ; **interdit** : `Menace aux docks atteint son point critique`. *Couvert par `tests/test_game/test_narrative_flow_service.py` (garde anti-fuite + neutralité de genre).*
3. **Observer un danger** ⏳ — examiner une zone dangereuse à distance → jet d'observation **ou** annonce de risque avant toute sauvegarde ; pas de DEX Save arbitraire sans exposition. *Cf. C re-cadré (§2.6) : le DEX Save observé venait de la crise d'horloge, pas d'un jet d'observation — à confirmer en replay.*
4. **PNJ parle proprement** ⏳ (D) — pas de préfixe « Le Maire Valerius… » en tête, pas de guillemets englobants doublés.

**Corriger le 5ᵉ** (« compagnon non fantôme » supposait Vael = IA) → le remplacer par **deux** invariants distincts :
- **Plafond compagnon IA** (E1) : sur N actions monde dangereuses avec ≥1 PC `is_ai=True`, **au plus 2** réactions (anti-saturation oasis).
- **PC sans contrôleur** (E2) : un PC `is_ai=False` non réclamé **n'est pas** narré comme acteur ; une fois réclamé (hand-off), il peut agir.

**P4** reste hors harness (vérification par lecture de code + frontend).

**Nettoyage acté** : la fixture de replay encode encore `khalid_guide.status="missing"` comme état de base ([test_tabletop_replay_live.py:160-162](../backend/tests/test_e2e_live/test_tabletop_replay_live.py)) — ce que le doc Oasis §5 signalait comme « figeant le bug comme normalité ». P1 étant livré (et le scénario de portage P1 vivant dans la même fixture, [:345](../backend/tests/test_e2e_live/test_tabletop_replay_live.py)/[:423](../backend/tests/test_e2e_live/test_tabletop_replay_live.py)), **réconcilier cette baseline** pour ne plus poser le bug comme état initial.
