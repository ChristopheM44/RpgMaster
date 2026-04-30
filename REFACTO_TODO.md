# Audit RpgMaster — Suivi refacto par sprints

Cadence : stop après chaque lot → tests + diff review + ✅ user avant d'enchaîner.

---

## SPRINT 1 — Flux narratif unifié 🎯

### Lot 1.1 — Mutualisation des helpers d'agents ✅ TERMINÉ
- [x] Créer `REFACTO_TODO.md`
- [x] Déplacer `_format_messages` vers `BaseAgent` (supprime la duplication gm_agent:258 ↔ player_agent:978)
- [x] Déplacer `_build_messages` vers `BaseAgent` (supprime la duplication gm_agent:215 ↔ player_agent:905)
- [x] Déléguer depuis `GMAgent` et `PlayerAgent`
- [x] `pytest tests/test_agents/ -v` → 56 passed (10 échecs ollama_client préexistants, non liés)
- [x] `ruff check app/agents/` propre
- [x] ✅ Validation user → passer au Lot 1.2

> Note scope : `parse_llm_json` unifié écarté (fallbacks GM vs Player récupèrent des structures
> incompatibles ; le fallback `repair` est async avec accès à `_client`). `_extract_json` est
> déjà dans `BaseAgent` (l.61). La déduplication réelle se limite aux deux méthodes ci-dessus.

### Lot 1.2 — Constantes centralisées ✅ TERMINÉ
- [x] Créer `backend/app/game/constants.py` avec `CombatantStatus`, `INACTIVE_STATUSES`, `ARMOR_CATEGORIES`, `MONSTER_TYPE_COLORS`
- [x] Remplacer `_INACTIVE_NPC_STATUSES` dans `player_agent.py`, `ai_player_manager.py`, `ws_game.py`
- [x] Remplacer `_ARMOR_CATEGORIES` / `_ARMOR_CATS` dans `routes_character.py`, `ws_game.py`
- [x] Migrer `_MONSTER_TYPE_COLORS` de `ws_game.py` vers `constants.py`
- [x] `pytest tests/test_engine/ tests/test_game/ tests/test_agents/ -v` → 107 passed
- [x] `grep -rn "_INACTIVE_NPC_STATUSES\|_ARMOR_CATEGORIES\|_ARMOR_CATS" backend/app/` → vide
- [x] ✅ Validation user → passer au Lot 1.3

### Lot 1.3 — Tests d'intégration de référence (avant Lot 1.4)
- [x] Créer `tests/test_game/test_action_pipeline.py` (4 scénarios baseline)
- [x] Créer `tests/test_agents/test_agent_helpers.py`
- [x] Tests verts → baseline confirmée
- [x] ✅ Validation user → passer au Lot 1.4

### Lot 1.4 — Pipeline unifié de résolution d'action 🎯🎯
- [x] Créer `backend/app/game/action_pipeline.py` (`ActionRequest`, `ResolvedAction`, `ActionPipeline`)
- [x] Créer `backend/app/game/gm_response_executor.py`
- [x] Modifier `action_resolver.py` → façade compatible qui délègue au pipeline
- [x] Modifier `ai_player_manager.py` → les actions arbitrées passent par le pipeline ; `talk` / `wait` restent locaux
- [x] Modifier `ws_game.py` `_handle_ai_turns()` → les monstres passent par `action_resolver.resolve(..., actor_kind="monster")`
- [x] Mettre à jour `tests/test_game/test_action_pipeline.py` → plus de divergence humain / monstre, `ROLL_RESULT` canonique pour les 3 acteurs
- [x] `pytest backend/tests/test_game backend/tests/test_agents -v` → 234 passed
- [x] `pytest backend/tests --cov=app.game --cov=app.agents -q` → 723 passed
- [x] Smoke local scripté OK : humain + compagnon + monstre publient tous `ROLL_RESULT`, puis narration MJ uniforme
- [ ] Smoke test manuel UI/WebSocket complet (session réelle 1 humain + 1 compagnon IA + 1 monstre)
- [ ] ✅ Validation user → Sprint 1 terminé

> Note : `COMBAT_ACTION` reste présent pour compatibilité code/frontend, mais les attaques unifiées de ce lot publient désormais `ROLL_RESULT` puis narration `speaker="Maître du Jeu"` pour humain, compagnon et monstre.

### Lot 1.5 — Flux narratif Table Vivante ✅ TERMINÉ
- [x] Créer `backend/app/services/narrative_flow_service.py` pour orchestrer les scènes d'exploration
- [x] Ajouter la détection d'audience : `gm` / `world` / `party` / `companion` / `mixed`
- [x] Étendre le WebSocket `action` avec `addressed_to`, `audience`, `scene_id`
- [x] Ajouter `PlayerAgent.respond_to_player()` + prompt `player_dialogue.txt`
- [x] Ajouter `CombatGMAgent` + prompt `gm_combat_system.txt`
- [x] Router `ActionPipeline` vers le MJ narratif ou le MJ combat selon la phase
- [x] Enrichir les payloads `narration` avec `speaker_id`, `speaker_kind`, `entry_kind`, `scene_id`
- [x] Frontend : boutons `@Compagnon`, ciblage compagnon, rendu distinct des dialogues
- [x] Tests : `test_narrative_flow_service.py`, `test_combat_gm_agent.py`
- [x] Documentation : `docs/NARRATIVE_FLOW.md` + mise à jour `docs/PROJECT.md`
- [x] `backend/.venv/bin/pytest backend/tests -q` → 737 passed
- [x] `cd frontend && npm run type-check && npm run build` → OK
- [x] Correctif post-smoke : les actions arbitrables de compagnon (`examine`, `move`, `use_item`, `help`) gardent leur dialogue visible puis repassent toujours par le MJ, y compris en mode `sober`
- [x] Tests ciblés correctif : `pytest backend/tests/test_game -q` → 165 passed

> Note : `AIPlayerManager.run_party_reaction_batch()` et `run_exploration_reactions()`
> restent disponibles pour compatibilité, déclenchement manuel et mode sobre, mais le
> flux normal d'exploration passe désormais par `NarrativeFlowService`.
> En mode sobre, seuls les échanges sociaux purs évitent l'appel MJ ; une action de
> compagnon qui touche le monde reste arbitrée pour préserver les transitions.

---

## SPRINT 2 — Allègement backend

### Lot 2.1 — Extraction services depuis ws_game.py ✅ IMPLÉMENTÉ
- [x] Créer `backend/app/services/equipment_service.py` (equip/unequip/use/drop)
- [x] Créer `backend/app/services/rest_service.py` (short/long rest)
- [x] Ajouter `Character.hit_dice` + migration Alembic `d4e5f6a7b8c9`
- [x] Étendre WebSocket : `short_rest`, `long_rest`, alias `take_rest`, `hit_dice_spend`
- [x] Ajouter l'événement `hit_dice_updated`
- [x] Frontend : `RestDialog.vue` avec choix repos court/long et dépense de dés de vie
- [x] `ws_game.py` : handlers équipement/repos délèguent aux services (reste ~1982 lignes ; cible ~1100 indicative)
- [x] Tests automatisés équip/repos
- [x] Documentation : `docs/PROJECT.md` + `backend/CLAUDE.md`
- [ ] Smoke test manuel UI/WebSocket complet équip/repos
- [ ] ✅ Validation user

> Vérifications Lot 2.1 : `backend/.venv/bin/pytest backend/tests -q` → 747 passed ;
> `cd frontend && npm run type-check && npm run build` → OK ;
> `ruff check` ciblé sur les fichiers modifiés → OK.
> Le `ruff check app tests` global reste rouge sur dette préexistante hors lot
> (275 erreurs historiques listées par `--statistics`).

### Lot 2.2 — LLM retry mutualisé
- [ ] Créer `backend/app/llm/retry.py` décorateur `@with_llm_retry`
- [ ] Modifier `ollama_client.py` et `openai_compatible_client.py`
- [ ] ✅ Validation user

### Lot 2.3 — Tests API/agents manquants (couverture 65% → >80%)
- [ ] `tests/test_api/test_routes_admin.py`
- [ ] `tests/test_api/test_routes_campaign.py`
- [ ] `tests/test_api/test_routes_encounters.py`
- [ ] `tests/test_game/test_ai_player_manager.py` (étoffer)
- [ ] ✅ Validation user

---

## SPRINT 3 — Typage bout-en-bout

### Lot 3.1 — CharacterCreate/Update factorisés
- [ ] `schemas/character.py` : `CharacterBase` + héritage propre
- [ ] ✅ Validation user

### Lot 3.2 — Events Pydantic discriminés
- [ ] Créer `backend/app/schemas/events.py` (NarrationEvent, CombatStartEvent…)
- [ ] `event_bus.py` : validation via union discriminé
- [ ] Aligner `frontend/src/types/index.ts`
- [ ] ✅ Validation user

---

## SPRINT 4 — Frontend cohérent

### Lot 4.1 — Composables formatting
- [ ] `frontend/src/composables/useCharacterFormatting.ts`
- [ ] `frontend/src/utils/dndFormulas.ts`
- [ ] ✅ Validation user

### Lot 4.2 — useGameActions & GameSessionHeader
- [ ] `frontend/src/composables/useGameActions.ts`
- [ ] Extraire `GameSessionHeader.vue`
- [ ] ✅ Validation user

### Lot 4.3 — campaign.ts → api.ts
- [ ] Migrer `stores/campaign.ts` vers `services/api.ts::campaignApi`
- [ ] ✅ Validation user

### Lot 4.4 — ActionBar.vue refactorisé
- [ ] Extraire `SpellCastPanel`, `ItemPicker`, `TargetSelector`
- [ ] Composable `useCombatActions()`
- [ ] ✅ Validation user

---

## Vérification globale (fin de chaque sprint)

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check app/ && ruff format --check app/
pytest tests/test_engine/ tests/test_game/ tests/test_agents/ tests/test_api/ -v
pytest --cov=app

# Frontend
cd frontend && npm run type-check && npm run build
```
