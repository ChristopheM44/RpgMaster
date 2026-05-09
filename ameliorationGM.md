# Analyse du dialogue Thorvald–Azaka — Améliorations du MJ IA

## Contexte

Ce document analyse un dialogue extrait d'une session RpgMaster entre Thorvald (joueur humain) et le MJ IA. L'objectif est d'identifier les écarts entre cette session et une vraie partie de JDR sur table, et d'en déterminer les causes racines dans le code.

**Dialogue analysé** : 13 échanges, de la fontaine du marché jusqu'à la négociation avec Azaka Stormfang à l'auberge du Crocodile Endormi.

---

## Problèmes identifiés — par sévérité

### CRITIQUE (8 problèmes)

| # | Problème | Ce qui se passerait en vrai JDR | Cause racine |
|---|----------|-------------------------------|--------------|
| 1 | **Aucun jet de Persuasion** quand Thorvald demande à Azaka d'être leur guide (tour 11). L'issue est entièrement laissée au LLM. | MJ : "Fais-moi un jet de Persuasion, DC 15." Tension du d20, risque d'échec. | `narrative_flow_service.py:196` — `detect_audience()` n'a aucun marqueur pour les intentions sociales (persuasion, intimidation). Audience = "gm" par défaut, pas de déclenchement de `engine/ability_checks.skill_check()`. |
| 2 | **Le garde est muet** (tour 3). Thorvald lui parle, le MJ narre son regard silencieux au lieu de le faire répondre. | Même un garde laconique répondrait : "Elle n'est pas là", "Attendez ici". | Le texte est routé vers `gm_agent.narrate()` (template `gm_narrate.txt`) qui est conçu pour la narration descriptive, pas le dialogue PNJ. Le LLM a choisi de décrire le silence. |
| 3 | **`run_npc_dialogue()` n'est jamais appelée**. Le `GMAgent` a une méthode dédiée avec le template `gm_npc_dialogue.txt` pour incarner les PNJ — elle n'est utilisée nulle part dans le flux d'exploration. | Chaque PNJ aurait une voix distincte, le MJ l'incarnerait directement. | Ni `narrative_flow_service.py`, ni `action_pipeline.py`, ni `ws_game.py` n'appellent `run_npc_dialogue()`. Tout passe par `narrate()`. |
| 4 | **Narration coupée sans réponse** (tour 13). La réponse s'arrête au milieu d'une phrase, Azaka ne répond pas verbalement. | Azaka répondrait. La conversation ne s'arrêterait pas net. | Probablement `max_tokens=2048` insuffisant (`gm_agent.py:253`). Le JSON tronqué échoue au parsing, le fallback regex extrait un texte incomplet publié tel quel. |
| 5 | **Le système repose à 100% sur le LLM pour l'arbitrage social**. Aucune mécanique déterministe n'arbitre les interactions sociales, contrairement au combat. | Les règles D&D fournissent un cadre (jets, DC, avantage/désavantage). Le MJ arbitre dedans. | `engine/ability_checks.py` a `skill_check()` parfaitement opérationnel mais il n'est **jamais** utilisé pour les interactions sociales en exploration. Le pattern existe pour le combat, pas pour le social. |
| 6 | **Aucun suivi de relation PNJ**. Après 13 tours avec Azaka, le système n'a aucune trace structurelle de cette relation. | Le MJ noterait : "Azaka Stormfang — guide potentielle, attitude amicale, connaît Omu, a accepté d'aider contre compensation." | `campaign_dossier_service.py:34` — `npc_relationships: []` existe dans le schéma mais n'est **jamais peuplé** par le code. Aucun handler ne met à jour les relations. |
| 7 | **Pas de système de rounds sociaux** ni de conséquences cumulatives. Chaque tour est traité comme un `free_text` isolé, sans mémoire mécanique de la conversation. | Une interaction sociale complexe utiliserait l'attitude initiale du PNJ (hostile/indifférente/amicale), des jets successifs avec DC adaptés. | `game_loop.py` n'a pas de phase `SOCIAL_ENCOUNTER`. `state_data` n'a pas de champ `npc_attitudes`. L'`ActiveSession` a `last_gm_intent` mais c'est un tag, pas un état. |
| 8 | **Texte tronqué affiché sans nettoyage** (tour 13). | Le MJ reformulerait ou s'excuserait. | `gm_agent.py:264` — le fallback regex extrait `"narration"` du JSON cassé sans vérifier que la phrase est complète. Aucun post-traitement. |

### MAJEUR (10 problèmes)

| # | Problème | Cause racine |
|---|----------|-------------|
| 9 | **DC social hardcodé à 12** pour le fallback de combat social (`action_pipeline.py:673`). Intimider un chef de guerre ≠ un gobelin blessé. | Aucun calcul contextuel du DC. |
| 10 | **L'action `social_outcome` est reconnue mais ignorée** (`gm_response_executor.py:144`). Le handler est vide, aucun effet. | Pas de handler `_apply_social_outcome()`. |
| 11 | **Aucun jet d'Insight** quand Thorvald sonde les motivations d'Azaka (tour 12 : "que redoutez-vous ?"). | Même cause que #1 : pas de détection d'intention de skill check. |
| 12 | **Aucune garantie de cohérence de personnalité PNJ** entre les tours. Azaka est cohérente ici par chance, mais rien ne la force structurellement. | Pas de `npc_states` dans `state_data` avec personnalité, attitude, motivations. |
| 13 | **Pas de distinction visuelle entre dialogue PNJ et narration MJ**. Les répliques d'Azaka sont noyées dans le flux narratif. | Tout est publié en `EventType.NARRATION`. Le `EventType.DIALOGUE` existe mais n'est jamais utilisé. |
| 14 | **Les compagnons IA sont muets** pendant toute la conversation (tours 5-13). | `detect_audience()` classe l'adresse à Azaka comme "gm" → `should_ask_companions = False`. |
| 15 | **Le prompt `gm_narrate.txt` est un couteau-suisse** : il gère description de lieu, dialogue PNJ, résolution d'action, transition de scène. | Un seul template pour toutes les situations d'exploration. |
| 16 | **Pas de phase sociale dans le game loop**. Le social est un sous-cas de l'exploration. | `game_loop.py` : LOBBY, EXPLORATION, COMBAT, etc. — pas de `SOCIAL_ENCOUNTER`. |
| 17 | **Le joueur n'a pas d'agency sur les ellipses temporelles**. Tour 4 et 10 : le MJ skip directement à la scène suivante sans permettre d'interaction pendant le trajet. | Le LLM fait des ellipses agressives. Le `gm_system.txt` dit "ne déplace jamais la scène sans action explicite" mais le joueur a dit "nous vous suivons" → interprété comme consentement. |
| 18 | **JSON recovery fragile** en cas d'échec de parsing (`gm_agent.py:264`). Le regex ne capture qu'une string simple, pas d'Unicode complexe ni d'échappements. | Extraction regex basique, pas d'utilisation de `json_recovery.py`. |

### MINEUR (5 problèmes)

| # | Problème | Cause racine |
|---|----------|-------------|
| 19 | Le "mot de passe" ("La chasse au serpent") n'est pas mémorisé structurellement. | Le LLM le voit dans `recent_messages` mais aucune persistance garantie. |
| 20 | Manque d'ambiance sensorielle pendant le dialogue à l'auberge (tours 11-13). | Le LLM en mode `narrate()` se concentre sur la réponse, pas l'atmosphère. |
| 21 | Les `TURN_END` en exploration n'ont pas de sens (publiés mais inutiles hors combat). | Le `turn_manager` n'est pas actif en exploration. |
| 22 | Le fallback "Le Maître du Jeu réfléchit..." n'explique pas l'erreur technique. | `_FALLBACK_NARRATION` statique et vague. |
| 23 | Azaka mentionne une "compensation" que Thorvald ignore complètement — le MJ ne relance pas. | Le LLM ne poursuit pas les fils narratifs non résolus. |

---

## Résumé des causes racines principales

1. **`narrative_flow_service.py` — `detect_audience()`** : ne détecte pas les intentions sociales (persuasion, intimidation, insight). Tout est classé "gm" et traité en narration descriptive.

2. **`gm_agent.py`** : `run_npc_dialogue()` existe mais n'est jamais appelée. `max_tokens=2048` insuffisant. Le fallback JSON est fragile.

3. **`action_pipeline.py`** : le pattern "mécanique → LLM → narration" existe pour le combat mais pas pour le social. Le DC social est hardcodé à 12.

4. **`gm_response_executor.py`** : `social_outcome` reconnu mais ignoré. Aucun handler pour les relations PNJ.

5. **`state_data` (blob JSON)** : pas de `npc_states`, `npc_attitudes`, `active_conversation`. Les PNJ n'ont pas d'existence structurelle.

6. **`campaign_dossier_service.py`** : `npc_relationships` existe dans le schéma mais n'est jamais peuplé.

---

## Recommandations prioritaires

1. **Fix technique immédiat** : `max_tokens` → 4096, cleanup de texte tronqué
2. **Détection d'intention sociale + jets automatiques** : transformer l'expérience sociale
3. **Router vers `run_npc_dialogue()`** : rendre les PNJ vivants
4. **Tracking d'attitude PNJ dans `state_data`** : donner une mémoire
5. **Handler `social_outcome`** : conséquences durables des interactions

---

## Vérification

Pour vérifier l'impact de ces problèmes :
- Rejouer le même scénario et observer si le MJ demande des jets de Persuasion/Insight
- Vérifier que les PNJ adressés répondent verbalement (pas de regards silencieux)
- Vérifier que les réponses ne sont jamais tronquées en milieu de phrase
- Vérifier que les compagnons IA réagissent pendant les dialogues sociaux
- Vérifier que les relations PNJ persistent après fermeture/réouverture de session
