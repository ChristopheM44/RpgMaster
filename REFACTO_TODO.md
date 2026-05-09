# Plan de refacto consolide RpgMaster

> Derniere mise a jour : 2026-05-09

Objectif : garder un seul plan actif apres les audits et le durcissement critique, avec une cible **local renforce**. Les audits restent des sources de diagnostic, pas des roadmaps a appliquer telles quelles.

---

## Orientation

- Cible principale : outil local / reseau de confiance, pas service public multi-tenant.
- Priorite : securite locale, robustesse WebSocket, reduction progressive de la dette, preservation du comportement de jeu.
- Hors chemin critique : JWT utilisateurs, table `api_keys`, Redis, Postgres, rate limiting lourd, refacto profond de `player_agent.py`, JSON mode LLM natif.
- Ne pas melanger le sweep frontend, la migration Python 3.11 ou le nettoyage Ruff global avec les corrections de securite deja livrees.

---

## Baseline actuelle

Etat de reference du 2026-05-09 apres durcissement critique :

- Backend : `backend/.venv/bin/pytest tests -q` -> `1471 passed`.
- Frontend : `npm run test` -> `8 files passed`, `29 tests passed`.
- Frontend : `npm run build` -> OK.
- Ruff global : `backend/.venv/bin/ruff check app tests --statistics` -> `216 errors`.

Note de suivi Ruff : les fichiers modifies lors du durcissement sont propres dans leurs checks cibles. Le `ruff check app tests` global reste une dette preexistante, mesuree a 216 diagnostics, et doit etre reduit par lots sans elargir les ignores.

---

## Deja livre avant ce cycle

- [x] Schemas WebSocket stricts dans `backend/app/api/ws_schemas.py`.
- [x] `ConnectionManager`, locks par session, `state_schema` v1.
- [x] `EventBus` borne avec logs/metrics de drops.
- [x] Extraction initiale `ws_payloads.py` et handlers `encounter_intro.py`, `combat.py`, `ai_control.py`.
- [x] Tests WS/API/frontend existants autour des payloads, intros, combat handlers et `useWebSocket`.
- [x] Frontend token optionnel `VITE_RPGMASTER_ACCESS_TOKEN`.
- [x] SSRF : validation des URLs LLM/TTS via `security_url`.
- [x] Sessions DB courtes pour les chemins WebSocket.
- [x] Backpressure explicite sur le bus d'evenements.
- [x] Rate-limit admin.
- [x] TTS decouple de la resolution mecanique.
- [x] Spellcasting sorti de la mecanique pure quand l'action implique orchestration.
- [x] JSON recovery extrait des agents.

---

## Lots de consolidation restants

### Lot A - Sweep couleurs inline frontend

- [x] Stabiliser une convention unique dans `frontend/src/assets/main.css` : classes `.rpg-*`, tokens `@theme`, variantes tonales `blood`, `arcane`, `gold`, `teal`, `muted`, `green`.
- [x] Remplacer progressivement les `:style` purement statiques par des classes Tailwind ou `.rpg-*`.
- [x] Lot 1 : composants communs, navigation, boutons, dialogs, action bar.
- [x] Lot 2 : lobby, session, narrative log.
- [x] Lot 3 : combat, battlemap, tracker.
- [x] Lot 4 : character, exploration, campaign.
- [x] Garder en inline uniquement les styles dynamiques : largeur HP, positions de grille, couleurs derivees d'etat metier, animation delay.
- [x] Ajouter une regle d'equipe : pas de nouveau `rgba(...)` inline hors cas dynamique justifie.

Note d'execution Lot A, 2026-05-09 : les `:style` restants sont limites aux exceptions dynamiques prevues (HP/progression, positions de grille/map, couleurs derivees d'etat metier, animation delay). Regle equipe : aucun nouveau `rgba(...)` dans un template Vue ou un binding `:style` sans justification dynamique explicite. Validation frontend : `npm run test` -> 8 fichiers / 29 tests, `npm run build` -> OK.

### Lot B - Migration backend Python 3.11

- [ ] Passer `backend/pyproject.toml` a `requires-python = ">=3.11"` et Ruff `target-version = "py311"`.
- [ ] Mettre a jour `README.md`, `CLAUDE.md`, les docs d'audit et les commentaires de `voxtral_client.py` qui decrivent encore le backend principal en Python 3.9.
- [ ] Recreer le venv backend en Python 3.11, reinstaller les dependances, puis valider Alembic, FastAPI startup et toute la suite pytest.
- [ ] Moderniser les annotations : `list`, `dict`, `set`, `tuple`, `X | None`, sauf cas SQLAlchemy prouve par test.
- [ ] Supprimer ou reduire l'ignore Ruff `UP045` seulement apres validation des modeles SQLAlchemy sous 3.11.

### Lot C - Nettoyage Ruff global

- [ ] Mesure de depart : `ruff check app tests --statistics` -> 216 diagnostics le 2026-05-09.
- [ ] Appliquer d'abord les corrections sures : imports tries, imports inutilises, annotations quoted, `lru_cache(maxsize=None)`.
- [ ] Traiter ensuite manuellement : `UP006`, `UP035`, `UP007`, lignes trop longues, noms non conformes, variables inutilisees.
- [ ] Proceder par lots testables : `app/engine`, `app/api`, `app/services`, `app/game`, `app/agents`, puis `tests`.
- [ ] Objectif final : `ruff check app tests` vert sans elargir les ignores, sauf justification ecrite dans `pyproject.toml`.

### Lot D - Dette architecturale non bloquante

- [ ] Extraire les schemas admin vers `app/schemas/admin.py`, puis poursuivre avec `routes_game`, `routes_encounters`, `routes_character`, `routes_pregen`.
- [ ] Continuer le decoupage de `action_pipeline.py` : garder la resolution dans le pipeline, deplacer persistance, publication et narration vers l'orchestrateur deja cree.
- [ ] Ajouter une vraie memoire longue LLM : utiliser `played_canon.rolling_summary` dans les prompts actifs, puis automatiser la synthese apres seuil de messages.
- [ ] Preparer l'abstraction event bus pour Redis sans migrer tout de suite : interface stable, factory injectable, singleton conserve comme implementation par defaut.
- [ ] Etendre l'admin token vers des roles lecture/ecriture si l'interface admin devient exposee hors local.

---

## Verifications attendues

- Avant chaque lot : garder `pytest`, `npm run test` et `npm run build` verts.
- Apres chaque lot frontend : `cd frontend && npm run test && npm run build`.
- Sweep visuel : verification manuelle lobby, session, combat, character sheet, campaign, mobile et desktop.
- Apres Python 3.11 : `python --version`, `pytest`, `ruff check app tests`, Alembic upgrade/downgrade sur DB temporaire, FastAPI startup.
- Apres refactors backend : tests cibles par sous-systeme, puis suite complete backend.
- Memoire longue : tests unitaires sur injection de `rolling_summary` et tests agent avec historique long.
