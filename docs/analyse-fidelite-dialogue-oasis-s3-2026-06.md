# Analyse de fidélité — 3ᵉ dialogue (Piste d'Ambre → Oasis d'Émeraude, session 3)

> **Date** : 2026-06-04 · **Code lu** : `main` (working tree courant)
> **Objet** : analyser un **3ᵉ dialogue réel** (rejoué après tous les lots livrés A/B/D/G + P1/P2/P3 + lots présence/symétrie), confronter chaque constat au code, distinguer ce qui **fonctionne mieux** de ce qui **reste à corriger**, mapper sur le backlog **A–H** et proposer un **plan à discuter** (aucune implémentation ici).
> **Suite de** : [`analyse-croisee-fidelite-2026-06.md`](analyse-croisee-fidelite-2026-06.md) (backlog unifié A–H), [`analyse-fidelite-dialogue-2026-06.md`](analyse-fidelite-dialogue-2026-06.md) (Oasis, P1–P6), [`analyse-fidelite-dialogue-port-azur-2026-06.md`](analyse-fidelite-dialogue-port-azur-2026-06.md) (Port d'Azur, Q1–Q7).

## Légende des statuts

- 🟢 **Progrès confirmé** — un correctif antérieur tient, vérifié sur ce dialogue.
- ✅ **Tracé au code** — symptôme suivi jusqu'à un mécanisme précis.
- 🔶 **Fork ouvert** — cause non close par la seule lecture de code ; à trancher par un log de session ou un replay live.
- 🧩 **Décision à discuter** — plusieurs designs possibles ; arbitrage attendu avant codage.

---

## 1. Ce qui fonctionne maintenant (crédit avant critique)

Ce dialogue **valide en conditions réelles** plusieurs correctifs. À noter explicitement, car ça change la lecture du reste :

- 🟢 **P1 re-validé live (le bug d'origine ne se reproduit plus).** Khalid **reste présent et accompagnant** sur toute la traversée *et* toute la scène de l'oasis : il commente la carcasse, presse vers l'oasis, marche avec le groupe, puis esquive au bord du bassin. C'est exactement le bug que visait la session 1 (« Khalid disparaît au voyage ») — il est **fermé**. La fixture `test_tabletop_replay_live.py` nettoyée encode désormais ce contrat.
- 🟢 **Ouverture diégétique sans étiquette (P3 tient).** Aucune ligne de fiche (« Accroche : », « Mission : ») ; le contrat affleure en fiction (la soif, la chaleur, la promesse de l'Oasis). L'enjeu **concret** passe bien.
- 🟢 **Parole PNJ propre (D tient).** Les répliques de Khalid n'ont ni préfixe de nom redondant, ni guillemets englobants parasites ; la didascalie est fondue (« *Il recule d'un pas…* »).
- 🟢 **Compagnons IA crédibles.** Elara/Solana/Oaken ont des voix distinctes et des angles cohérents (arcanes / foi / pragmatisme). C'est le point fort à **préserver** dans tout plafonnement.

> Constat utilisateur confirmé : « l'ensemble est bien meilleur », « l'intro est bien meilleure ». La suite porte sur les **résidus** et **constats neufs**, pas sur une régression.

---

## 2. Constats neufs tracés au code

### N1 — Double réponse de Khalid (constat utilisateur) ✅

**Symptôme** : Solana (compagnon IA) interpelle Khalid → *rien de visible ne se passe* → Thorvald (humain) reposte la même question via `@Khalid` → **deux répliques de Khalid** s'enchaînent.

**Causes tracées** (deux, complémentaires) :

1. **Aucun indicateur « le PNJ répond » sur le chemin de dialogue PNJ.** L'indicateur `thinking` existe pour le **MJ** ([action_pipeline.py:305](../backend/app/game/action_pipeline.py)) et pour le **compagnon qui parle** ([narrative_flow_service.py:493](../backend/app/services/narrative_flow_service.py)), mais **`resolve_npc_dialogue` n'en publie aucun** ([action_resolver.py:246-291](../backend/app/game/action_resolver.py)). Quand Solana déclenche le relais compagnon→PNJ ([ai_player_manager.py:865-903](../backend/app/game/ai_player_manager.py) `_relay_companion_talk_to_npc`), l'appel LLM gemma4 (plusieurs secondes, jusqu'à 240 s de read-timeout) tourne **en silence**. Le joueur, ne voyant rien, **repose la question** → 2ᵉ déclenchement.
2. **Aucun garde anti-concurrence sur le même PNJ.** Le chemin compagnon-relais et le chemin action-humaine appellent tous deux `resolve_npc_dialogue` **sans coordination** : rien ne dit « une réplique de `khalid_guide` est déjà en vol ». Les deux tâches courent en parallèle → deux répliques.

**Cadrage du défaut (important — ne pas sur-corriger)** : sur les **3** répliques de Khalid du dialogue, **seul le couple Solana+Thorvald** (même question, déclencheurs en course) est le bug. La **3ᵉ** réplique (réponse à Oaken qui le pousse) est une **relance multi-personnage légitime** — c'est de la *bonne* dynamique de table, pas à supprimer. Le correctif doit donc viser « même PNJ, même tour, déclencheur déjà en vol », **jamais** « interdire qu'un PNJ réponde plusieurs fois ».

**Rattachement backlog** : généralise **P4** (indicateur) au chemin PNJ + petit garde anti-concurrence neuf.

---

### N2 — Déconnexions « Déconnecté du serveur » ×2 🔶 — ❌ HORS SCOPE

> **Tranché par l'utilisateur (2026-06-04)** : ces deux déconnexions ont été **provoquées par un développement back en cours** pendant la partie, **pas** par un bug applicatif. **Retiré du plan.** L'analyse ci-dessous est conservée pour mémoire (la fragilité « audio-via-bus gonfle les rafales » reste vraie en théorie, mais n'est pas la cause de cet épisode).

**Symptôme** : deux « Déconnecté du serveur » consécutifs, juste après la salve de répliques de Khalid (forte concurrence : relais PNJ ×2-3 + compagnons).

**Ce qui est établi par le code** :
- Le frontend **auto-reconnecte** avec backoff et logge le code de fermeture ([useWebSocket.ts:118-138](../frontend/src/composables/useWebSocket.ts)). Donc **2× « Déconnecté » = au moins un vrai drop** (chaque drop affiche le message ; reconnexion ; éventuel re-drop).
- Il existe **un chemin de fermeture serveur sur backpressure** : si la file d'événements d'un abonné déborde, le bus remplace le backlog par une erreur `backpressure` ([event_bus.py:309/331-355](../backend/app/game/event_bus.py)) et le relais **ferme le socket en `code=1013`** ([ws_game.py:111-116](../backend/app/api/ws_game.py)). File par défaut = **256** ([config.py:53](../backend/app/config.py)).
- **L'audio TTS transite par le bus** comme events `AUDIO` (gros payloads base64, [main.py:148-156](../backend/app/main.py)). Un tour de dialogue PNJ publie **plusieurs** events (`scene_layout_changed` + `visible_entry` + `AUDIO`), et le relais les envoie **un par un** sur le WS. Sous dialogues concurrents (Khalid ×2-3 + compagnons), la rafale d'events lourds peut, si le client draine lentement, **remplir la file** → backpressure → 1013.
- Côté keepalive : ping **client→serveur** ([ws_game.py:441](../backend/app/api/ws_game.py)), actions traitées en tâches de fond « so pings remain responsive » → l'idle-timeout est **moins** probable, mais pas exclu.

**Honnêteté sur la cause (fork)** : j'ai prouvé *dans le code* que `1013 ⇐ backpressure`. Je **n'ai pas** prouvé que **ce** drop **était** un 1013. « Déconnecté du serveur » est générique et compatible avec : (a) backpressure 1013, (b) timeout idle 1006 pendant un long appel gemma4, (c) exception de tâche non gérée. **Le remède diffère selon la cause** (plafonner/délester l'audio vs ping serveur vs durcir les tâches). → **Fragilité réelle trouvée** (l'audio-via-bus gonfle les rafales sous dialogue concurrent), **mais la cause exacte de ce drop demande le log** : code de fermeture dans la console navigateur (`[WS] closed — code:`) **ou** un `grep "backpressure\|1013\|WS closed"` sur les logs serveur de la session. **Ne pas figer un correctif disconnect avant ce diagnostic.**

**Rattachement backlog** : **neuf** (robustesse WS) ; recoupe **E1** (la concurrence non plafonnée est un facteur aggravant commun avec N1).

---

### N3 — Construction d'aventure : l'objectif n'a **ni route jouable surfacée, ni destination atteignable** (constat utilisateur, reformulé) ✅ 🧩

**Symptôme utilisateur** : on doit « descendre » jusqu'à la source du mal ; on trouve un bassin, puis une fissure au fond — mais **physiquement on ne peut pas passer** (c'est plein d'eau). « Gros doute sur la construction de l'aventure. »

**Reformulation (le symptôme est la physique ; la cause est ailleurs)** : la fiction n'est **pas** forcément incohérente — la fissure est décrite comme « *l'évent d'une structure beaucoup plus vaste enfouie sous les sables* », et une vaste structure enfouie a *plausiblement* d'autres accès (un puits à sec, assécher/écarter l'eau, un rituel, un siphon). Le vrai échec n'est pas la physique, c'est que **le succès n'a produit que de la prose, jamais une prise jouable vers l'objectif**. Deux racines, toutes deux tracées :

1. **Les affordances de progression existent… mais en privé MJ-only.** `gm_narrate.txt` **anticipe littéralement cette scène** : « *Pour une scène à objectif ou obstacle (**oasis corrompue**, rituel, passage dangereux…), propose une progression jouable avec plusieurs approches : analyser, purifier, contourner, interroger, **chercher la source**…* » ([gm_narrate.txt:98](../backend/app/agents/prompts/gm_narrate.txt)). Il existe même une action dédiée `scene_progress_update` portant **« approches encore possibles »**, **« révélations accessibles »** et **« issue de réussite »** ([:99](../backend/app/agents/prompts/gm_narrate.txt)). **Mais cette action est explicitement « privée MJ-only »** : les approches encore possibles **ne sont jamais montrées au joueur** comme options cliquables. Résultat : la fissure trouvée (succès) devient une **révélation en prose**, pas un nouvel interactable (« assécher le bassin », « plonger avec respiration aquatique », « trouver le puits à sec »). → **lot F**, avec la découverte que **l'infrastructure existe mais reste invisible et sous-émise**.
2. **La destination de l'objectif n'existe pas comme nœud → cul-de-sac structurel.** Le prompt **interdit** d'inventer un lieu absent des sorties/nœuds connus : « *N'invente PAS un lieu qui ne figure dans aucune sortie, noeud, ni l'ÉTAT DU JEU* » ([gm_narrate.txt:55](../backend/app/agents/prompts/gm_narrate.txt)). Or « la source / la structure enfouie » **n'est définie nulle part** comme nœud atteignable : la forge produit des objectifs **narratifs abstraits** (« Découvrir ce qui menace la région », [campaign_dossier_service.py:1448](../backend/app/services/campaign_dossier_service.py)) et un brief d'**ambiance** ([adventure_seeds.py:306-399](../backend/app/engine/adventure_seeds.py)), mais **aucune colonne vertébrale spatiale** ne dit « l'objectif *trouver la source* se satisfait au nœud *X*, accessible via *Y* ». Faute de destination, le MJ ne **peut pas** créer une sortie vers elle — il ne peut que décrire la fissure comme un décor. **Chaque approche dead-end parce qu'il n'y a nulle part où aller.** C'est le cœur du « doute sur la construction de l'aventure ».

**🧩 Décision à discuter** (3 designs, du moins au plus structurant) :
- **(F-prompt)** Garde-fou de prompt : à la résolution d'un obstacle-objectif (succès *ou* échec utile), **obliger** à surfacer 2–4 prises concrètes via `scene_update`/interactions POI (pas seulement `scene_progress_update` privé ni prose). *Cheap, mais fiabilité LLM fragile.*
- **(F-visible)** Rendre une partie de `scene_progress_update` **visible** : un panneau objectif/journal montrant « pour atteindre la source : assécher le bassin **ou** trouver le puits à sec **ou** … ». *Moyen ; réutilise une donnée déjà calculée.*
- **(Forge-spine)** La forge définit, par objectif, une **destination atteignable** + au moins une **« clé »** (condition de passage) → garantit qu'un chemin existe avant que le joueur n'y bute. *Plus robuste, plus coûteux ; évite le validateur de physique (inconstruisible, jugement LLM trop fragile — à proscrire).*

**Rattachement backlog** : **F** (généralisé à la colonne vertébrale d'objectif) + composante **forge** neuve.

---

### N4 — Économie d'indices : 3 jets ratés d'affilée, aucun *fail-forward* ✅

**Symptôme** : sur la carcasse aux veines noires, **trois** jets ratent coup sur coup — Thorvald INT (Investigation) **1**, Elara INT (Arcana) **11** vs 12, Solana INT (Religion) **6** vs 13. Résultat : **zéro information** ; la carcasse devient un **indice mort**. Le lien carcasse↔corruption n'est établi que **plus tard** à l'oasis, par le 20 naturel d'Elara.

**Lecture tabletop** : à une vraie table, un indice **nécessaire à l'intrigue** n'est jamais bloqué derrière un seul jet, et un MJ ne laisse pas le groupe rebondir 3× sur le même objet pour rien (cf. *Three Clue Rule*, *fail-forward*). Ici, trois échecs produisent **trois narrations quasi-identiques** de « malaise indéfinissable » — répétition sans escalade ni info partielle. Le moteur **sait** faire « échec utile » (`scene_progress_update` mentionne « coûts d'échec », [gm_narrate.txt:99](../backend/app/agents/prompts/gm_narrate.txt)), mais rien ne **garantit** qu'un indice-clé livre **au moins une bribe** sur échec.

**Sous-constat lié — roll-spam / saturation** : 3 compagnons enchaînent 3 compétences différentes sur **le même** objet. C'est en partie naturel (angles distincts), mais ça matérialise le motif « *tout le monde lance jusqu'à ce que quelqu'un réussisse* » — le **vecteur E1** (chemin social broadcast non plafonné, [narrative_flow_service.py:484-564](../backend/app/services/narrative_flow_service.py)).

**Rattachement backlog** : **neuf** (économie d'indices / fail-forward) + recoupe **E1**.

---

### N5 — Khalid détient un secret mais **aucun levier jouable** n'est offert ✅

**Symptôme** : Khalid est manifestement terrifié et au courant (il évite de regarder l'eau, tic nerveux, recule). Les joueurs le pressent **3×** — il **esquive 3×**. Aucun jet d'**Intuition (Insight)** pour lire « il cache quelque chose de précis », aucune option d'**Intimidation/Persuasion** surfacée, aucune horloge qui le force à craquer. Le PNJ est une **porte verrouillée sans clé visible**.

**Lecture tabletop** : à une table, un PNJ qui ment appelle un *contested Insight* (« tu sens qu'il connaît le nom de ce mal mais que la peur le musèle ») qui **donne du levier**. Ici l'interaction sociale **stagne** : pression → esquive → pression → esquive, sans progression mécanique. Même famille que N3 (le secret devrait devenir une **prise jouable**, pas une boucle de prose).

**Rattachement backlog** : **F** + neuf (PNJ-réticent → levier social surfacé).

---

## 3. Artefacts qualité-modèle (priorité basse — *cheap-regex* ou *wontfix*)

Ni structurels, ni bloquants ; à dimensionner comme bruit de modèle, pas comme lots :
- **Fuite d'anglais dans la prose française** : « *Solana s'incline… elle reconnaît **own** certain aspect putride* » — token anglais parasite (code-switching gemma4). Candidat : règle de sanitisation légère **ou** wontfix (dépend du modèle).
- **Prose de « dread » répétitive** : « *le silence du désert se referme* », « *goût d'amertume et de cendres* », « *malaise s'intensifie* », « *infection abyssale* ». Atmosphérique mais **répété** ; les 3 échecs de N4 produisent la même « horreur indéfinissable ». Rendement décroissant. Candidat : nudge de variété/escalade dans le prompt — bas.

---

## 4. Mapping au backlog A–H

| Constat (S3) | Nature | Backlog |
|---|---|---|
| **N1** double réponse PNJ | indicateur PNJ manquant + garde anti-concurrence | généralise **P4** + neuf (petit) |
| **N2** déconnexions ×2 | robustesse WS ; audio-via-bus gonfle les rafales ; **cause exacte = fork** | **neuf** ; recoupe **E1** |
| **N3** objectif sans route ni destination | affordances MJ-only + pas de nœud-destination | **F** généralisé + **forge** neuve |
| **N4** 3 échecs, pas de fail-forward + roll-spam | économie d'indices | **neuf** + recoupe **E1** |
| **N5** PNJ-secret sans levier | levier social non surfacé | **F** + neuf |
| **N6** intro origine/how sous-surfacée | résidu P3 (tension étiquette↔origine) | **P3-adjacent** (nudge prompt) |
| Fuite « own », prose répétitive | qualité-modèle | bas |

### N6 — Intro : « je sais *où*, pas *comment* ni *pourquoi* » (constat utilisateur) ✅

À isoler car **subtil** : l'ouverture établit superbement le **lieu** (Piste d'Ambre, carcasses, cap sur l'Oasis) et le guide, mais **sous-surface l'origine** : *qui* engage le groupe, *pourquoi* il traverse la Piste d'Ambre, *quel* contrat il a accepté. Le prompt `gm_open_scene.txt` **demande pourtant** « *pourquoi le groupe est là, **d'où vient la mission**, l'objectif public… et le PNJ commanditaire* » ([:27](../backend/app/agents/prompts/gm_open_scene.txt)) — mais **en tension** avec « *tisse dans la fiction, **jamais d'étiquette*** » + « *ne recopie pas l'objectif méta* » ([:33](../backend/app/agents/prompts/gm_open_scene.txt)). Le modèle a **résolu la tension en sur-indexant l'ambiance** (la soif, la corruption = le *concret*) et en **lâchant l'origine** (le *pourquoi/d'où*).

**Distinction clé** : le **contrat/pourquoi-concret** (P3) **tient** ; c'est l'**origine/comment** qui a fuité ici. Fix candidat = **nudge de prompt d'une ligne** (« même tissé en fiction, l'ouverture doit ancrer *d'où vient la mission* et *qui l'a confiée* ») **ou** renfort du **journal** (le `journal_update` existe déjà et le prompt pousse à y mettre les affordances, [:36/:39](../backend/app/agents/prompts/gm_open_scene.txt)) — **pas** de réintroduction d'étiquettes en prose. À noter : si la forge n'a peuplé qu'un `primary_objective` générique (« Découvrir ce qui menace la région »), l'ouverture n'a **rien de net** à ancrer → recoupe **N3 / forge**.

---

## 5. Plan proposé (à discuter — aucune implémentation)

Ordre par *(impact fidélité × déterminisme × coût)*. Les forks 🔶/🧩 ne se codent **pas** avant arbitrage.

| # | Lot | Contenu | Type | Priorité |
|---|---|---|---|---|
| **1** | **N1 — Indicateur + garde PNJ** | (a) publier `thinking` (kind `npc`, nom du PNJ) à l'entrée de `resolve_npc_dialogue`, éteint en `finally` (calque G/P4) ; (b) garde anti-concurrence **étroit** : si une réplique de `npc_id` est déjà en vol ce tour, coalescer/ignorer le 2ᵉ déclencheur identique — **jamais** brider les relances multi-PNJ légitimes (Oaken). | déterministe | ✅ **livré 2026-06-04** |
| **2** | **N2 — Disconnect** | ❌ **Hors scope** — tranché par l'utilisateur : provoqué par un dev back en cours pendant la partie, pas un bug applicatif (cf. §2 N2). | — | ❌ retiré |
| **3** | **N3 — Route & destination d'objectif** | 🧩 **Décidé : les deux phases** — **F-visible** (rendre les « approches encore possibles » de `scene_progress_update` cliquables) **puis** **Forge-spine** (chaque objectif clé porte une destination atteignable + ≥1 « clé »). **Pas** de validateur de physique. *Design à creuser avant code.* | 🧩 → design | 🟠 (cœur du doute utilisateur) |
| **4** | **N5 — Levier sur PNJ réticent** | Quand un PNJ esquive ≥2× sur un sujet qu'il connaît (secret/peur), surfacer une prise : *Insight* contesté (« il cache un nom précis ») + option Intimidation/Persuasion en interaction POI. Sous-cas de F. | prompt + interactions | 🟠 |
| **5** | **N4 — Fail-forward des indices-clés** | Garantir qu'un indice nécessaire livre **au moins une bribe** sur échec (échec utile), et éviter la triple-narration « horreur indéfinissable ». À coupler au **plafond E1** (anti roll-spam). | prompt + E1 | 🟡 |
| **6** | **N6 — Origine d'ouverture** | Nudge `gm_open_scene.txt` (ancrer *d'où vient la mission* / *qui l'a confiée*, sans étiquette) **ou** renfort journal. Vérifier d'abord la richesse de `primary_objective` issu de la forge (recoupe N3). | prompt léger | 🟡 |
| **7** | **E1 — Plafond compagnons IA** | (rappel backlog) Capper `_run_companion_responses` (chemin social broadcast non plafonné) — facteur commun N2 (rafales) + N4 (roll-spam). À doser en replay live. | déterministe (dosage live) | 🟡 |
| **8** | Qualité-modèle | Fuite « own » (sanitisation légère ou wontfix) ; variété de prose (nudge). | bas | ⚪ |

**Recommandation de séquence** : ~~**1**~~ ✅ livré → ~~**2**~~ ❌ hors scope → **3** (la vraie question de fond — discuter le *design* F-visible + Forge-spine avant code) → **5/4/6** (prompts) → **7** (E1, dosage live). **8** opportuniste.

> **Note de méthode** : conformément à la discipline analyse-croisée, **N3 (🧩)** reste une **décision de design** (arbitrage F-visible + Forge-spine) à creuser **avant** d'écrire la moindre ligne. *(N2 retiré ; N1 livré.)*

### Suivi d'implémentation

- **N1 ✅ livré 2026-06-04** — `resolve_npc_dialogue` scindé en **wrapper public** (résout `npc_id`, garde anti-concurrence via le champ transient `ActiveSession.npc_dialogue_in_flight`, publie l'indicateur `ai_thinking` kind `npc` en `try/finally`) + `_resolve_npc_dialogue_impl` (corps inchangé). Indicateur rendu par un kind `npc` **dédié** côté frontend → libellé **« {PNJ} répond »** (et **jamais** « Le joueur IA réfléchit ») : `game.ts` (`thinkingNpcNames` + branche `npc` dans `applyAiThinking`), `NarrativeLog.vue` (`thinkingLabel` priorise le PNJ), `types/index.ts` (`agent_kind` élargi à `'npc'`). Garde **étroit** : coalesce le 2ᵉ déclencheur **concurrent** du **même** PNJ ; une relance d'un autre PNJ ou séquentielle (Oaken) reste permise. Tests : `test_action_resolver.py::TestNpcDialogueIndicatorAndGuard` (indicateur on/off + coalescing concurrent, déterministe via `asyncio.Event`) ; `NarrativeLog.test.ts` (libellé PNJ). Vérif : backend `test_game` **376 ✓**, frontend vitest **92 ✓**, type-check ✓, ruff check+format ✓.
