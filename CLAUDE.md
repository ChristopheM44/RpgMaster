# RpgMaster - CLAUDE.md

## Projet

Application de jeu de role avec un Maitre de Jeu IA, utilisant les regles D&D SRD 5.2 (CC-BY-4.0). Un ou plusieurs joueurs humains peuvent jouer aux cotes de compagnons IA dans des sessions narratives en temps reel.

## Stack technique

| Composant | Technologie | Details |
|-----------|------------|---------|
| Backend | Python 3.9+ / FastAPI | Async, app factory dans `backend/app/main.py` |
| Frontend | Vue.js 3 / TypeScript | Composition API, `<script setup>`, Pinia, Vue Router |
| CSS | TailwindCSS v4 | Tokens `@theme` + classes `.rpg-*` dans `src/assets/main.css` |
| LLM texte | Ollama | Modele local configurable (default: mistral:7b) |
| LLM voix | Voxtral 4B TTS | Via vLLM-Omni (PAS Ollama), optionnel, port 8091 |
| Base de donnees | SQLite | Via SQLAlchemy async (aiosqlite) + Alembic |
| Temps reel | WebSocket | Natif FastAPI, endpoint `/ws/game/{session_id}` |

## Lancer le stack

```bash
# Backend
cd backend && source .venv/bin/activate
alembic upgrade head && python -m uvicorn app.main:app --reload   # → http://localhost:8000

# Frontend
cd frontend && npm run dev                                         # → http://localhost:5173
```

## Variables d'environnement

Copier `.env.example` vers `backend/.env`.

| Variable | Defaut | Note |
|----------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `GM_MODEL` / `PLAYER_MODEL` | `mistral:7b` | |
| `DATABASE_URL` | `sqlite+aiosqlite:///./rpgmaster.db` | |
| `VOXTRAL_ENABLED` | `false` | Garder `false` si vLLM-Omni non démarré |
| `VOXTRAL_BASE_URL` | `http://localhost:8091` | Si TTS active |
| `MAX_CONTEXT_MESSAGES` | `20` | |
| `TTS_ASYNC` | `true` | |

## Commandes

```bash
# Backend (dans backend/ avec venv actif)
python -m uvicorn app.main:app --reload     # Dev server
pytest / pytest tests/test_engine/ -v / pytest --cov=app
ruff check app/ && ruff format app/
alembic upgrade head && alembic history

# Frontend
npm run dev / npm run build / npm run type-check
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
│   ├── components/          # exploration/, combat/, campaigns/, common/
│   ├── stores/              # Pinia (session, game, character, chat)
│   ├── composables/         # useWebSocket, useGameActions, useAudio
│   ├── services/            # api.ts, websocket.ts
│   └── types/               # Interfaces TypeScript
└── docs/
```

## Frontend — Design System

**Direction** : Dark-fantasy premium (Ember + gold sur obsidienne). Interface = grimoire vivant, pas un dashboard SaaS.

### Tokens de couleur (`src/assets/main.css` → `@theme`)

| Token | Valeur | Usage |
|---|---|---|
| `--color-bg` | `#0e0d14` | Fond app global |
| `--color-bg-elev` | `#181623` | Header, panneaux, footer |
| `--color-surface` | `#1f1c2e` | Cartes, sections |
| `--color-surface-raised` | `#2a2640` | Hover, sélection |
| `--color-parchment` | `#f7ecd0` | Texte principal |
| `--color-parchment-dark` | `rgba(247,236,208,.75)` | Texte secondaire |
| `--color-text-muted` | `rgba(247,236,208,.50)` | Labels, metadata |
| `--color-text-dim` | `rgba(247,236,208,.32)` | Placeholders |
| `--color-border` | `rgba(255,235,180,.07)` | Séparateurs discrets |
| `--color-border-strong` | `rgba(255,235,180,.18)` | Inputs focus, boutons |
| `--color-ember` | `#ff8247` | Accent CTA, joueur humain |
| `--color-gold` | `#f0c764` | Titres forts, sélection, tour actif |
| `--color-blood` | `#e84545` | Danger, ennemis, HP critiques |
| `--color-arcane` | `#c090ff` | IA, sorts, magie |
| `--color-teal` | `#4fd8c0` | Alliés, déplacement, succès |
| `--color-green` | `#6fd96f` | HP pleins, zone sûre |
| `--grad-primary` | `linear-gradient(135deg, #ff8247, #f0c764)` | Bouton CTA, logo, barres |

### Typographie

| Token | Police | Rôle |
|---|---|---|
| `--font-display` | **Cinzel** | Titres, noms, CTA, eyebrows — uppercase + letter-spacing |
| `--font-serif` | **Fraunces** | Récit narratif, taglines — `text-wrap: pretty`, `line-height: 1.65` |
| `--font-body` | **Inter** | UI courante, boutons, labels |
| `--font-mono` | **JetBrains Mono** | Stats, compteurs, dates, metadata |

### Classes `.rpg-*` (réutiliser en priorité)

| Classe | Usage |
|---|---|
| `.rpg-eyebrow` | Label 10px Cinzel uppercase doré `✦ TITRE` |
| `.rpg-section-title` | Header de section avec filet dégradé |
| `.rpg-card` | Carte : fond `bg-elev`, border 1px, radius `lg` |
| `.rpg-btn-primary` | CTA gradient ember→gold, shadow ember |
| `.rpg-btn-secondary` | Contour or, fond transparent |
| `.rpg-btn-tonal` | Bouton teinté : `.tone-blood` `.tone-arcane` `.tone-teal` `.tone-gold` |
| `.rpg-input` | Input/textarea fond sombre, focus ember |
| `.rpg-chip` | Chip statut 10px uppercase |
| `.rpg-sparkle` | Icône `✦` ember devant un titre |
| `.prose-narrative` | Prose Fraunces pilotée par `--narrative-scale` |

### Règles frontend

- Couleurs **toujours** via tokens `var(--color-*)` — jamais de hex en dur dans les templates
- Hiérarchie de fond : `bg` → `bg-elev` → `surface` → `surface-raised`
- Animations : 120ms ease (interactions), 200ms (ouvertures/fermetures)
- `overflow: hidden` sur `html, body` — scroll géré par colonnes internes
- Scrollbars fines et semi-transparentes (global)
- Icônes : Unicode (✦ ◆ ⚔ ◉ ❦) + SVG custom dans `icons/color/` et `icons/mono/`
- Layout : AppNav 56px + colonne principale + panneau droit 380–580px + ActionBar

### Checklist nouveau composant

- [ ] Tokens `--color-*` (pas de hex en dur)
- [ ] Polices via `--font-display / serif / body / mono`
- [ ] Classes `.rpg-*` réutilisées si applicable
- [ ] Titres Cinzel uppercase avec letter-spacing
- [ ] Récit Fraunces avec `text-wrap: pretty`
- [ ] Stats/chiffres JetBrains Mono
- [ ] Accents sémantiques : ember=joueur, arcane=IA, blood=danger, teal=allié/succès, gold=sélection

## Strategie de tests

| Suite | Dossier | Ce qu'elle teste |
|-------|---------|-----------------|
| Engine | `tests/test_engine/` | Logique pure D&D, sans I/O |
| API | `tests/test_api/` | Endpoints REST avec DB SQLite en memoire |
| Agents | `tests/test_agents/` | GMAgent, PlayerAgent, ContextManager (Ollama mocke) |
| Game loop | `tests/test_game/` | Event bus, session manager, turn manager, WebSocket |

Les tests `engine/` sont purement unitaires. Les tests `game/` utilisent `pytest-asyncio`.

## Principes de conception

1. **Moteur de regles souverain** : `engine/` = logique pure sans I/O. Le LLM ne resout jamais les mecaniques.
2. **Sorties JSON structurees** : Agents retournent du JSON valide par Pydantic, pas du texte libre.
3. **TTS non-bloquant** : texte immédiat, audio asynchrone et optionnel.
4. **Game state = JSON blob** : Pydantic valide a l'entree/sortie. Pas de nouvelles tables SQLAlchemy.
5. **Event bus in-process** : `asyncio.Queue` → Redis si multijoueur reseau.

## Machine a etats

```
LOBBY → CHARACTER_CREATION → EXPLORATION → ENCOUNTER_START →
COMBAT (rounds) → ENCOUNTER_END → EXPLORATION → ...
                              → REST (court/long) → LEVEL_UP → SESSION_END
```

## Convention de code

- **Python** : ruff, line-length 100, `from __future__ import annotations`
- **TypeScript** : Vue 3 Composition API, `<script setup lang="ts">`
- **Commits** : Messages concis en anglais, format conventionnel
- **Langue** : Interface en francais, code/variables en anglais

## Contraintes

- Python 3.9.6 (pas 3.11+)
- Voxtral TTS via vLLM-Omni uniquement (port 8091) — PAS Ollama
- Frontend port 5173, backend port 8000, CORS configure pour `http://localhost:5173`

## Anti-patterns

- **WebSocket** : ne jamais creer une session SQLAlchemy dans un handler — reutiliser le `db` injecte.
- **WebSocket** : ne jamais appeler un LLM de facon bloquante — `asyncio.create_task()` obligatoire.
- **Mecaniques** : jets de des, degats, initiative → `engine/` uniquement. Le LLM = narration seulement.
- **Game state** : pas de champs relationnels complexes, pas de nouvelles tables SQLAlchemy.
- **`engine/`** : zero I/O — reste testable sans DB ni reseau.
- **TTS** : ne pas utiliser `tts_backend="vllm"` sans vLLM-Omni actif.
