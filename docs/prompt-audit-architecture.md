# Prompt d'audit technique et architectural — RpgMaster

## Rôle

Tu es un architecte logiciel senior et un expert en applications temps réel collaboratives. Tu dois auditer une application de jeu de rôle (JdR) assistée par IA.

## Contexte projet

- **Nom** : RpgMaster
- **But** : Permettre à un ou plusieurs joueurs humains de jouer à un JdR D&D SRD 5.2 (CC-BY-4.0) en temps réel, accompagnés d'un Maître de Jeu IA et de compagnons joueurs IA.
- **Stack** :
  - Backend : Python 3.9+ / FastAPI, SQLite (aiosqlite) + Alembic, WebSocket natif (`/ws/game/{session_id}`)
  - Frontend : Vue.js 3 / TypeScript, Composition API + Pinia + Vue Router, TailwindCSS v4
  - IA : Ollama (texte, modèle local `mistral:7b`), Voxtral 4B TTS via vLLM-Omni (port 8091, optionnel)
- **Architecture clé** :
  - `backend/app/engine/` : moteur de règles D&D pur, zero I/O
  - `backend/app/agents/` : agents IA (GM, joueurs) avec prompts Jinja2, sorties JSON structurées via Pydantic
  - `backend/app/game/` : orchestration (game loop, turn manager, event bus via `asyncio.Queue`)
  - `backend/app/llm/` : clients Ollama + Voxtral
  - Frontend : stores Pinia, composables `useWebSocket`, `useGameActions`, `useAudio`
- **Contraintes** : Python 3.9.6 (pas 3.11+), moteur de règles souverain (le LLM ne résout jamais les mécaniques), TTS non-bloquant, game state = JSON blob (pas de tables SQLAlchemy relationnelles complexes).

## Mission

Effectue une analyse en deux volets — **technique** et **architecturale** — pour déterminer si l'application est bien conçue pour atteindre son but. Ne te contente pas de décrire : évalue, note les risques et propose des recommandations priorisées.

---

## 1. Analyse technique (qualité du code et de la stack)

Pour chaque point, indique si c'est un **point fort**, un **risque modéré** ou un **risque critique** :

- **Code quality** : lisibilité, respect des conventions (ruff, line-length 100, type hints), complexité cyclomatique des modules critiques (`engine/`, `game/`, `agents/`)
- **Tests** : couverture et pertinence des suites (`test_engine/`, `test_api/`, `test_agents/`, `test_game/`). Les tests `engine/` sont-ils purs ? Les tests `game/` utilisent-ils `pytest-asyncio` correctement ? Y a-t-il des mocks abusifs qui masqueraient des bugs en production ?
- **Sécurité** : validation des inputs (Pydantic), gestion des sessions WebSocket, injections possibles dans les prompts Jinja2 envoyés au LLM, CORS, exposition de données sensibles.
- **Performance & scalabilité** : gestion asynchrone des LLM (`asyncio.create_task()`), boucle de jeu en temps réel, SQLite comme choix de DB (suffisant pour du temps réel multijoueur ?), gestion de la mémoire contextuelle (`MAX_CONTEXT_MESSAGES=20`), latence WebSocket.
- **Dépendances & dette** : version de Python 3.9.6 (obsolescence, manque de fonctionnalités modernes), couplage avec Ollama/Voxtral (portabilité), Alembic bien maintenu ?
- **API design** : cohérence REST + WebSocket, sérialisation Pydantic, gestion d'erreurs, documentation OpenAPI auto-générée.

---

## 2. Analyse architecturale (adéquation au but métier)

Évalue si l'architecture supporte réellement une **session narrative temps réel avec IA** :

- **Séparation des responsabilités** :
  - Le moteur de règles (`engine/`) est-il réellement souverain et découplé du reste ?
  - Les agents IA (`agents/`) se contentent-ils de narration, ou font-ils de la logique métier par effet de bord ?
  - La couche `game/` orchestre-t-elle proprement sans mélanger état, réseau et logique LLM ?

- **Flux de données et state management** :
  - Le game state est-il bien un JSON blob unique, versionné et synchronisé entre backend et frontend via WebSocket ?
  - Le frontend (Pinia) gère-t-il correctement la réconciliation des états temps réel ?
  - Y a-t-il des risques de race conditions sur le tour de jeu / initiative ?

- **Intégration LLM** :
  - Les prompts Jinja2 sont-ils maintenables et testables ?
  - Le JSON structuré en sortie d'agent est-il robuste (gestion des hallucinations, retry, fallback) ?
  - La gestion du contexte (`MAX_CONTEXT_MESSAGES`) est-elle suffisante pour une session narrative cohérente sur 2+ heures ?
  - Le TTS asynchrone (`TTS_ASYNC=true`) est-il correctement isolé pour ne pas bloquer la boucle de jeu ?

- **Extensibilité** :
  - Peut-on facilement ajouter un nouveau modèle LLM (ex: remplacer Ollama par un API cloud) ?
  - Peut-on ajouter de nouvelles races/classes/sorts sans toucher au moteur ?
  - Le passage de l'event bus `asyncio.Queue` à Redis (multijoueur réseau) est-il envisageable sans réécriture ?

- **UX temps réel** :
  - La latence LLM (génération de réponse MJ) ne casse-t-elle pas le rythme du jeu ?
  - Le frontend gère-t-il les états intermédiaires (loading, streaming, audio) de manière fluide ?
  - Le système de machine à états (LOBBY → CHARACTER_CREATION → EXPLORATION → ENCOUNTER_START → COMBAT → ...) est-il robuste et sans trous ?

---

## 3. Alignement global : est-elle bien conçue pour le but ?

Pose-toi ces questions synthétiques :

- Cette architecture permet-elle de livrer une **expérience de JdR temps réel immersive** dans 3 mois, ou faut-il refactorer des fondations ?
- Les choix techniques (SQLite, Ollama local, WebSocket natif) sont-ils des **accélérateurs** pour un MVP ou des **verrous** pour la production ?
- Quels sont les **3 risques majeurs** qui pourraient faire échouer le projet à atteindre son but ?
- Quels sont les **3 points forts** à préserver absolument ?

---

## Format de sortie attendu

Réponds dans ce format :

1. **Executive Summary** (3-4 phrases) : l'application est-elle bien conçue pour son but ? Score global sur 10.
2. **Tableau de risques** : Risque | Gravité (Critique/Majeur/Mineur) | Justification | Recommandation.
3. **Analyse technique** (bullet points par catégorie).
4. **Analyse architecturale** (bullet points par catégorie).
5. **Verdict sur l'alignement but/architecture** (paragraph court).
6. **Roadmap d'amélioration priorisée** : 3 actions immédiates, 3 actions à moyen terme.

---

## Instructions additionnelles

- Sois précis : cite des fichiers ou modules si tu les identifies.
- Ne propose pas de réécriture complète à moins que ce soit justifié par un risque critique.
- Adapte tes recommandations à la contrainte Python 3.9.6 et au caractère local/self-hosted du projet.
