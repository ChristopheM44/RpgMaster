# Analyse de fidélité — dialogue de partie « Oasis corrompue »

> **Date** : 2026-06-01 · **Code lu** : `main`, HEAD `2a8575e`
> **Objet** : confronter un dialogue réel de partie (chronique Test, scène désert → Oasis d'Émeraude) au code, pour distinguer ce qui s'écarte d'une vraie table de JDR.
> **Suite de** : [`suivi-tabletop-fidelity.md`](suivi-tabletop-fidelity.md) (lots 1→12), [`audit-data-flow-gm.md`](audit-data-flow-gm.md) (A1→A6). Ce doc-ci est un **retour de terrain** : les frontières d'information tiennent, mais le dialogue révèle des problèmes de **continuité fictionnelle** et de **rythme**, pas de fuite.

## Légende des statuts

- ✅ **Confirmé** — symptôme tracé jusqu'à un mécanisme précis dans le code.
- 🔶 **Hypothèse** — cause plausible mais non reproduite ; à valider en live LLM avant correctif.

---

## Méthode

Chaque symptôme du dialogue a été suivi jusqu'à son site dans le code (fichier:ligne), puis classé. Les passages clés du dialogue servent de preuve. Le but n'est pas de lister des bugs mais de comprendre **pourquoi l'expérience s'écarte d'une table** et **où agir**.

---

## 1. Constats

### 1.1 ✅ Ouverture : le contrat de quête est **dupliqué** et collé en en-tête de formulaire

**Symptôme** (ressenti utilisateur : « on dirait le champ accroche de la chronique collé »). L'ouverture commence par :

> **Accroche :** Vous avez été engagés, ou vous êtes poussés par la nécessité, pour traverser les terres arides et découvrir pourquoi les oasis s'assèchent… **Mission confiée au groupe :** Survivre aux conditions extrêmes du désert.

…puis enchaîne sur une prose LLM de bonne tenue (« L'air vibre sous une chaleur écrasante… »), qui **redit déjà le hook** : « Vous avez été engagés pour traverser ces terres arides et comprendre pourquoi les oasis s'assèchent… ».

**Mécanisme (et correction d'un diagnostic initial).** Le LLM **tisse bien** le hook dans sa prose. Le problème n'est pas une omission mais une **duplication déclenchée par l'objectif** :

- `_ensure_opening_public_prologue` ([routes_game.py:195](../backend/app/api/routes_game.py)) préfixe le briefing **si `missing_hook` OU `missing_objective`**.
- `_contract_words_present` ([routes_game.py:182](../backend/app/api/routes_game.py)) cherche les mots-clés du contrat dans la prose. Hook = présent (« engagés / traverser / arides / oasis / assèchent ») → `missing_hook = False`. Objectif = « Survivre aux conditions extrêmes du désert » → mots {survivre, conditions, extremes, desert}, seuil de 2 présences requis, **aucun** présent dans la prose → `missing_objective = True`.
- Le prépend est **tout-ou-rien** : il colle le briefing **complet** (`_party_briefing_text`, [routes_game.py:164](../backend/app/api/routes_game.py)) → re-colle le hook déjà tissé **+ ajoute les labels** « Accroche : » / « Mission confiée au groupe : ».

**Deux problèmes distincts** se superposent :
1. **Mécanique** : prépend tout-ou-rien + labels de formulaire + matching mot-à-mot intolérant à la paraphrase → duplication visible.
2. **Contenu** : le `hook` de forge est un fourre-tout (« ou vous êtes poussés par la nécessité » est une tournure de couverture, pas de la fiction), et l'objectif « Survivre aux conditions extrêmes du désert » est un méta-but de survie qui n'apparaîtra jamais verbatim dans une scène.

**Écart avec une vraie table.** Un MJ n'énonce jamais la fiche de quête au mot près en préambule ; il ouvre **dans la fiction** et laisse le contrat affleurer. Ici le joueur lit deux fois la même chose, dont une version « spec ».

### 1.2 ✅ Transition de scène non déterministe : le « clic caché » obligatoire

**Symptôme** (obs. 4). Thorvald écrit « **Tres bien rendons nous a l'oasis d'émeraude** ouvrez la route Khalid, nous vous suivons ». Le MJ narre une mise en marche (Oaken prend la tête) **mais la scène ne change pas**. Il faut ensuite **cliquer le POI de sortie** — d'où l'entrée suivante « Je me dirige vers **Vers l'Oasis d'Émeraude** » (le double « vers Vers » trahit un texte gabarit injecté par le clic POI).

**Mécanisme.**
- `detect_travel_intent` ([travel_detection.py:197](../backend/app/game/travel_detection.py)) repose sur une liste de marqueurs. Elle contient « nous nous rendons a » mais **pas la forme impérative** « rendons-nous à ». Le texte du joueur ne matche **aucun** marqueur → `is_travel = False`, aucun hint injecté.
- Même détecté, le `travel_intent` n'est **qu'un hint** passé au prompt ([action_pipeline.py:317](../backend/app/game/action_pipeline.py)). La transition réelle dépend du LLM qui **choisit** d'émettre `scene_layout`. C'est non-déterministe.
- Le clic sur le POI de sortie produit le texte gabarit « Je me dirige vers … » qui, lui, **contient** un marqueur explicite → hint injecté → `scene_layout` émis de façon fiable.

**Résultat** : le joueur apprend implicitement que **son texte est « faux »** et que seul le clic POI « compte ». C'est l'inverse d'une table, où dire « on va à l'oasis » suffit. Deux registres d'entrée (texte libre vs POI) ne convergent pas.

### 1.3 ✅✅✅ Khalid disparaît : trois mécanismes cumulés (plus profond que l'hypothèse initiale)

**Symptôme** (obs. 5). Khalid accompagne le groupe dans la narration jusqu'à l'oasis, puis « a disparu » sans cause scénarisée. Le dossier ne prévoit aucune disparition ; `npc_states.khalid_guide.status = "missing"` et la note « Disparu mystérieusement » finissent **figés dans `played_canon`**.

**Mécanisme — trois couches qui s'additionnent :**

1. ✅ **Aucun concept de PNJ « accompagnant ».** La recherche (`accompan|follows_party|escort|travels_with`) ne renvoie **rien**. Les PNJ sont **liés à un lieu** (`last_location`), jamais **au groupe**. Quand le LLM génère le `scene_layout` de l'oasis, `current_scene` est **remplacé en entier** ([gm_response_executor.py:942](../backend/app/game/gm_response_executor.py)) ; les PJ et compagnons IA suivent, mais **un PNJ guide n'a aucun mécanisme de report** vers la nouvelle scène.

2. ✅ **Un filtre qui supprime activement le guide même s'il était reporté.** `_filter_absent_npc_pois` ([gm_response_executor.py:1688](../backend/app/game/gm_response_executor.py)) retire tout POI de PNJ dont `last_location != scene_id` de la nouvelle scène. Khalid garde `last_location = «piste d'ambre»` ; la nouvelle scène est l'oasis → **même si le LLM le réintroduisait, il serait effacé**. Ce filtre, conçu pour empêcher un PNJ mort/parti de réapparaître, est **hostile à un PNJ qui voyage légitimement avec le groupe**.
   - ⚠️ *Détail technique* : `last_location` vaut le `scene_id` quand il existe, mais retombe sur un **label** (venue/terrain/location_place) sinon ([gm_response_executor.py:1657](../backend/app/game/gm_response_executor.py)). Le champ est **surchargé** (tantôt id, tantôt label) alors que le filtre compare à un `scene_id`. Tout correctif basé sur `last_location` est donc fragile.

3. ✅ **Contamination du canon : un artefact mécanique devient une intrigue.** Le MJ, constatant l'absence, l'improvise en fiction (« Khalid a disparu ») et pose la note dans `npc_states`. La **synthèse** parcourt ensuite `npc_states` et copie `notes` → `played_canon.npc_relationships[].context` ([campaign_dossier_service.py:1764-1776](../backend/app/services/campaign_dossier_service.py)). La disparition, née d'un trou de transition, est **promue en vérité permanente** de la campagne. 🔶 *Le déclencheur exact du `status="missing"` dans cette session (npc_update du MJ vs inférence) n'est pas reproduit, mais le chemin de promotion vers le canon est confirmé.*

**Écart avec une vraie table.** Un guide marche avec le groupe **par défaut** ; il ne disparaît que si le MJ le décide pour une raison. Ici la fiction est **pilotée par un artefact d'implémentation**, puis gravée dans le marbre.

### 1.4 ✅🔶 Indicateur MJ / IA : composant présent, mais latence et trous de séquencement

**Symptôme** (obs. 3) : « on attend le MJ ou le LLM mais on ne sait pas s'il se passe quelque chose ».

**Ce qui existe** : un vrai système `ai_thinking` (pill « MJ »/« IA » + points animés), câblé du backend ([event_bus `AI_THINKING`](../backend/app/game/event_bus.py)) au store ([game.ts:436](../frontend/src/stores/game.ts)) et au composant ([NarrativeLog.vue:78](../frontend/src/components/narrative/NarrativeLog.vue)).

**Causes identifiées :**
- ✅ **Latence avant le 1er event (chemin action).** `thinking:True` est publié à [action_pipeline.py:321](../backend/app/game/action_pipeline.py) — **après** `load_recent_messages` (I/O DB) **et** `_game_state_for_gm` (compilation d'état). Sur ces opérations, l'indicateur n'est pas encore affiché alors que le système travaille déjà. (À l'ouverture, à l'inverse, `thinking:True` est publié **avant** la préparation — [routes_game.py:1286](../backend/app/api/routes_game.py) — donc le comportement est incohérent entre chemins.)
- 🔶 **Trous entre acteurs.** Orchestration joueur → MJ → compagnon → compagnon → MJ : entre un `thinking:False` et le `thinking:True` suivant, l'indicateur peut « clignoter » à vide. Non reproduit ; à confirmer.
- 🔶 **Pas de notion de « qui a la parole ».** Aucune file de tour exposée : on ne sait pas *qui* on attend.

**Écart avec une vraie table.** On sait toujours qui « a la main » et qu'il réfléchit.

### 1.5 ✅ Compagnons IA : excellents (point positif), mais deux risques de fidélité

**Positif** (obs. 2, confirmé par le dialogue). Elara propose son expertise (« Si c'est une corruption magique, mes yeux sauront… »), Solana pousse l'action, Oaken prend la tête : voix en 1ʳᵉ personne, persona, propose-don't-impose. **À préserver tel quel** (fruit des lots 3/10/11).

**Risque 1 — saturation & joueur humain spectateur.** Sur chaque action de Thorvald, **plusieurs** compagnons réagissent (Elara *puis* Solana *puis* Oaken). Le tour de l'humain est noyé, et le rythme devient **piloté par les IA**. À une table, le MJ rend la main au joueur actif.

**Risque 2 — effet spectateur renforcé par les jets.** Thorvald échoue son Investigation (4 vs 14) puis sa Perception (4 vs 13) ; pendant ce temps Elara réussit (18, 14). Le fail-forward narratif existe (lot 2) mais, côté vécu, l'humain « lance, rate, et l'IA trouve ». L'échec humain ne lui donne pas d'agentivité en retour.

### 1.6 🔶 PNJ clés sans persona persistante

`important_npcs` est **vide** pour cette chronique → Khalid est un stub `light` improvisé tour par tour, sans voix/savoir persistants. Un guide central au chapitre **devrait être ancré** comme persona persistante (cf. [`persona.py`](../backend/app/agents/persona.py), `stub_then_enrich`). Un PNJ non-ancré est mécaniquement **plus facile à « oublier »** à une transition (lien direct avec §1.3).

---

## 2. Thèmes structurels (ce que les constats ont en commun)

1. **Frontières « soft » (jugement LLM) vs « hard » (déterministe) mal placées.**
   - La **transition de scène** est *trop soft* : elle dépend du bon vouloir du LLM (§1.2) alors qu'une intention de voyage claire devrait être **assistée/déterministe**.
   - La **présence d'un PNJ** est *trop hard* : un filtre brutal efface un PNJ par comparaison de lieu (§1.3) au lieu de raisonner « accompagne le groupe ou non ».

2. **Les artefacts mécaniques fuitent dans le canon.** Aucune garde n'empêche une absence due à une transition de devenir un fait de campagne (§1.3.3). Le pipeline `npc_states → synthèse → played_canon` traite toute note comme vérité.

3. **L'identité PNJ n'a pas de « domicile » pour un PNJ mobile.** L'audit data-flow (A4) a unifié `npc_states ↔ pois` pour un PNJ **statique**. Mais rien ne modélise un PNJ **mobile** (escorte/guide) : c'est l'angle mort suivant de l'unification d'identité.

---

## 3. Plan proposé (à discuter)

> Priorisé par **impact fidélité × visibilité joueur**. Chaque lot indique objectif, point d'attache, risque, et **questions ouvertes** à trancher ensemble. Rien n'est implémenté à ce stade.

### P1 — Continuité du guide : PNJ « accompagnant » + anti-contamination du canon 🔴 *(impact max)*

**Objectif** : un PNJ qui voyage avec le groupe **reste présent** d'une scène à l'autre, sauf décision narrative explicite du MJ ; et un trou de transition **ne peut plus** se figer en canon.

**Mécanisme proposé :**
- Introduire un état explicite `npc_states[id].disposition = "accompanying"` (le groupe l'escorte / il escorte le groupe), **indépendant de `last_location`** (pour contourner la surcharge id/label du §1.3).
- À l'application d'un `scene_layout` (transition), **reporter** les PNJ `accompanying` : les injecter dans les POI de la nouvelle scène et mettre à jour leur ancrage. Les **exempter** de `_filter_absent_npc_pois`.
- **Garde anti-contamination** : un passage en `missing`/`absent` survenant dans la même passe qu'une transition de scène, **sans `npc_update` explicite du MJ portant une cause**, est ignoré (le PNJ accompagnant reste présent). La disparition redevient une **décision**, pas un défaut.
- Prompt MJ : au cadrage, marquer le guide comme `accompanying` ; sur voyage, le **maintenir présent** sauf départ explicite (capture/mort/fuite via `npc_update` ou `stealth_event`).

**Points d'attache** : `scene_state_service.py` (report + reconcile), `gm_response_executor.py:1688` (exemption du filtre), `gm_response_executor.py:1764` côté synthèse / `campaign_dossier_service.py:1764` (garde), `gm_*` prompts (vocabulaire `accompanying`).

**Risque** : moyen — touche la transition de scène (chemin critique). Tests de non-régression sur PNJ statiques (le filtre doit continuer d'écarter un mort/parti).

**Questions ouvertes** :
**✅ Décisions verrouillées (2026-06-01) :**
- (a) `disposition` porté par **`npc_states`** (pas la persona).
- (b) **Choix C — portage-par-défaut ancré sur la présence réelle.** ⚠️ *Fait vérifié* : `_infer_opening_present_npcs` (routes_game.py:396) saute tout PNJ absent du hook, et `_infer_opening_host` (routes_game.py:420) exige le motif « chez {nom} » → **aucune des deux n'aurait capturé Khalid**. Donc on n'ancre **pas** sur une heuristique d'ouverture : on porte les PNJ **présents en POI dans la scène quittée** lors d'une transition de voyage (sauf `disposition="stationary"` ou statut de départ), on les marque `accompanying`, et le MJ écrit les départs. Sur-portage = bénin et corrigeable (asymétrie assumée vs sous-portage qui casse l'histoire).
- (c) **Exiger une cause, pas bloquer** — mais le **correctif principal est la ré-injection** (le MJ ne voit jamais le PNJ absent → n'improvise pas sa disparition). La garde « cause » est de la défense-en-profondeur, posée **au site d'écriture** (`_merge_npc_updates`), pas à la synthèse.

### P2 — Transition de scène assistée et déterministe 🟠 *(corrige le « clic caché »)*

**Objectif** : « on va à l'oasis » (texte **ou** clic) déclenche la même transition fiable.

**Mécanisme proposé :**
- Élargir les marqueurs de `detect_travel_intent` : impératifs (« rendons-nous à », « allons à », « conduis-nous à », « en avant vers », « direction X »).
- Faire du travel-intent un **signal fort** : quand il matche une sortie/un nœud connu, **garantir** la transition — si le LLM n'émet pas de `scene_layout`, soit re-prompter, soit synthétiser une transition minimale déterministe.
- **Convergence UI** : quand un voyage est détecté en texte libre, proposer une **confirmation 1-clic** (« Voyager vers l'Oasis ? ») reliée au même POI de sortie. Texte et clic mènent au même endroit.

**Points d'attache** : `travel_detection.py` (marqueurs), `action_pipeline.py` (signal fort + garde post-LLM), frontend (affordance de confirmation).

**Risque** : moyen — une transition trop agressive peut « sauter » des interactions. Garder l'exception déjà prévue : déplacement vague (« on y va ») → le MJ demande « où ? » ([gm_narrate.txt:201](../backend/app/agents/prompts/gm_narrate.txt)).

**✅ Décisions verrouillées (2026-06-01) :**
- (a) **Choix C — fallback déterministe immédiat + enrichissement au tour suivant** (pas de re-prompt : éviterait 30–120 s de latence sur le chemin du déplacement). L'enrichissement est fiable car « décrire où l'on est » est le **métier de base** du MJ (narration), pas une action structurée à émettre en plein milieu. Le fallback est nourri dans le prompt suivant (« tu es maintenant à [destination], décris la scène »).
- (b) Confirmation UI : repoussée (non bloquante pour P1+P2) — à décider au moment du frontend.

### P3 — Ouverture écrite, pas « spec collée » 🟠 *(corrige §1.1, faible risque)*

**Objectif** : une ouverture qui se lit comme de la fiction, sans doublon ni labels.

**Mécanisme proposé** (le LLM tisse **déjà** le hook ; ne pas « lui réapprendre ») :
- Préfixer **uniquement la partie manquante** (jamais le briefing complet) → supprime la duplication.
- Rendre `_contract_words_present` **tolérant à la paraphrase** (lemmes / synonymes / seuil revu), surtout pour un objectif méta comme « survivre… » qui n'apparaît pas verbatim.
- **Supprimer les labels** « Accroche : » / « Mission confiée : » — si un prépend de secours est nécessaire, le rédiger en **prose diégétique**.
- (Contenu) revoir la **forge** pour produire un `hook` jouable (pas de tournure de couverture) et un objectif public concret.

**Points d'attache** : `routes_game.py:182-211` (matching + prépend), `campaign_forge_*` (qualité du hook).

**Risque** : faible. Garde-fou lot 8 (le contrat doit rester visible) préservé, mais sans le coller deux fois.

**Questions ouvertes** :
- (a) Tolère-t-on que l'objectif **n'apparaisse pas** en ouverture s'il est déjà visible ailleurs (journal/quête) ? Sinon, le faire **réécrire en fiction** par le LLM plutôt que collé.

### P4 — Robustesse de l'indicateur d'attente 🟡

**Objectif** : on sait **toujours** que ça travaille et **qui** on attend.

**Mécanisme proposé :**
- Publier `thinking:True` **au tout début** du chemin action (avant `load_recent_messages` / `_game_state_for_gm`) → aligne le chemin action sur le chemin ouverture.
- Maintenir un indicateur **continu** sur toute l'orchestration multi-acteurs (pas de clignotement entre MJ et compagnons).
- Exposer **qui** est en train de « parler »/réfléchir (nom d'acteur), idéalement une mini-file de tour.

**Points d'attache** : `action_pipeline.py:321`, orchestration compagnons ([ai_player_manager.py](../backend/app/game/ai_player_manager.py)), `game.ts` / `NarrativeLog.vue`.

**Risque** : faible (surtout frontend + repositionnement d'un publish).

**Question ouverte** : 🔶 confirmer d'abord en live les trous multi-acteurs (§1.4) avant d'investir dans la file de tour.

### P5 — Rendre la main au joueur humain (spotlight & rythme) 🟡

**Objectif** : l'humain n'est pas spectateur de ses compagnons.

**Mécanisme proposé :**
- Plafonner les réactions de compagnons par action humaine (vérifier l'état du lot 3 « une prise jouable ») et **rendre explicitement la main** à l'humain après une salve.
- Sur **échec humain**, orienter le fail-forward vers **son** agentivité (un indice qu'il peut suivre), pas vers une réussite IA qui le remplace.

**Points d'attache** : orchestration compagnons, prompts MJ (fail-forward orienté joueur).

**Risque** : faible/moyen — ne pas brider les compagnons au point de perdre le point positif §1.5.

**Question ouverte** : combien de réactions compagnons par tour humain est « juste » (1 ? 1 + une réplique courte) ?

### P6 — Ancrage persona des PNJ clés 🟡

**Objectif** : un PNJ central (guide du contrat) a une persona persistante dès sa 1ʳᵉ apparition → voix/savoir cohérents + résistance à l'oubli (renforce P1).

**Mécanisme proposé** : à l'introduction d'un PNJ nommé impliqué dans le chapitre, déclencher `stub_then_enrich` et persister en `played_canon.npc_personas`.

**Points d'attache** : `persona_factory.py`, point d'introduction PNJ.

**Risque** : faible. Coût LLM additionnel (enrichissement) → garder asynchrone.

---

## 4. À trancher ensemble (priorités proposées)

| # | Lot | Impact joueur | Risque | Ordre suggéré |
|---|-----|---------------|--------|---------------|
| P1 | Continuité guide + anti-canon | 🔴 très visible | moyen | **1er** |
| P2 | Transition assistée | 🟠 visible | moyen | 2e (lié à P1) |
| P3 | Ouverture LLM | 🟠 visible | faible | 3e (rapide) |
| P4 | Indicateur | 🟡 confort | faible | 4e |
| P5 | Spotlight humain | 🟡 rythme | faible/moyen | 5e |
| P6 | Persona PNJ clés | 🟡 fond | faible | continu |

**Points de décision (mise à jour 2026-06-01) :**
1. ✅ **DÉCIDÉ — P1 + P2 traités ensemble.** La transition de scène est l'événement qui perd Khalid ; on corrige la continuité du guide *et* la fiabilité de la transition dans le même lot.
2. ✅ **DÉCIDÉ — P3 : le LLM réécrit l'objectif en fiction** (plutôt qu'un simple prépend de la partie manquante). L'ouverture ne colle plus aucun champ ; le contrat affleure dans la prose générée.
3. ✅ **DÉCIDÉ — P4/P5 gardés en fin de file.** P4 = petit correctif direct (cause confirmée, pas de replay nécessaire). P5 = à mesurer plus tard (invariant de saturation dans le harness). Les **2 scénarios d'acceptation Khalid/transition sont intégrés à P1+P2** (voir §5).

---

## 5. Le harness de replay live (clarification)

`tests/test_e2e_live/test_tabletop_replay_live.py` rejoue des entrées joueur **contre le vrai LLM configuré** (pas de mock ; gemma4/Ollama Cloud) via la vraie `ActionPipeline`, collecte tous les events publiés sur le bus, et **vérifie des invariants** : aucune erreur technique fuitée dans la fiction, jet attribué au bon acteur (Thorvald, pas Elara), `scene_update` publié quand attendu, un PNJ `missing` ne parle pas, etc.

**✅ DÉCIDÉ — 2 scénarios d'acceptation à ajouter dans le lot P1+P2 :**
1. « Khalid accompagne → voyage vers l'oasis → Khalid **toujours présent** dans la nouvelle scène (et ne passe pas `missing` sans cause explicite) ».
2. « `rendons-nous à l'oasis` (impératif) → `SCENE_LAYOUT_CHANGED` **publié** ».

Les deux **échouent aujourd'hui** (ils prouvent les bugs vécus) et **passeront après** P1+P2 (preuve du correctif + anti-régression permanente).

- **P5** (saturation compagnons) : mesurable par un invariant (nb de tours compagnons par action humaine).
- **P4** (indicateur) : cause confirmée par lecture de code → correctif direct, **pas besoin de replay**. Le clignotement visuel inter-acteurs reste un sujet **frontend** que le harness backend ne capture qu'indirectement.

> ⚠️ Le fixture actuel encode déjà `khalid_guide.status = "missing"` comme état de base — il **fige le bug comme normalité**. À revoir quand P1 sera traité.

---

## 6. État d'implémentation — P1+P2 (branche `fidelity-p1-p2-npc-continuity`)

**Livré (2026-06-01) :**
- **P1 portage** — `scene_state_service.carry_accompanying_npcs()` : sur transition de voyage (`scene_id` change), porte les PNJ présents en POI de la scène quittée (sauf `stationary`/départ) vers le nouveau layout (inject POI + `last_location` = nouvelle scène + `disposition="accompanying"`). Branché dans `gm_response_executor._apply_scene_layout` **avant** `_filter_absent_npc_pois` (l'ordre fait que le PNJ porté survit au filtre).
- **P2 garde** — `_merge_npc_updates` : un départ (`missing/absent/left/abducted/dead`) d'un PNJ `accompanying` **sans cause** (note/reason) est ignoré ; une cause explicite met fin à l'état `accompanying`. `disposition` est parsé depuis `npc_updates`.
- **P2 marqueurs** — `travel_detection` : impératifs ajoutés (« rendons-nous à », « allons vers/au », « conduis/mène/guide-nous », « en avant vers », « cap sur »…) ; `_normalize_text` neutralise apostrophes **et** traits d'union (« rendons-nous à l'oasis » est désormais détecté).
- **P2 fallback** — `action_pipeline._with_travel_scene_fallback` : voyage clair vers une destination connue + aucun `scene_layout` émis par le MJ → injection d'un `scene_layout` sobre (déclenche le portage). Le tour suivant enrichit.
- **Vocabulaire MJ** — `gm_system.txt` / `gm_narrate.txt` : `disposition` documenté, transport automatique des accompagnants, cause obligatoire pour un départ.

**Tests :** `tests/test_game/test_npc_accompanying_carry.py` (15 unitaires, verts) ; 2 scénarios d'acceptation live ajoutés à `test_tabletop_replay_live.py` (`test_live_llm_guide_survives_travel_transition`) — à exécuter avec Ollama/gemma4.

**Reste (hors ce lot) :** confirmation UI 1-clic du voyage (P2-b, frontend) ; P3 (ouverture), P4 (indicateur), P5 (spotlight), P6 (persona). Dette ruff pré-existante (`asyncio`/`field` F401, E501, W292) **non corrigée** — hors périmètre.
