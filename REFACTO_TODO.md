# Audit RpgMaster - Suivi refacto post-audit

> Derniere mise a jour : 2026-05-03

Objectif du cycle : terminer le refacto demarre apres audit sans reprendre les lots deja livres, en gardant la compatibilite des tests existants.

---

## Etat global

| Lot | Statut | Resultat |
|-----|--------|----------|
| Securite / robustesse locale | Termine | Schemas WS, auth locale optionnelle, EventBus borne, locks session, state schema v1 |
| Lot 4 - Extraction progressive `ws_game.py` | Termine | Payloads et handlers intro/combat/IA extraits avec facade compatible |
| Lot 5 - ActionPipeline / Resolver | Termine | Mecanique extraite dans `action_mechanics.py`, `ActionResolver` conserve comme facade |
| Lot 6 - Combat et transitions | Termine | Boucle unique des tours IA combat compagnons + monstres, `start_mode` couvert |
| Lot 7 - Frontend WS | Termine | Types WS alignes backend, guards runtime legers, reconnexion/token preserves |

Il ne reste pas de lot technique post-audit ouvert dans ce fichier. Les seules actions restantes sont des smokes manuels UI/WebSocket si besoin.

---

## Fondations deja livrees

- [x] `backend/app/api/ws_schemas.py`
- [x] `backend/app/api/connection_manager.py`
- [x] `backend/app/security.py`
- [x] `backend/app/game/state_schema.py`
- [x] `EventBus` renomme en `InProcessEventBus`, alias compatible `EventBus`
- [x] `schema_version=1` dans `state_data`
- [x] Locks par session dans `SessionManager`
- [x] Auth locale optionnelle via `app_access_token`
- [x] Frontend token optionnel `VITE_RPGMASTER_ACCESS_TOKEN`
- [x] Reconnexion WS frontend avec `characterId` persistant
- [x] `ENCOUNTER_START -> EXPLORATION` autorise
- [x] `GMResponse.start_mode` ajoute pour les intros de rencontre

Derniere validation connue avant ce cycle :

- `backend/.venv/bin/pytest backend/tests -q` -> `1161 passed`
- `cd frontend && npm run type-check && npm run test && npm run build` -> OK
- `ruff check` cible sur fichiers modifies -> OK

---

## Lot 4 - Extraction progressive de `ws_game.py` - Termine

But : reduire `backend/app/api/ws_game.py` sans changement comportemental.

- [x] Creer `backend/app/api/ws_payloads.py`
  - `build_session_state_payload`
  - `build_combat_start_payload`
  - helpers tokens/couleurs/actions monstres
  - snapshot personnage et calcul AC
- [x] Creer `backend/app/api/ws_handlers/encounter_intro.py`
  - intro rencontre dediee
  - `start_mode`
  - pause en `ENCOUNTER_START`
  - execution sure du `scene_layout` d'intro
- [x] Creer `backend/app/api/ws_handlers/combat.py`
  - helpers purs de ciblage social combat
  - guard hors tour
  - textes et raisons de fin de combat
- [x] Creer `backend/app/api/ws_handlers/ai_control.py`
  - boucle des tours IA combat extraite
  - resolution compagnon + monstre depuis un meme point d'entree
- [x] Garder `game_websocket()`, `_dispatch_action()` et les fonctions privees historiques de `ws_game.py` comme facade compatible avec les tests.
- [x] Tests ajoutes :
  - `backend/tests/test_api/test_ws_payloads.py`
  - `backend/tests/test_api/test_ws_encounter_intro.py`
  - `backend/tests/test_api/test_ws_combat_handlers.py`

Notes :

- `ws_game.py` reste volontairement la facade WebSocket principale.
- L'extraction est progressive : les handlers equipement/repos et le dispatch global restent en place pour eviter un big bang.

---

## Lot 5 - ActionPipeline / Resolver - Termine

But : clarifier `ActionResolver` sans casser les tests existants.

- [x] Creer `backend/app/game/action_mechanics.py`.
- [x] Deplacer les helpers mecaniques historiques :
  - `_resolve_attack`
  - `_normalize_roll_event`
  - `_resolve_generic_roll`
  - `_resolve_cast_spell`
  - `_resolve_death_save`
  - `_apply_death_save_outcome`
  - `_resolve_stabilize`
  - `_execute_roll_request`
- [x] Garder `ActionResolver` comme facade compatible via heritage `ActionMechanics`.
- [x] Garder la reutilisation durable de `ActionPipeline` par `ActionResolver`.
- [x] Ne pas renommer `ActionResolver` en `ActionService` : risque inutile pour le moment.
- [x] Tests ajoutes :
  - `backend/tests/test_game/test_action_mechanics.py`

---

## Lot 6 - Combat et transitions - Termine

But : unifier la logique des tours IA combat.

- [x] Extraire la boucle commune dans `backend/app/api/ws_handlers/ai_control.py`.
- [x] Garder `_handle_ai_turns()` dans `ws_game.py` comme facade.
- [x] Eviter la duplication :
  - compagnons IA -> `AIPlayerManager.process_ai_turns(..., max_turns=1)`
  - monstres -> meme boucle WS extraite, action resolue par `ActionResolver`
- [x] `trigger_ai_reactions` en combat repasse par `_handle_ai_turns()`, y compris si le tour courant est un monstre et qu'il n'y a aucun compagnon IA.
- [x] Verification `pending_phase_transition` :
  - consommation apres succes dans `_consume_pending_combat_transition`
  - pas de suppression avant `_handle_start_combat`
- [x] `start_mode: "pause" | "combat"` integre :
  - fallback texte pour sommation
  - `start_mode="pause"` garde `ENCOUNTER_START`
  - `start_mode="combat"` force le lancement direct meme avec marqueurs de pause
- [x] Test dedie ajoute dans `backend/tests/test_game/test_action_pipeline.py`.

---

## Lot 7 - Frontend WS - Termine

But : finaliser l'alignement protocole frontend/backend.

- [x] Aligner `WsEventType` avec `EventType` backend :
  - ajout `dialogue`
  - ajout `damage_applied`
  - conservation de `pong` comme extension protocolaire WS hors `EventType`
- [x] Ajouter des guards runtime legers dans `useWebSocket.ts` :
  - `session_state`
  - `narration` / `dialogue`
  - `roll_result`
  - `turn_start`
  - `phase_change`
  - `combat_start`
  - `hp_changed`
  - updates personnage critiques
  - `error` / `audio`
- [x] Revalider les chemins existants :
  - token HTTP/WS conserve (`VITE_RPGMASTER_ACCESS_TOKEN`)
  - reconnexion avec `characterId` persistant conservee
  - handlers `player_joined`, `player_left`, `turn_end`, `round_start` conserves
- [x] Tests frontend ajoutes dans `frontend/src/composables/__tests__/useWebSocket.test.ts`.

---

## Verifications de ce cycle

Verifications deja executees pendant l'implementation :

- `backend/.venv/bin/pytest backend/tests/test_api/test_ws_payloads.py backend/tests/test_api/test_ws_encounter_intro.py backend/tests/test_api/test_ws_combat_handlers.py backend/tests/test_game/test_action_mechanics.py backend/tests/test_game/test_action_resolver.py backend/tests/test_game/test_action_pipeline.py -q` -> `50 passed`
- `cd frontend && npm run type-check` -> OK
- `cd frontend && npm run test -- useWebSocket` -> OK (`4 passed`)

Verifications finales :

- [x] `backend/.venv/bin/pytest backend/tests/test_game backend/tests/test_api -q` -> `262 passed`
- [x] `backend/.venv/bin/ruff check ...` cible fichiers modifies -> OK
- [x] `cd frontend && npm run type-check && npm run test && npm run build` -> OK (`8 files`, `19 tests`, build OK)

---

## Hors lot / manuel

- [ ] Smoke manuel UI/WebSocket complet : 1 humain + 1 compagnon IA + 1 monstre.
- [ ] Smoke manuel equipement/repos si besoin.
- [ ] Couverture API/agents supplementaire hors refacto :
  - `tests/test_api/test_routes_admin.py`
  - `tests/test_api/test_routes_campaign.py`
  - `tests/test_api/test_routes_encounters.py`
  - etoffer `tests/test_game/test_ai_player_manager.py`
