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
| **R1 = G-bis** | Jet **clic-POI** attribué « Système »/« — » : `_normalize_roll_event` ([action_mechanics.py:132-147](../backend/app/game/action_mechanics.py)) jette `character_name`, `_enrich_roll_event` ([action_pipeline.py:1258-1262](../backend/app/game/action_pipeline.py)) ne le restaure pas → speaker « Système » ([message_service.py:76](../backend/app/services/message_service.py)). Le fix G n'a colmaté qu'`execute_roll_request`. **Texte libre OK** (chemin gm_response_executor). | ✅ tracé — **à coder (déterministe, top)** |
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
| **N3** | Objectif sans **route jouable** ni **destination atteignable** (le bassin/fissure « cul-de-sac ») | 🧩 **décidé, à coder** — *cœur du doute utilisateur* |
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

## Prochaine étape déterministe = **G-bis** (cheap, avant le design N3)

Ferme une **régression live** d'un lot « livré » (Q7). À `_normalize_roll_event` (branche `skill_check`, [action_mechanics.py:132-147](../backend/app/game/action_mechanics.py)) ajouter `"character_name": raw.get("character_name")` **et/ou** à `_enrich_roll_event` ([action_pipeline.py:1258-1262](../backend/app/game/action_pipeline.py)) `enriched.setdefault("character_name", enriched.get("actor_name") or actor_name)`. Test : un jet d'**interaction de scène** persiste le nom du PJ, jamais « Système »/vide. *(Vérifier au passage que le clic-POI transmet `actor_id` du cliqueur ; sinon le fallback `roll_executor:50-55` prend le 1ᵉʳ perso — ici le mod −1 = Thorvald, donc seul le nom fuyait.)*

## Étape de design = **N3** (à discuter le design AVANT de coder)

> **Sharpening (4ᵉ chronique)** : la cible Forge-spine n'est pas « définir un nœud-destination » en l'air, mais **garantir que l'aboutissement de l'objectif est atteignable comme chaîne scène/sortie** (donjon salle-par-salle) **ou** un POI à **clé de déblocage explicite** — **jamais un POI terminal bloqué** (le cas Oasis). **F-visible rétrogradé** en confort de fiabilité (la prose nette a suffi aux Ruines Blanches). Vérifier d'abord le fork §3.1 (donjon vs scène ouverte).

Questions à trancher pour démarrer :
1. **F-visible** : où surfacer les approches ? (panneau Objectif/journal dédié, ou interactions POI dans `scene_update` ?) Quelle forme de donnée passe du privé `scene_progress_update` au visible ?
2. **Forge-spine** : granularité de la « clé » par objectif ; où vit la destination atteignable (champ de forge à la génération, ou nœud de scène posé au fil du jeu ?) ; comment garantir « au moins un chemin existe » sans sur-spécifier.
3. Recoupe **N6** : vérifier d'abord si la forge peuple un `primary_objective` concret (sinon l'intro ET l'objectif manquent d'ancrage).

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
