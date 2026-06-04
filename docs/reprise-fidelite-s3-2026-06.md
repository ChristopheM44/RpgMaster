# Reprise — Fidélité table, session 3 (handoff)

> **But de ce fichier** : point de départ autonome pour **reprendre à froid** dans un autre contexte. Résume l'état, les décisions et la prochaine étape. **Analyse complète** (preuves tracées au code, plan détaillé) : [`analyse-fidelite-dialogue-oasis-s3-2026-06.md`](analyse-fidelite-dialogue-oasis-s3-2026-06.md).
> **Date** : 2026-06-04 · **Branche** : `main` (working tree, **non commité**).

## Contexte en 30 s

3ᵉ dialogue réel analysé (Piste d'Ambre → Oasis d'Émeraude), rejoué **après** tous les lots déjà livrés (P1/P2/P3, A/B/D/G, symétrie/présence). Verdict utilisateur : « bien meilleur ». **P1 re-validé live** : Khalid reste présent et accompagnant sur tout le voyage + la scène oasis (le bug d'origine ne se reproduit plus). L'analyse a relevé 6 constats neufs (N1–N6).

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

## Prochaine étape = **N3** (à discuter le design AVANT de coder)

Questions à trancher pour démarrer :
1. **F-visible** : où surfacer les approches ? (panneau Objectif/journal dédié, ou interactions POI dans `scene_update` ?) Quelle forme de donnée passe du privé `scene_progress_update` au visible ?
2. **Forge-spine** : granularité de la « clé » par objectif ; où vit la destination atteignable (champ de forge à la génération, ou nœud de scène posé au fil du jeu ?) ; comment garantir « au moins un chemin existe » sans sur-spécifier.
3. Recoupe **N6** : vérifier d'abord si la forge peuple un `primary_objective` concret (sinon l'intro ET l'objectif manquent d'ancrage).

## Backlog restant (plus léger, après N3)

- **N5** — PNJ réticent : après ≥2 esquives sur un sujet qu'il connaît, surfacer un *Insight* contesté + option Intimidation/Persuasion (sous-cas de F).
- **N4** — fail-forward : garantir qu'un indice-clé livre **au moins une bribe** sur échec ; éviter la triple-narration « horreur indéfinissable ». À coupler à **E1**.
- **N6** — origine d'ouverture : nudge `gm_open_scene.txt` (ancrer *d'où vient la mission* / *qui l'a confiée*, sans étiquette) ou renfort journal.
- **E1** — plafond compagnons IA : capper `_run_companion_responses` (chemin social broadcast non plafonné, [narrative_flow_service.py:484](../backend/app/services/narrative_flow_service.py)) — anti roll-spam. Doser en replay live.
- **Qualité-modèle** (bas) : fuite « own » ; variété de prose.

## Pointeurs

- **Analyse complète + plan** : [`docs/analyse-fidelite-dialogue-oasis-s3-2026-06.md`](analyse-fidelite-dialogue-oasis-s3-2026-06.md)
- **Historique du chantier fidélité** (lots A–H, P1–P6) : [`docs/analyse-croisee-fidelite-2026-06.md`](analyse-croisee-fidelite-2026-06.md)
- **Mémoire projet** : `fidelity_dialogue_analysis` (index `MEMORY.md`) — contient le détail technique de N1 et les décisions.
