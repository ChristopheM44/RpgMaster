# RpgMaster - TODO

## Sprint 0 : Bootstrap [TERMINE]
- [x] Init monorepo, git, .gitignore, .env.example
- [x] docker-compose.yml (Ollama + Voxtral)
- [x] Backend : pyproject.toml, dependances, venv
- [x] Backend : squelette FastAPI (main.py, config.py, routes stub, WebSocket)
- [x] Frontend : Vue.js 3 + TypeScript + Pinia + Vue Router
- [x] Frontend : TailwindCSS v4 + theme dark fantasy
- [x] Frontend : vues placeholder (Home, Lobby, CharacterCreation, GameSession)

## Sprint 1 : Moteur de regles D&D SRD 5.2
- [x] `engine/dice.py` : Jets de des (d4-d100, avantage/desavantage, notations type "2d6+3", "4d6kh3")
- [x] `engine/ability_checks.py` : Tests de caracteristiques, competences, jets de sauvegarde, bonus de maitrise
- [x] `engine/combat.py` : Initiative, jets d'attaque, degats, jets de mort, economie d'action
- [x] `engine/conditions.py` : Conditions SRD 5.2 (a terre, etourdi, empoisonne, etc.)
- [x] `engine/spells.py` : Resolution de sorts, emplacements, concentration
- [x] `engine/character_creation.py` : Achat de points, traits d'espece, capacites de classe (niveau 1)
- [x] `engine/equipment.py` : Armes, armures, calcul de CA
- [x] `engine/srd_data/` : Extraction des donnees SRD 5.2 en JSON (subset minimal)
  - [x] `classes.json` (4 classes : Guerrier, Magicien, Roublard, Clerc)
  - [x] `species.json` (3 especes : Humain, Elfe, Nain)
  - [x] `spells.json` (20 sorts niveaux 0-3)
  - [x] `monsters.json` (10 monstres CR 0-5)
  - [x] `equipment.json` (armes, armures, kit d'aventurier)
- [x] Tests unitaires complets du moteur (`tests/test_engine/`)

## Sprint 2 : Couche donnees + API REST
- [x] Modeles SQLAlchemy : Character, Session, GameState, Message
- [ ] Schemas Pydantic : request/response pour chaque endpoint
- [ ] Alembic : configuration + migration initiale
- [ ] API CRUD Sessions (create, list, get, update, save, load)
- [ ] API CRUD Characters (create, list, get, update)
- [ ] API SRD reference data (classes, especes, sorts, monstres, equipement)
- [ ] Tests API (`tests/test_api/`)

## Sprint 3 : Integration LLM
- [ ] `llm/ollama_client.py` : Client async Ollama avec retry et gestion d'erreur
- [ ] `llm/model_router.py` : Routage des requetes vers le bon backend LLM
- [ ] `agents/context_manager.py` : Fenetre glissante de contexte + summarization
- [ ] `agents/base_agent.py` : Interface abstraite d'agent
- [ ] `agents/gm_agent.py` : Agent MJ avec pipeline (contexte -> prompt -> LLM -> parse -> validate)
- [ ] `agents/prompts/gm_system.txt` : System prompt du MJ
- [ ] `agents/prompts/gm_narrate.txt` : Prompt de narration
- [ ] `agents/prompts/gm_combat.txt` : Prompt de combat
- [ ] `agents/prompts/gm_npc_dialogue.txt` : Prompt de dialogue PNJ
- [ ] Tests agents (`tests/test_agents/`)

## Sprint 4 : Game Loop + WebSocket
- [ ] `game/game_loop.py` : Machine a etats (phases LOBBY -> EXPLORATION -> COMBAT -> ...)
- [ ] `game/turn_manager.py` : Gestion de l'ordre des tours (initiative en combat, round-robin en exploration)
- [ ] `game/session_manager.py` : Cycle de vie des sessions actives
- [ ] `game/event_bus.py` : Bus d'evenements in-process (asyncio.Queue)
- [ ] `api/ws_game.py` : Implementation complete du protocole WebSocket
- [ ] Integration bout-en-bout : action joueur -> moteur -> GM -> broadcast
- [ ] Tests integration

## Sprint 5 : Agents joueurs IA
- [ ] `agents/player_agent.py` : Prise de decision basee sur personnalite et capacites
- [ ] `agents/prompts/player_decide.txt` : Prompt de decision
- [ ] `agents/prompts/player_roleplay.txt` : Prompt de roleplay
- [ ] Systeme de personnalite (brave, prudent, cupide, noble, etc.)
- [ ] Validation des actions IA (respect des capacites du personnage)
- [ ] Integration avec le turn manager
- [ ] Test : combat 1 humain + 2 IA compagnons vs gobelins

## Sprint 6 : Frontend MVP
- [ ] Shell app + navigation complete
- [ ] LobbyView : creer/charger session, voir les sessions sauvegardees
- [ ] CharacterCreationView : wizard etape par etape (espece, classe, background, stats, skills, equip, nom)
- [ ] GameSessionView : layout 3 panneaux (NarrativeLog 60% | CombatTracker + CharacterSummary 40% | ActionBar bas)
- [ ] Composant NarrativeLog : scroll de narration, dialogue, resultats de des
- [ ] Composant CombatTracker : ordre d'initiative, barres de PV, conditions
- [ ] Composant ActionBar : input texte libre + boutons contextuels (combat : Attaquer, Sort, Objet, Dash...)
- [ ] Composant DiceRollResult : affichage anime des jets de des
- [ ] Composable `useWebSocket.ts` : connexion, envoi, reception, dispatch vers stores Pinia
- [ ] Stores Pinia : session, game, character, chat
- [ ] Service `api.ts` : client REST (fetch/axios)

## Sprint 7 : Integration + Voix
- [ ] Flow end-to-end complet : creation session -> personnage -> jeu -> combat -> repos
- [ ] `llm/voxtral_client.py` : Client HTTP pour vLLM-Omni
- [ ] Composable `useAudio.ts` : lecture audio des narrations
- [ ] Mapping voix : 1 voix MJ narration, voix distinctes par PNJ
- [ ] Save/Load : serialisation et restauration complete du game state
- [ ] Gestion de deconnexion et reconnexion WebSocket

## Sprint 8 : Polish + Playtest
- [ ] CharacterSheetView : fiche de personnage complete et detaillee
- [ ] Flow de lancement de sorts : selection, cible, emplacement
- [ ] Gestion d'inventaire : equiper, utiliser, lacher
- [ ] Variete de rencontres : pre-construites + generation dynamique
- [ ] Tuning des prompts GM et joueurs IA (iterations basees sur le playtesting)
- [ ] Gestion d'erreur gracieuse (LLM lent/indisponible, deconnexion)
- [ ] Responsive design mobile

## Backlog (post-MVP)
- [ ] Phase 2 multijoueur : multi local (plusieurs humains, meme serveur)
- [ ] Phase 3 multijoueur : multi reseau (Redis pub/sub, authentification)
- [ ] Carte tactique de combat (grille 2D)
- [ ] Systeme de campagne (enchainement de sessions, progression persistante)
- [ ] Generateur de donjon procedural
- [ ] Plus de classes, especes, sorts, monstres (SRD 5.2 complet)
- [ ] Support d'autres systemes de regles (modulaire)
- [ ] Mode spectateur
- [ ] Export de session (journal de partie en PDF/Markdown)
