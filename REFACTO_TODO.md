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
- [ ] Créer `tests/test_game/test_action_pipeline.py` (4 scénarios baseline)
- [ ] Créer `tests/test_agents/test_agent_helpers.py`
- [ ] Tests verts → baseline confirmée
- [ ] ✅ Validation user → passer au Lot 1.4

### Lot 1.4 — Pipeline unifié de résolution d'action 🎯🎯
- [ ] Créer `backend/app/game/action_pipeline.py` (`ResolvedAction`, `ActionPipeline`)
- [ ] Créer `backend/app/game/gm_response_executor.py`
- [ ] Modifier `action_resolver.py` → délègue au pipeline
- [ ] Modifier `ai_player_manager.py` → délègue au pipeline
- [ ] Modifier `ws_game.py` `_handle_ai_turns()` → délègue au pipeline
- [ ] `pytest tests/test_game/ tests/test_agents/ -v` vert
- [ ] Smoke test manuel (humain + compagnon + monstre → narration identique)
- [ ] ✅ Validation user → Sprint 1 terminé

---

## SPRINT 2 — Allègement backend

### Lot 2.1 — Extraction services depuis ws_game.py
- [ ] Créer `services/equipment_service.py` (equip/unequip/use/drop)
- [ ] Créer `services/rest_service.py` (short/long rest)
- [ ] `ws_game.py` : handlers délèguent aux services (~2123 → ~1100 lignes)
- [ ] Tests + smoke test équip/repos
- [ ] ✅ Validation user

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
