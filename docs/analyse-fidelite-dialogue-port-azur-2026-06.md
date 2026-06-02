# Analyse de fidélité — dialogue de partie « Port d'Azur / Entrepôt 13 »

> **Date** : 2026-06-01 · **Code lu** : `main`, HEAD `ec36179`
> **Objet** : analyser un dialogue réel de partie (Place du Marché Central → docks → égouts → Siphon d'Éclat) pour repérer ce qui s'écarte encore d'une vraie table de JDR après les lots de fidélité déjà livrés.
> **Suite de** : [`suivi-tabletop-fidelity.md`](suivi-tabletop-fidelity.md), [`analyse-fidelite-dialogue-2026-06.md`](analyse-fidelite-dialogue-2026-06.md).

## Légende des statuts

- ✅ **Confirmé** — symptôme tracé jusqu'à un mécanisme précis dans le code.
- 🔶 **Hypothèse** — cause plausible mais à valider par replay/live ou inspection d'état de session.
- 🟢 **Progrès confirmé** — point qui montre qu'un lot précédent fonctionne mieux.

---

## 1. Lecture d'ensemble

Le dialogue est meilleur que celui de l'oasis sur trois points importants : le contrat de quête est intégré dans la fiction, les transitions ne cassent pas le PNJ Valerius, et l'objectif de scène produit une vraie pression. En revanche, l'expérience reste encore trop "application" par moments : les clics de carte injectent des formulations mécaniques, l'horloge de menace parle avec son libellé interne, les jets de danger se répètent sans vraie conséquence lisible, et le compagnon Vael devient presque invisible.

Le problème central n'est plus seulement la continuité de scène. C'est le **rythme de table** : qui parle, pourquoi un jet arrive, quel coût il impose, et comment l'interface traduit une intention du joueur en phrase naturelle.

---

## 2. Constats

### 2.1 🟢 Ouverture : P3 fonctionne nettement mieux

**Symptôme positif.** L'ouverture ne colle plus les champs "Accroche" / "Mission". Le contrat affleure dans la prose : Valerius convoque le groupe, le problème des docks est public, et l'urgence est immédiatement sensible par le bourdonnement toutes les trente secondes.

**Écart restant.** La phrase "Le contrat est clair" garde une légère odeur de fiche de quête. Ce n'est plus un bug de collage, plutôt un style à durcir : à une table, le MJ dirait peut-être "Valerius vous a promis tant d'or..." ou "son messager vous a tirés hors de la fête..." plutôt que nommer "le contrat".

**Impact.** Faible. P3 est globalement validé par ce dialogue.

### 2.2 ✅ Prompts de clic : le joueur lit encore des commandes de carte

**Symptômes.**

- "Je me dirige vers **Direction les Docks**."
- "Je me dirige vers **Accès Égouts**."
- "Je me dirige vers **Profondeurs**."
- "J'examine : **Zone de vibration**."

Ces phrases révèlent le libellé brut du POI ou de la sortie. "Direction les Docks" est un label d'interface, pas une destination fictionnelle. Le même problème avait déjà produit "vers Vers l'Oasis d'Émeraude" dans l'analyse précédente.

**Mécanisme.**

- Le chemin desktop V2 `ExplorationLayout` émet directement `Je me dirige vers ${poi.title}.` pour une sortie, sans nettoyage ni phrase naturalisée ([ExplorationLayout.vue:34-36](../frontend/src/components/exploration/ExplorationLayout.vue)).
- Le chemin mobile / battlemap a déjà une version plus propre : `handleSceneExit()` applique `cleanExitLabel()` ([GameSessionView.vue:276-292](../frontend/src/views/GameSessionView.vue)).
- Les interactions POI mobiles ont aussi un générateur plus naturel (`buildScenePoiInteractionPrompt`) ([scenePoiInteractions.ts:54-76](../frontend/src/utils/scenePoiInteractions.ts)), mais le desktop V2 utilise encore son propre gabarit plus ancien ([ExplorationLayout.vue:38-47](../frontend/src/components/exploration/ExplorationLayout.vue)).

**Écart avec une vraie table.** Le joueur ne dirait pas "j'examine deux-points Zone de vibration". Il dirait "je m'accroupis près des planches qui vibrent" ou "je vais vers les docks". Le clic devrait produire une intention humaine, pas une commande.

### 2.3 ✅ Horloge de menace : bonne idée, mauvaise voix visible

**Symptôme.** Après l'arrivée aux docks, le récit publie :

> "Menace aux docks atteint son point critique. L'instabilité se libère d'un coup ; le personnage exposé doit réagir immédiatement."

Puis :

> "Oaken encaisse le contrecoup de Menace aux docks sans perdre pied..."

"Menace aux docks" est un nom d'horloge interne. "Le personnage exposé" est un placeholder. La crise est réelle, mais la voix n'est pas celle d'un MJ.

**Mécanisme.**

- `infer_clock_start_from_opening()` crée automatiquement une horloge nommée "Menace aux docks" si le texte contient docks/quai/entrepôt et des marqueurs de menace ([social_scene_state.py:650-675](../backend/app/game/social_scene_state.py)).
- L'horloge avance à chaque action joueur (`tick_on = "player_action"`) jusqu'au max ([social_scene_state.py:705-751](../backend/app/game/social_scene_state.py)).
- Si aucun texte spécifique n'est fourni, `_default_clock_crisis_text()` et `_clock_roll_outcome_text()` publient des phrases génériques contenant directement le label de l'horloge ([social_scene_state.py:924-943](../backend/app/game/social_scene_state.py)).

**Écart avec une vraie table.** Un MJ ne dirait pas "Menace aux docks atteint son point critique". Il décrirait les amarres qui claquent, les pilotis qui se tordent, un pavé qui saute, Valerius qui blêmit, puis demanderait un jet.

### 2.4 ✅ Horloge et dangers : les jets existent, mais les coûts sont mous

**Symptôme.** Oaken réussit plusieurs DEX Save. Le jeu publie la réussite, mais l'effet concret reste flou : il "évite le pire", continue à examiner, puis descend dans les égouts. La menace est dite "critique", mais n'impose ni choix difficile, ni ressource consommée, ni changement de scène vraiment exploitable.

**Mécanisme.**

- `resolve_scene_clock_crises()` publie une narration, résout un jet, puis publie une narration de résultat ([social_scene_state.py:754-810](../backend/app/game/social_scene_state.py)).
- Le texte de succès est un repli générique : "sans perdre pied, juste assez vite pour éviter le pire" ([social_scene_state.py:932-939](../backend/app/game/social_scene_state.py)).
- Le dialogue ne montre pas de conséquence durable claire dans la scène : pas de blessure évitée explicitement, pas de passage bloqué, pas d'alerte publique, pas de clock suivante visible.

**Écart avec une vraie table.** Sur une horloge remplie, même une réussite doit faire avancer la situation : le quai s'effondre derrière eux, un témoin hurle, l'accès aux docks devient dangereux, Valerius doit contenir la foule, ou le groupe gagne seulement une fenêtre courte.

### 2.5 ✅🔶 Type de jet et intention joueur : observer déclenche parfois esquiver

**Symptômes.**

- "J'examine : Zone de vibration" déclenche un DEX Save.
- "J'examine : Canal d'eaux noires" déclenche encore un DEX Save.
- Le récit donne ensuite des informations d'analyse détaillées, sans qu'un jet d'Investigation/Nature/Arcanes soit visible pour ces informations.

**Mécanisme confirmé en partie.**

- Le pipeline résout automatiquement les mécaniques d'un POI si `scene_interaction_context.mechanics.roll` existe ([action_pipeline.py:168-175](../backend/app/game/action_pipeline.py), [action_pipeline.py:1048-1083](../backend/app/game/action_pipeline.py)).
- L'inférence par défaut distingue normalement observation et contact dangereux : une interaction `examine/search` sur un danger devrait produire un INT(Investigation), tandis qu'un `use/custom` dangereux produit un DEX Save ([social_scene_state.py:342-386](../backend/app/game/social_scene_state.py)).

**Hypothèse.** Dans cette session, les POI ou interactions générés par le MJ portent probablement des mécaniques explicites de sauvegarde DEX, ou une interaction labellisée "examiner" est transmise comme `custom/use`. Il faut confirmer avec l'état `current_scene.pois[].interactions`.

**Écart avec une vraie table.** Si le joueur dit "j'observe à distance", le MJ peut demander Perception/Investigation/Nature. Il ne demande un DEX Save que si le personnage s'expose physiquement, ou après avoir annoncé clairement le risque : "si tu t'approches autant, tu devras garder l'équilibre".

### 2.6 ✅ Dialogue PNJ : la voix de Valerius est bonne, mais le canal mélange parole et didascalie

**Symptômes.**

Les entrées `❦ Maire Valerius` contiennent une longue narration à la troisième personne, puis une réplique entre guillemets :

> "Le Maire Valerius sursaute légèrement... « Enfin ! ... »"

La deuxième réplique fait pareil. Valerius a une personnalité lisible, mais la carte de dialogue affiche aussi la mise en scène que le MJ devrait porter.

**Mécanisme.**

- `gm_npc_dialogue.txt` demande explicitement que le champ `narration` contienne "la réplique du PNJ entre guillemets, avec au plus une courte réaction physique/émotionnelle" ([gm_npc_dialogue.txt:51](../backend/app/agents/prompts/gm_npc_dialogue.txt)).
- Le backend et le frontend retirent surtout les préfixes de speaker, pas les guillemets ni les didascalies longues ([visible_events.py:15-36](../backend/app/game/visible_events.py), [game.ts:38-54](../frontend/src/stores/game.ts)).

**Écart avec une vraie table.** La mise en scène est utile, mais l'UI devrait distinguer "Valerius dit" de "le MJ décrit Valerius". Là, la carte PNJ fait parler le narrateur à la place du PNJ.

### 2.7 🟢 Continuité PNJ : Valerius ne disparaît pas comme Khalid

**Symptôme positif.** Valerius reste cohérent : il suit jusqu'aux quais, refuse de descendre dans les égouts, puis le récit rappelle qu'on abandonne sa silhouette nerveuse derrière soi.

**Lecture.** C'est exactement le type de continuité que P1/P2 cherchait à protéger. Le PNJ ne disparaît pas par accident ; son arrêt devient une décision fictionnelle claire.

**Reste à surveiller.** Valerius n'est pas forcément un "accompanying" durable : il suit temporairement puis reste en arrière. Le système doit préserver cette nuance entre "escorté par le groupe", "reste sur le seuil" et "absent de la scène suivante".

### 2.8 🔶 Vael, compagnon fantôme

**Symptôme.** Vael est nommé dans l'ouverture et dans les transitions ("Vael et Oaken progressent"), mais ne réagit jamais. Il ne commente pas l'urgence, n'aide pas à analyser, ne propose pas de précaution, ne prend pas la main quand Oaken échoue.

**Mécanisme probable.**

- Le flux demande les compagnons seulement si la détection d'audience vise `companion`, `party` ou `mixed` ([narrative_flow_service.py:251-301](../backend/app/services/narrative_flow_service.py)).
- Une réaction automatique existe après crise d'horloge ou dialogue PNJ, mais elle est cappée et silencieuse si aucun compagnon IA actif n'est présent ([narrative_flow_service.py:236-249](../backend/app/services/narrative_flow_service.py), [narrative_flow_service.py:669-730](../backend/app/services/narrative_flow_service.py)).

**Écart avec une vraie table.** Après plusieurs minutes de danger, un autre personnage présent devrait au moins demander "je peux aider ?", "je surveille Valerius", ou "je tiens la corde". Le dialogue inverse le problème de saturation observé dans l'oasis : ici, le compagnon devient décor.

### 2.9 🔶 Progression d'enquête : beaucoup d'indices, peu de décisions

**Symptôme.** Les descriptions sont riches et cohérentes : pulsation organique, eau noire iridescente, gaz violacés, pompe invisible, énergie derrière le mur. Mais les choix du joueur restent linéaires : examiner le POI suivant, aller à la sortie suivante.

**Écart avec une vraie table.** Le MJ devrait transformer ces indices en embranchements jouables : prévenir la foule, sécuriser le quai, interroger Valerius sur l'Entrepôt 13, couper la pompe, contourner le canal, envoyer Vael en éclaireur, marquer le mur, chercher une vanne, etc.

**Lien avec les lots existants.** Le lot 9 demandait plusieurs prises jouables et une progression même sur échec. Ici, la scène avance, mais les options restent principalement une chaîne de POI.

### 2.10 ✅ Affichage de jet : quelques micro-fuites UI

**Symptômes dans le texte copié.**

- `OakenDEX Save` et `SystèmeDEX Save` semblent manquer d'espaces.
- `1d2018` semble concaténer notation et résultat.
- Un jet de sauvegarde environnemental apparaît parfois comme `Système`, même quand la narration parle d'Oaken.

**Mécanisme probable.**

- Le payload de jet contient bien `character_name` quand `execute_roll_request()` trouve le personnage ([roll_executor.py:43-49](../backend/app/game/roll_executor.py), [roll_executor.py:94-105](../backend/app/game/roll_executor.py)).
- La persistance retombe sur speaker `"Système"` si `character_name` manque ([message_service.py:73-81](../backend/app/services/message_service.py)).

**À vérifier.** Il faut reproduire côté UI actuelle, car le texte copié peut avoir perdu des espaces au collage. Mais l'invariant est simple : un save subi par Oaken ne doit jamais être présenté comme un jet de "Système".

---

## 3. Thèmes structurels

1. **La scène sait produire de la pression, mais la pression parle avec des libellés internes.** Les horloges sont utiles, mais leur `label` ne doit pas devenir une phrase de MJ.

2. **Le contrat "clic → intention" n'est pas uniformisé.** Mobile/battlemap et desktop V2 n'ont pas le même générateur de phrases. Cela suffit à refaire apparaître les vieux "Vers/Direction".

3. **Les mécaniques de danger confondent exposition et observation.** Le joueur doit comprendre pourquoi il jette DEX plutôt qu'Investigation, et pouvoir choisir une approche prudente contre un risque moindre ou une information plus limitée.

4. **Les compagnons manquent d'un juste milieu.** Après l'oasis, on craignait la saturation. Ici, Vael est absent. Il faut un système de spotlight plus contextuel : réaction courte quand l'enjeu monte, silence quand l'humain a clairement la main.

5. **Le dialogue PNJ a besoin de deux canaux visibles.** Une réplique PNJ peut avoir une didascalie, mais pas devenir un paragraphe de narration déguisé en parole.

---

## 4. Plan proposé (à discuter)

### Q1 — Naturaliser toutes les actions issues de la carte 🔴

**Objectif** : un clic produit la même qualité de phrase qu'un texte libre humain.

**Mécanisme proposé :**
- Faire utiliser `buildScenePoiInteractionPrompt()` par `ExplorationLayout` desktop, pas seulement par le chemin mobile/battlemap.
- Centraliser aussi le nettoyage des sorties (`cleanExitLabel`) dans un util partagé.
- Ajouter une normalisation des labels de sortie : retirer `Vers`, `Direction`, `Accès`, `Profondeurs` seulement quand c'est un préfixe d'interface, et générer "Je vais aux docks", "Je descends vers les égouts", "Je m'enfonce vers les profondeurs" selon le rôle.
- Tests frontend : sortie `Direction les Docks` → phrase sans doublon ; POI `Zone de vibration` → phrase naturalisée sans deux-points.

**Risque** : faible. C'est surtout un alignement frontend.

### Q2 — Donner une voix fictionnelle aux horloges de menace 🔴

**Objectif** : garder les horloges, supprimer les labels internes visibles.

**Mécanisme proposé :**
- Remplacer les textes génériques de `_default_clock_crisis_text()` / `_clock_roll_outcome_text()` par des templates fictionnels selon `clock.kind`, `linked_scene`, `severity`, `label`.
- Ajouter à `clock_start.on_fill` un champ optionnel `public_narration` ou `fictional_trigger` obligatoire pour les horloges créées par le MJ ; fallback déterministe seulement si absent.
- Ne jamais insérer `clock.label` tel quel dans une phrase visible, sauf dans un badge UI d'horloge.
- Tests backend : aucun event narration d'horloge ne contient "Menace aux docks atteint son point critique" ; il contient un phénomène concret.

**Risque** : faible/moyen. Il faut préserver l'horloge visible du header, mais changer la narration.

### Q3 — Clarifier exposition, observation et conséquences des dangers 🟠

**Objectif** : "j'observe" ne doit pas se transformer en "je subis" sans annonce.

**Mécanisme proposé :**
- Étendre `ScenePoiInteraction.mechanics` avec une notion d'`exposure`: `safe`, `near`, `contact`, `reckless`.
- Pour `safe/near + examine/listen/search`, privilégier Investigation/Perception/Nature/Arcanes ; pour `contact/reckless/use`, utiliser les sauvegardes.
- Si une sauvegarde est demandée sur une intention d'observation, le MJ doit d'abord publier une micro-annonce : "Pour voir cela, il faut t'approcher sur les planches instables."
- En cas de succès sur une horloge critique, appliquer quand même un changement de scène : passage endommagé, timer suivant, complication évitée mais coût narratif.
- Tests backend : interaction `examine` sur hazard sans `exposure=contact` ne produit pas DEX Save ; interaction `use/contact` oui.

**Risque** : moyen. Touche le contrat backend des POI et certains prompts MJ.

### Q4 — Séparer parole PNJ et didascalie visible 🟠

**Objectif** : une carte PNJ affiche d'abord ce que le PNJ dit, avec une courte posture séparée si nécessaire.

**Mécanisme proposé :**
- Modifier le prompt `gm_npc_dialogue.txt` : ne plus demander des guillemets dans `narration`; demander `narration` sans guillemets, une à trois phrases maximum, dont au plus une courte didascalie.
- Idéalement, faire évoluer le schéma vers `spoken_text` + `stage_direction` pour les dialogues PNJ ; l'UI affiche la didascalie en texte atténué et la parole en dialogue.
- Ajouter un sanitizer visible : retirer guillemets englobants et préfixes "Le Maire Valerius..." quand ils redoublent le speaker.
- Tests backend/frontend : `speaker=Maire Valerius`, texte visible ne commence pas par "Le Maire Valerius" et n'est pas doublement guillemeté.

**Risque** : faible si sanitizer ; moyen si changement de schéma.

### Q5 — Réintroduire les compagnons au bon moment 🟡

**Objectif** : éviter à la fois la saturation de l'oasis et le compagnon fantôme de Port d'Azur.

**Mécanisme proposé :**
- Ajouter un "spotlight trigger" contextuel : réaction max 1 compagnon quand une horloge se remplit, un PJ échoue un jet important, une nouvelle scène dangereuse commence, ou un indice correspond fortement à la spécialité du compagnon.
- La réaction doit être courte et non résolutive : conseil, aide proposée, prise de poste, question au joueur.
- Exposer au MJ un état `companion_recently_spoke` / cooldown pour éviter l'enchaînement.
- Invariant replay : sur 6 actions monde dangereuses, au moins 1 réaction compagnon pertinente, au plus 2.

**Risque** : moyen. C'est du rythme, donc à valider en live LLM.

### Q6 — Transformer les indices en options jouables 🟡

**Objectif** : sortir du couloir "POI suivant".

**Mécanisme proposé :**
- Dans les prompts MJ, après deux indices convergents, demander explicitement 2-4 approches possibles via `scene_update` / interactions POI : sécuriser, contourner, interroger, analyser, agir sur le mécanisme.
- Les faits découverts doivent alimenter de nouvelles interactions concrètes, pas seulement enrichir la prose.
- Tests/replay : après "canal d'eaux noires" + "vibrations derrière le mur", la scène contient au moins deux options autres que "aller plus profond".

**Risque** : faible/moyen. Dépend surtout de prompt + fallback de scène.

### Q7 — Durcir l'affichage des jets environnementaux 🟡

**Objectif** : un jet subi par un personnage est toujours attribué et lisible.

**Mécanisme proposé :**
- Invariant backend : tout `ROLL_RESULT` visible avec `target/fallback_actor_id` doit avoir `character_id` et `character_name`.
- Invariant frontend : rendu avec espaces stables entre `character_name`, `label`, `dice_notation`, résultat.
- Si un jet est réellement collectif ou environnemental, le label doit l'indiquer ("Groupe", "Horloge") et non "SystèmeDEX Save".

**Risque** : faible.

---

## 5. Ordre suggéré

| # | Lot | Impact joueur | Risque | Ordre |
|---|-----|---------------|--------|-------|
| Q1 | Actions carte naturalisées | 🔴 très visible | faible | 1 |
| Q2 | Horloges en voix fictionnelle | 🔴 très visible | faible/moyen | 2 |
| Q3 | Exposition/danger/conséquences | 🟠 important | moyen | 3 |
| Q4 | Dialogue PNJ propre | 🟠 visible | faible/moyen | 4 |
| Q5 | Compagnons contextuels | 🟡 rythme | moyen | 5 |
| Q6 | Options jouables depuis indices | 🟡 profondeur | faible/moyen | 6 |
| Q7 | Affichage jets | 🟡 polish | faible | parallèle |

**Priorité proposée** : traiter Q1+Q2 ensemble en premier. Ce sont les défauts les plus visibles et les plus déterministes. Q3 vient juste après, car il touche le ressenti "mes choix causent des jets compréhensibles". Q4 est un bon lot court. Q5/Q6 méritent un replay live parce qu'ils concernent le dosage narratif.

---

## 6. Scénarios d'acceptation à ajouter au harness live

1. **Port d'Azur — clic sortie naturalisé**
   - Sortie label `Direction les Docks`.
   - Action visible attendue : pas de "vers Direction", pas de doublon de préposition.

2. **Port d'Azur — horloge critique fictionnelle**
   - Une horloge "Menace aux docks" atteint son maximum.
   - Narration visible attendue : phénomène concret ; interdit : `Menace aux docks atteint son point critique`.

3. **Port d'Azur — observer un danger**
   - Action joueur : examiner une zone dangereuse à distance.
   - Attendu : jet d'observation ou annonce de risque avant sauvegarde ; pas de DEX Save arbitraire sans exposition.

4. **Port d'Azur — PNJ parle proprement**
   - Oaken parle à Valerius.
   - Entrée `dialogue` attendue : pas de préfixe "Le Maire Valerius..." en tête, pas de guillemets englobants doublés.

5. **Port d'Azur — compagnon non fantôme**
   - Sur une crise d'horloge ou un échec significatif, Vael réagit une fois au maximum, avec une proposition courte qui ne résout pas la scène à la place d'Oaken.

---

## 7. Décision à prendre

Je recommande de valider d'abord ce découpage :

- **Q1+Q2** comme prochain lot immédiat.
- **Q3** juste après, car il modifie le contrat mécanique des interactions.
- **Q4** en lot court si on veut vite améliorer le rendu des dialogues PNJ.
- **Q5/Q6** après un replay live, pour doser le rythme sans casser les progrès déjà obtenus.

