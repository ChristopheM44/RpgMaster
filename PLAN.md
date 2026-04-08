# Plan de corrections et améliorations — RpgMaster

> Généré le 2026-03-31. Mis à jour à chaque étape complétée.

## Causes racines identifiées

- **Bug 1 (Save/Load)** : Le modèle `Message` existe en DB mais n'est jamais écrit — aucune narration n'est persistée. `get_history` retourne 0 messages. La reconnexion après load est manuelle.
- **Bug 2 (accueil)** : Le handler `join` WebSocket ne déclenche rien si la phase est déjà `exploration`. Le MJ ne parle pas spontanément.
- **Bug 4 (désync combat)** : `_handle_start_combat` génère l'encounter par niveau du groupe uniquement, sans consulter le contexte narratif du MJ.
- **Bug 5 (transparence IA)** : Pas d'event structuré `COMBAT_ACTION` — seule une prose LLM est émise lors des tours IA/monstres.

---

## Phase 1 — Bugs critiques ✅ / 🔄 / ⬜

### Bug 1 : Save/Load — log vide + reconnexion manuelle

| # | Fichier | Changement | Status |
|---|---------|-----------|--------|
| 1a | `backend/app/services/message_service.py` (nouveau) | Fonction `persist_narration()` qui insère en DB | ✅ DONE |
| 1b | `backend/app/game/action_resolver.py` | Appeler `persist_narration()` après chaque narration MJ | ✅ DONE |
| 1c | `backend/app/api/routes_game.py` | Persister narration `start_game` + broadcast `SESSION_STATE` après `load_save` | ✅ DONE |
| 1d | `backend/app/api/ws_game.py` | Persister narrations de `combat_end`, `take_rest`, `start_combat` | ✅ DONE |
| 1e | `frontend/src/components/ui/SaveLoadPanel.vue` | Émettre `@load-complete` au lieu de "Reconnexion recommandée" | ✅ DONE |
| 1f | `frontend/src/views/GameSessionView.vue` | Extraire `initSession()`, gérer `@load-complete` | ✅ DONE |

### Bug 2 : Message d'accueil au rejoindre

| # | Fichier | Changement | Status |
|---|---------|-----------|--------|
| 2a | `backend/app/api/ws_game.py` | Dans handler `join`, si phase = `exploration`, lancer `GMAgent.narrate()` en `create_task()` | ✅ DONE |

---

## Phase 2 — Cohérence narration/combat + Feature "Lancer l'aventure" ⬜

### Bug 4 : Désynchronisation rencontre/narration

| # | Fichier | Changement | Status |
|---|---------|-----------|--------|
| 4a | `backend/app/agents/prompts/gm_system.txt` | Ajouter type d'action `encounter_setup` | ✅ DONE |
| 4b | `backend/app/agents/prompts/gm_narrate.txt` | Instruction : émettre `encounter_setup` quand ennemis décrits | ✅ DONE |
| 4c | `backend/app/game/action_resolver.py` | Gérer `encounter_setup` → `state_data["pending_encounter"]` | ✅ DONE |
| 4d | `backend/app/services/encounter_service.py` | Nouvelle méthode `build_from_monster_ids()` | ✅ DONE |
| 4e | `backend/app/api/ws_game.py` | `_handle_start_combat` consomme `pending_encounter` en priorité | ✅ DONE |

### Feature 3 : Bouton "Lancer l'aventure"

| # | Fichier | Changement | Status |
|---|---------|-----------|--------|
| 3a | `backend/app/api/routes_game.py` | `start_game` accepte body `{adventure_script?, auto_generate?}` | ✅ DONE |
| 3b | `frontend/src/components/ui/AdventureStartModal.vue` (nouveau) | Modal 3 options : libre / script / génération auto | ✅ DONE |
| 3c | `frontend/src/views/GameSessionView.vue` | Remplacer bouton par ouverture du modal | ✅ DONE |
| 3d | `frontend/src/services/api.ts` | `gameApi.start()` accepte body optionnel | ✅ DONE |

---

## Phase 3 — Transparence des actions IA en combat ✅

### Bug 5 : Log structuré des actions IA

| # | Fichier | Changement | Status |
|---|---------|-----------|--------|
| 5a | `backend/app/game/event_bus.py` | Ajouter `COMBAT_ACTION` event type | ✅ DONE |
| 5b | `backend/app/api/ws_game.py` | Résolution mécanique déterministe monstres + émettre `COMBAT_ACTION` | ✅ DONE |
| 5c | `backend/app/agents/prompts/gm_combat.txt` | LLM narration prose uniquement, pas de mécaniques | ✅ DONE |
| 5d | `frontend/src/types/index.ts` | Ajouter `CombatActionPayload` et type `'combat_action'` | ✅ DONE |
| 5e | `frontend/src/stores/game.ts` | Ajouter `addCombatAction()` | ✅ DONE |
| 5f | `frontend/src/composables/useWebSocket.ts` | Gérer `case 'combat_action'` | ✅ DONE |
| 5g | `frontend/src/components/narrative/NarrativeLog.vue` | Afficher entrées `combat_action` structurées | ✅ DONE |

---

## Risques à surveiller

- **DB async** : Réutiliser le `db` existant dans les handlers, ne pas créer de nouvelle session SQLAlchemy
- **LLM lent au join** : Appel GMAgent dans handler `join` en `asyncio.create_task()` — non-bloquant
- **Scripts aventure** : Passer contenu brut au LLM sans parser (gère prose et JSON)
