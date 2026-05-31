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

## Commandes De Test

Backend ciblé :

```bash
cd backend
.venv/bin/pytest tests/test_game/test_action_pipeline.py -q
.venv/bin/pytest tests/test_engine/test_ability_checks.py tests/test_engine/test_encounter_builder.py tests/test_game/test_stealth_resolution.py tests/test_game/test_action_pipeline.py -q
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
- Les erreurs techniques restent hors fiction : elles transitent par `EventType.ERROR` et le frontend les convertit en message système.
