# Flux narratif Table Vivante

Ce document décrit le flux narratif introduit pour rapprocher l'expérience d'une vraie table de jeu de rôle : les joueurs peuvent parler au MJ, au monde, au groupe ou à un compagnon IA précis ; les compagnons répondent quand ils sont concernés ; le MJ arbitre ensuite seulement si la scène touche le monde, les règles ou la suite.

## Objectifs

- Remplacer le flux exploration mécanique `action joueur -> réponse MJ -> réactions IA éventuelles` par un flux de scène.
- Permettre un vrai dialogue avec un compagnon IA via `@Nom`, sélection UI, ou ciblage WebSocket explicite.
- Garder le MJ comme arbitre final du monde et des règles, sans lui faire parler à la place des compagnons.
- Séparer la narration de combat dans un agent MJ spécialisé avec un contexte compact.
- Conserver les contrats existants : pas de migration DB, payloads WebSocket enrichis mais rétrocompatibles.

## Vue d'ensemble

### Exploration

```text
ActionBar / WebSocket action
  -> ws_game._dispatch_action()
  -> NarrativeFlowService.handle_exploration_action()
  -> detection audience
  -> réponses des compagnons IA ciblés
  -> ActionResolver si arbitrage MJ nécessaire
  -> EventBus -> frontend
```

`NarrativeFlowService` est la nouvelle porte d'entrée des actions libres hors combat. Il construit un `SceneExchange` avec :

- `scene_id` : identifiant de l'échange, fourni par le client ou généré serveur.
- `audience` : `gm`, `world`, `party`, `companion` ou `mixed`.
- `target_ids` : compagnons IA concernés.
- `companion_responses` : paroles visibles produites par les agents joueurs IA.
- `gm_arbitrated` : indique si le MJ a arbitré la scène.

### Combat

```text
Action combat
  -> ActionResolver
  -> ActionPipeline
  -> moteur de règles
  -> roll_result / dégâts / état
  -> CombatGMAgent
  -> narration courte du tour
```

Le combat reste structuré par initiative. La différence est que `ActionPipeline` route les appels de phase `COMBAT` vers `CombatGMAgent`, qui utilise un system prompt dédié et un état compact.

## Détection d'audience

Le backend accepte maintenant trois champs optionnels sur les messages WebSocket `action` :

```json
{
  "type": "action",
  "action_type": "free_text",
  "content": "@Thorin que penses-tu ?",
  "character_id": "human_1",
  "addressed_to": "thorin_1",
  "audience": "companion",
  "scene_id": "optional-scene-id"
}
```

Règles principales :

- `audience` explicite gagne si sa valeur est connue.
- `addressed_to` cible un compagnon par id ou par nom.
- `@Nom`, `Nom, ...` ou `Nom ...` ciblent un compagnon précis.
- Les marqueurs de groupe comme `compagnons`, `votre avis`, `que pensez`, `on fait quoi` ciblent le groupe IA.
- Les marqueurs d'action comme `j'examine`, `je fouille`, `j'ouvre`, `j'avance` indiquent une interaction avec le monde.
- Social + action monde donne `mixed`.

Exemples :

| Message | Audience | Effet |
|---|---|---|
| `@Thorin que penses-tu ?` | `companion` | Seul Thorin répond ; pas de conclusion MJ forcée. |
| `Compagnons, que fait-on ?` | `party` | Tous les compagnons IA concernés répondent ; le MJ conclut la scène sociale. |
| `J'examine la porte, vous me couvrez ?` | `mixed` | Les compagnons répondent, puis le MJ arbitre l'examen de la porte. |
| `J'écoute derrière la porte.` | `world` | Le MJ arbitre directement, avec jet si nécessaire. |
| `Que vois-je autour de moi ?` | `gm` ou `world` | Le MJ répond selon le contexte. |

## Réponses des compagnons IA

`PlayerAgent` expose maintenant `respond_to_player()`, qui utilise `player_dialogue.txt`.

Ce mode est distinct de `roleplay()` :

- `roleplay()` reste une réaction spontanée à la scène.
- `respond_to_player()` répond à une parole humaine adressée au compagnon ou au groupe.
- Le compagnon peut produire une réponse purement sociale (`talk`) ou proposer une action arbitrable (`examine`, `move`, `use_item`, `help`).

Si un compagnon produit une action arbitrable, `NarrativeFlowService` publie d'abord sa parole visible, puis appelle `ActionResolver.resolve()` avec :

- `actor_kind="companion"`
- `display_text` égal au texte visible
- `persist_actor_action=False` pour éviter de dupliquer le message déjà persisté
- `content` égal à une intention d'action propre, sans préfixe social comme `[Compagnon IA]`

La parole visible du compagnon reste son `roleplay_text` naturel. Par exemple, Shade peut dire qu'il passe devant et demande au groupe d'attendre ; l'intention envoyée au MJ reste séparée, comme `Shade examine le passage secret pour détecter les pièges.`.

Un dialogue direct avec un compagnon ne déclenche pas de narration de conclusion MJ. Le MJ intervient seulement si le compagnon choisit une action qui touche le monde ou si le message initial est `mixed`.

## Arbitrage MJ en exploration

`NarrativeFlowService` décide quand réutiliser le pipeline existant :

- `companion` : réponses IA seulement, sauf action arbitrable du compagnon.
- `party` : réponses IA puis `ActionResolver.social_conclude()`.
- `mixed` : réponses IA puis `ActionResolver.resolve()` pour l'action monde du joueur.
- `world` / `gm` : `ActionResolver.resolve()` directement.

Le mode LLM `sober` ne regroupe plus les réactions de compagnons en un batch social. Les réactions d'exploration passent par les agents joueurs individuels pour garder des intentions concrètes ; les actions de monde d'un compagnon (`examine`, `move`, `use_item`, `help`) repassent toujours par le MJ, même si le texte mentionne un compagnon.

Le pipeline mécanique existant reste la source d'autorité pour :

- jets de dés (`roll_request`)
- transitions vers combat (`encounter_setup` + `state_transition`)
- mises à jour canon (`journal_update`, `quest_add`, `chronicle_add`)
- narration d'issue après jet

## MJ Combat

`CombatGMAgent` hérite de `GMAgent`, mais remplace le system prompt par `gm_combat_system.txt` et compacte le `game_state`.

Le prompt de combat impose :

- narration courte, 2 à 3 phrases ;
- aucun résultat de dé inventé ;
- aucun `damage_apply` en combat ;
- actions autorisées limitées à `roll_request`, conditions et `combatant_status` ;
- traitement social possible en combat sans forcer une attaque immédiate.

`ActionResolver` accepte maintenant un `combat_gm_agent` optionnel. En usage normal, il crée un `CombatGMAgent`. En test, il garde une compatibilité avec les anciens mocks qui patchent `action_resolver._gm.think`.

## Événements WebSocket enrichis

Le payload `narration` accepte maintenant des champs optionnels :

```json
{
  "text": "Je te couvre, avance prudemment.",
  "speaker": "Thorin",
  "speaker_id": "thorin_1",
  "speaker_kind": "companion",
  "entry_kind": "dialogue",
  "scene_id": "..."
}
```

Valeurs prévues :

- `speaker_kind` : `gm`, `human`, `companion`, `npc`, `monster`
- `entry_kind` : `narration`, `dialogue`, `action`, `system`

Ces champs sont optionnels. Les anciens clients peuvent continuer à lire `text` et `speaker`.

## Frontend

`ActionBar.vue` ajoute une rangée `Parler à` hors combat :

- chaque compagnon IA a un bouton `@Nom` ;
- cliquer sur le bouton préfixe le texte et envoie `addressed_to` + `audience="companion"` ;
- le texte libre détecte aussi `@Nom`, `Nom, ...`, `compagnons`, `votre avis`, etc.

`NarrativeLog.vue` distingue maintenant :

- narration MJ ;
- dialogue compagnon / PNJ ;
- action joueur ;
- jets ;
- système.

`stores/game.ts` mappe `entry_kind="dialogue"` vers une entrée `dialogue`, sans casser les narrations existantes.

## Persistance

Aucune migration DB n'a été ajoutée.

Les informations de scène sont stockées dans `Message.metadata_` :

- `scene_id`
- `speaker_kind`
- `audience`
- `addressed_to`
- `is_ai_player`
- `character_id`
- `action_type`

Les messages compagnons sont persistés avec `role=player` et `message_type=dialogue`, ce qui permet aux agents suivants de les voir dans l'historique récent.

## Fichiers principaux

- `backend/app/services/narrative_flow_service.py` : orchestration exploration.
- `backend/app/agents/player_agent.py` : `respond_to_player()`.
- `backend/app/agents/prompts/player_dialogue.txt` : prompt de dialogue compagnon.
- `backend/app/agents/combat_gm_agent.py` : MJ combat spécialisé.
- `backend/app/agents/prompts/gm_combat_system.txt` : system prompt combat.
- `backend/app/game/action_pipeline.py` : routage MJ narratif / MJ combat.
- `backend/app/game/action_resolver.py` : injection `combat_gm_agent`, flag `persist_actor_action`.
- `backend/app/api/ws_game.py` : champs WebSocket `addressed_to`, `audience`, `scene_id` et branche exploration.
- `frontend/src/components/common/ActionBar.vue` : ciblage compagnon.
- `frontend/src/components/narrative/NarrativeLog.vue` : rendu dialogue.
- `frontend/src/stores/game.ts` et `frontend/src/types/index.ts` : types et mapping.

## Tests

Tests ajoutés :

- `backend/tests/test_game/test_narrative_flow_service.py`
  - parsing `@Nom`
  - détection groupe
  - détection mixte
  - dialogue direct sans MJ
  - dialogue de compagnon visible puis arbitrage MJ si le compagnon agit sur le monde
  - échange de groupe avec conclusion MJ
  - mixte avec réponses IA puis arbitrage MJ
- `backend/tests/test_agents/test_combat_gm_agent.py`
  - état combat compact dans le prompt
  - routage `ActionResolver` vers `CombatGMAgent`
- `backend/tests/test_game/test_action_pipeline.py`
  - une action de monde d'un compagnon appelle le MJ même en mode `sober`

Commandes validées lors de l'implémentation :

```bash
backend/.venv/bin/pytest backend/tests -q
cd frontend && npm run type-check
cd frontend && npm run build
```

Correctif post-smoke des transitions compagnon :

```bash
backend/.venv/bin/pytest backend/tests/test_game -q
backend/.venv/bin/ruff check backend/app/llm/budget.py backend/app/game/action_pipeline.py backend/app/services/narrative_flow_service.py backend/tests/test_game/test_narrative_flow_service.py backend/tests/test_game/test_action_pipeline.py
```

Le lint ciblé des nouveaux fichiers est propre :

```bash
backend/.venv/bin/ruff check \
  backend/app/agents/combat_gm_agent.py \
  backend/app/agents/player_agent.py \
  backend/app/game/action_pipeline.py \
  backend/app/services/narrative_flow_service.py \
  backend/tests/test_game/test_narrative_flow_service.py \
  backend/tests/test_agents/test_combat_gm_agent.py
```

Note : le `ruff check backend/app ...` global remonte encore des problèmes historiques non liés dans d'anciens fichiers.

## Points d'attention

- `run_exploration_reactions()` reste le déclenchement manuel de compatibilité pour les réactions de compagnons hors combat. L'ancien batch sobre de groupe a été retiré pour éviter les réponses trop génériques.
- Le `TurnManager` reste surtout utile au combat ; l'exploration fonctionne désormais comme scène libre.
- Le MJ ne doit pas inventer la parole des compagnons dans une scène sociale : les compagnons parlent via leurs propres agents.
- Les actions mécaniques restent résolues par le moteur, jamais par le LLM.
