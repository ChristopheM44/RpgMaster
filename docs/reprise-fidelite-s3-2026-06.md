# Reprise — Fidélité table, session 3 (handoff)

> **But de ce fichier** : point de départ autonome pour **reprendre à froid** dans un autre contexte. Résume l'état, les décisions et la prochaine étape. **Analyse complète** (preuves tracées au code, plan détaillé) : [`analyse-fidelite-dialogue-oasis-s3-2026-06.md`](analyse-fidelite-dialogue-oasis-s3-2026-06.md).
> **Date** : 2026-06-04 · **Branche** : `main` (working tree, **non commité**).
>
> **⟳ Mise à jour 2026-06-04 (soir)** : une **4ᵉ chronique** (donjon « Ruines Blanches → Crypte du Cœur », **build récent**, **jouée hors de ce poste**) a été analysée → [`analyse-fidelite-chronique-ruines-blanches-2026-06.md`](analyse-fidelite-chronique-ruines-blanches-2026-06.md). **Bonne nouvelle de fond : N3 ne se reproduit pas** (route jouable + source atteinte). **Nouveau top déterministe : G-bis** (régression live de l'attribution de jet Q7 sur le chemin clic-POI). Voir la section dédiée plus bas.

## Contexte en 30 s

3ᵉ dialogue réel analysé (Piste d'Ambre → Oasis d'Émeraude), rejoué **après** tous les lots déjà livrés (P1/P2/P3, A/B/D/G, symétrie/présence). Verdict utilisateur : « bien meilleur ». **P1 re-validé live** : Khalid reste présent et accompagnant sur tout le voyage + la scène oasis (le bug d'origine ne se reproduit plus). L'analyse a relevé 6 constats neufs (N1–N6).

## 4ᵉ chronique — Ruines Blanches (2026-06-04, build récent)

Donjon « Les Ruines Blanches → Crypte du Cœur ». Table = **Thorvald (PC humain)** + Elara/Shade/Solana (compagnons IA), **aucun PNJ**. **Build récent confirmé** → les écarts sont des **trous live dans des lots livrés**. Détail tracé au code : [`analyse-fidelite-chronique-ruines-blanches-2026-06.md`](analyse-fidelite-chronique-ruines-blanches-2026-06.md).

**Crédit (ce qui tient)** : 🟢 **N3 ne se reproduit pas** (route jouable Parvis→…→Crypte, **source atteinte**) ; 🟢 succès → prise jouable (Perception 20 = passage secret + dilemme) ; 🟢 compagnons IA déférents (renvoient la décision à l'humain) ; 🟢 pas de roll-spam ; 🟢 ouverture ancre QUI+POURQUOI (progrès N6).

**Constats neufs** :

| Constat | Résumé | Statut |
|---|---|---|
| **R1 = G-bis** | Jet **clic-POI** attribué « Système »/« — » : `_normalize_roll_event` jette `character_name`, `_enrich_roll_event` ne le restaure pas. | ✅ **LIVRÉ 2026-06-04** (edit A normalize + edit B enrich garde-piège ; 3 tests ; 556 ✓) |
| **R2** | Relique **ramassée sans déclaration** du PC humain (suggérée par un compagnon) → non-conformité [gm_narrate.txt:111](../backend/app/agents/prompts/gm_narrate.txt) + [:116](../backend/app/agents/prompts/gm_narrate.txt) | ✅ tracé — renfort E2-cheap (prompt) |
| **R3** | « L'entrée a disparu » : **assertion-monde non arbitrée** par le MJ, ratifiée par un compagnon → INTENTION≠FAIT [gm_narrate.txt:92](../backend/app/agents/prompts/gm_narrate.txt) | ✅ tracé — neuf petit (prompt) + recoupe N3 |
| **R4** | Ouverture : commanditaire **anonyme** + objectif en **liste** (résidu N6/P3) → tension [gm_open_scene.txt:27/:33](../backend/app/agents/prompts/gm_open_scene.txt) | ✅ tracé — = N6 |
| **§3.1** | Pourquoi N3 marche ici : **hypothèse structurelle** (donjon salle-par-salle = chaîne scène/sortie vs Oasis = POI terminal bloqué). Sharpening Forge-spine ; F-visible rétrogradé en confort. | 🔶 fork (session non inspectable) |

**Non exercés** : N1/D (pas de PNJ), N5 (pas de PNJ), N4 (5 jets réussis, aucun échec), E1 (pas de saturation).

## État des constats

| Constat | Résumé | Statut |
|---|---|---|
| **N1** | Double réponse PNJ : pas d'indicateur « le PNJ répond » + pas de garde anti-concurrence | ✅ **livré 2026-06-04** |
| **N2** | 2 déconnexions WS | ❌ **hors scope** (dev back en cours pendant la partie, pas un bug) |
| **N3** | Objectif sans **route jouable** ni **destination atteignable** (le bassin/fissure « cul-de-sac ») | ✅ **LIVRÉ 2026-06-05** (seed carte + A2 nudge ; **mécanisme corrigé** : edge VISIBLE + nom flou, pas edge caché — la version verrouillée était inerte. Voir section dédiée) |
| **N5** | PNJ détenteur d'un secret sans **levier jouable** (Khalid esquive 3×, aucun Insight/Intimidation) | ⏳ ouvert (prompt) |
| **N4** | 3 jets ratés d'affilée sur la carcasse → **aucun fail-forward** + roll-spam | ⏳ ouvert (prompt + E1) |
| **N6** | Intro : *où* clair, *origine/pourquoi* sous-surfacé (tension avec P3 « jamais d'étiquette ») | ⏳ ouvert (nudge prompt) |
| — | Fuite anglais « own » dans la prose FR ; prose « dread » répétitive | ⚪ bas (model-quality) |

## Ce qui est fait — N1 (livré)

**Problème** : Solana interpelle Khalid → relais PNJ **silencieux** → le joueur repose la question → 2 tâches frappent Khalid **en parallèle** → 2 réponses.

**Correctif** — `resolve_npc_dialogue` scindé en **wrapper public** + `_resolve_npc_dialogue_impl` (corps inchangé) :
- **Indicateur dédié** kind `npc` → libellé **« {PNJ} répond »** (jamais « Le joueur IA réfléchit », qui serait une couture). Publié en `try/finally`.
- **Garde anti-concurrence étroit** : champ transient `ActiveSession.npc_dialogue_in_flight` ; check-and-add **atomique** (aucun `await` entre le test et le `.add()`). Coalesce le 2ᵉ déclencheur **concurrent du même PNJ** ; **ne bride pas** une relance d'un autre PNJ ni séquentielle (Oaken reste légitime).
- **Anti-couture (fold-in advisor)** : le nom d'affichage retombe sur le **nom du POI** (`_poi_by_id`) au premier contact, jamais l'id brut (« `masked_stranger` »).

**Fichiers touchés** :
- Backend : [action_resolver.py](../backend/app/game/action_resolver.py) (wrapper + `_publish_npc_thinking`), [session_manager.py](../backend/app/game/session_manager.py) (champ `npc_dialogue_in_flight`).
- Frontend : [game.ts](../frontend/src/stores/game.ts) (`thinkingNpcNames`, branche `npc`, computeds `isNpcThinking`/`npcThinkingNames`), [NarrativeLog.vue](../frontend/src/components/narrative/NarrativeLog.vue) (`thinkingLabel`), [types/index.ts](../frontend/src/types/index.ts) (`agent_kind` += `'npc'`).
- Tests : `test_action_resolver.py::TestNpcDialogueIndicatorAndGuard` (3), `NarrativeLog.test.ts` (libellé PNJ).

**Vérifier (commande)** :
```bash
# backend
cd backend && source .venv/bin/activate
python -m pytest tests/test_agents/ tests/test_game/ -q          # → 553 passed
ruff check app/game/action_resolver.py app/game/session_manager.py
# frontend
cd frontend && npm run type-check && npx vitest run               # → 92 passed
```
**Reste à confirmer une fois** : rendu **live** (interpeller un PNJ en jeu → voir « X répond »). Non prouvable en test unitaire ; rien d'autre ne le bloque (même bloc de template que les indicateurs MJ/IA existants).

## Décisions prises (2026-06-04)

- **N2 = hors scope** — déconnexions provoquées par un dev back en cours, pas un bug applicatif. Retiré du plan.
- **N3 = les deux phases** :
  - **Phase 1 — F-visible** : rendre **cliquables** les « approches encore possibles » que le MJ calcule déjà dans `scene_progress_update` ([gm_narrate.txt:99](../backend/app/agents/prompts/gm_narrate.txt)) — aujourd'hui **« privé MJ-only »**, donc jamais montrées au joueur.
  - **Phase 2 — Forge-spine** : chaque objectif clé porte une **destination atteignable** + ≥1 **« clé »** de passage, défini à la génération (sinon le MJ ne peut pas créer de sortie vers « la source » → cul-de-sac, cf. [gm_narrate.txt:55](../backend/app/agents/prompts/gm_narrate.txt) + objectifs forge abstraits [campaign_dossier_service.py:1448](../backend/app/services/campaign_dossier_service.py)).
  - **Pas** de validateur de physique (inconstruisible, jugement LLM trop fragile).

## G-bis — **LIVRÉ** (2026-06-04, sur `main`, non commité)

Régression Q7 (attribution jet clic-POI) fermée. **2 edits complémentaires** :
- (A) [action_mechanics.py](../backend/app/game/action_mechanics.py) `_normalize_roll_event` branche `skill_check` propage `"character_name": raw.get("character_name")` → le nom du PC **résolu** survit à la normalisation.
- (B) [action_pipeline.py](../backend/app/game/action_pipeline.py) `_enrich_roll_event` backfill **garde-piège** : `if not enriched.get("character_name"): fallback = payload.get("actor_name") or actor_name; if fallback: enriched["character_name"]=str(fallback)`. Garde-piège ≠ `setdefault` (edit A peut insérer `None`) ; lecture de `payload` (pré-coercion) car `effective_actor_name=str(...)` peut valoir la chaîne `"None"`. Chokepoint roll-type-agnostic (couvre toute branche normalize). Scope borné : **pas** `_enrich_mechanics_result` ni les autres branches (advisor).
- **Tests** ([test_action_mechanics.py](../backend/tests/test_game/test_action_mechanics.py), 3 neufs) : round-trip scène, backfill depuis actor, sans-nom reste « Système » jamais « None ». **Vérif : test_action_mechanics 10 ✓ ; test_agents+test_game 556 ✓ (+1 ERROR = flake d'isolation `test_ws_game::TestJoin` PRÉ-EXISTANT, passe en isolation 22 ✓) ; ruff clean.**

## N3 — ✅ LIVRÉ (2026-06-05) : seed carte (edge **VISIBLE**) + nudge A2

> **⚠️ Correction de mécanisme à l'implémentation (preuve au code).** Le design verrouillé reposait sur un **edge `hidden:true`** (« le joueur ne voit pas le pin, le MJ route quand même »). **Les deux moitiés sont fausses au code** : (1) le contexte carte du MJ passe par `_game_state_for_gm → map_context_for_session → compact_map_context → public_region_map`, qui **retire les edges cachés** → le MJ ne verrait PAS l'endpoint non plus (`nearby_map_nodes` lit des edges déjà filtrés, [gm_agent.py:268-296](../backend/app/agents/gm_agent.py)) → **fix inerte** ; (2) `public_region_map` filtre les **edges**, jamais les **nœuds**, et le frontend rend tous les nœuds ([NodeMap.vue:72](../frontend/src/components/map/NodeMap.vue)) → le joueur voit le pin de toute façon. **Décision utilisateur (2026-06-05) = Option A : edge VISIBLE + nom de nœud flou/évocateur + hint de voyage non-spoiler.** Le MJ voit l'endpoint (route), le joueur a une piste directionnelle non-spoiler ; aucune modif de la plomberie carte.

**Construit (LIVRÉ 2026-06-05, `main`, non commité)** :
- **Champ forge** `objective_endpoint` `{name, kind, hint}` par chapitre — `_sanitize_objective_endpoint` + ajout à `_sanitize_private_chapter` ; projeté **MJ-only** dans `_private_active_chapter_for_context` (pas la vue publique → le `hint` ne fuit pas via campaign_context). Prompts : [campaign_forge_dossier.txt](../backend/app/agents/prompts/campaign_forge_dossier.txt) + [campaign_forge_chapter.txt](../backend/app/agents/prompts/campaign_forge_chapter.txt) (nom évocateur **non-spoiler**, kind régional, hint sûr).
- **Seed pur** `map_service.build_seed_region_map(start_name, endpoint)` : nœud départ (`current`, depuis `opening_scene.venue|place`) + nœud-objectif (`rumored`) + **1 edge VISIBLE** (`hidden:false`), ids/positions distincts (pas de carte dégénérée 1-nœud). Renvoie `None` sans endpoint.
- **Lieu du seed = `gm_dossier["region_map"]`** (source de vérité campagne, lue en 1er par `map_context_for_session`, écrite par `region_map_update`), **PAS** `state_data.world_maps`/`session_manager:138` comme disait le design : un seed dans state_data serait écrasé en lecture et ignoré par le 1er merge MJ. Semé via `seed_region_map_from_dossier()` à la **forge** (`forge_dossier` + `_run_forge_job`) et au **reset** (`reset_played_state` ne nulle plus aveuglément → re-sème).
- **Nudge A2** [gm_narrate.txt](../backend/app/agents/prompts/gm_narrate.txt) : un obstacle gardant un nœud proche connu/rumored n'est jamais un cul-de-sac → router vers lui (journal_update + scene_layout) ou poser une sortie une fois franchi.
- **Anti skip-to-climax (conséquence d'Option A)** : edge visible ⇒ l'endpoint devenait une cible de voyage **clic-tour-1** (`canTravel` ne gatait que la reachabilité). Gate ajoutée [map/RegionMap.vue](../frontend/src/components/map/RegionMap.vue) : **pas de « Voyager » vers un nœud `rumored`** (la piste reste visible — pin + chemin surlignés — mais non téléportable ; le MJ le passe en known/visited par le jeu).

**Tests (sans LLM)** : `build_seed_region_map` (6, test_map_service) ; MJ voit l'endpoint via **carte compactée** dans `nearby_map_nodes` (test_gm_agent) ; piste visible côté joueur (`public_region_map`) ; `seed_region_map_from_dossier` + sanitize + **forge intègre** (test_campaign_dossier) ; gate voyage rumored (RegionMap.test.ts). **Vérif : back `test_agents+test_game` 600 ✓, `test_api+test_engine` 1289 ✓, ruff clean ; front type-check ✓, vitest 100 ✓.**

**Portée honnête (ne pas arrondir « livré+tests » en « N3 réglé »)** : les tests sans-LLM prouvent la **précondition** (endpoint dans `nearby_map_nodes` côté MJ), **pas** que le MJ **route effectivement** vers lui — fiabilité de routage **replay-gated** (comme F-visible). Bénéficie aux campagnes **fraîchement forgées ou resetées** seulement : les sauvegardes existantes (Oasis) n'ont pas d'`objective_endpoint` → pas de seed (pas de rétro-fix). **Cosmétique** : pré-semer `region_map` le rend « présent dans world_maps » → [gm_narrate.txt:186-187](../backend/app/agents/prompts/gm_narrate.txt) dit au MJ de **ne pas** créer de décor pour la région → repli décor procédural pour les campagnes semées (acceptable).

---

<details><summary>Design d'origine (verrouillé 2026-06-04) — conservé pour historique ; mécanisme edge-caché corrigé ci-dessus.</summary>

> **Fork §3.1 clos par lecture de code** (plus une hypothèse) : l'endpoint est non-routable **par construction** — (1) la forge ne produit jamais de `region_map` (le prompt demande `known_objectives`/`key_locations` en *strings*, jamais un graphe nodes/edges) ; (2) l'ouverture de session fige `region_map: None` en dur ([session_manager.py:138-140](../backend/app/game/session_manager.py)), **jamais semé depuis le dossier** ; (3) `nearby_map_nodes` ([gm_agent.py:267-296](../backend/app/agents/gm_agent.py)) ne lit que `world_maps.region_map` → `None` ⇒ le MJ n'a aucun nœud où router ⇒ il ne reste que les exits de scène (chemin LLM fragile). Le donjon marche car chaque salle pose un **exit** vers la suivante ; l'Oasis a modélisé « la source » en **POI terminal** sans exit ni nœud → gm_narrate.txt:55 interdit d'inventer le lieu → cul-de-sac.

**Décisions utilisateur (verrouillées)** :
1. **Endpoint** = **nouveau champ forge explicite** `{name, kind, hint}` pour l'objectif du chapitre actif (matière du nœud-destination ; nourrit aussi **N6**).
2. **Révélation** = **caché-joueur / connu-MJ** : edge `hidden:true` + nœud au nom **flou/évocateur** (pas spoiler). `public_region_map` filtre les edges cachés côté joueur ([map_service.py:145](../backend/app/services/map_service.py)) **mais** `nearby_map_nodes` lit les edges **bruts côté MJ** → l'endpoint est **disponible** au routage MJ dès le tour 1 (le joueur ne voit pas le pin). Flip `hidden→false` sur indice = **polish optionnel**, non requis pour le fix. **Portée honnête** : le seed **élimine le cul-de-sac *structurel* de façon déterministe** (gm_narrate.txt:55 ne peut plus bloquer : le lieu existe comme nœud) ; mais le **routage *effectif*** (le MJ choisit d'y aller) reste **A2/prompt-médié** — le test sans LLM prouve la *précondition* (endpoint dans `nearby_map_nodes`), pas le routage. **Fiabilité de routage à valider en replay live**, comme F-visible.
3. **Ampleur** = **minimal** : nœud départ (`status:"current"`) + nœud endpoint (`status:"rumored"`) + **1 edge caché**. La lazy-growth en jeu (`region_map_update`, merge par id) étoffe le reste.

**Slice d'implémentation** :
- **Forge** : `campaign_forge_dossier.txt` + `sanitize_gm_dossier` ([campaign_dossier_service.py:~1490-1520](../backend/app/services/campaign_dossier_service.py)) — émettre/valider l'endpoint structuré du chapitre actif.
- **Seed** : helper `build_seed_region_map(dossier)` (schéma `RegionMap`/`MapNode`/`MapEdge` de [schemas/map.py](../backend/app/schemas/map.py) ; `MapEdge.hidden`, `MapNode.status="rumored"`, `updated_at` requis). Nœud départ depuis `opening_scene.venue` du dossier (déjà présent), sinon générique. **Injection** à l'init de `state_data.world_maps` ([session_manager.py:138-140](../backend/app/game/session_manager.py)) : si `region_map` None et dossier porte un endpoint → semer au lieu de `None`.
- **Reset** : `reset_played_state:332` ([campaign_dossier_service.py:332](../backend/app/services/campaign_dossier_service.py)) ne nulle plus aveuglément → re-sème depuis le dossier.
- **Nudge A2** : `gm_narrate.txt` — un obstacle gardant un nœud `rumored`/connu n'est **jamais** un POI terminal ; router vers le nœud (ou poser une sortie vers lui) une fois franchi.
- **Test sans LLM** : seed → l'endpoint apparaît dans `nearby_map_nodes` (côté MJ) ; `public_region_map` ne l'expose pas au joueur.

**Hors slice** : **F-visible différé** (la prose nette a suffi aux Ruines Blanches ; n'y revenir que si un replay re-montre un blocage). Pas de validateur de physique. Pas de primitive flip-exit (le bug ne le réclame pas — advisor).

</details>

## Backlog restant (plus léger, après N3)

- **N5** — PNJ réticent : après ≥2 esquives sur un sujet qu'il connaît, surfacer un *Insight* contesté + option Intimidation/Persuasion (sous-cas de F).
- **N4** — fail-forward : garantir qu'un indice-clé livre **au moins une bribe** sur échec ; éviter la triple-narration « horreur indéfinissable ». À coupler à **E1**.
- **N6** — origine d'ouverture : nudge `gm_open_scene.txt` (ancrer *d'où vient la mission* / *qui l'a confiée*, sans étiquette) ou renfort journal. **Précision R4 (4ᵉ chro)** : **nommer/donner un visage** au commanditaire si le dossier l'établit + **tisser** l'objectif en une phrase d'enjeu (jamais une **liste d'infinitifs**).
- **R2** — relique ramassée sans déclaration : renfort `gm_narrate.txt:111` — ne **jamais** placer un objet dans l'inventaire d'un PC humain (ni narrer qu'il ramasse) **sans action déclarée** par lui (ou `loot_grant` canonique) ; une **suggestion de compagnon ne vaut pas action du PC humain**. (Prompt, cheap.)
- **R3** — assertions-monde : quand un joueur **affirme/interroge un état du monde** (sortie disparue, passage bloqué, objet présent), le MJ **tranche explicitement** (confirme le *beat* ou infirme) — **jamais** de délégation de cet arbitrage à un compagnon IA. Recoupe N3 (sortie de retour persistée). (Prompt, cheap.)
- **E1** — plafond compagnons IA : capper `_run_companion_responses` (chemin social broadcast non plafonné, [narrative_flow_service.py:484](../backend/app/services/narrative_flow_service.py)) — anti roll-spam. Doser en replay live.
- **Qualité-modèle** (bas) : fuite « own » ; variété de prose.

## Pointeurs

- **Analyse 4ᵉ chronique (Ruines Blanches)** : [`docs/analyse-fidelite-chronique-ruines-blanches-2026-06.md`](analyse-fidelite-chronique-ruines-blanches-2026-06.md) — N3 OK + G-bis + R2/R3/R4
- **Analyse complète + plan (3ᵉ, Oasis)** : [`docs/analyse-fidelite-dialogue-oasis-s3-2026-06.md`](analyse-fidelite-dialogue-oasis-s3-2026-06.md)
- **Historique du chantier fidélité** (lots A–H, P1–P6) : [`docs/analyse-croisee-fidelite-2026-06.md`](analyse-croisee-fidelite-2026-06.md)
- **Mémoire projet** : `fidelity_dialogue_analysis` (index `MEMORY.md`) — contient le détail technique de N1 et les décisions.
