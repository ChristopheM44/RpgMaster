# RpgMaster — Avancement du projet

> Derniere mise a jour : 2026-03-29 (Sprint 2 en cours)

---

## Etat global

| Sprint | Titre | Statut |
|--------|-------|--------|
| Sprint 0 | Bootstrap | ✅ Termine |
| Sprint 1 | Moteur de regles D&D SRD 5.2 | ✅ Termine |
| Sprint 2 | Couche donnees + API REST | 🔄 En cours |
| Sprint 3 | Integration LLM | 🔲 A faire |
| Sprint 4 | Game Loop + WebSocket | 🔲 A faire |
| Sprint 5 | Agents joueurs IA | 🔲 A faire |
| Sprint 6 | Frontend MVP | 🔲 A faire |
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
│   │   ├── routes_session.py    🔲 Stubs CRUD sessions
│   │   ├── routes_character.py  🔲 Stub CRUD personnages
│   │   ├── routes_game.py       🔲 Stub endpoints jeu
│   │   └── ws_game.py           🔲 Echo WebSocket (pas encore de logique)
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
│   ├── schemas/         🔲 Vide — a creer (Sprint 2)
│   ├── services/        🔲 Vide — a creer (Sprint 2+)
│   ├── agents/          🔲 Vide — a creer (Sprint 3+)
│   ├── llm/             🔲 Vide — a creer (Sprint 3)
│   └── game/            🔲 Vide — a creer (Sprint 4)
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
    ├── test_api/        🔲 Vide — a creer (Sprint 2)
    └── test_agents/     🔲 Vide — a creer (Sprint 3)
```

---

## Sprint 2 — Couche données + API REST (en cours)

### ✅ Modèles SQLAlchemy (`backend/app/models/`)

Quatre modèles ORM créés et validés :

| Modèle | Table | Description |
|--------|-------|-------------|
| `Session` | `sessions` | Session de jeu avec statut (enum : LOBBY → SESSION_END) |
| `Character` | `characters` | Personnage humain ou IA avec stats JSON, équipement, sorts, conditions |
| `GameState` | `game_states` | Blob JSON one-to-one avec Session, contient l'état complet du jeu |
| `Message` | `messages` | Entrée du journal de partie (narration, dialogue, jet de dés, système) |

**Points notables :**
- `SessionStatus` enum couvre toute la machine à états du jeu
- `Character.ability_scores`, `.equipment`, `.spell_slots`, `.conditions` sont des JSON blobs
- `GameState.state_data` est le blob autoritatif de l'état (initiative, PNJs, environnement…)
- `Message` supporte `role` (gm/player/system) + `message_type` + `metadata_` JSON pour les résultats de jets
- `Character.session_id` est nullable (FK avec `SET NULL`) : un personnage peut exister sans session
- Correction Python 3.9 : utilisation de `Optional[X]` car SQLAlchemy évalue les annotations via `eval()` au runtime — `X | None` n'est pas supporté sur Python 3.9 dans ce contexte
- `UP045` exclu de ruff pour les modèles SQLAlchemy

---

## Prochaines etapes (Sprint 2 suite)

2. **Schemas Pydantic** dans `backend/app/schemas/` :
   - Requetes et reponses pour chaque endpoint REST

3. **Migration Alembic** initiale :
   ```bash
   alembic init alembic
   alembic revision --autogenerate -m "initial"
   alembic upgrade head
   ```

4. **Implementer les routes REST** :
   - `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
   - `POST /characters`, `GET /characters/{id}`, `PUT /characters/{id}`
   - `GET /srd/classes`, `GET /srd/species`, `GET /srd/spells`, `GET /srd/monsters`

5. **Tests API** dans `tests/test_api/` avec client de test FastAPI

---

## Liens utiles

| Ressource | URL |
|-----------|-----|
| API docs (dev) | http://localhost:8000/docs |
| Frontend (dev) | http://localhost:5173 |
| Ollama API | http://localhost:11434 |
| Voxtral TTS (optionnel) | http://localhost:8091 |
| Licence SRD 5.2 | CC-BY-4.0 (dans `engine/srd_data/`) |
