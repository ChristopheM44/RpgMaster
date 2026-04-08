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
- [x] Schemas Pydantic : request/response pour chaque endpoint
- [x] Alembic : configuration + migration initiale
- [x] API CRUD Sessions (create, list, get, update, save, load)
- [x] API CRUD Characters (create, list, get, update)
- [x] API SRD reference data (classes, especes, sorts, monstres, equipement)
- [x] Tests API (`tests/test_api/`)

## Sprint 3 : Integration LLM [TERMINE]
- [x] `llm/ollama_client.py` : Client async Ollama avec retry et gestion d'erreur
- [x] `llm/model_router.py` : Routage des requetes vers le bon backend LLM
- [x] `agents/context_manager.py` : Fenetre glissante de contexte + summarization
- [x] `agents/base_agent.py` : Interface abstraite d'agent
- [x] `agents/gm_agent.py` : Agent MJ avec pipeline (contexte -> prompt -> LLM -> parse -> validate)
- [x] `agents/prompts/gm_system.txt` : System prompt du MJ
- [x] `agents/prompts/gm_narrate.txt` : Prompt de narration
- [x] `agents/prompts/gm_combat.txt` : Prompt de combat
- [x] `agents/prompts/gm_npc_dialogue.txt` : Prompt de dialogue PNJ
- [x] Tests agents (`tests/test_agents/`)

## Sprint 4 : Game Loop + WebSocket
- [x] `game/game_loop.py` : Machine a etats (phases LOBBY -> EXPLORATION -> COMBAT -> ...)
- [x] `game/turn_manager.py` : Gestion de l'ordre des tours (initiative en combat, round-robin en exploration)
- [x] `game/session_manager.py` : Cycle de vie des sessions actives
- [x] `game/event_bus.py` : Bus d'evenements in-process (asyncio.Queue)
- [x] `api/ws_game.py` : Implementation complete du protocole WebSocket
- [x] Integration bout-en-bout : action joueur -> moteur -> GM -> broadcast
- [x] Tests integration

## Sprint 5 : Agents joueurs IA [TERMINE]
- [x] `agents/player_agent.py` : Prise de decision basee sur personnalite et capacites
- [x] `agents/prompts/player_decide.txt` : Prompt de decision
- [x] `agents/prompts/player_roleplay.txt` : Prompt de roleplay
- [x] Systeme de personnalite (brave, prudent, cupide, noble, etc.)
- [x] Validation des actions IA (respect des capacites du personnage)
- [x] Integration avec le turn manager (`is_ai_controlled` sur TurnEntry + `AIPlayerManager`)
- [x] Test : combat 1 humain + 2 IA compagnons vs gobelins

## Sprint 6 : Frontend MVP
- [x] Shell app + navigation complete
- [x] LobbyView : creer/charger session, voir les sessions sauvegardees
- [x] CharacterCreationView : wizard etape par etape (espece, classe, background, stats, skills, equip, nom)
- [x] GameSessionView : layout 3 panneaux (NarrativeLog 60% | CombatTracker + CharacterSummary 40% | ActionBar bas)
- [x] Composant NarrativeLog : scroll de narration, dialogue, resultats de des
- [x] Composant CombatTracker : ordre d'initiative, barres de PV, conditions
- [x] Composant ActionBar : input texte libre + boutons contextuels (combat : Attaquer, Sort, Objet, Dash...)
- [x] Composant DiceRollResult : affichage anime des jets de des
- [x] Composable `useWebSocket.ts` : connexion, envoi, reception, dispatch vers stores Pinia
- [x] Stores Pinia : session, game, character, chat
- [x] Service `api.ts` : client REST (fetch/axios)

## Sprint 7 : Integration + Voix
- [x] Flow end-to-end complet : creation session -> personnage -> jeu -> combat -> repos
- [x] `tts_service/synthesize.py` : Script CLI Kokoro-ONNX (micro-service isole Python 3.11)
- [x] `llm/voxtral_client.py` : Client TTS dual-backend (Kokoro subprocess + vLLM-Omni HTTP)
- [x] `api/routes_admin.py` : API admin — GET/PUT settings TTS, GET health backends
- [x] `game/event_bus.py` : Ajout EventType.AUDIO pour diffusion audio WebSocket
- [x] `game/action_resolver.py` : Hook TTS fire-and-forget apres chaque narration GM
- [x] Composable `useAudio.ts` : lecture audio WAV via Web Audio API
- [x] Composable `useWebSocket.ts` : handler evenement audio -> playAudioB64
- [x] Store `settings.ts` : gestion Pinia des parametres TTS (fetch/update)
- [x] Vue `AdminView.vue` + composant `TtsSettingsPanel.vue` : menu admin configurable
- [x] Composant `OllamaStatusPanel.vue` : etat Ollama (connexion, modeles disponibles, modeles configures MJ/IA)
- [ ] Mapping voix : 1 voix MJ narration, voix distinctes par PNJ
- [x] Save/Load : serialisation et restauration complete du game state
- [x] Gestion de deconnexion et reconnexion WebSocket

## Sprint 8 : Polish + Playtest
- [x] CharacterSheetView : fiche de personnage complete et detaillee
- [x] Flow de lancement de sorts : selection, cible, emplacement
- [x] Francisation complete : labels UI + descriptions SRD JSON en francais (SRD 5.2.1 FR CC-BY-4.0)
- [x] Gestion d'inventaire : equiper, utiliser, lacher
- [x] Variete de rencontres : pre-construites + generation dynamique
- [x] Transparence actions IA en combat : resolution deterministe + event COMBAT_ACTION structure
- [x] Tuning des prompts GM et joueurs IA (iterations basees sur le playtesting)
- [x] Gestion d'erreur gracieuse (LLM lent/indisponible, deconnexion)
- [x] Responsive design mobile

## Sprint 9 : Personnages Prétirés + Flux Setup [TERMINE]
- [x] `engine/srd_data/pregens.json` : 12 templates prétirés niveau 1 (un par classe SRD 5.2)
- [x] `api/routes_pregen.py` : GET /api/characters/pregenerated + POST /api/characters/pregenerated/{class_id}
- [x] `main.py` : enregistrement du router pregen avant le router character
- [x] `types/index.ts` : interface PregenTemplate
- [x] `services/api.ts` : pregenApi (list + create)
- [x] `views/CharacterSetupView.vue` : écran intermédiaire /session/:id/setup (liste groupe, ajout prétiré via modal, création wizard, lancement partie)
- [x] `router/index.ts` : route character-setup
- [x] `views/LobbyView.vue` : redirect vers character-setup après création/ajout
- [x] `views/CharacterCreationView.vue` : redirect vers character-setup après création

## Backlog (post-MVP)
- [x] Phase 2 multijoueur : multi local hot-seat (plusieurs humains, meme ordi)
- [ ] Phase 3 multijoueur : multi reseau (Redis pub/sub, authentification)
- [x] Carte tactique de combat (grille 2D)
- [x] Systeme de campagne (enchainement de sessions, progression persistante)
- [ ] Generateur de donjon procedural
- [x] Plus de classes, especes, sorts, monstres (SRD 5.2 complet)
- [ ] Support d'autres systemes de regles (modulaire)
- [ ] Mode spectateur
- [ ] Export de session (journal de partie en PDF/Markdown)
