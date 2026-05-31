# Suivi Tabletop Fidelity

Objectif : rapprocher l'exploration de RPGMaster d'une vraie table de JDR, avec un état de scène fiable, des jets attribués au bon acteur, des compagnons IA plus utiles sans prendre le contrôle, et des erreurs techniques clairement séparées de la diégèse.

## État Global

- [x] Service backend `scene_update` ajouté dans `backend/app/game/scene_state_service.py`.
- [x] Exécution `scene_update` branchée dans `GMResponseExecutor`.
- [x] `scene_layout_changed` republie la scène complète fusionnée après patch.
- [x] Types frontend étendus pour `state`, `visibility`, `discovered`, `physical_state` et `facts`.
- [x] Inspecteur d'exploration capable d'afficher état, matière et faits découverts.
- [x] Prompts MJ durcis pour l'attribution des jets, la continuité de scène et les PNJ absents.
- [x] Prompts compagnons enrichis pour persona, classe, voix et limite d'agency.
- [x] Fallbacks LLM sortis des voix MJ/PNJ/compagnons et publiés comme messages système.
- [x] Tests unitaires backend et frontend ciblés ajoutés.
- [x] Squelette de replays E2E live LLM obligatoire ajouté.
- [x] Furtivité/Perception passive ajoutée avec jets PNJ cachés, action joueur `hide`, et POI cachés non rendus avant découverte.
- [x] Contexte privé MJ injecté dans les prompts sans fuite frontend/compagnons.
- [x] Prologue public et contrat de quête renforcés à l'ouverture.
- [x] Mémoire interne `gm_scene_state` et action MJ `scene_progress_update` ajoutées.
- [x] Sorts environnementaux des compagnons routés vers l'arbitrage MJ.
- [x] Texte visible des compagnons priorise `roleplay_text` en première personne.
- [ ] Replays live de fidélité narrative à exécuter avec le LLM cible.

## Lots

### Lot 1 - Source De Vérité De Scène

- [x] Fusion incrémentale de POI, éléments, positions, faits et états physiques.
- [x] Gestion de PNJ présent, absent, disparu, caché, enlevé ou mort via `npc_updates`.
- [x] Conservation de `current_scene` dans `state_data`, sans nouvelle table SQLAlchemy.
- [x] Publication WebSocket `scene_layout_changed` avec scène complète.

Critères d'acceptation :
- Un objet découvert reste visible dans la scène.
- Un PNJ disparu n'apparaît plus comme POI.
- Les positions du groupe changent sans recréer toute la carte.

### Lot 2 - Action, Jet, Conséquence

- [x] `roll_results` enrichi avec `actor_id`, `actor_name`, `actor_kind`, `target_id`, `scene_poi_id`, `success`, `dc`, `margin` et résumé existant.
- [x] Garde-fou post-LLM contre l'attribution d'une découverte au mauvais compagnon.
- [x] Prompts MJ : aucun `roll_request` redondant après jet résolu.
- [x] Fail-forward demandé explicitement sur échec.

Critères d'acceptation :
- Si Thorvald réussit un jet, la narration ne donne pas la découverte à Elara.
- Un échec d'investigation donne un coût, un indice ambigu ou une complication.

### Lot 3 - Compagnons IA

- [x] Prompts roleplay/dialogue enrichis par classe, persona, style de parole et lien au groupe.
- [x] Décisions coûteuses ou irréversibles formulées comme propositions.
- [x] Réactions limitées à une prise jouable pour éviter la saturation de scène.
- [x] Les pannes compagnon IA deviennent des événements système.

Critères d'acceptation :
- Un compagnon prudent propose d'observer avant d'agir.
- Aucun compagnon ne force un départ, sacrifice, rituel ou combat sans confirmation humaine.

### Lot 4 - Frontend

- [x] Types `SceneLayout`, `PointOfInterest`, `SceneElement` étendus.
- [x] Adaptation `useExplorationPois` des nouveaux champs backend.
- [x] `SelectionInspector` affiche état, matière et faits.
- [x] Erreurs WebSocket/LLM affichées comme entrées système.

Critères d'acceptation :
- Une dalle découverte affiche son état et ses faits dans l'inspecteur.
- Une erreur provider apparaît comme notification système, pas comme réplique.

### Lot 5 - Replays E2E Live LLM

- [x] Scénarios déclarés : `oasis_corrompue`, `disparition_guide`, `objet_cache`, `discussion_compagnons`, `echec_investigation`.
- [x] Tests marqués `live_llm` sans skip automatique.
- [x] Échec explicite si le LLM configuré ne répond pas.

Critères d'acceptation :
- Les replays échouent si Ollama/Ollama Cloud est indisponible.
- Les invariants d'état et d'événements sont vérifiés sur chaque scénario.

### Lot 6 - Furtivité, Interactions Et Carte

- [x] `stealth_event` ajouté au contrat MJ pour les actions furtives de PNJ/monstres.
- [x] Résolution moteur DEX(Stealth) vs Perception passive du groupe sans publication `ROLL_RESULT` visible.
- [x] Action joueur `hide` résolue par le pipeline et publiée comme jet visible.
- [x] Perception passive SRD ajoutée dans `engine/ability_checks.py`.
- [x] `ability_scores`, `senses` et `passive_perception` propagés sur les monstres de rencontre.
- [x] Bouton "Approcher" branché et actions POI desktop alignées avec les métadonnées mobile.
- [x] POI `visibility="hidden"` masqués jusqu'à `discovered=true`.
- [x] Sorties basées sur `SceneExit.active ?? true`, plus d'heuristique "dernière sortie active".
- [x] Prompts MJ mis à jour pour le placement spatial conditionnel et les événements furtifs.

Critères d'acceptation :
- Un PNJ peut tenter une fuite/enlèvement discret sans révéler de carte de jet aux joueurs.
- Un personnage qui choisit `hide` lance un jet visible et consomme son action en combat.
- Un POI caché n'apparaît pas sur la carte tant qu'il n'est pas découvert.
- Les actions POI desktop transportent `scene_poi_id`, `scene_interaction_id` et `scene_interaction_intent`.

### Lot 7 - Contexte Privé MJ Et Intrigue Exploitable

- [x] Helper backend non persistant `build_gm_prompt_context(session_id, db, state_data)`.
- [x] Bloc `DOSSIER MJ PRIVÉ` injecté dans les prompts MJ principaux.
- [x] Secrets globaux, secrets du chapitre actif, révélations, fronts, factions, PNJ importants, lieux, objets et canon joué accessibles au MJ.
- [x] `gm_scene_state` transmis au MJ via le dossier privé quand il existe.
- [x] `_gm_prompt_context` et `gm_scene_state` retirés du JSON `ÉTAT DU JEU` des prompts.
- [x] Vue compagnon/public inchangée : pas de secret dans `SESSION_STATE` ni `companion_visible_game_state()`.

Critères d'acceptation :
- Le contexte public compilé ne contient toujours pas `gm_dossier`, secrets ni sources privées.
- Le MJ reçoit les secrets du chapitre actif et les PNJ importants dans un bloc privé.
- Les compagnons IA ne reçoivent jamais `_gm_prompt_context`.

### Lot 8 - Prologue Et Contrat De Quête

- [x] Ouverture renforcée par un prologue public déterministe si le LLM omet le cadrage.
- [x] Prologue public construit depuis `player_contract.hook` et `known_objectives`.
- [x] Prompts MJ d'ouverture demandent : pourquoi le groupe est là, origine de mission, objectif public, enjeu immédiat et commanditaire/guide si établi.
- [x] Prompts de forge durcis pour produire un `hook` jouable et un objectif public concret.

Critères d'acceptation :
- Une ouverture de campagne explique pourquoi les PJ sont là avant de demander "Que faites-vous ?".
- Le prologue n'introduit pas de secret privé ni de PNJ physiquement absent.

### Lot 9 - Scènes À Objectifs Et Progression

- [x] Nouveau type d'action MJ `scene_progress_update`.
- [x] Stockage interne `active.state_data["gm_scene_state"]`.
- [x] Suivi privé par scène et obstacle : objectif, statut, progrès, approches, révélations, coûts d'échec, issue de réussite.
- [x] Aucune publication WebSocket publique pour `scene_progress_update`.
- [x] Prompts MJ demandent plusieurs prises jouables et une progression même sur échec.

Critères d'acceptation :
- Une oasis corrompue peut avancer par analyse, purification, contournement, interrogation, recherche de source ou danger déclenché.
- Un échec ajoute un coût ou une piste ambiguë au lieu de bloquer la scène.

### Lot 10 - Actions Compagnons Arbitrées

- [x] `cast_spell` autorisé comme action d'exploration arbitrable.
- [x] `params.spell_id` et `params.slot_level` relayés au `ActionResolver` quand disponibles.
- [x] Les sorts environnementaux des compagnons passent par le pipeline MJ au lieu d'être traités comme simple dialogue.
- [x] Prompts compagnons demandent de réserver `cast_spell` aux POI, dangers ou solutions environnementales établies.

Critères d'acceptation :
- Un compagnon qui lance un sort sur un obstacle appelle `ActionResolver.resolve(... action_type="cast_spell" ...)`.
- Le MJ arbitre l'effet fictionnel et mécanique au lieu de laisser le compagnon résoudre le monde.

### Lot 11 - Voix Compagnons En Première Personne

- [x] Texte visible compagnon basé en priorité sur `roleplay_text`.
- [x] `action_description` reste l'intention claire envoyée au MJ.
- [x] Prompts compagnons demandent une formulation visible en première personne.
- [x] Tests ajoutés pour vérifier texte visible et contenu envoyé au MJ.

Critères d'acceptation :
- Le joueur voit "Je tends la main..." plutôt que "Elara examine...".
- Le MJ reçoit encore une intention exploitable comme "Elara examine la rune".

### Lot 12 - Replays De Fidélité Narrative

- [x] Invariants de replays définis pour prologue, obstacle multi-issues, fail-forward, compagnon pris en compte et PNJ à secret.
- [ ] Exécution live LLM sur la chronique de test ou un scénario équivalent.
- [ ] Ajustements prompts après replays si le MJ révèle trop, bloque l'obstacle ou ignore les compagnons.

Critères d'acceptation :
- Ouverture avec prologue public présent.
- Obstacle corrompu avec au moins trois issues jouables.
- Échec qui avance la scène.
- Compagnon proposant puis exécutant une action prise en compte par le MJ.
- PNJ avec secret privé guidant sa réponse sans révélation gratuite.

## Commandes De Test

Backend ciblé :

```bash
cd backend
.venv/bin/pytest tests/test_game/test_action_pipeline.py -q
.venv/bin/pytest tests/test_engine/test_ability_checks.py tests/test_engine/test_encounter_builder.py tests/test_game/test_stealth_resolution.py tests/test_game/test_action_pipeline.py -q
.venv/bin/pytest tests/test_api/test_campaign_dossier.py tests/test_api/test_routes_game.py tests/test_agents/test_gm_agent.py tests/test_game/test_ai_player_exploration.py -q
```

Frontend ciblé :

```bash
cd frontend
npm run test -- useExplorationPois SelectionInspector game
npm run test -- SelectionInspector useExplorationPois ExplorationLayout
```

Replays live LLM obligatoires :

```bash
cd backend
.venv/bin/pytest tests/test_e2e_live/test_tabletop_replay_live.py -q -m live_llm
```

Qualité :

```bash
cd backend
.venv/bin/ruff check app tests/test_game/test_action_pipeline.py tests/test_e2e_live/test_tabletop_replay_live.py
cd ../frontend
npm run type-check
```

## Notes D'Implémentation

- `scene_update` accepte des alias pratiques (`upsert_pois`, `update_pois`, `discovered_ids`, `party_positions`, `npc_updates`) pour réduire la fragilité des sorties LLM.
- `scene_layout` reste le contrat de nouvelle scène ; `scene_update` est le contrat de changement dans la même scène.
- `scene_progress_update` est une mémoire privée MJ : aucune publication publique, aucune nouvelle table SQLAlchemy.
- Le dossier privé MJ est reconstruit à la demande et injecté seulement dans les prompts MJ.
- Les erreurs techniques restent hors fiction : elles transitent par `EventType.ERROR` et le frontend les convertit en message système.
