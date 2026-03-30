# RpgMaster — Avancement du projet

> Derniere mise a jour : 2026-03-30 (Sprint 6 en cours — 2/11 taches)

---

## Etat global

| Sprint | Titre | Statut |
|--------|-------|--------|
| Sprint 0 | Bootstrap | ✅ Termine |
| Sprint 1 | Moteur de regles D&D SRD 5.2 | ✅ Termine |
| Sprint 2 | Couche donnees + API REST | ✅ Termine |
| Sprint 3 | Integration LLM | ✅ Termine |
| Sprint 4 | Game Loop + WebSocket | ✅ Termine |
| Sprint 5 | Agents joueurs IA | ✅ Termine |
| Sprint 6 | Frontend MVP | 🔄 En cours (2/11) |
| Sprint 7 | Integration + Voix | 🔲 A faire |
| Sprint 8 | Polish + Playtest | 🔲 A faire |

---

## Ce qui a ete realise

### Sprint 0 — Infrastructure de base

- **Monorepo** avec `backend/` (Python/FastAPI) et `frontend/` (Vue 3/TypeScript)
- **Docker Compose** pour Ollama (LLM local, port 11434) et Voxtral TTS optionnel (port 8091)
- **Backend FastAPI** : squelette avec CORS, lifespan, routeurs stubbes, WebSocket echo sur `/ws/game/{session_id}`
- **Config** Pydantic Settings chargee depuis `.env` (URLs LLM, base de donnees, ports)
- **Base de donnees** : moteur SQLAlchemy async avec aiosqlite, pret a recevoir les modeles
- **Frontend Vue 3** : TypeScript, Pinia, Vue Router, 4 vues placeholder (Home, Lobby, CharacterCreation, GameSession)
- **Theme dark fantasy** TailwindCSS v4 avec couleurs personnalisees (parchment, ink, blood, gold, arcane)

### Sprint 1 — Moteur de regles D&D SRD 5.2

C'est la piece maitresse actuellement implementee. Tout le code est dans `backend/app/engine/` et constitue de la **logique pure sans I/O** (pas de base de donnees, pas de reseau).

#### `engine/dice.py` — Systeme de des

Parseur de notation standard D&D et resolution des jets.

- Notations supportees : `d20`, `2d6`, `4d6kh3`, `2d6+3`, `1d8-1`
- `kh` (keep highest) et `kl` (keep lowest) pour garder N des
- Avantage et desavantage (2d20, garder le plus haut/bas)
- `RollResult` dataclass avec decomposition complete du jet
- Generation de caracteristiques : `roll_ability_scores()` (methode 4d6kh3)

#### `engine/ability_checks.py` — Tests et jets de sauvegarde

- Calcul du modificateur : `(score - 10) // 2`
- Bonus de maitrise par niveau de personnage (niveaux 1 a 20)
- Mapping des 18 competences vers leurs 6 caracteristiques
- `ability_check()`, `skill_check()`, `saving_throw()`
- `CheckResult` avec label, decomposition, succes/echec

#### `engine/combat.py` — Mecanique de combat

- Jet d'initiative avec modificateur DEX
- Jets d'attaque (bonus d'attaque + CA cible) avec avantage/desavantage
- Calcul de degats avec resistances et vulnerabilites
- Jets de mort (20 naturel = recupere 1 PV, 1 naturel = 2 echecs)
- Economie d'action : action, action bonus, reaction, deplacement

#### `engine/conditions.py` — Conditions SRD 5.2

- 14 conditions standard : a terre, aveugle, charge, effraye, empoisonne, enchante, entrave, epuise, etourdi, invisible, immobilise, incapacite, paralyse, petrifie
- `ConditionEffects` : desavantage aux attaques, avantage contre la cible, critique automatique en melee, vitesse zero, etc.
- Niveaux d'epuisement 0-6 avec effets cumulatifs

#### `engine/character_creation.py` — Creation de personnage

- **Achat de points** (27 points) : scores de 8 a 15 avant les bonus raciaux
- Traits d'espece : Humain (+1 a toutes les caract.), Elfe (+2 DEX, +2 INT, vision dans le noir), Nain (+2 CON, +2 FOR, resistance poison)
- Capacites de classe niveau 1 : Guerrier (Second Souffle), Magicien (Preparation de sorts), Roublard (Attaque sournoise), Clerc (Domaine divin)
- Calcul des PV maximaux au niveau 1 (de de vie max + modificateur CON)

#### `engine/equipment.py` — Armes, armures et CA

- Catalogue de 30+ armes SRD : simples et de guerre, avec proprietes (finesse, a deux mains, polyvalente, portee, etc.)
- Armures legeres, intermediaires, lourdes et bouclier
- Calcul de CA selon le type d'armure et le modificateur DEX
- `WeaponStats` et `ArmorStats` dataclasses

#### `engine/spells.py` — Sorts et emplacements

- Catalogue de 20 sorts SRD niveaux 0 a 3 (Boule de feu, Soin des blessures, Projectile magique, etc.)
- Suivi des emplacements de sorts par niveau
- Mecanique de concentration (un seul sort a la fois)
- Resolution des effets de sort (degats, soins, sauvegardes)

#### `engine/srd_data/` — Donnees JSON SRD 5.2 (CC-BY-4.0)

| Fichier | Contenu |
|---------|---------|
| `classes.json` | 4 classes : Guerrier, Magicien, Roublard, Clerc (de de vie, maitrise, capacites niveau 1) |
| `species.json` | 3 especes : Humain, Elfe, Nain (bonus de caracteristiques, traits) |
| `spells.json` | 20 sorts niveaux 0-3 (ecole, composantes, degats/soins) |
| `monsters.json` | 10 monstres CR 0-5 : Gobelin, Orc, Troll, Jeune Dragon, etc. |
| `equipment.json` | Armes, armures, kit d'aventurier |

#### Tests unitaires — Couverture complete

**2 439 lignes de tests** pour le moteur de regles :

| Fichier | Lignes | Ce qui est teste |
|---------|--------|-----------------|
| `test_dice.py` | 148 | Parsing de notation, kh/kl, avantage/desavantage |
| `test_ability_checks.py` | 206 | Tests, competences, jets de sauvegarde, maitrise |
| `test_combat.py` | 279 | Initiative, attaques, degats, jets de mort |
| `test_conditions.py` | 333 | Les 14 conditions + epuisement |
| `test_character_creation.py` | 526 | Achat de points, especes, classes, PV |
| `test_equipment.py` | 573 | Armes, armures, calcul de CA |
| `test_spells.py` | 374 | Mecanique des sorts |

---

## Ce qui peut etre documente et utilise des maintenant

### Utiliser le moteur de regles en Python

Le moteur est autonome, sans dependances externes. On peut l'importer directement :

```python
from app.engine.dice import roll, roll_with_advantage
from app.engine.ability_checks import ability_check, skill_check
from app.engine.combat import roll_initiative, roll_attack, roll_damage
from app.engine.conditions import get_condition_effects
from app.engine.character_creation import apply_point_buy, apply_species_traits
from app.engine.equipment import get_weapon_stats, calculate_ac
from app.engine.spells import resolve_spell

# Lancer un d20 avec avantage
result = roll_with_advantage("d20")
print(result.total, result.rolls)  # ex: 17, [17, 9]

# Test de caracteristique
check = ability_check(score=14, proficient=True, level=3)
print(check.total, check.success)

# Jet d'initiative
initiative = roll_initiative(dex_score=16)
print(initiative.total)  # ex: 14

# Attaque avec epee longue
attack = roll_attack(attack_bonus=5, target_ac=15)
if attack.hit:
    dmg = roll_damage("1d8+3")
    print(f"Touche ! {dmg.total} degats")
```

### Lancer le backend

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload
# API disponible sur http://localhost:8000
# Docs interactives sur http://localhost:8000/docs
```

### Lancer le frontend

```bash
cd frontend
npm run dev
# Application sur http://localhost:5173
```

### Lancer les tests du moteur

```bash
cd backend
source .venv/bin/activate
pytest tests/test_engine/ -v              # Tests moteur uniquement
pytest --cov=app --cov-report=term-missing  # Couverture complete
```

### Demarrer Ollama (LLM local)

```bash
docker-compose up ollama
# Ollama disponible sur http://localhost:11434
# Tirer le modele par defaut :
docker exec -it rpgmaster-ollama ollama pull mistral:7b
```

### Verifier la qualite du code

```bash
cd backend
ruff check app/      # Lint
ruff format app/     # Formatage auto
npm run type-check   # (dans frontend/) Verification TypeScript
```

---

## Architecture actuelle en un coup d'oeil

```
RpgMaster/
├── backend/app/
│   ├── main.py          ✅ FastAPI app factory, CORS, routeurs, lifespan
│   ├── config.py        ✅ Pydantic Settings (.env)
│   ├── api/
│   │   ├── routes_session.py    ✅ CRUD sessions (list, create, get, update, delete)
│   │   ├── routes_character.py  ✅ CRUD personnages (list, create, get, update, delete)
│   │   ├── routes_srd.py        ✅ Reference SRD (classes, species, spells, monsters, equipment)
│   │   ├── routes_game.py       🔲 Stub endpoints jeu
│   │   └── ws_game.py           ✅ Protocole WebSocket complet + dispatch actions
│   ├── engine/          ✅ COMPLET — Moteur de regles D&D pur, sans I/O
│   │   ├── dice.py
│   │   ├── ability_checks.py
│   │   ├── combat.py
│   │   ├── conditions.py
│   │   ├── character_creation.py
│   │   ├── equipment.py
│   │   ├── spells.py
│   │   └── srd_data/    ✅ JSON SRD 5.2
│   ├── db/database.py   ✅ Moteur SQLAlchemy async
│   ├── models/          ✅ Session, Character, GameState, Message
│   ├── schemas/         ✅ Session, Character (request/response Pydantic)
│   ├── services/        🔲 Vide — a creer (Sprint 2+)
│   ├── agents/          🔄 schemas, base_agent, context_manager, gm_agent, player_agent + prompts/
│   ├── llm/             ✅ ollama_client, model_router
│   └── game/            ✅ game_loop, turn_manager, session_manager, event_bus, action_resolver
├── frontend/src/
│   ├── router/index.ts  ✅ 4 routes lazy-loaded
│   ├── views/           🔲 Vues placeholder (Home fonctionnelle, reste = stub)
│   ├── assets/main.css  ✅ Theme dark fantasy TailwindCSS v4
│   ├── components/      🔲 Vide — a creer (Sprint 6)
│   ├── composables/     🔲 Vide — a creer (Sprint 6)
│   ├── services/        🔲 Vide — a creer (Sprint 6)
│   ├── stores/          🔲 Placeholder counter (a remplacer, Sprint 6)
│   └── types/           🔲 Vide — a creer (Sprint 6)
└── tests/
    ├── test_engine/     ✅ 2 439 lignes, couverture complete du moteur
    ├── test_api/        ✅ 50 tests (sessions 13, characters 17, srd 20) — 50/50
    ├── test_agents/     ✅ 36 tests (ollama_client 10, context_manager 13, gm_agent 13)
    ├── test_agents/     ✅ 59 tests (ollama_client, context_manager, gm_agent, player_agent)
    └── test_game/       ✅ 98 tests (game_loop, turn_manager, session_manager, event_bus, ws_game, integration, ai_player_combat)
```

---

## Sprint 6 — Frontend MVP [EN COURS — 2/11]

### Tâches accomplies

#### Shell app + navigation (`src/App.vue`, `src/components/common/AppNav.vue`)

- `AppNav.vue` : barre de navigation fixe (header), affichée sur toutes les routes sauf l'accueil
- Logo "⚔ RpgMaster" avec lien vers `/`, nom de la session courante si active, lien Lobby
- `App.vue` : shell avec `AppNav` conditionnel + `pt-14` pour compenser la hauteur du header

#### LobbyView (`src/views/LobbyView.vue`)

- **Créer une session** : champ texte (nom) + bouton → `POST /api/sessions` → redirige vers création de personnage
- **Sessions sauvegardées** : liste des sessions avec nom, badge de statut coloré, date de modification
- **Rejoindre** : redirige vers la bonne vue selon le statut (character_creation ou game-session)
- **Supprimer** : double confirmation inline avant suppression (`DELETE /api/sessions/:id`)
- Gestion des états : chargement, vide, erreur

#### Fondations frontend

- `src/types/index.ts` : interfaces TypeScript (`Session`, `SessionCreate`, `SessionUpdate`, `SessionStatus`)
- `src/services/api.ts` : client REST générique avec gestion d'erreur + `sessionApi` (list, create, get, update, delete)
- `src/stores/session.ts` : store Pinia (`sessions`, `currentSession`, `loading`, `error`, `fetchSessions`, `createSession`, `deleteSession`, `setCurrentSession`)

---

## Sprint 5 — Agents joueurs IA [TERMINÉ — 7/7]

### Taches accomplies

#### `agents/player_agent.py` — Agent joueur IA

- Hérite de `BaseAgent` (même pipeline Jinja2 + extraction JSON que `GMAgent`)
- **`decide_action()`** : choix tactique en combat → prompt `player_decide.txt`
- **`roleplay()`** : réaction narrative hors combat → prompt `player_roleplay.txt`
- **`validate_action()`** : garde-fou pré-moteur — vérifie emplacements de sorts, inventaire, PV > 0
- Système de personnalité injectable via `PlayerPersonality` (1 à 3 traits)
- Fallback safe si LLM indisponible (action `wait`)

#### Système de personnalité (8 traits)

| Trait | Comportement |
|-------|-------------|
| `brave` | Attaque les ennemis les plus dangereux, ne recule jamais |
| `cautious` | Conserve les ressources, préfère soins/soutien |
| `greedy` | Cible les ennemis portant des richesses |
| `noble` | Protège les alliés blessés, interpose |
| `vengeful` | Concentre sur l'ennemi qui a blessé un allié |
| `arcane` | Préfère systématiquement les sorts |
| `reckless` | Attaque sans calculer les risques |
| `protective` | Reste aux côtés des alliés vulnérables, Help/Dodge |

#### `agents/prompts/player_decide.txt` — Prompt de décision (combat)

- Contexte : données personnage + game_state + actions disponibles + personnalité
- Priorités tactiques : PV < 25% → survie, sorts disponibles, cible selon trait
- Réponse JSON : `action_type`, `target`, `params`, `roleplay_text`, `inner_reasoning`

#### `agents/prompts/player_roleplay.txt` — Prompt de roleplay (exploration)

- Contexte narratif : scène en cours + messages récents + background
- Actions possibles : parler, examiner, interagir avec PNJ, exprimer une émotion
- Même schéma JSON que `player_decide.txt`

#### Nouveaux schémas Pydantic (`agents/schemas.py`)

- `PlayerActionChoice` : action choisie avec `action_type`, `target`, `params`, `roleplay_text`
- `PlayerPersonality` : traits + backstory_hook + speech_style
- Constantes `PLAYER_ACTION_TYPES` (12 actions) et `PERSONALITY_TRAITS` (8 traits)

### Ce qui peut etre utilise des maintenant

```python
from app.agents.player_agent import PlayerAgent
from app.agents.schemas import PlayerPersonality

# Creer un agent joueur IA avec personnalite
agent = PlayerAgent(
    character_id="thorin_1",
    character_name="Thorin",
    personality=PlayerPersonality(
        traits=["brave", "noble"],
        backstory_hook="Cherche a venger son clan detruit",
        speech_style="gruff",
    )
)

# Decision tactique en combat
action = await agent.decide_action(game_state=current_state)
print(action.action_type)    # "attack"
print(action.roleplay_text)  # "Thorin charge avec un cri de guerre !"

# Validation avant de passer au moteur
is_valid, reason = agent.validate_action(action, current_state)

# Roleplay en exploration
reaction = await agent.roleplay(game_state=current_state, scene_context="Le groupe arrive en ville")
```

#### `game/turn_manager.py` — Champ `is_ai_controlled`

- `CombatantInfo.is_ai_controlled: bool = False` — marque les compagnons IA
- `TurnEntry.is_ai_controlled: bool = False` — propagé lors du `setup_combat()`
- Sérialisation/désérialisation complète (`to_dict()` / `from_dict()`)

#### `game/session_manager.py` — Registre des agents IA

- `ActiveSession.ai_players: Dict[str, Any]` — mappe `combatant_id → PlayerAgent`
- Populé par l'appelant (ws_game ou test) avant le début du combat

#### `game/ai_player_manager.py` — Orchestrateur des tours IA

- `AIPlayerManager.process_ai_turns(session_id, active, action_resolver)` :
  - Parcourt les tours consécutifs IA depuis la position courante
  - S'arrête dès qu'un combattant non-IA est atteint
  - Pour chaque IA : appel `decide_action()` / `roleplay()` → `validate_action()` → `ActionResolver.resolve()`
  - Si l'action est invalide : fallback vers `wait` (personnage inconscient, sorts épuisés, etc.)
  - Si aucun agent enregistré : saute le tour (log warning)
  - Retourne le nombre d'actions IA déclenchées

#### Tests Sprint 5 — 33 nouveaux tests

| Fichier | Tests | Couverture |
|---------|-------|------------|
| `tests/test_agents/test_player_agent.py` | 23 | Personnalité, validate_action (7 cas), decide_action, roleplay, think() |
| `tests/test_game/test_ai_player_combat.py` | 10 | Sérialisation TurnEntry, setup_combat, AIPlayerManager (5 scénarios), round complet |

**Total tests : 611/611 passants**

---

## Sprint 4 — Game Loop + WebSocket [TERMINÉ]

### Machine à états (`backend/app/game/game_loop.py`)

- Table de transitions valides entre toutes les phases (`LOBBY → CHARACTER_CREATION → EXPLORATION → COMBAT → …`)
- `GameLoop.validate_transition()` lève `InvalidTransitionError` si la transition est interdite
- Helpers : `can_transition()`, `get_valid_transitions()`, `is_terminal()`, `is_combat_phase()`

### Gestionnaire de tours (`backend/app/game/turn_manager.py`)

- Mode **combat** : jet d'initiative via `engine/combat.py`, tri du plus haut au plus bas
- Mode **exploration** : round-robin dans l'ordre d'ajout
- `next_turn()` avance et réinitialise l'économie d'action du nouveau combattant
- `remove_combatant()` retire un combattant sans sauter de tour
- Sérialisation/désérialisation complète (`to_dict()` / `load_dict()`) pour persistance dans `GameState`

### Gestionnaire de sessions (`backend/app/game/session_manager.py`)

- `ActiveSession` dataclass : état en mémoire (phase, turn_manager, state_data, dirty flag)
- `open_session()` : charge depuis la DB ou retourne l'instance existante (idempotent)
- `close_session()` : persiste et retire de la mémoire
- `transition_phase()` : valide via `GameLoop` puis sauvegarde
- `save_state()` : synchronise `Session.status` + `GameState.state_data` en DB

### Bus d'événements (`backend/app/game/event_bus.py`)

- Une `asyncio.Queue` par abonné → pas de head-of-line blocking
- `publish()` broadcast à tous les abonnés d'une session
- `publish_to_session()` helper pour construire et publier en une ligne
- Conçu pour être remplacé par Redis pub/sub en Phase 2 (multijoueur réseau)

### WebSocket (`backend/app/api/ws_game.py`)

Protocole complet :

| Message client | Effet |
|---------------|-------|
| `{"type": "join", "character_id": "..."}` | Broadcast `player_joined` |
| `{"type": "action", ...}` | Pipeline complet → événements broadcastés |
| `{"type": "ping"}` | Réponse `pong` |

Gestion du cycle de vie : connexion → session ouverte → `session_state` envoyé → boucle de réception → déconnexion → `player_left` → session fermée si dernier client.

### Résolveur d'actions (`backend/app/game/action_resolver.py`)

Pipeline bout-en-bout :

```
action joueur
      │
      ▼
résolution mécanique (engine/)
  ├── attack   → roll_attack() + roll_damage() → ROLL_RESULT event
  ├── cast_spell → roll("d20") → ROLL_RESULT event
  └── autres   → pas de jet de dé
      │
      ▼
AgentContext → GMAgent.think()   ← narration LLM (ou fallback)
      │
      ▼
NARRATION event
      │
      ▼
actions GM (damage_apply, condition_add/remove)
  └── HP_CHANGED / CONDITION_CHANGED events
      │
      ▼
TURN_END event (incrémente turn_number)
```

### Tests (`tests/test_game/`) — **88/88 passants**

| Fichier | Tests | Couverture |
|---------|-------|------------|
| `test_game_loop.py` | ~20 | Transitions valides/invalides, helpers |
| `test_turn_manager.py` | ~20 | Setup combat/exploration, next_turn, remove, sérialisation |
| `test_session_manager.py` | ~18 | Lifecycle, transitions, persistance |
| `test_event_bus.py` | ~10 | Subscribe/unsubscribe, publish, broadcast |
| `test_ws_game.py` | ~10 | Protocole WS (connect, join, ping, action, erreurs) |
| `test_integration.py` | 10 | Pipeline complet action→moteur→GM→broadcast |

---

## Sprint 3 — Intégration LLM [TERMINÉ]

### Client Ollama (`backend/app/llm/`)

| Fichier | Rôle |
|---------|------|
| `ollama_client.py` | Client async Ollama : `chat()`, `generate()`, `stream_chat()`, `is_available()` |
| `model_router.py` | Fabrique les clients LLM selon le rôle (MJ vs joueur IA) |

Fonctionnalités clés :
- Retry avec backoff exponentiel (3 tentatives, délai doublé) sur `ConnectError`, `TimeoutException`, `ResponseError`
- `OllamaError` comme exception unifiée levée après épuisement des tentatives
- Streaming via `AsyncIterator[str]` (chunks texte) pour les futures intégrations WebSocket

### Agents (`backend/app/agents/`)

| Fichier | Rôle |
|---------|------|
| `schemas.py` | Modèles Pydantic : `GMAction`, `GMResponse`, `ContextMessage`, `AgentContext`, `AgentResponse` |
| `base_agent.py` | Classe abstraite : rendu Jinja2, extraction JSON robuste (3 stratégies de fallback) |
| `context_manager.py` | Fenêtre glissante (`deque(maxlen=N)`) avec conversion format Ollama |
| `gm_agent.py` | Agent MJ complet : narrate, run_combat_turn, run_npc_dialogue |

### Templates de prompts (`backend/app/agents/prompts/`)

| Fichier | Usage |
|---------|-------|
| `gm_system.txt` | System prompt statique — règles absolues + schéma JSON obligatoire |
| `gm_narrate.txt` | Narration d'exploration (Jinja2 : game_state, player_action, recent_messages) |
| `gm_combat.txt` | Tour de combat (Jinja2 : + roll_results) |
| `gm_npc_dialogue.txt` | Dialogue PNJ (Jinja2 : npc_name, npc_personality, player_message) |

### Pipeline MJ

```
player_action + game_state
       │
       ▼
  ContextManager.to_ollama_messages()   ← fenêtre glissante N derniers messages
       │
       ▼
  Jinja2 template (gm_narrate / gm_combat / gm_npc_dialogue)
       │
       ▼
  OllamaClient.chat()   ← avec retry automatique
       │
       ▼
  BaseAgent._extract_json()   ← parse JSON, markdown block, ou texte brut
       │
       ▼
  GMResponse (Pydantic)   ← narration + actions mécaniques + mood
```

### Robustesse

- Si Ollama est injoignable → narration de fallback, pas d'exception propagée
- Si le LLM ne retourne pas du JSON → texte brut utilisé comme narration
- Actions malformées → filtrées silencieusement (seuls les `dict` sont acceptés)

### Tests agents (`tests/test_agents/`) — **36/36 passants**

| Fichier | Tests | Couverture |
|---------|-------|------------|
| `test_ollama_client.py` | 10 | chat, generate, retry, is_available |
| `test_context_manager.py` | 13 | fenêtre glissante, format Ollama, metadata |
| `test_gm_agent.py` | 13 | narrate, combat, NPC, fallbacks, think() |

**Total tests : 578/578 passants** (moteur + API + agents + game loop + intégration)

---

## Sprint 2 — Couche données + API REST [TERMINÉ]

### Modèles SQLAlchemy (`backend/app/models/`)

| Modèle | Table | Description |
|--------|-------|-------------|
| `Session` | `sessions` | Session de jeu avec statut (enum : LOBBY → SESSION_END) |
| `Character` | `characters` | Personnage humain ou IA avec stats JSON, équipement, sorts, conditions |
| `GameState` | `game_states` | Blob JSON one-to-one avec Session, contient l'état complet du jeu |
| `Message` | `messages` | Entrée du journal de partie (narration, dialogue, jet de dés, système) |

### Schemas Pydantic (`backend/app/schemas/`)

- `SessionCreate`, `SessionUpdate`, `SessionResponse`, `SessionListResponse`
- `CharacterCreate`, `CharacterUpdate`, `CharacterResponse`, `CharacterListResponse`

### Alembic

- Configuration + migration initiale générée (`alembic init` + `alembic revision --autogenerate`)

### API REST

| Endpoints | Description |
|-----------|-------------|
| `GET/POST /api/sessions/` | Liste paginée + création |
| `GET/PUT/DELETE /api/sessions/{id}` | Détail, mise à jour, suppression |
| `GET/POST /api/characters/` | Liste avec filtre session_id + création |
| `GET/PUT/DELETE /api/characters/{id}` | Détail, mise à jour, suppression |
| `GET /api/srd/classes\|species\|spells\|monsters\|equipment` | Référence SRD (lecture seule, filtres) |

### Tests API (`tests/test_api/`) — **50/50 passants**

| Fichier | Tests | Couverture |
|---------|-------|------------|
| `test_sessions.py` | 13 | CRUD complet, validation, pagination |
| `test_characters.py` | 17 | CRUD complet, filtrage par session, validation |
| `test_srd.py` | 20 | Toutes les ressources SRD, filtres (niveau, classe, CR, catégorie) |

**Bugfix découvert via les tests** : `routes_srd.py` — l'endpoint `/equipment` ne gérait pas la structure imbriquée de `equipment.json` (`weapons` et `armor` sont des dicts de listes, pas des listes plates). Corrigé avec `_flatten_equipment()`.

---

## Liens utiles

| Ressource | URL |
|-----------|-----|
| API docs (dev) | http://localhost:8000/docs |
| Frontend (dev) | http://localhost:5173 |
| Ollama API | http://localhost:11434 |
| Voxtral TTS (optionnel) | http://localhost:8091 |
| Licence SRD 5.2 | CC-BY-4.0 (dans `engine/srd_data/`) |
