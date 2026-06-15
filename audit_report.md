# Audit Report - RpgMaster

Date de l'audit : 2026-06-15  
Mode d'audit : statique, lecture seule, sans execution de tests

## Resume executif

RpgMaster presente une base globalement solide : l'architecture FastAPI/Vue est claire, la logique de jeu est largement decoupee, le moteur de regles est majoritairement isole, le design system frontend est bien installe, et la couverture de tests est deja substantielle cote backend comme frontend.

Aucun blocage P0 n'a ete confirme pendant l'audit. Les risques les plus importants sont toutefois de niveau P1 et doivent etre traites avant de considerer le systeme robuste en production ou en usage multi-utilisateur expose :

- Les frontieres de confidentialite MJ/joueur sont bonnes dans plusieurs chemins, mais le WebSocket Realtime dialogue injecte aujourd'hui des secrets GM-only dans une IA qui repond directement au joueur.
- Les endpoints `gm-dossier` et `personas` exposent des donnees GM-only hors espace admin strict.
- La documentation est contradictoire sur des points structurants : `Campaign.dossier` JSON vs table `CampaignDossier`, et `OLLAMA_API_KEY` via `.env` vs configuration runtime admin.
- Le fallback vocal `VoiceRouter` existe mais n'est pas integre a tous les flux, en particulier le dialogue Realtime bidi.
- Le frontend est conforme dans l'esprit, mais contient encore des origines API/WS hardcodees, des couleurs directes hors tokens, un token WebSocket en query string et des logs non bornes.
- Les tests sont nombreux, mais les tests live LLM ne sont pas exclus par defaut, il n'y a pas de garde reseau globale, et le vrai endpoint `/ws/dialogue/*` manque de tests contractuels.

Conclusion courte : le projet est viable et avance, mais la prochaine tranche de travail devrait d'abord clarifier la source de verite documentaire, verrouiller les frontieres de confidentialite, puis aligner les chemins voix/Realtime et les tests sur cette decision.

## Sources verifiees et derives documentaires

L'audit initial devait suivre `AGENTS.md`. Une verification complementaire a ete faite pour eviter de s'appuyer sur une specification potentiellement obsolete.

Sources verifiees :

- `AGENTS.md` racine : derniere modification observee `2026-05-31`, commit `ef96b3d`.
- `.env.example` : derniere modification observee `2026-06-01`, commit `ec36179`.
- `backend/CLAUDE.md` : derniere modification observee `2026-06-01`, commit `ec36179`.
- `README.md` : derniere modification observee `2026-05-29`, commit `a5a2b49`.
- `docs/PROJECT.md` et docs d'audit historiques.
- Code actuel dans `backend/app`, `frontend/src`, `backend/tests` et tests frontend.

Classification utilisee dans ce rapport :

- **Ecart a AGENTS.md** : le code actuel ne suit pas la specification demandee dans `AGENTS.md`.
- **Spec probablement obsolete** : le code et/ou une doc plus recente semblent assumer une autre decision.
- **Risque reel d'implementation** : comportement fragile ou dangereux independamment des documents.
- **Contradiction documentaire** : plusieurs documents donnent des instructions incompatibles.

Derives documentaires majeures :

- `OLLAMA_API_KEY` : `AGENTS.md` indique que la cle doit venir de l'environnement. `.env.example`, `README.md` et `backend/CLAUDE.md` indiquent au contraire que la cle est geree via l'UI admin et `.runtime/llm_runtime.json`. Le code actuel confirme plutot cette seconde voie.
- `Campaign.dossier` : `AGENTS.md` interdit une table SQLAlchemy dediee et demande un JSON blob dans `Campaign.dossier`. Le code actuel utilise `CampaignDossier` comme table dediee et plusieurs docs internes plus recentes la decrivent comme autorite de campagne.
- Voice Router : `AGENTS.md` et `docs/PROJECT.md` presentent le fallback local comme global. Le code contient bien le routeur, mais certains flux continuent de le contourner.

Ces points ne doivent pas etre lus comme des bugs simples. Ils signalent surtout que les sources de verite du projet doivent etre alignees avant toute refonte.

## Synthese des risques prioritaires

| Priorite | Risque | Type | Zones |
|---|---|---|---|
| P1 | Secrets GM-only injectes dans le brief Realtime joueur | Risque reel | `backend/app/api/ws_dialogue.py`, `_persona_render.j2` |
| P1 | Endpoints GM/personas exposant secrets et motivations cachees | Risque reel | `backend/app/api/routes_campaign.py` |
| P1 | Architecture dossier non alignee avec `AGENTS.md` | Contradiction documentaire | `CampaignDossier`, `AGENTS.md`, docs internes |
| P1 | Configuration `OLLAMA_API_KEY` contradictoire | Contradiction documentaire | `AGENTS.md`, `.env.example`, `README.md`, `backend/CLAUDE.md`, `config.py` |
| P1 | API/WS frontend hardcodes et token WS en query string | Risque reel | `frontend/src/services/api.ts`, `frontend/src/composables/useWebSocket.ts` |
| P1 | Tests live LLM inclus dans le run standard | Risque reel | `backend/pyproject.toml`, `backend/tests/test_e2e_live` |
| P2 | `VoiceRouter` fallback partiellement non branche | Risque reel | `backend/app/main.py`, `backend/app/voice`, `backend/app/api/ws_dialogue.py` |
| P2 | Engine contient I/O SRD et quelques bugs mecaniques | Ecart + risque | `backend/app/engine` |
| P2 | Logs frontend et `seenEventIds` non bornes | Risque perf | `frontend/src/stores/game.ts` |

## Axe 1 - Backend & DB

### Constats - Forces

- FastAPI est structure autour d'une app factory claire dans `backend/app/main.py`, avec lifespan, CORS, routers REST et WebSocket.
- SQLAlchemy async est centralise dans `backend/app/db/database.py` avec `async_sessionmaker` et `get_db`.
- Les routes REST utilisent majoritairement `Depends(get_db)`.
- Le WebSocket principal utilise une fabrique de session injectee dans plusieurs chemins et lance les actions joueur en background task.
- Les schemas WebSocket sont defensifs : validation Pydantic, limitation de taille et `extra="forbid"` dans `backend/app/api/ws_schemas.py`.
- Le client Ollama applique bien un connect timeout court et un read timeout long, coherent avec les generations narratives longues.

### Constats - Faiblesses et risques

- `backend/app/models/campaign.py` definit une relation vers `CampaignDossier`, et `backend/app/models/campaign_dossier.py` definit une table `campaign_dossiers`. Cela contredit `AGENTS.md`, mais semble etre une decision actuelle assumee par d'autres docs.
- `backend/app/api/ws_game.py` utilise encore directement `async_session()` dans le cleanup de derniere deconnexion, au lieu d'utiliser partout la factory injectee.
- Certains chemins WebSocket peuvent encore attendre des actions IA inline, notamment sur `join` en combat, ce qui peut bloquer la boucle de reception.
- Les endpoints `/api/campaigns/{id}/gm-dossier` et `/api/campaigns/{id}/personas` retournent des informations GM-only, incluant potentiellement secrets et motivations cachees, hors prefixe `/api/admin`.
- Les mutations profondes de JSON SQLAlchemy doivent etre auditees : sans reassignation, `MutableDict` ou `flag_modified`, certaines modifications imbriquees peuvent ne pas etre persistees selon le chemin.

### Ecarts / contradictions avec les specs

- **Contradiction documentaire** : `AGENTS.md` demande `Campaign.dossier` JSON sans table dediee, tandis que le code et plusieurs docs internes assument `CampaignDossier`.
- **Contradiction documentaire** : `AGENTS.md` demande `OLLAMA_API_KEY` via env, alors que `.env.example`, `README.md`, `backend/CLAUDE.md` et le code actuel utilisent une cle runtime admin.
- **Ecart a AGENTS.md** : `MAX_CONTEXT_MESSAGES` est documente a 20 dans `AGENTS.md` et `.env.example`, mais la valeur par defaut de `backend/app/config.py` est 50.
- **Ecart a AGENTS.md** : anti-pattern partiel sur les sessions DB dans les handlers WebSocket.

### Fiches d'actions prioritaires

- **P1 - Choisir l'autorite dossier** : soit migrer vers `Campaign.dossier` JSON, soit mettre a jour `AGENTS.md` pour officialiser `CampaignDossier`.
- **P1 - Aligner la configuration Ollama Cloud** : choisir env ou runtime admin comme source officielle, puis aligner `AGENTS.md`, `.env.example`, `README.md`, `backend/CLAUDE.md`, `config.py` et les tests.
- **P1 - Proteger les endpoints GM-only** : deplacer sous `/api/admin`, exiger admin token/RBAC, ou separer explicitement endpoints joueur/MJ.
- **P2 - Supprimer les sessions directes en WS** : remplacer `async_session()` par `db_session_factory` dans tous les chemins WebSocket.
- **P2 - Decoupler les tours IA du receive loop** : lancer les chemins IA longs via tasks journalisees et file/backpressure par session.
- **P2 - Auditer les mutations JSON** : reassignation explicite, `MutableDict`/`MutableList`, ou `flag_modified`.

## Axe 2 - Rules Engine

### Constats - Forces

- Le moteur `backend/app/engine` n'importe pas FastAPI, SQLAlchemy, services applicatifs, agents LLM ou voix dans les modules principaux de mecanique.
- Les jets, attaques, degats, conditions, XP, inventaire et grille tactique sont majoritairement synchrones et testables.
- Plusieurs fonctions acceptent un `random.Random`, ce qui rend les tests deterministes.
- Les donnees SRD `spells.json` et `monsters.json` sont validees par schemas Pydantic.

### Constats - Faiblesses et risques

- `backend/app/engine/srd_data/__init__.py` lit les JSON au premier acces. C'est un I/O dans `engine/`, ce qui contredit le principe strict "zero I/O".
- Les loaders SRD retournent des objets mutables caches globalement. Un consommateur peut modifier le canon SRD en memoire.
- `ActionEconomy.spend_movement()` accepte une distance negative, ce qui peut augmenter le mouvement restant.
- `currency.subtract_cost()` peut crediter la richesse avec des couts negatifs.
- Certains calculs d'upcast spell/damage et de pathfinding avec terrain difficile meritent correction et tests de regression.
- Les seuils d'encounter semblent limites aux niveaux 1-10 ou silencieusement clampes, alors que D&D attend une progression jusqu'au niveau 20.
- Des donnees d'especes/classes sont partiellement recodees en Python en plus des JSON SRD.

### Ecarts / contradictions avec les specs

- **Ecart a AGENTS.md** : `engine/` n'est pas strictement zero I/O a cause du chargement JSON SRD.
- **Ecart a AGENTS.md** : certains tests places sous `test_engine` importent des services applicatifs, donc la suite engine n'est pas parfaitement pure.
- **Risque reel** : quelques entrees mecaniques invalides peuvent produire des effets inverses, notamment distances/couts negatifs.

### Fiches d'actions prioritaires

- **P1 - Bloquer les valeurs negatives** : `spend_movement()`, `subtract_cost()` et autres entrees de ressources doivent refuser les valeurs negatives.
- **P1 - Clarifier le chargement SRD** : sortir l'I/O de `engine/`, precharger au demarrage, ou documenter une exception officielle.
- **P1 - Proteger les donnees SRD cachees** : retourner copies profondes, structures immutables, ou vues readonly.
- **P2 - Corriger upcast/pathfinding** : ajouter tests obstacles + terrain difficile + modificateurs negatifs.
- **P2 - Etendre ou refuser explicitement les niveaux 11-20** dans l'encounter builder.
- **P3 - Deplacer le contenu narratif/procedural** hors `engine/` si son role n'est pas mecanique pure.

## Axe 3 - AI & Prompts

### Constats - Forces

- Les personas sont bien modelees avec `NPCPersona`, `MonsterPersona`, `CompanionPersona`, sous-modeles vocaux/motivations/connaissances et deserialisation polymorphe.
- `_persona_render.j2` centralise le rendu et masque bien `motivations.hidden`, `secrets`, `quest_hooks` quand `include_hidden=False`.
- Les templates joueur/compagnon utilisent globalement `include_hidden=False`; les templates MJ utilisent `include_hidden=True`.
- `PersonaFactory` applique bien le pattern stub-then-enrich avec retry et fallback pour PNJ, et fallback deterministe pour monstres mindless/muets.
- Des tests couvrent personas, factory, legacy coercion et frontiere de confidentialite compagnon.

### Constats - Faiblesses et risques

- Les sentinelles de `prompt_safety.delimit_user_input()` ne sont pas echappees si l'utilisateur injecte lui-meme la sentinelle de fin.
- L'historique et certains messages recents sont injectes de facon moins bornee que l'action courante.
- Le rendu public expose `knowledge.knows` et `knowledge.rumors` meme quand `include_hidden=False`. Si un prompt de generation y place un secret fonctionnel, ce secret peut sortir cote joueur.
- `PlayerAgent` depend fortement des appelants pour recevoir un `game_state` deja filtre. Une defense en profondeur interne manque.
- Les listes/textes de persona n'ont pas tous des bornes Pydantic strictes, ce qui augmente le risque de prompts trop longs et de surface d'injection.

### Ecarts / contradictions avec les specs

- **Pas d'ecart direct majeur** sur `include_hidden=True` cote MJ et `False` cote joueur IA pour les templates principaux.
- **Risque reel** : la notion `knowledge.knows` n'est pas explicitement separee en public/prive, alors qu'elle peut porter des secrets de jeu.
- **Risque reel** : la defense prompt injection est partielle et depend de conventions d'appel.

### Fiches d'actions prioritaires

- **P1 - Echappement unique des entrees non fiables** : appliquer une fonction commune aux actions joueur, messages recents, historiques, contexte de scene et champs libres.
- **P1 - Separer connaissance publique/privee** : `knowledge_public` / `knowledge_private`, ou filtrage strict de `knowledge` dans les rendus publics.
- **P2 - Filtrage interne PlayerAgent** : garantir que `PlayerAgent` nettoie l'etat meme si l'appelant oublie.
- **P2 - Borner les personas** : `max_length`, `max_items`, truncation controlee et tests de regression.
- **P3 - Elargir les tests d'injection** : sentinelles imbriquees, historique hostile, secrets dans `knowledge`, `quest_hooks` absents du rendu public.

## Axe 4 - Realtime Voice & WebSocket

### Constats - Forces

- `OPENAI_REALTIME_API_KEY` reste cote backend ; aucune exposition frontend directe n'a ete observee.
- `RealtimeSession` isole la connexion WebSocket OpenAI et dispose de tests offline pour connect, audio, commit, cancel et transcript.
- `VoiceRouter` implemente la selection local/realtime/hybrid et le fallback local sur `VoiceProviderError`.
- Le protocole `/ws/dialogue/{session_id}/{persona_id}` est clairement documente dans `ws_dialogue.py`.

### Constats - Faiblesses et risques

- `_render_persona_brief()` utilise `include_hidden=True` pour le brief Realtime. L'IA qui parle directement au joueur recoit donc motivations cachees, peurs et secrets.
- Le WebSocket dialogue contourne `VOICE_PROVIDER` : si la cle OpenAI existe, il tente Realtime meme si le mode global est `local`.
- Le fallback `VoiceRouter` ne s'applique pas au dialogue bidi. En cas de cle absente ou connexion Realtime impossible, le WS renvoie une erreur visible puis ferme.
- `VoiceRouter` existe mais le flux TTS publie dans `main.py` passe encore par `tts_router.synthesize_and_broadcast`.
- Les chunks `audio_b64` ne semblent pas limites en taille ni validates avec `base64.b64decode(..., validate=True)`.
- Le transcript publie sur le bus n'est pas directement consommable par le frontend actuel, qui attend un payload de dialogue avec `text`.
- L'endpoint manque de tests WebSocket de bout en bout : auth, cle absente, persona absente, audio invalide, commit/cancel/close, transcript.

### Ecarts / contradictions avec les specs

- **Ecart a AGENTS.md** : ne jamais exposer `motivations.hidden`, `secrets`, `quest_hooks` au joueur. Le chemin Realtime injecte actuellement ces donnees dans une IA qui parle au joueur.
- **Ecart a AGENTS.md / docs PROJECT** : fallback local presente comme automatique, mais pas effectif dans `/ws/dialogue/*`.
- **Risque reel** : absence de quotas audio et payload non borne.

### Fiches d'actions prioritaires

- **P1 - Brief Realtime player-safe** : utiliser `include_hidden=False` ou un brief dedie qui transforme les secrets en contraintes comportementales non revelables.
- **P1 - Gater `/ws/dialogue/*`** : respecter `VOICE_PROVIDER`, verifier session/persona/personnage, presence ou permission de dialogue.
- **P1 - Proteger les secrets Realtime par mecanique** : une revelation doit passer par le MJ/moteur, pas par simple conversation vocale.
- **P2 - Brancher `VoiceRouter` au flux TTS publie** et initialiser `RealtimeVoiceProvider` au startup si le mode le demande.
- **P2 - Ajouter quotas et validation audio** : taille max, decode strict, duree max, rate limit, semaphore par session/persona.
- **P2 - Normaliser le transcript** : event dedie ou payload consommable frontend, puis injection controlee dans la continuite MJ.
- **P2 - Tests contractuels endpoint** : couvrir le vrai WebSocket avec `RealtimeSession` fake et event bus mocke.

## Axe 5 - Frontend & Design System

### Constats - Forces

- Stack conforme : Vue 3, TypeScript, Pinia, Vue Router et TailwindCSS v4.
- `frontend/src/assets/main.css` contient bien `@theme`, tokens couleur, polices, classes `.rpg-*`, `prose-narrative`, scrollbars et `html, body { overflow: hidden; }`.
- Les layouts jeu utilisent largement `h-full`, `min-h-0` et `overflow-hidden`/scroll interne.
- `useWebSocket.ts` gere ping/pong, reconnect, parsing defensif, cleanup et tests Vitest dedies.
- Pas de `v-html` ou `innerHTML` repere dans la passe statique.
- La cle `OPENAI_REALTIME_API_KEY` n'est pas exposee cote frontend.

### Constats - Faiblesses et risques

- `frontend/src/services/api.ts` hardcode `http://localhost:8000/api`.
- `frontend/src/composables/useWebSocket.ts` hardcode `ws://localhost:8000`.
- Le token d'acces WebSocket est passe en query string, ce qui peut fuiter dans logs, proxy ou outils dev.
- De nombreux hex/rgba restent hors tokens, notamment dans `GameSessionView.vue`, `RegionMap.vue`, `TownMap.vue`, `RpgMapIcon.vue`, `library.ts` et le moteur 3D.
- Le moteur 3D a des contraintes legitimes de couleurs materielles, mais les fallbacks hex doivent etre centralises/documentes comme exception.
- `narrativeLog` et `seenEventIds` dans le store jeu ne semblent pas bornes.
- L'UI affiche une limite reconnect differente de la constante reelle.
- Certaines vues admin/techniques restent proches d'un dashboard Tailwind standard plutot que du grimoire vivant.

### Ecarts / contradictions avec les specs

- **Ecart a AGENTS.md** : couleurs hardcodees hors tokens dans plusieurs composants/templates/styles.
- **Ecart a AGENTS.md** : quelques vues utilisent encore `min-h-screen` ou `100vh`, en tension avec le scroll global bloque.
- **Risque reel** : hardcodes API/WS limitent reverse proxy, HTTPS, staging, LAN et mobile.
- **Risque reel** : token WebSocket dans l'URL.

### Fiches d'actions prioritaires

- **P1 - Externaliser API/WS** : utiliser variables `VITE_*`, origine courante, ou proxy Vite selon environnement.
- **P1 - Revoir auth WS** : cookie SameSite, ticket court REST, ou auth dans un premier message WS plutot qu'en query string.
- **P1/P2 - Nettoyer couleurs directes** : priorite au loader `GameSessionView`, cartes exploration, couleurs metier de `library.ts`, composants combat.
- **P2 - Centraliser les couleurs 3D** : resolver unique lisant tokens CSS avec fallbacks documentes.
- **P2 - Borner logs et event IDs** : LRU ou fenetre glissante pour `narrativeLog` et `seenEventIds`.
- **P2 - Harmoniser reconnect UI** : exporter la constante ou afficher la vraie limite.
- **P3 - Restyler admin** : primitives `.rpg-*`, gating visuel selon capacite admin, et suppression des panneaux redondants.

## Axe 6 - QA & Test Coverage

### Constats - Forces

- Couverture backend large : environ 85+ fichiers de tests Python observes.
- Couverture frontend significative : environ 28 fichiers Vitest dans `frontend/src`.
- Les tests API utilisent SQLite in-memory et overrides FastAPI propres dans `backend/tests/conftest.py`.
- Les tests WebSocket game utilisent `StaticPool`, lifespan dedie et stub global LLM dans `backend/tests/test_game/conftest.py`.
- Les suites engine couvrent des mecaniques centrales : des, combat, conditions, equipement, XP, pathfinding, cartes.
- Les tests privacy couvrent la non-fuite public/compagnons et l'anonymisation de PNJ inconnus.
- Les tests voice sont offline, sans reseau ni subprocess reel.

### Constats - Faiblesses et risques

- `backend/pyproject.toml` ne semble pas exclure `live_llm` par defaut. Un `pytest` standard peut donc lancer des tests live si l'environnement le permet.
- Le garde reseau global n'est pas generalise. Le stub LLM autouse est local a la suite `test_game`.
- Le vrai endpoint `/ws/dialogue/{session_id}/{persona_id}` n'est pas teste de bout en bout.
- Certains tests sous `test_engine` importent des services applicatifs, ce qui brouille la promesse de purete engine.
- Certains helpers WebSocket peuvent attendre indefiniment si l'evenement attendu n'arrive pas ; pas de timeout global observe.
- Le test du loader SRD invalide valide surtout le schema, pas necessairement le loader complet.

### Ecarts / contradictions avec les specs

- **Ecart a AGENTS.md** : `tests/test_engine` n'est pas strictement limite a la logique pure.
- **Risque reel** : tests live LLM non opt-in par defaut.
- **Risque reel** : absence de garde reseau globale pour les tests non marques live.

### Fiches d'actions prioritaires

- **P1 - Exclure live LLM du run standard** : `addopts = "-m 'not live_llm'"` ou `skipif` env explicite.
- **P1 - Tester `/ws/dialogue/*` reel** : auth, cle absente, persona absente, audio invalide, commit, cancel, close, transcript.
- **P2 - Garde reseau globale** : bloquer `OllamaClient`, `httpx.AsyncClient`, `websockets.connect` sauf marqueur live.
- **P2 - Reorganiser tests engine** : deplacer services/data hors `test_engine` ou renommer les suites.
- **P2 - Timeouts WS** : helper de reception borne ou plugin timeout.
- **P3 - Couverture minimale** : seuils `--cov=app` par module critique et jobs separes backend/frontend/live.

## Priorites consolidees

### P1 - A traiter en premier

1. Clarifier et aligner les docs sur `CampaignDossier` vs `Campaign.dossier`.
2. Clarifier et aligner les docs/config/tests sur `OLLAMA_API_KEY`.
3. Rendre le brief Realtime player-safe et arreter d'injecter secrets GM-only dans l'IA vocale joueur.
4. Proteger les endpoints GM-only (`gm-dossier`, `personas`) par admin/RBAC ou les deplacer.
5. Externaliser API/WS frontend et remplacer l'auth WS en query string.
6. Exclure `live_llm` du run pytest standard.
7. Corriger les bugs mecaniques negatives dans engine.

### P2 - Robustesse et maintenabilite

1. Brancher reellement `VoiceRouter` et le fallback local dans les flux TTS/Realtime.
2. Ajouter quotas/validation au WS dialogue.
3. Ajouter tests contractuels `/ws/dialogue/*`.
4. Introduire garde reseau globale dans les tests.
5. Nettoyer couleurs frontend hors tokens et documenter les exceptions WebGL.
6. Borner logs frontend et `seenEventIds`.
7. Auditer les mutations JSON SQLAlchemy.

### P3 - Dette et polish

1. Restyler les panneaux admin avec les primitives RPG.
2. Deplacer ou renommer le contenu narratif/procedural hors engine.
3. Dedoublonner donnees SRD Python/JSON.
4. Ajouter accessibilite ciblée aux boutons iconiques.
5. Nettoyer docs historiques qui peuvent etre lues comme specs actuelles.

## Conclusion - Viabilite et risques

RpgMaster est une base de code ambitieuse et deja bien structuree. Les fondations sont bonnes : le backend async est coherent, le moteur de regles porte l'essentiel des mecaniques, les agents sont contraints par schemas JSON, les personas sont modelees proprement, le frontend a une identite visuelle forte, et les tests sont nombreux.

Le risque principal n'est pas une absence d'architecture, mais une divergence entre architecture decrite, architecture implementee et architecture documentee plus recemment. Tant que `AGENTS.md`, `.env.example`, `README.md`, `backend/CLAUDE.md` et les docs internes ne racontent pas la meme histoire, chaque audit ou refactor risque de corriger la mauvaise cible.

Le second risque est la confidentialite : les frontieres public/MJ sont bien pensees, mais quelques chemins sensibles, surtout Realtime et endpoints GM, peuvent contourner cette intention. C'est le chantier a traiter avant d'elargir l'usage du mode vocal riche ou du multi-utilisateur.

Le systeme est donc viable pour continuer le developpement, mais il doit passer par une phase courte de consolidation : choix documentaire officiel, verrouillage des secrets, branchement complet du VoiceRouter, tests WS Realtime et nettoyage des points frontend/deploiement.
