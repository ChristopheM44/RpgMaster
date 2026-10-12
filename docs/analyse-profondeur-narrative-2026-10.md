# Analyse de la profondeur narrative de RPGMaster

Date : 11 octobre 2026. Code examiné : commit `d989563`, avec lecture du code présent dans le workspace. Analyse et propositions uniquement ; aucune modification fonctionnelle réalisée dans le cadre de cet audit.

## Diagnostic

RPGMaster possède déjà plusieurs ingrédients d'une bonne campagne : un dossier privé, des secrets, des factions, des fronts, des personas et un canon joué. Le problème principal est leur articulation. Le système favorise les éléments faciles à matérialiser — lieu, obstacle, jet, indice, combat, récompense — davantage que l'évolution des intentions, des relations et des conséquences.

Cela explique plausiblement le ressenti « porte-monstre-trésor », mais une lecture de code ne mesure pas à elle seule la qualité des récits produits. Les constats ci-dessous distinguent les comportements vérifiés des hypothèses sur leur effet narratif.

La configuration locale lue dans un processus Python neuf indique `ollama`, `gemma4:31b` pour le MJ et les compagnons, et une limite d'historique de 50 messages. Ce n'est pas une mesure de la configuration d'un serveur déjà démarré. Aucun appel à un LLM ni benchmark de modèles n'a été effectué.

## Ce qui mérite d'être conservé

- Le moteur D&D reste souverain pour les jets et les effets mécaniques.
- Le dossier privé arrive réellement jusqu'au MJ : arc global, chapitre privé, PNJ, factions, fronts, complications et canon sont injectés par `build_gm_prompt_context`.
- Les prompts demandent déjà des situations ouvertes, des intérêts divergents, un pilier non-combat et des choix moraux.
- Les personas contiennent motivations, limites de savoir et relations ; il faut faire vivre ces données plutôt que remplacer ce système.
- La progression de scène, les révélations enregistrées, les horloges et les réactions des compagnons existent déjà.
- La priorité « joué > révélé > prévu » constitue une bonne règle de continuité.

Source principale : [construction du contexte privé](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:886).

## Constats dans le code

### 1. La forge définit trop tard le socle privé de l'histoire

Le job procède ainsi : notes de sources → contrat et plan publics → génération de chaque chapitre privé → index globaux privés.

Chaque appel à `forge_chapter` reçoit le contrat public, le chapitre public, les sources et les options. Il ne reçoit ni les chapitres privés précédents ni une bible privée globale préalable. `narrative_arc`, les factions et les personas globales sont construits ensuite à partir des chapitres déjà écrits.

**Effet probable :** les chapitres peuvent être cohérents avec les titres publics tout en manquant de causalité commune. Une révélation préparée plusieurs chapitres auparavant, un mensonge partagé ou une évolution de relation doivent être reconstruits après coup. Dans une campagne importée, les notes de sources peuvent compenser en partie cette limite.

Sources : [ordre des phases](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:1070), [informations reçues par un chapitre](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/campaign_forge_agent.py:100), [index globaux](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/prompts/campaign_forge_indexes.txt:24).

### 2. Le traitement des one-shots ajoute un monstre et une récompense

`sanitize_gm_dossier` appelle `_repair_one_shot_table_spine`. Ce traitement s'applique notamment dès qu'il existe un seul chapitre. Il ajoute des complications et des indices génériques si nécessaire, puis appelle les fonctions de création d'une menace signature, d'un objet récompense et d'une mécanique légère.

Quand ni bestiaire ni monstre custom ne sont présents, une « menace signature » est créée, avec `goblin` comme base ultime de repli. Elle est ajoutée aux rencontres possibles. Cela ne déclenche pas automatiquement un combat, mais introduit cette possibilité dans une aventure qui n'en demandait aucune.

**Vérification directe :** un dossier synthétique « Conseil des héritiers », décrit comme une négociation politique sans combat, reçoit `menace_signature` et une relique après sanitisation.

Le test existant `test_sanitize_gm_dossier_repairs_poor_one_shot_spine` exige justement un antagoniste, des monstres, un bestiaire et des objets pour un exemple d'enquête maritime. La notion de dossier suffisamment riche est donc en partie assimilée à la présence de ces éléments.

Sources : [réparation des one-shots](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:1630), [menace automatique](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:1826), [test associé](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/tests/test_api/test_campaign_dossier.py:753).

### 3. Les consignes de continuité restreignent fortement l'invention

Le MJ est présenté comme inventif, mais `gm_narrate` lui interdit d'inventer des PNJ spécifiques, des objets et des événements non établis, puis lui demande de rester générique en cas de doute. Il doit pourtant faire émerger la vie du monde et matérialiser des éléments du dossier privé.

Ces consignes protègent des erreurs réelles. Leur portée mélange toutefois deux choses : contredire le canon et créer un détail compatible dans un espace encore vide.

**Effet probable :** un MJ prudent répète l'atmosphère, attend une action précise et réutilise les quelques éléments déjà visibles. Il lui manque une autorisation explicite d'introduire une nouvelle personne, une interruption ou une conséquence sociale cohérente et de l'enregistrer.

Autres tensions vérifiées : le schéma demande 2 à 4 paragraphes, les consignes de style limitent l'exploration à 3–4 phrases ; les échanges adressés aux compagnons réduisent le MJ à 1–2 phrases d'ambiance. La consigne de `scene_request` demande au moins un couvert et un danger dans les features, y compris sans distinction de scène sociale ou tactique.

Sources : [verrou d'invention](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/prompts/gm_narrate.txt:26), [format et features de scène](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/prompts/gm_system.txt:90), [style](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/prompts/gm_system.txt:249).

### 4. La mémoire narrative présente trois pertes distinctes

**Historique récent.** La configuration locale autorise 50 messages chargés par `load_recent_messages`, mais `_format_messages` n'en injecte que les 25 derniers. Ce sont des messages, pas 25 tours humains : MJ et compagnons consomment aussi cette fenêtre.

**Résumé conversationnel.** `ContextManager` conserve des extraits de 160 caractères, sur 12 lignes ; ce n'est pas une synthèse sémantique. Surtout, le chemin `ActionPipeline → GMAgent.think → narrate` utilise `context_manager=None`. Ce mécanisme ne résout donc pas la mémoire du chemin principal examiné.

**Canon de la première session.** `build_gm_prompt_context` vide le canon dès que la session est la première de la campagne et que l'index de session vaut zéro. Cette condition ne distingue pas une ouverture de partie d'un tour joué beaucoup plus tard.

**Vérification directe avec dépendances DB simulées :** une promesse présente dans `dossier.played_canon.established_facts` devient une liste vide dans le contexte privé du MJ pour une première session en exploration. Les messages récents et certains états de scène peuvent encore porter cette promesse ; elle n'est donc pas nécessairement oubliée immédiatement. Sa mémoire durable n'arrive cependant plus par ce canal.

Enfin, quand le pipeline déclenche une synthèse du canon après une action marquée `canon_dirty`, il transmet `recent_messages=[]`. Le synthétiseur voit l'état de jeu, mais pas automatiquement l'échange qui vient de donner son sens à une décision ou une relation. Une parole sans action structurée peut également ne pas déclencher cette synthèse.

Sources : [fenêtre de 25 messages](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/base_agent.py:126), [chemin MJ](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/gm_agent.py:387), [reset du canon](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:909), [synthèse sans échanges récents](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/game/action_pipeline.py:582).

### 5. Les factions et les fronts servent surtout de matière au prompt

Dans les modules de jeu et services examinés, les factions et fronts sont générés, stockés et injectés au MJ. Je n'ai pas trouvé de mécanisme dédié qui fasse avancer leurs agendas, établisse ce qu'ils apprennent des actions des PJ et conserve leurs prochaines décisions.

Les horloges de scène ont déjà une progression et des crises ; elles ne remplacent pas cette évolution de campagne. Une faction qui cherche à gagner une élection ou à préserver un secret ne se résume pas à un compte à rebours local.

**Effet probable :** le monde réagit à l'action immédiate, mais produit moins de conséquences différées. Le récit a des complications disponibles plutôt que des adversaires et alliés qui poursuivent des objectifs dans le temps.

Source : [fronts et factions injectés](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:922).

### 6. La structure jouable privilégie destinations et obstacles

Les chapitres possèdent un objectif, une destination d'aboutissement, des lieux, des indices et des rencontres. C'est utile pour éviter les impasses, mais les schémas ne structurent pas avec la même précision les convictions d'un PNJ, les conditions d'un accord, les promesses, les coûts sociaux ou les différentes résolutions d'un conflit.

Les chapitres sont reconstruits par une liste de champs autorisés. Ajouter une consigne dans un prompt ne suffit donc pas : un nouveau champ narratif peut être supprimé à la sanitisation puis à la projection privée. Un champ synthétique `relationship_changes` a effectivement été supprimé lors du probe.

Pour les aventures utilisant le générateur de donjon, la colonne vertébrale est explicitement une route de l'entrée vers l'antre du boss. Les branches et boucles modifient la topologie ; elles ne créent pas à elles seules une intrigue sociale ou une histoire causale des salles. Cette limite concerne les donjons procéduraux, pas toutes les campagnes.

Sources : [sanitisation de chapitre](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:2859), [projection privée](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:2529), [générateur de donjon](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/engine/dungeon_generator.py:97).

### 7. Les compagnons ont des voix, mais sont souvent mobilisés comme conseillers

Les prompts utilisent déjà leurs traits, peurs et passé, et autorisent des émotions et des désaccords. Il serait inexact de dire qu'ils ne font que commenter.

Cependant, les réactions sont déclenchées après les actions du monde et les dialogues PNJ, avec un biais de spécialité. Les consignes demandent fréquemment une prochaine étape utile : le mage lit la magie, le roublard pense aux pièges, etc. Cette orientation favorise des assistants compétents. Une relation mémorable exige aussi le souvenir d'une promesse, une blessure de confiance, une loyauté conflictuelle et des moments qui ne cherchent pas à résoudre l'obstacle.

Le lien entre personnage et campagne reste léger dans `party_hooks` : identifiant, nom, classe et background. La forge a lieu avant la composition du groupe dans le flux examiné ; une étape ultérieure de personnalisation aurait de la valeur.

Sources : [réactions après une action du monde](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/narrative_flow_service.py:737), [réponse des compagnons](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/agents/prompts/player_dialogue.txt:29), [hooks du groupe](/Users/christophe/Documents/Projet-Dev/RpgMaster/backend/app/services/campaign_dossier_service.py:874).

## Évolutions proposées

### A. Corriger d'abord les comportements qui dégradent le récit

1. Vider le canon uniquement lors d'une initialisation ou d'un reset explicite. Préserver le canon réellement acquis pendant la première session.
2. Alimenter la synthèse avec les échanges pertinents et les changements effectivement acceptés, en distinguant intentions, faits et informations privées.
3. Harmoniser la fenêtre d'historique avec un budget de tokens explicite. Conserver des souvenirs importants au-delà de cette fenêtre.
4. Rendre les réparations de dossier compatibles avec le genre : une négociation peut être complète sans monstre, relique ou combat.
5. Revoir les contradictions du prompt et conditionner les outils au contexte : une scène sociale n'a pas besoin du catalogue complet de géométrie et de combat.
6. Autoriser explicitement les ajouts compatibles avec le canon : nouveau détail ou acteur enregistré, sans retcon, sans gain mécanique arbitraire et sans décision imposée au joueur.

Ce lot devrait avoir un bon rapport impact/complexité. Il doit précéder une nouvelle accumulation de consignes littéraires.

### B. Construire la forge autour d'une bible privée préalable

Ordre proposé : brief → bible privée → contrat public dérivé → situations et chapitres → audit de cohérence → compilation technique.

La bible contient un conflit central concret, une question thématique, une vérité cachée, les acteurs et leurs intérêts, leurs relations, et ce qui arriverait sans intervention des PJ. Les chapitres s'appuient sur cette même base, avec des identifiants stables.

Pour chaque acteur important : ce qu'il veut maintenant, ce qu'il refuse de perdre, ce qu'il croit à tort, sa limite morale et ce qui pourrait le faire changer d'avis. Pour chaque dilemme : qui gagne, qui perd, quels coûts deviennent visibles et quelles conséquences peuvent réapparaître plus tard.

Éviter des scripts du type « au chapitre 3, le joueur découvre forcément la trahison ». Prévoir plusieurs voies de découverte et des conséquences si le groupe abandonne l'enquête. Le secret existe avant le choix ; le choix détermine comment il est découvert et ce qui advient ensuite.

Compromis : génération plus élaborée et audit supplémentaire à la création, mais meilleur socle pour toute la partie. Modifier les schémas, sanitizers et projections avec les prompts ; les blobs JSON existants suffisent, sans nouvelle table.

### C. Donner au MJ une direction narrative explicite

Introduire un petit état privé de direction du récit : fils actifs, intentions actuelles des PNJ, questions encore ouvertes, pressions, promesses à rappeler et changements provoqués par le dernier choix.

Avant une réponse importante, le MJ doit pouvoir décider : quel acteur a une raison d'agir, ce qui change réellement, quel élément ancien revient, et quelle nouvelle décision s'ouvre au joueur. Une scène calme peut approfondir une relation ; une scène d'enquête peut donner un indice essentiel sans imposer un jet ; un combat peut porter un enjeu autre que l'élimination.

Commencer par un plan compact inclus dans l'appel MJ existant. Tester ensuite, si nécessaire, un appel séparé aux transitions ou décisions majeures. Éviter plusieurs appels supplémentaires pour chaque clic : latence et coût risqueraient d'annuler le gain d'expérience.

Ne pas confondre direction narrative et rails : elle arbitre les réactions du monde, elle ne choisit ni la réponse du joueur ni une fin prédéterminée.

### D. Faire vivre le monde et les relations

Ajouter un état persistant pour les intentions des factions et PNJ, avec progression motivée par le temps fictionnel, leurs moyens et les informations dont ils disposent. Les réactions sont des propositions structurées validées avant application. Les effets mécaniques restent au moteur.

Étendre la mémoire des relations avec des événements concrets : promesse tenue ou rompue, dette, aide reçue, secret confié, humiliation, désaccord non résolu. Un score de confiance peut aider, mais ne remplace pas le souvenir de sa cause.

Les compagnons récupèrent leurs souvenirs pertinents sans accès aux secrets du MJ. Ils peuvent rester silencieux, demander une conversation, exprimer une conviction ou proposer une action liée à leur passé. Le contrôle des décisions du joueur demeure intact.

Compromis : davantage d'état à gérer. Commencer avec les deux ou trois acteurs centraux de l'aventure, plutôt qu'une simulation permanente de tout l'univers.

### E. Adapter les scènes et la restitution à l'expérience souhaitée

Une scène devrait avoir une fonction : négociation, découverte, poursuite, confidence, dilemme, affrontement ou résolution. Son traitement dépend de cette fonction.

- Dialogue : répliques adaptées à l'intention du PNJ, au rapport de force et aux échanges précédents.
- Enquête : indices menant à des questions et connexions ; les jets modulent précision, coût ou risque sans bloquer systématiquement l'aventure.
- Transition : ellipse proportionnée au choix du joueur, avec conséquences pertinentes.
- Combat : géométrie et mécanique tactique complètes.
- Résolution : conséquences humaines, retour des acteurs et possibilité d'épilogue.

Proposer à terme un mode de lecture centré sur le récit, avec carte et chiffres accessibles quand utiles. C'est une proposition de produit ; elle ne nécessite pas de remplacer le design system. La longueur devrait varier avec la scène et les préférences du joueur. Des descriptions plus longues ne suffisent pas à créer de la profondeur.

## Exemple de résultat recherché

Une marchande demande de récupérer un registre volé. La structure faible produit une piste, un entrepôt, des gardes, puis le registre et une récompense.

Une structure plus riche établit que la marchande veut le registre pour sauver sa fille, que le voleur cherche à prouver une fraude, que les gardes protègent les emplois d'un quartier et qu'un compagnon a une dette envers l'un d'eux. Ces faits privés existent avant que le joueur tranche.

Le joueur peut récupérer, publier, falsifier ou négocier le registre, ou proposer une autre voie. Chaque solution a un coût compréhensible. Sauver la fille peut protéger une fraude ; publier le registre peut faire perdre des emplois. Deux scènes plus tard, un acteur revient à cause de ce choix, une promesse est rappelée et un compagnon modifie son attitude pour une raison précise.

Le gain recherché est cette continuité des causes et des relations. Le combat reste possible si la situation y mène.

## Ordre de mise en œuvre conseillé

| Lot | Contenu | Impact attendu | Complexité relative |
|---|---|---|---|
| 1 | Canon première session, échanges de synthèse, biais one-shot, consignes contradictoires | Fort et immédiat | Faible à moyenne |
| 2 | Bible privée avant chapitres, conflits et relations explicites, audit de forge | Très fort sur les nouveaux scénarios | Moyenne |
| 3 | Mémoire des décisions et relations, contexte sélectionné selon la scène | Très fort sur la durée | Moyenne |
| 4 | Direction narrative, intentions et conséquences différées des acteurs | Fort sur les campagnes longues | Élevée |
| 5 | Arcs des compagnons, personnalisation au groupe, restitution centrée récit | Fort sur l'attachement et le rythme | Moyenne à élevée |

Ce sont des estimations de conception, pas des mesures. Le meilleur premier périmètre serait une enquête ou une négociation courte, avec trois acteurs récurrents et deux choix ayant des conséquences différées.

## Évaluer une amélioration réelle

Les tests actuels examinés vérifient notamment JSON, confidentialité, continuité spatiale, attribution des jets et présence de champs. Ils sont utiles ; ils ne démontrent pas la qualité dramatique d'une partie sur plusieurs scènes.

Créer un petit corpus de parties de 20–30 tours : enquête, négociation, aventure avec combat et exploration ouverte. Inclure une promesse ancienne, un refus de mission, un échec, un retour dans un lieu visité et un choix qui contredit le plan initial.

Comparer à modèle constant la version actuelle et les évolutions, sur plusieurs runs. Observer :

- conséquences distinctes de décisions différentes ;
- rappel correct des promesses, dettes et événements anciens ;
- motivations et réactions reconnaissables des acteurs ;
- indices préparant réellement les révélations ;
- résolution viable sans combat lorsque le genre le permet ;
- absence de répétitions, de blocages et de contrôle abusif du personnage humain ;
- latence, erreurs et nombre d'appels LLM.

Combiner assertions déterministes sur l'état, lecture humaine à l'aveugle et éventuellement évaluation LLM avec une grille fixe. Un juge LLM seul peut favoriser une prose spectaculaire sans détecter des conséquences fictives ou incohérentes. Comparer les modèles seulement après avoir établi cette base, afin de séparer le gain architectural du gain de modèle.

## Vérifications réalisées et limites

- Lecture du pipeline de forge, des prompts principaux MJ/compagnons, du contexte privé, du canon, du pipeline d'action, des réactions et du générateur de donjon.
- Consultation des audits historiques comme contexte ; leurs constats ne sont pas présumés toujours actuels. Plusieurs corrections anciennes sont déjà visibles dans le code présent.
- Six tests ciblés passés : les quatre tests de `test_campaign_forge_prompts.py`, le test de réparation one-shot et le test de reset du canon privé sur la première session.
- Deux probes sans réseau ni écriture DB : sanitisation d'une négociation sans combat et projection d'un canon acquis pendant une première session.
- Aucun replay live, nouvelle campagne réelle ou comparaison de prose n'a été lancé. Les effets sur la qualité narrative restent à mesurer ; les transformations d'état reproduites sont établies.

Recommandation : traiter ensemble la mémoire, le biais de remplissage des dossiers et l'ordre de construction de la forge. Ces trois changements donnent au MJ de meilleures raisons d'agir et de meilleures informations pour se souvenir, avant d'augmenter sa sophistication.
