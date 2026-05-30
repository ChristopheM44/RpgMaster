# Audit d'architecture — RpgMaster

> **Date** : 2026-05-30 · **Périmètre** : backend FastAPI + frontend Vue 3 · **Méthode** : lecture du code réel (branche `main`, HEAD `3bed28b`).
> **Légende sévérité** : 🔴 **BLOQUANT** (corriger avant tout déploiement réseau / bug de correction actif) · 🟠 **IMPORTANT** (défaut réel, pas catastrophique en solo-local) · 🟡 **SOUHAITABLE** (qualité / maintenabilité).

---

## Note liminaire — le brief est partiellement périmé

Plusieurs prémisses de la commande d'audit ne correspondent plus au code. C'est un **bon signe** : un audit précédent a déjà eu lieu (commit `b5a3e11 "Début refacto suite audit"`) et la refonte est en cours. Corrections factuelles, vérifiées :

| Prémisse du brief | Réalité du code | Preuve |
|---|---|---|
| `ws_game.py` = 1934 lignes / 68 fonctions | **698 lignes**, éclaté en `api/ws_handlers/` | `wc -l app/api/ws_game.py` |
| EventBus **bloque** quand les queues sont pleines | `put_nowait` + erreur backpressure + close WS `1013` — **jamais bloquant** | [event_bus.py:276-292](backend/app/game/event_bus.py) |
| CORS `localhost:5173` seul rempart | Couche **token d'accès** HTTP + WS, CORS configurable par env | [main.py:69-95](backend/app/main.py), [security.py](backend/app/security.py) |
| Injection via `content` non traitée | `delimit_user_input` + consignes prompt anti-injection | [prompt_safety.py](backend/app/agents/prompt_safety.py), [gm_agent.py:303](backend/app/agents/gm_agent.py) |
| `MAX_CONTEXT_MESSAGES` = 20 | **50** par défaut | [config.py:50](backend/app/config.py) |

Le **vrai** centre de gravité du code (et donc des problèmes) s'est déplacé vers :
`campaign_dossier_service.py` (2217 l.), `routes_game.py` (1893 l.), `ws_handlers/combat.py` (1842 l.), `gm_response_executor.py` (1710 l.), `ai_player_manager.py` (1583 l.), `action_pipeline.py` (1560 l.).

Le reste de l'audit porte sur l'état **actuel** du code.

---

## 1. Architecture globale

### Forces (réelles, à préserver)

- **`engine/` souverain et pur** : aucune I/O, testable sans DB/réseau. Le principe « le LLM ne résout jamais les mécaniques » est tenu — `action_resolver` → `ActionMechanics` → `engine/`, narration séparée. C'est l'atout structurel majeur.
- **EventBus découplé et robuste** : une `asyncio.Queue` par abonné (pas de head-of-line blocking inter-clients), backpressure terminale propre, abstraction `EventBusProtocol` prête pour un swap Redis. [event_bus.py:135-156](backend/app/game/event_bus.py)
- **Refonte WS déjà engagée** : `ws_game.py` n'est plus qu'un dispatcher ; les handlers sont thématisés (`combat.py`, `equipment.py`, `rest.py`, `encounter_intro.py`…).
- **Frontend défensif** : déduplication d'événements par `event_id`, type-guards runtime par payload, reconnexion backoff+jitter, heartbeat ping/pong.

### Faiblesses

#### 1.1 🟠 La machine à états existe mais **n'est pas faisante autorité**
`game_loop.py` définit une table de transitions valides et un validateur propre (`_transition_active_phase` appelle `validate_transition`, [combat.py:545](backend/app/api/ws_handlers/combat.py)). **Mais** la phase est aussi assignée **en direct**, contournant la validation, à au moins 5 endroits :

- [combat.py:1261](backend/app/api/ws_handlers/combat.py) — `active.phase = SessionStatus.COMBAT`
- [combat.py:1381](backend/app/api/ws_handlers/combat.py) — reset combat → EXPLORATION
- [routes_game.py:1499](backend/app/api/routes_game.py) — start → EXPLORATION
- [encounter_intro.py:203](backend/app/api/ws_handlers/encounter_intro.py) — → ENCOUNTER_START
- [rest_service.py:171](backend/app/services/rest_service.py) — → EXPLORATION

Pire : `VALID_TRANSITIONS` **ne contient pas** `EXPLORATION → COMBAT` ([game_loop.py:24-29](backend/app/game/game_loop.py)) — la table impose `EXPLORATION → ENCOUNTER_START → COMBAT`. Le code saute pourtant directement en COMBAT depuis l'exploration (déclencheur agressif). La validation est contournée **précisément parce qu'elle rejetterait la transition réellement utilisée**.

> **Pas de deadlock possible** (le validateur est sans état). Le risque est l'**invariant fictif** : la table est aspirationnelle, pas appliquée. Quiconque s'y fiera (génération d'UI, futur multijoueur, tests) raisonnera sur un graphe que le runtime viole.

**Correctif** : choisir une discipline unique. Soit (a) router 100 % des changements de phase par `session_manager.transition_phase` / `_transition_active_phase` et **compléter la table** (ajouter `EXPLORATION → COMBAT`, `ENCOUNTER_START → COMBAT`…) ; soit (b) supprimer la table et assumer des phases libres. L'état mi-figue actuel est le pire des deux.

#### 1.2 🟡 Inversions de dépendance (couplage circulaire)
Les handlers réimportent l'endpoint qui les appelle : `from app.api import ws_game` **à l'intérieur** des fonctions de `combat.py` ([combat.py:1011, 1273, 1362](backend/app/api/ws_handlers/combat.py)). Les imports différés masquent un cycle de couches : `ws_game` (façade) ↔ `ws_handlers` (détail). Idem `ws_game.py:615-698` qui réexporte 30+ symboles « pour les tests legacy ». **Correctif** : extraire les helpers partagés (`_build_session_state_payload`, `action_resolver`, `event_bus`) dans un module neutre (`ws_handlers/shared.py`) dont dépendent les deux côtés, sans réimport circulaire.

#### 1.3 🟡 Monolithe modulaire : bon choix, mais limite atteinte sur 3 services
Le monolithe est justifié (solo, latence, simplicité). Le TTS sorti en sous-process est cohérent. Mais `campaign_dossier_service.py` (2217 l.) cumule forge + synthèse canon + upsert persona + contexte cartes : c'est un *god-service* qui mélange 4 responsabilités (cf. §4).

---

## 2. Cohérence du flux narratif

### Chemin d'une action joueur (tracé réel)
```
WS receive_json (ws_game.py:425)
  → PlayerActionMessage (Pydantic, extra="forbid")          ws_schemas.py
  → asyncio.create_task(_run_action_bg)                     ws_game.py:521   ⚠ §5.2
    → session_lock(session_id)                              ws_game.py:340
    → _dispatch_action                                      ws_game.py:134
      ├─ prime_combat_from_aggressive_action ?              combat_triggers.py:240
      ├─ hors combat → NarrativeFlowService.handle_exploration_action
      │     → detect_audience (gm/world/party/companion/mixed)
      │     → companions IA répondent → action_resolver.social_conclude
      │     → ou resolve() → ActionPipeline → engine + GMAgent → execute_gm_response
      └─ combat → action_resolver.resolve → ActionPipeline → end_turn / ai_turns
  → EventBus.publish_to_session → queue → _relay_events → websocket.send_json
```
Le découpage est sain et le `session_lock` sérialise correctement la mutation d'état.

### Points d'attention

#### 2.1 🟠 La double voie combat/hors-combat repose sur des heuristiques regex fragiles
`combat_triggers.py` infère monstres et nombres depuis le **texte FR libre** du joueur ([combat_triggers.py:130-173](backend/app/game/combat_triggers.py)) : table d'alias figée (14 monstres), comptage par fenêtre de 60 caractères, défaut « 3 si pluriel ». C'est explicitement un *filet de sécurité*, mais il est sur le **chemin chaud** : une narration GM mentionnant « les bandits » peut déclencher un combat non voulu, et un monstre hors-liste (« gobelours » est couvert, « basilic » non) ne déclenchera rien. **Correctif** : faire de l'`encounter_setup` structuré émis par le LLM la **source unique**, et reléguer le regex en secours *journalisé* avec compteur, pour mesurer combien de fois on s'appuie dessus (observabilité). Aujourd'hui on ne sait pas s'il se déclenche 1 % ou 40 % du temps.

#### 2.2 Pipeline d'intro de combat — cohérent
`encounter_setup` (LLM) → `pending_encounter` ([gm_response_executor.py:500](backend/app/game/gm_response_executor.py)) → `pause_at_encounter_start` joue l'intro et marque `intro_played` ([encounter_intro.py:178-203](backend/app/api/ws_handlers/encounter_intro.py)) → action suivante consomme `pending_phase_transition` → `handle_start_combat`. Le garde `intro_already_played` ([combat.py:1023](backend/app/api/ws_handlers/combat.py)) évite la double-intro. **RAS**, hormis l'assignation directe de phase (§1.1).

#### 2.3 🟠 Compagnons IA : double appel LLM par tour social, non plafonné en coût
En exploration sociale, chaque compagnon ciblé appelle le LLM ([narrative_flow_service.py:439-451](backend/app/services/narrative_flow_service.py)), **puis** `social_conclude` rappelle le MJ ([action_resolver.py:472-517](backend/app/game/action_resolver.py)), **puis** une passe de réaction (`_react_after_world_action`, cap 1). Sur Ollama local mono-requête (`ollama_max_concurrent_requests=1`), une simple phrase « Qu'en pensez-vous ? » peut enchaîner 3-4 appels LLM **séquentiels** sous le `session_lock` → latence ressentie de plusieurs dizaines de secondes, pings gelés côté serveur de jeu (mitigé par le fait que le dispatch est en tâche de fond). Le mode `sober` ([budget.py:55](backend/app/llm/budget.py)) atténue en combat mais **pas** ce chemin social. **Correctif** : plafond global d'appels LLM par tour joueur + court-circuit `sober` sur `social_conclude`.

#### 2.4 🟠 `resolve_npc_dialogue` : dialogue PNJ à deux étapes, copie d'état superficielle
[action_resolver.py:228](backend/app/game/action_resolver.py) `game_state = dict(active.state_data)` est une **copie superficielle** : les sous-dicts (`npc_states`, `characters`) restent partagés. Si `execute_gm_response` mute un sous-dict pendant que la 2ᵉ étape lit `game_state_2`, l'aliasing est silencieux. Aujourd'hui sans bug observé (lecture seule en pratique), mais c'est un piège latent. **Correctif** : `copy.deepcopy` du contexte passé au LLM, ou figer un snapshot immutable.

#### 2.5 Conditions de course WS ↔ game loop
Le `session_lock` ([session_manager.py:204](backend/app/game/session_manager.py)) sérialise correctement les mutations. La vraie fragilité de course est le **lock-pop à la fermeture** (§5.3), pas le flux narratif lui-même.

---

## 3. Sécurité

> Posture globale **nettement meilleure** que ne le suppose le brief. Les vrais trous sont le modèle d'autorisation et le défaut « fail-open ».

#### 3.1 🔴 Authentification *fail-open* par défaut + **aucune autorisation**
- `app_access_token` vide par défaut ⇒ `is_valid_access_token` **retourne `True` pour tout le monde** ([security.py:41-45](backend/app/security.py)). Le garde-fou `validate_access_token_configuration` n'échoue que si `app_debug=False` ([security.py:33-38](backend/app/security.py)) — or `app_debug=True` par défaut ([config.py:38](backend/app/config.py)). **En configuration par défaut, le WS et toute l'API sont ouverts.**
- **Aucun modèle d'utilisateur/propriété** : `grep` sur `owner|user_id|current_user|class User` → **0 résultat**. Le token est un secret unique partagé (tout ou rien). N'importe quel client authentifié peut se connecter à **n'importe quel** `session_id` et jouer **n'importe quel** `character_id` de la session ([ws_game.py:451-468](backend/app/api/ws_game.py) ne vérifie que l'appartenance personnage↔session, pas joueur↔personnage).

C'est **acceptable pour un solo-local** (intention du projet), **bloquant** dès toute exposition réseau ou multi-joueur. **Correctif minimal** : (a) inverser le défaut — exiger un token sauf `app_debug` explicite, ou avertir au boot ; (b) avant tout multi-joueur, introduire une notion de session/personnage possédé (même un simple secret par personnage signé).

#### 3.2 ✅ Injection prompt — correctement mitigée (défense en profondeur)
`delimit_user_input` encapsule **tout** texte joueur passé au LLM ([gm_agent.py:303, 323, 363, 436, 483, 528](backend/app/agents/gm_agent.py)) et **chaque template** rappelle au modèle de ne pas interpréter le contenu délimité comme instruction ([gm_narrate.txt:55](backend/app/agents/prompts/gm_narrate.txt), `gm_combat.txt`, `gm_npc_dialogue.txt`…). C'est l'état de l'art. *Réserve* : aucune mitigation n'est infaillible contre l'injection LLM ; la narration ré-affichée reste du texte que le front rend en données (Vue échappe par défaut). **RAS, à maintenir.**

#### 3.3 ✅ SSRF — protection complète
`security_url.py` rejette schémas non-http(s), credentials d'URL, et **toute IP non publique après résolution DNS** (privée/loopback/link-local/multicast/réservée), plus `localhost`/`.local` ([security_url.py:13-93](backend/app/security_url.py)). Couvre la génération d'images / fetch de sources. **Exemplaire.**

#### 3.4 ✅ Clés API — stockage et exposition corrects
Persistées dans `.runtime/llm_runtime.json` avec écriture **atomique** (`NamedTemporaryFile` + `os.replace`) et permissions `0600`/`0700` ([config.py `_save_runtime_llm`](backend/app/config.py)). Les endpoints admin renvoient `api_key_set: bool`, **jamais la clé** ([routes_admin.py:283-309](backend/app/api/routes_admin.py)). Bien.

#### 3.5 ✅ Pas de fuite GM→joueur dans `session_state` (vérifié)
Le payload est construit par **allowlist explicite** de champs ([ws_payloads.py:57-72](backend/app/api/ws_payloads.py)) : phase, journal, quêtes, chronique, scène, combat. Il **ne sérialise pas** `npc_states`, `played_canon`, ni les `motivations.hidden`/`secrets`/`quest_hooks` des personas (qui vivent dans `Campaign.dossier`). Côté compagnons IA, `companion_visibility.py` filtre en plus `revealed_secrets`. **Pas de fuite.**

#### 3.6 ✅ Validation d'entrée WS — stricte
`extra="forbid"`, IDs sur regex `^[A-Za-z0-9_.:-]{1,128}$`, `content` borné (`max_player_action_chars=4000`), whitelists `audience`/`ability`/`mode`, bornes `slot_level 0-9`, `hit_dice_spend ≤ 12 clés / 0-20` ([ws_schemas.py](backend/app/api/ws_schemas.py)). Très bon.

#### 3.7 🟡 Pas d'auth sur le WebSocket au niveau transport hors token de requête
Le token WS passe en **query string** (`?access_token=`, [useWebSocket.ts:425](frontend/src/composables/useWebSocket.ts)) — il apparaît dans les logs serveur/proxy. Sur du local c'est mineur ; en prod, préférer un sous-protocole WS ou un cookie httpOnly. 🟡

#### 3.8 🟡 Pas de rate-limit sur le WS ni sur `/start`
`FixedWindowRateLimiter` n'est branché que sur `llm_ping` ([routes_admin.py:380](backend/app/api/routes_admin.py)). Voir §5.2 (conséquence DoS).

---

## 4. Qualité du code et maintenabilité

#### 4.1 🟠 *God-files* — le problème a été déplacé, pas résorbé
La refonte a vidé `ws_game.py` mais reconstitué des fichiers massifs ailleurs :

| Fichier | Lignes | Symptôme |
|---|---|---|
| `services/campaign_dossier_service.py` | 2217 | 4 responsabilités (forge / synthèse / persona / cartes) |
| `api/routes_game.py` | 1893 | ~40 helpers `_opening_*`/`_infer_opening_*` de construction de scène d'ouverture **dans le module de routes** |
| `api/ws_handlers/combat.py` | 1842 | 40 fonctions ; `handle_start_combat` ≈ **320 lignes** ([combat.py:995-1313](backend/app/api/ws_handlers/combat.py)) |
| `game/gm_response_executor.py` | 1710 | exécution monolithique des actions GM |
| `game/ai_player_manager.py` | 1583 | combat + exploration + ciblage + sorts |

**Plan de refacto concret** :
- `routes_game.py` → extraire toute la logique d'ouverture (`_opening_*`, `_infer_*`, `_build_opening_brief`) dans `services/opening_scene_service.py`. Le routeur ne doit garder que les 6 endpoints HTTP. Gain : ~1000 lignes hors du module de routes.
- `combat.py` → scinder `handle_start_combat` en `_spawn_encounter` / `_build_combatants` / `_roll_initiative_and_announce`. Sortir la construction d'aftermath (`_build_fallback_aftermath_scene`, `_apply_*`) dans `combat_aftermath.py`.
- `campaign_dossier_service.py` → 4 modules : `forge`, `canon_synthesis`, `persona_store`, `map_context`.

#### 4.2 🟡 Duplication combat manuel / IA — **modérée**, pas critique
Le brief soupçonne une duplication forte ; en réalité les deux voies convergent sur `action_resolver.resolve()` (l'humain via `_dispatch_action`, l'IA via `handle_ai_combat_turns` → même resolver). La duplication réelle est plus fine : `ai_player_manager` possède son propre `_normalize_combat_action` / `_resolve_movement_intent` / `_build_deterministic_combat_action` ([ai_player_manager.py:1123-1355](backend/app/game/ai_player_manager.py)) qui reconstruisent une intention que le chemin humain reçoit déjà structurée. **Correctif** : factoriser un `CombatActionNormalizer` partagé. 🟡

#### 4.3 🟠 Gestion d'erreur — `except Exception` trop larges et **silencieux**
Motif récurrent `try/except Exception: pass` ou `logger.debug` qui **avale** les pannes : récupération de contexte cartes ([action_resolver.py:238, 339](backend/app/game/action_resolver.py)), `repair_visual_coherence` ([ws_payloads.py:33, 93](backend/app/api/ws_payloads.py)), lookup persona ([action_resolver.py:459](backend/app/game/action_resolver.py)). Conséquence : une carte ou une persona peut disparaître sans trace exploitable. **Correctif** : remonter au moins en `WARNING` avec contexte, et distinguer « optionnel dégradable » (cartes) de « anormal » (LLM JSON invalide).

#### 4.4 🟡 Typage `Any` omniprésent sur le hot-path
`ActiveSession.state_data: dict[str, Any]` ([session_manager.py:65](backend/app/game/session_manager.py)), `ai_players: dict[str, Any]`, signatures `active: Any` dans tout `combat.py`. Il **existe** un schéma typé (`state_schema.py`) mais tous ses modèles sont `extra="allow"` ([state_schema.py:14, 29, 45, 53](backend/app/game/state_schema.py)) : il valide une poignée de champs (hp≥0, level 1-20, phase) et laisse passer le reste **non typé**. Le typage est donc **advisory**, en tension avec le principe affiché « sorties JSON validées par Pydantic ». **Correctif** : typer `ActiveSession` (au moins `state_data: GameStateData`) et resserrer progressivement les `extra="allow"` sur les sous-structures stables (combatants, turn_manager).

#### 4.5 Testabilité — bonne
69 fichiers de test, suites séparées engine/api/agents/game/voice. `engine/` pur testable sans I/O. `ActionResolver` injecte un `gm_agent` mockable. Bon découplage global. Le frein restant est le couplage circulaire `ws_game` ↔ `ws_handlers` qui force les réexports « legacy tests » ([ws_game.py:615-698](backend/app/api/ws_game.py)).

---

## 5. Performance et scalabilité

#### 5.1 ✅ EventBus plein → **ne bloque pas**
`put_nowait` ; si `QueueFull` : on **vide le backlog** et on pousse une erreur backpressure terminale, le relais ferme le WS en `1013` ([event_bus.py:276-327](backend/app/game/event_bus.py), [ws_game.py:111-116](backend/app/api/ws_game.py)). Le client reconnecte et resync via `session_state`. Design correct. La prémisse « risque de blocage » est **infondée**.

#### 5.2 🔴 Tâches de fond **non bornées** sur le chemin d'action
Chaque message `action` fait `asyncio.create_task(_run_action_bg(...))` ([ws_game.py:521](backend/app/api/ws_game.py)) — **brut** (pas `create_logged_task`), **non stocké**, **non annulé à la déconnexion**, **sans rate-limit ni sémaphore**. Conséquences :
1. **Épuisement ressources** : un client (ou un bug front) qui pousse N actions crée N tâches qui s'empilent sur le `session_lock`, chacune retenant action+factory et déclenchant un appel LLM. Mémoire O(N), file LLM saturée. Aucun garde-fou serveur (le `setProcessing` front est de la courtoisie, pas une contrainte).
2. **Tâche orpheline** : `create_task` brut — CPython ne garde qu'une référence faible ; sans stockage la tâche peut être GC avant la fin. À déconnexion, la tâche continue, publie dans un bus **sans abonné** → events perdus.

**Correctif (bloquant avant multi-client)** : (a) `create_logged_task` + stocker les tâches par session pour les annuler dans le `finally` ; (b) sémaphore/`Queue` bornée par session (ex. 1 action en vol + 1 en attente, le reste rejeté avec erreur explicite) ; (c) rate-limit par IP/session sur le type `action`.

#### 5.3 🟠 `close_session` *pop* le lock pendant qu'un appelant le détient
Mécanisme exact : à la dernière déconnexion, le `finally` du WS prend `session_lock` puis appelle `close_session` qui fait `self._locks.pop(session_id, None)` ([session_manager.py:185](backend/app/game/session_manager.py)) **tout en détenant ce lock**. Une action concurrente entrée dans la fenêtre obtient, via `lock_for_session` `setdefault` ([session_manager.py:200-202](backend/app/game/session_manager.py)), un **nouvel objet Lock** → exclusion mutuelle rompue de part et d'autre de la fermeture. **Rayon d'explosion faible** : la tâche en retard tombe sur `get_session() is None` et ne fait rien. **Réel, latent, basse sévérité.** **Correctif** : ne pas pop le lock dans `close_session` ; le purger paresseusement hors de toute section critique, ou garder le lock vivant tant que `connection_count > 0`.

#### 5.4 🟠 SQLite mal réglé pour de l'async temps réel
[database.py:8-9](backend/app/db/database.py) : `create_async_engine(url, echo=settings.app_debug)` — **aucun PRAGMA** (`grep busy_timeout|journal_mode|WAL|foreign_keys` → 0). Donc :
- **`echo=app_debug` (True par défaut)** : **chaque requête SQL est loggée** — surcoût I/O notable en jeu réel. 🟠 à passer à `False`.
- **Pas de `journal_mode=WAL`** : lecteurs et écrivain se bloquent mutuellement (mode `DELETE`).
- **Pas de `busy_timeout`** : sous contention, `OperationalError: database is locked` **immédiat** au lieu d'attendre. Plusieurs `ActiveSession` qui committent (chacun réécrit son blob) peuvent collisionner.
- **Pas de `PRAGMA foreign_keys=ON`** : les `ondelete="CASCADE"` ne sont **pas** appliqués par SQLite (seul l'ORM cascade via `delete-orphan`). Un delete hors ORM laisserait des orphelins.

**Correctif** : un `event.listens_for(engine.sync_engine, "connect")` posant `WAL`, `busy_timeout=5000`, `foreign_keys=ON` ; `echo=False`. Sans cela, SQLite reste un **plafond dur** pour tout passage multi-session.

#### 5.5 🟡 Game state = blob JSON réécrit **intégralement** à chaque sauvegarde
`save_state` sérialise tout `state_data` (personnages, npc_states, cartes, journal, canon, turn_manager) dans une colonne `JSON` à **chaque** action ([session_manager.py:219-256](backend/app/game/session_manager.py), [game_state.py:41](backend/app/models/game_state.py)). En session longue, le blob grossit (cartes + canon) et chaque tour le réécrit en entier. Acceptable en solo, coûteux ensuite (cf. §7). 🟡

#### 5.6 🟡 Fuite mémoire mineure dans EventBus
`_dropped_events[session_id]` et `_max_queue_size[session_id]` sont écrits à **chaque** publish ([event_bus.py:279, 284](backend/app/game/event_bus.py)) mais **jamais nettoyés** : `unsubscribe` ne purge que `_subscribers` ([event_bus.py:212-224](backend/app/game/event_bus.py)). Un `int` par `session_id` s'accumule pour la vie du process. Trivial par session, mais c'est exactement le motif de croissance non bornée à corriger. **Correctif** : purger ces deux dicts dans `unsubscribe` quand la session n'a plus d'abonné.

#### 5.7 ✅ TTS fire-and-forget
`tts_router` publie l'audio via un publisher injecté ([main.py:36-44](backend/app/main.py)) ; texte immédiat, audio asynchrone. Conforme au principe « TTS non bloquant ».

---

## 6. Frontend — intégration et robustesse

#### 6.1 ✅ Protocole bien défini et défensif
`WS_EVENT_TYPES_LIST` filtre les events connus ; **chaque** payload a un type-guard runtime ([useWebSocket.ts:438-659](frontend/src/composables/useWebSocket.ts)) — le front ne fait jamais confiance aveugle au backend. La recette « 4 couches » du CLAUDE.md (EventType → types → guard → store) est respectée.

#### 6.2 ✅ Reconnexion et état partagé
Backoff exponentiel + jitter, plafond 10 essais, heartbeat ping/pong avec timeout de pong ([useWebSocket.ts:40-43, 351-360, 429-436](frontend/src/composables/useWebSocket.ts)). **Déduplication par `event_id`** (`consumeEventId`, [useWebSocket.ts:143](frontend/src/composables/useWebSocket.ts)) → idempotence sur replay/reconnexion. `character_id` mémorisé en `sessionStorage` pour re-`join` automatique. Très solide.

#### 6.3 🟡 Couverture des EventType — quasi complète, un mort silencieux
`damage_applied` est reçu mais **traité comme no-op** ([useWebSocket.ts:337-338](frontend/src/composables/useWebSocket.ts)) — les dégâts ne transitent que par `hp_changed`. Cohérent mais à documenter (sinon piège pour un futur dev qui émettra `damage_applied` en attendant qu'il fasse quelque chose).

#### 6.4 🟡 État « processing » sans terminaison garantie
`setProcessing(true)` à l'envoi ([useWebSocket.ts:370](frontend/src/composables/useWebSocket.ts)), remis à `false` par certains events (`phase_change`, `turn_end`, `combatant_moved`, `social_outcome`, `error`…) mais **pas tous**. Si le backend échoue sans émettre d'event terminal, l'UI peut rester « en attente » jusqu'au timeout de pong. **Correctif** : un timeout de sécurité côté store qui lève `processing` après N s.

#### 6.5 🟡 URL backend codée en dur
`WS_BASE = 'ws://localhost:8000'` ([useWebSocket.ts:38](frontend/src/composables/useWebSocket.ts)) — pas d'env, pas de `wss://`. Bloquant pour tout déploiement non-local. 🟡

---

## 7. Base de données et persistance

#### 7.1 🟠 SQLite pour du temps réel — défendable en solo, plafond dur ensuite
Pour **un** joueur local : justifié (zéro ops, fichier portable). Mais combiné à §5.4 (pas de WAL/busy_timeout) et §5.5 (réécriture blob), SQLite devient le premier goulot dès qu'on vise le multi-session concurrent. La roadmap Redis (event bus) ne résout **pas** la persistance — il faudra Postgres pour le multi-écrivain. **Décision à acter explicitement** : SQLite = mode solo assumé ; tout multi-joueur ⇒ Postgres + revue des accès concurrents.

#### 7.2 Schéma — propre, cohérent
`Session 1—1 GameState`, `1—N Character/Message/SaveSlot`, cascades ORM, `Message.session_id` indexé, timestamps microseconde explicites pour préserver l'ordre ([message.py:57-66](backend/app/models/message.py)). `expire_on_commit=False` (correct en async). Bon.

#### 7.3 🟡 Cohérence in-memory ↔ colonnes
La doc d'`ActiveSession` ([session_manager.py:50-54](backend/app/game/session_manager.py)) reconnaît que `state_data` est l'autorité en session et que les colonnes `Character` typées sont des snapshots synchronisés « aux frontières de service ». C'est un **double stockage** (HP dans `state_data["characters"]` *et* dans `Character.hp_current`) réconcilié par `sync_ai_control_from_db` / `character_snapshot`. Source de divergence possible si une écriture oublie une frontière. **Correctif** : documenter la direction d'autorité par champ, ou centraliser la synchro dans un seul `CharacterSyncService`. 🟡

#### 7.4 🟡 Enum `LOBBY` vestigial
`SessionStatus.LOBBY` subsiste ([session.py:14](backend/app/models/session.py)) et reste le défaut de `Session.status`, alors que le lobby a été retiré (`git log`: `a65b826 "Suppression Lobby, devient chronique"`). `CHARACTER_CREATION → LOBBY` pollue encore `VALID_TRANSITIONS`. Nettoyer.

---

## 8. Synthèse

### Top 5 des risques les plus critiques

| # | Risque | Sévérité | Réf. |
|---|---|---|---|
| 1 | **Auth fail-open par défaut + zéro autorisation/propriété** : tout client atteint n'importe quelle session/personnage ; ouvert si `app_debug=True` (défaut) | 🔴 | §3.1 |
| 2 | **Tâches de fond non bornées** sur le chemin d'action (pas de rate-limit/sémaphore, non annulées, `create_task` brut) → épuisement ressources | 🔴 | §5.2 |
| 3 | **SQLite non réglé** (pas de WAL/busy_timeout/FK, `echo=True`) → `database is locked` et surcoût dès la moindre concurrence | 🟠→🔴 si multi | §5.4 |
| 4 | **Machine à états non appliquée** (assignations directes contournant `validate_transition` ; `EXPLORATION→COMBAT` absent de la table mais utilisé) | 🟠 | §1.1 |
| 5 | **Cascade d'appels LLM séquentiels** par tour social sous `session_lock` (Ollama mono-requête) → latence multi-dizaines de secondes | 🟠 | §2.3 |

### Top 5 des décisions architecturales à reconsidérer

1. **FSM mi-appliquée** : l'imposer partout (un seul point de passage + compléter la table) **ou** l'assumer libre. État actuel = pire des deux. (§1.1)
2. **Game state = blob JSON monolithique** réécrit à chaque tour : extraire au moins les structures volumineuses et stables (cartes, canon) hors du blob d'action, ou passer à des mises à jour partielles. (§5.5, §7.1)
3. **God-files reconstitués** : la refonte a déplacé la masse (combat 1842, routes_game 1893, dossier_service 2217) — finir le découpage par responsabilité. (§4.1)
4. **Typage advisory** (`Any` + `extra="allow"` partout) en contradiction avec le principe « Pydantic strict » : typer `ActiveSession.state_data`. (§4.4)
5. **EventBus sans persistance/replay** : les events mécaniques transitoires sont perdus entre reconnexions (mitigé par resync `session_state`, mais incohérent) — décider si le bus doit être durable avant le swap Redis. (§5.1, §5.6)

### Roadmap de refactoring priorisée (3 mois)

**Mois 1 — Sécuriser & stabiliser le runtime (bloquants)**
- Inverser le défaut d'auth ou avertir au boot ; documenter « solo-local = pas d'autorisation ». (§3.1)
- Borner les tâches d'action : `create_logged_task` + suivi/annulation + sémaphore par session + rate-limit WS. (§5.2)
- Régler SQLite : WAL + `busy_timeout` + `foreign_keys=ON`, `echo=False`. (§5.4)
- Corriger le lock-pop de `close_session` + purge des dicts EventBus. (§5.3, §5.6)

**Mois 2 — Discipline d'état & flux**
- Trancher et appliquer la FSM (point de passage unique, table complétée, retrait `LOBBY`). (§1.1, §7.4)
- Plafond global d'appels LLM par tour + `sober` sur `social_conclude`. (§2.3)
- Faire de l'`encounter_setup` structuré la source unique de combat ; reléguer le regex en secours journalisé/compté. (§2.1)
- Typer `ActiveSession` (`state_data: GameStateData`), durcir les sous-schémas stables. (§4.4)

**Mois 3 — Découplage & dette de structure**
- Extraire la logique d'ouverture hors de `routes_game.py` (`opening_scene_service`). (§4.1)
- Scinder `combat.py` (`handle_start_combat`, aftermath) et `campaign_dossier_service.py` (4 modules). (§4.1)
- Briser le cycle `ws_game ↔ ws_handlers` (`ws_handlers/shared.py`), supprimer les réexports legacy. (§1.2)
- Préparer la voie multi-joueur : abstraction de persistance (chemin Postgres) + décision sur la durabilité du bus. (§7.1)

---

### Verdict

Code **mature et bien intentionné**, au-dessus de la moyenne pour un projet de cette ambition : moteur de règles pur, EventBus propre, sécurité d'entrée sérieuse (Pydantic strict, SSRF, anti-injection, secrets chiffrés en perms), frontend défensif. La dette n'est pas dans l'ignorance des bonnes pratiques — elle est dans des **invariants à moitié appliqués** (FSM, typage), des **garde-fous runtime manquants** (bornage des tâches, réglage SQLite) et un **découpage inachevé** (god-files déplacés). Les deux risques **bloquants** (auth par défaut, tâches non bornées) sont corrigeables en quelques jours ; le reste est de l'hygiène structurelle à étaler. Aucun défaut de conception **fondamental** n'impose une réécriture.
