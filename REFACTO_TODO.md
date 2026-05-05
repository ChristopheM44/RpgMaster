# Plan de refacto consolide RpgMaster

> Derniere mise a jour : 2026-05-04

Objectif : garder un seul plan actif apres les deux audits, avec une cible **local renforce**. Les audits restent des sources de diagnostic, pas des roadmaps a appliquer telles quelles.

---

## Orientation

- Cible principale : outil local / reseau de confiance, pas service public multi-tenant.
- Priorite : securite locale, robustesse WebSocket, reduction progressive de la dette, preservation du comportement de jeu.
- Hors chemin critique : JWT utilisateurs, table `api_keys`, Redis, Postgres, rate limiting lourd, refacto profond de `player_agent.py`, JSON mode LLM natif.

---

## Deja livre avant ce cycle

- [x] Schemas WebSocket stricts dans `backend/app/api/ws_schemas.py`.
- [x] `ConnectionManager`, locks par session, `state_schema` v1.
- [x] `EventBus` borne avec logs/metrics de drops.
- [x] Extraction initiale `ws_payloads.py` et handlers `encounter_intro.py`, `combat.py`, `ai_control.py`.
- [x] Tests WS/API/frontend existants autour des payloads, intros, combat handlers et `useWebSocket`.
- [x] Frontend token optionnel `VITE_RPGMASTER_ACCESS_TOKEN`.

---

## Lots restants

### Lot A - Securite et configuration locale

- [ ] Revoquer/rotater toute cle exposee hors repo.
- [x] Remettre la config runtime LLM locale sur `http://localhost:11434` sans cle API stockee.
- [x] Completer `.env.example` avec `APP_ACCESS_TOKEN`, `VITE_RPGMASTER_ACCESS_TOKEN`, `RUNTIME_DIR`, `LLM_BUDGET_MODE`, `OLLAMA_MAX_CONCURRENT_REQUESTS`.
- [x] Refuser le demarrage si `APP_DEBUG=false` et aucun `APP_ACCESS_TOKEN` n'est configure.
- [x] Redacter les secrets presents dans les audits locaux non trackes.

### Lot B - WebSocket et API

- [x] Deplacer le singleton `session_manager` hors de `api/ws_game.py` vers un runtime partage.
- [x] Garder un alias temporaire dans `ws_game.py` pour compatibilite tests/imports historiques.
- [x] Valider au `join` WS que le `character_id` existe et appartient a la session.
- [x] Remplacer les messages `str(ValidationError)` envoyes au client par des erreurs generiques.
- [x] Ajouter un schema Pydantic `SaveSlotCreate` pour `POST /game/{session_id}/saves`.
- [ ] Continuer l'extraction progressive de `ws_game.py` sans big bang.

### Lot C - Robustesse async, prompts et mecanique

- [x] Ajouter `create_logged_task(coro, name)` et l'utiliser pour TTS/welcome narration fire-and-forget.
- [x] Delimiter les entrees joueur dans les prompts GM/combat/social/outcome.
- [x] Extraire `game/roll_executor.py` pour mutualiser `roll_request`.
- [x] Transformer `ActionResolver` vers la composition avec `ActionMechanics`, en gardant les methodes facade.
- [x] Documenter `ActiveSession.state_data` comme source autoritaire pendant une session active.
- [x] Ajouter un helper unique de synchronisation personnage pour HP/equipement/slots/hit dice/conditions.

### Lot D - Frontend

- [x] Creer une liste source unique `WS_EVENT_TYPES_LIST as const` et deriver `WsEventType`.
- [x] Ajouter des guards pour `combat_action`, `combatant_moved`, `combatant_status_changed`, `scene_layout_changed`.
- [x] Passer la reconnexion WS en backoff exponentiel + jitter.
- [x] Migrer `campaignStore` vers `frontend/src/services/api.ts`.
- [x] Supprimer le counter store/test inutilise.
- [x] Limiter la queue audio TTS et exposer `cancelAll()`.

---

## Verifications attendues

- Backend cible : `backend/.venv/bin/pytest backend/tests/test_game/test_ws_game.py backend/tests/test_api/test_ws_payloads.py backend/tests/test_api/test_ws_encounter_intro.py backend/tests/test_api/test_ws_combat_handlers.py -q`.
- Securite/API : tests pour token obligatoire hors debug, join personnage absent/hors session, erreurs Pydantic generiques, `SaveSlotCreate`.
- Action pipeline : tests pour `roll_executor`, composition `ActionResolver`, attaque/sort/death save/stabilize.
- Prompt safety : test de rendu avec texte joueur contenant `ignore previous instructions`.
- Frontend : `cd frontend && npm run type-check && npm run test && npm run build`.
- Smoke manuel final : 1 humain + 1 compagnon IA + 1 monstre, puis equipement/repos.
