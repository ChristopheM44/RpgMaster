# RpgMaster - CLAUDE.md

## Projet

Application de jeu de role avec un Maitre de Jeu IA, utilisant les regles D&D SRD 5.2 (CC-BY-4.0). Un ou plusieurs joueurs humains peuvent jouer aux cotes de compagnons IA dans des sessions narratives en temps reel.

## Stack technique

| Composant | Technologie | Details |
|-----------|------------|---------|
| Backend | Python 3.9+ / FastAPI | Async, app factory dans `backend/app/main.py` |
| Frontend | Vue.js 3 / TypeScript | Composition API, `<script setup>`, Pinia, Vue Router |
| CSS | TailwindCSS v4 | Theme dark fantasy (parchment/ink/blood/gold/arcane) |
| LLM texte | Ollama | Modele local configurable (default: mistral:7b) |
| LLM voix | Voxtral 4B TTS | Via vLLM-Omni (PAS Ollama), optionnel, port 8091 |
| Base de donnees | SQLite | Via SQLAlchemy async (aiosqlite) + Alembic |
| Temps reel | WebSocket | Natif FastAPI, endpoint `/ws/game/{session_id}` |
| Conteneurs | Docker Compose | Ollama + Voxtral (optionnel) |

## Lancer le stack complet

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate
alembic upgrade head          # a faire une seule fois, ou apres migration
python -m uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev

# URLs
# Frontend : http://localhost:5173
# Backend  : http://localhost:8000
# API docs : http://localhost:8000/docs
```

## Variables d'environnement

Copier `.env.example` vers `backend/.env` et ajuster si besoin.

| Variable | Defaut | Obligatoire |
|----------|--------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Oui |
| `GM_MODEL` | `mistral:7b` | Oui |
| `PLAYER_MODEL` | `mistral:7b` | Oui |
| `VOXTRAL_ENABLED` | `false` | Non |
| `VOXTRAL_BASE_URL` | `http://localhost:8091` | Si TTS active |
| `DATABASE_URL` | `sqlite+aiosqlite:///./rpgmaster.db` | Oui |
| `MAX_CONTEXT_MESSAGES` | `20` | Non |
| `TTS_ASYNC` | `true` | Non |

## Commandes

### Backend
```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload          # Dev server (port 8000)
pytest                                             # Tous les tests
pytest tests/test_engine/ -v                       # Tests moteur uniquement
pytest tests/test_api/ -v                          # Tests API uniquement
pytest tests/test_game/ -v                         # Tests game loop uniquement
pytest --cov=app                                   # Tests avec couverture
ruff check app/                                    # Lint
ruff format app/                                   # Format
alembic upgrade head                               # Migrations DB
alembic history                                    # Voir les migrations
```

### Frontend
```bash
cd frontend
npm run dev                                        # Dev server (port 5173)
npm run build                                      # Build production
npm run type-check                                 # Verification TypeScript
```

## Architecture

```
RpgMaster/
├── backend/app/
│   ├── main.py              # FastAPI app factory + CORS + routers
│   ├── config.py            # Pydantic Settings (.env)
│   ├── api/                 # Routes REST + WebSocket
│   ├── models/              # SQLAlchemy ORM
│   ├── schemas/             # Pydantic request/response
│   ├── services/            # Logique metier
│   ├── engine/              # Moteur de regles D&D (pure logic, NO I/O)
│   │   └── srd_data/        # Donnees SRD 5.2 en JSON
│   ├── agents/              # Agents IA (GM + joueurs)
│   │   └── prompts/         # Templates de prompts Jinja2
│   ├── llm/                 # Clients Ollama + Voxtral
│   ├── game/                # Orchestration (game loop, turn manager, event bus)
│   └── db/                  # SQLAlchemy async engine
├── frontend/src/
│   ├── views/               # Pages (Home, Lobby, CharacterCreation, GameSession)
│   ├── components/          # narrative/, combat/, character/, common/, ui/
│   ├── stores/              # Pinia (session, game, character, chat)
│   ├── composables/         # useWebSocket, useGameActions, useAudio
│   ├── services/            # api.ts, websocket.ts
│   └── types/               # Interfaces TypeScript
└── docs/                    # Documentation projet
```

## Strategie de tests

| Suite | Dossier | Ce qu'elle teste |
|-------|---------|-----------------|
| Engine | `tests/test_engine/` | Logique pure D&D, sans I/O — jets de des, combat, sorts, conditions |
| API | `tests/test_api/` | Endpoints REST avec DB SQLite en memoire |
| Agents | `tests/test_agents/` | GMAgent, PlayerAgent, ContextManager (Ollama mocke) |
| Game loop | `tests/test_game/` | Event bus, session manager, turn manager, WebSocket, integration |

Les tests `engine/` sont purement unitaires (rapides, aucune dependance externe).
Les tests `game/` peuvent necessiter une boucle asyncio — utiliser `pytest-asyncio`.

## Principes de conception

1. **Le moteur de regles fait autorite** : `engine/` est de la logique pure sans I/O. Le LLM ne peut pas halluciner de jets de des - c'est le moteur qui resout les mecaniques.
2. **Sorties JSON structurees** : Les agents IA retournent du JSON parse et valide par Pydantic, pas du texte libre.
3. **Voix asynchrone et optionnelle** : Le TTS ne bloque jamais le gameplay. Le texte apparait immediatement, l'audio suit.
4. **Game state = JSON blob** : Evite une modelisation relationnelle complexe. Pydantic valide a l'entree/sortie.
5. **Event bus in-process** : `asyncio.Queue` pour Phase 1 (solo). Evolutif vers Redis pour le multijoueur reseau.

## Machine a etats du jeu

```
LOBBY -> CHARACTER_CREATION -> EXPLORATION -> ENCOUNTER_START ->
COMBAT (rounds) -> ENCOUNTER_END -> EXPLORATION -> ...
                                 -> REST (court/long)
                                 -> LEVEL_UP -> SESSION_END
```

## Convention de code

- **Python** : ruff, line-length 100, `from __future__ import annotations`
- **TypeScript** : Vue 3 Composition API avec `<script setup lang="ts">`
- **CSS** : Classes utilitaires TailwindCSS, theme custom via `@theme` dans main.css
- **Commits** : Messages concis en anglais, format conventionnel
- **Langue de l'application** : Interface en francais, code/variables en anglais

## Contraintes importantes

- Python 3.9.6 est installe sur cette machine (pas 3.11+)
- Voxtral TTS necessite vLLM-Omni, PAS Ollama - deux backends LLM distincts
- Le frontend tourne sur le port 5173 (Vite), le backend sur le port 8000 (Uvicorn)
- CORS configure pour `http://localhost:5173`

## Anti-patterns a eviter

- **Ne jamais creer une nouvelle session SQLAlchemy dans un handler WebSocket** — reutiliser le `db` injecte via `Depends(get_db)` ou passe en parametre.
- **Ne jamais appeler le LLM de facon bloquante dans un handler WebSocket** — toujours utiliser `asyncio.create_task()` pour les appels GMAgent/PlayerAgent.
- **Ne pas faire resoudre les mecaniques par le LLM** — jets de des, calculs de degats, initiative : tout passe par `engine/`. Le LLM produit uniquement de la narration.
- **Ne pas ajouter de champs relationnels complexes au game state** — c'est un JSON blob valide par Pydantic. Eviter de creer de nouvelles tables SQLAlchemy pour des donnees de jeu.
- **Ne pas modifier `engine/` pour y faire des I/O** — ce package doit rester pure logic, testable sans base de donnees ni reseau.
- **Ne pas utiliser `tts_backend="vllm"` sans vLLM-Omni en cours** — l'app tombe en erreur. Garder `VOXTRAL_ENABLED=false` si Voxtral n'est pas demarre.
