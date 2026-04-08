# Frontend — CLAUDE.md

> Contexte specifique au dossier `frontend/`. Se combine avec le CLAUDE.md racine.

## Demarrage rapide

```bash
cd frontend
npm run dev          # http://localhost:5173
npm run type-check   # Verifier les types TypeScript
npm run build        # Build production (dist/)
```

## Structure src/

```
src/
├── views/
│   ├── HomeView.vue           # Page d'accueil
│   ├── LobbyView.vue          # Creation/chargement de session
│   ├── CharacterCreationView.vue  # Wizard multi-etapes
│   ├── CharacterSheetView.vue # Fiche personnage complete
│   ├── GameSessionView.vue    # Vue principale de jeu (layout 3 panneaux)
│   ├── CampaignView.vue       # Gestion des campagnes
│   └── AdminView.vue          # Parametres TTS + etat Ollama
├── components/
│   ├── narrative/             # NarrativeLog, MessageBubble, DiceRollResult
│   ├── combat/                # CombatTracker, InitiativeOrder, TacticalGrid
│   ├── character/             # CharacterSummary, SpellSlots, InventoryPanel
│   ├── ui/                    # ActionBar, SaveLoadPanel, AdventureStartModal
│   └── common/                # Composants generiques reutilisables
├── stores/                    # Pinia
│   ├── session.ts             # Session active, liste des sessions
│   ├── game.ts                # Game state, combat, narration log
│   ├── character.ts           # Personnages du joueur
│   ├── settings.ts            # Parametres TTS
│   └── campaign.ts            # Campagnes
├── composables/
│   ├── useWebSocket.ts        # Connexion WS, dispatch events -> stores
│   └── useAudio.ts            # Lecture audio WAV via Web Audio API
├── services/
│   └── api.ts                 # Client REST (fetch), toutes les routes backend
└── types/
    └── index.ts               # Interfaces TypeScript (GameState, Character, EventPayload...)
```

## Conventions Vue 3

- Toujours utiliser `<script setup lang="ts">` (Composition API)
- Props typees avec `defineProps<{...}>()`, emits avec `defineEmits<{...}>()`
- Pas de `Options API`, pas de `this`
- Nommage composants : PascalCase (`NarrativeLog.vue`)
- Nommage composables : camelCase prefixe `use` (`useWebSocket.ts`)

## Stores Pinia — responsabilites

| Store | Responsabilite |
|-------|---------------|
| `session` | Liste des sessions, session active (id, nom, phase) |
| `game` | Game state complet, log de narration, etat du combat, historique des actions |
| `character` | Personnages du joueur courant (stats, sorts, inventaire) |
| `settings` | Configuration TTS (backend, voix, enabled) |
| `campaign` | Campagnes et enchainements de sessions |

## Flux WebSocket

`useWebSocket.ts` est le point d'entree unique pour le temps reel :
1. Ouvre `ws://localhost:8000/ws/game/{session_id}?character_id={id}`
2. Recoit les evenements JSON du backend
3. Dispatche vers le store Pinia adequat selon le `type` de l'evenement
4. Les composants reactifs se mettent a jour automatiquement via les getters Pinia

```
Backend WS event -> useWebSocket -> store.game / store.character -> composant reactif
```

## Service API (api.ts)

Toutes les requetes HTTP passent par `src/services/api.ts`.
Ne jamais faire de `fetch` directement dans un composant ou un store.

## Theme TailwindCSS

Classes personnalisees definies dans `src/assets/main.css` via `@theme` :
- Couleurs : `parchment`, `ink`, `blood`, `gold`, `arcane`
- Utiliser les classes utilitaires standard Tailwind en priorite

## Anti-patterns a eviter

- **Ne pas faire de fetch HTTP dans un composant** — passer par `api.ts`
- **Ne pas ecrire dans le game state directement depuis un composant** — passer par les actions Pinia
- **Ne pas ouvrir plusieurs connexions WebSocket** — `useWebSocket` est un singleton via `provide/inject` ou le store session
- **Ne pas traduire les IDs internes** (`goblin`, `fire_bolt`, `short_rest`) — seul le texte visible est en francais
