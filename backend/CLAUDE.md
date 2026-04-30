# Backend — CLAUDE.md

> Contexte specifique au dossier `backend/`. Se combine avec le CLAUDE.md racine.

## Demarrage rapide

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m uvicorn app.main:app --reload
```

## Structure des modules

```
app/
├── api/
│   ├── routes_game.py       # REST sessions de jeu (start, save, load)
│   ├── routes_session.py    # CRUD sessions
│   ├── routes_character.py  # CRUD personnages
│   ├── routes_srd.py        # Donnees de reference SRD (classes, especes, sorts...)
│   ├── routes_encounters.py # Construction et gestion des rencontres
│   ├── routes_campaign.py   # Campagnes (enchainement de sessions)
│   ├── routes_admin.py      # Parametres TTS, health backends
│   └── ws_game.py           # WebSocket /ws/game/{session_id}
├── engine/                  # Logique D&D pure — AUCUN I/O
│   ├── dice.py              # Notations "2d6+3", "4d6kh3", avantage/desavantage
│   ├── ability_checks.py    # Tests de caracteristiques, jets de sauvegarde
│   ├── combat.py            # Initiative, attaque, degats, jets de mort
│   ├── conditions.py        # Conditions SRD (etourdi, a terre, empoisonne...)
│   ├── spells.py            # Resolution sorts, emplacements, concentration
│   ├── character_creation.py# Achat de points, traits espece, capacites classe
│   ├── equipment.py         # Armes, armures, calcul CA
│   ├── encounter_builder.py # Generation de rencontres par CR
│   └── srd_data/            # JSON SRD 5.2.1 FR
├── agents/
│   ├── gm_agent.py          # Agent MJ : contexte -> prompt -> LLM -> JSON valide
│   ├── player_agent.py      # Agent joueur IA : decision + roleplay
│   ├── context_manager.py   # Fenetre glissante, summarization
│   └── prompts/             # Templates Jinja2 (.txt)
├── game/
│   ├── game_loop.py         # Machine a etats (phases)
│   ├── turn_manager.py      # Ordre des tours, initiative
│   ├── session_manager.py   # Cycle de vie sessions actives en memoire
│   ├── action_resolver.py   # Dispatch actions joueur -> moteur -> narration
│   ├── ai_player_manager.py # Gestion des tours IA compagnons
│   └── event_bus.py         # asyncio.Queue pub/sub par session
├── llm/
│   ├── ollama_client.py     # Client async Ollama (retry, streaming)
│   └── voxtral_client.py    # Client TTS dual-backend (Kokoro ou vLLM-Omni)
└── services/
    ├── message_service.py        # Persistance narrations en DB
    ├── encounter_service.py      # Construction rencontres depuis monster_ids
    ├── narrative_flow_service.py # Orchestration exploration vivante
    ├── equipment_service.py      # Equip/use/drop, sync DB + ActiveSession
    └── rest_service.py           # Repos court/long, des de vie, sorts
```

## Protocole WebSocket

Endpoint : `ws://localhost:8000/ws/game/{session_id}?character_id={id}`

### Messages client -> serveur

```json
{ "type": "join", "character_id": "hero_1" }
{ "type": "action", "action_type": "free_text", "content": "Je cherche une porte secrete" }
{ "type": "action", "action_type": "attack", "target_id": "goblin_0" }
{ "type": "action", "action_type": "cast_spell", "spell_id": "fire_bolt", "target_id": "...", "slot_level": 1 }
{ "type": "action", "action_type": "start_combat" }
{ "type": "action", "action_type": "equip", "character_id": "hero_1", "item_id": "leather" }
{ "type": "action", "action_type": "use_item", "character_id": "hero_1", "item_id": "healing_potion" }
{ "type": "action", "action_type": "drop_item", "character_id": "hero_1", "item_id": "torch" }
{ "type": "action", "action_type": "short_rest", "hit_dice_spend": { "hero_1": 1 } }
{ "type": "action", "action_type": "long_rest" }
{ "type": "action", "action_type": "take_rest" }
```

`take_rest` reste un alias de compatibilite pour `long_rest`.
Le repos court depense les des de vie choisis par le client via
`hit_dice_spend`. Le format persiste sur `Character.hit_dice` :
`{"die": 10, "total": 1, "used": 0}`.

### Evenements serveur -> client (EventType)

| Type | Contenu |
|------|---------|
| `narration` | Texte narratif du MJ |
| `dialogue` | Dialogue PNJ |
| `roll_result` | Jet de des avec detail |
| `combat_action` | Action mecaniste resolue (attaque, sort, mouvement) |
| `hp_changed` | Changement de PV d'un combattant |
| `condition_changed` | Condition appliquee/retiree |
| `equipment_updated` | Inventaire/equipement d'un personnage |
| `spell_slot_updated` | Emplacements de sorts restaures ou consommes |
| `hit_dice_updated` | Des de vie disponibles/depenses |
| `turn_start` / `turn_end` | Debut/fin de tour |
| `combat_start` / `combat_end` | Transitions de phase |
| `phase_change` | Changement d'etat de la machine a etats |
| `session_state` | Snapshot complet du game state |
| `audio` | Audio WAV base64 (TTS) |
| `error` | Erreur applicative |

## Patterns SQLAlchemy async

```python
# CORRECT — session injectee via Depends
async def my_handler(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model))

# INTERDIT — ne jamais creer une session dans un handler WS
session = AsyncSession(engine)  # NON
```

## Ajouter un agent / modifier les prompts

Les prompts sont des templates Jinja2 dans `agents/prompts/`.
Le GMAgent attend une reponse JSON valide selon `agents/schemas.py` (classe `GMResponse`).
Tout nouveau type d'action doit etre ajoute dans `EventType` (event_bus.py) ET gere dans `action_resolver.py`.

Exceptions actuelles : les actions directes d'inventaire et de repos passent
par `EquipmentService` / `RestService`, puis publient directement leurs
evenements via l'event bus depuis `ws_game.py` ou le service.

## Tests

```bash
pytest tests/test_engine/ -v         # Moteur (rapide, aucune dependance)
pytest tests/test_api/ -v            # API (DB SQLite in-memory)
pytest tests/test_agents/ -v         # Agents (Ollama mocke)
pytest tests/test_game/ -v           # Game loop + WebSocket
pytest --cov=app --cov-report=term-missing
```
