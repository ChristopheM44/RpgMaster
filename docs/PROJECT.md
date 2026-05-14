# RpgMaster - Document de Projet

## Vision

RpgMaster est une application de jeu de role ou un Maitre de Jeu (MJ) propulse par l'intelligence artificielle guide un ou plusieurs joueurs a travers des aventures basees sur les regles de Donjons & Dragons SRD 5.2.

L'objectif est de permettre a quiconque de vivre une experience de JDR complete et immersive, meme en solo, grace a un MJ IA capable de narrer, gerer les combats, incarner les PNJ et adapter l'histoire en temps reel.

## Fonctionnalites principales

### Maitre de Jeu IA
- Narration dynamique et contextuelle des scenes, lieux et evenements
- Incarnation de PNJ avec des personnalites distinctes
- Gestion des rencontres (combat, social, exploration, enigmes)
- Application stricte des regles D&D SRD 5.2 via le moteur de regles
- Adaptation du rythme et de la difficulte en fonction du groupe
- Generation de dialogues vocaux via Voxtral TTS (optionnel)

### Joueurs IA (Compagnons)
- Agents IA jouant des personnages membres du groupe
- Profils de personnalite configurables (brave, prudent, cupide, noble...)
- Prise de decision basee sur les capacites du personnage et la situation
- Roleplay textuel automatique en combat et en exploration

### Joueurs Humains
- Interface web intuitive pour interagir avec le MJ IA
- Gestion de fiche de personnage (creation, progression, equipement)
- Actions en texte libre ou via boutons contextuels
- Visualisation des jets de des, du combat et du narratif

### Regles D&D SRD 5.2
- **Especes** : Humain, Elfe, Nain, Halfelin, Draconien, Gnome, Demi-Elfe, Demi-Orc, Tiefelin
- **Classes** : Barbare, Barde, Clerc, Druide, Guerrier, Moine, Paladin, Rodeur, Roublard, Ensorceleur, Occultiste, Magicien
- **Mecaniques** : Jets de des, tests de caracteristiques, jets de sauvegarde, combat (initiative, attaque, degats, mort), sorts, conditions, repos, progression par niveaux
- **Donnees** : Classes, especes, sorts, monstres, equipement, dons encodees en JSON

## Architecture technique

### Vue d'ensemble

```
┌─────────────────┐     WebSocket/REST     ┌──────────────────────┐
│                 │ ◄──────────────────────► │                      │
│   Frontend      │                         │    Backend FastAPI    │
│   Vue.js 3      │                         │                      │
│   TailwindCSS   │                         │  ┌────────────────┐  │
│                 │                         │  │  Game Loop      │  │
└─────────────────┘                         │  │  (State Machine)│  │
                                            │  └───────┬────────┘  │
                                            │          │           │
                                ┌───────────┤  ┌───────▼────────┐  │
                                │           │  │  Rules Engine   │  │
┌──────────────┐                │           │  │  (Pure Logic)   │  │
│  Ollama      │◄───────────────┤           │  └────────────────┘  │
│  (LLM texte) │                │  Agents   │                      │
└──────────────┘                │  (GM +    │  ┌────���───────────┐  │
                                │  Players) │  │  SQLite DB      │  │
┌──────────────┐                │           │  │  (Game State)   │  │
│  Voxtral TTS │◄───────────────┤           │  └────────────────┘  │
│  (vLLM-Omni) │                └───────────┤                      │
└──────────────┘                            └──────────────────────┘
```

### Flux de jeu typique

Le flux narratif complet est documente dans [NARRATIVE_FLOW.md](./NARRATIVE_FLOW.md).

En exploration :

1. **Joueur** envoie une action libre via WebSocket (ex: "@Thorin que penses-tu ?")
2. **NarrativeFlowService** detecte l'audience : MJ, monde, groupe, compagnon cible, ou mixte
3. **PlayerAgent(s)** des compagnons concernes repondent si la scene les sollicite
4. **GM Agent** arbitre ensuite seulement si l'action touche le monde, les regles ou la suite
5. **Rules Engine** resout les jets ou effets mecaniques demandes par le MJ
6. **Event Bus** diffuse dialogues, narration, jets et mises a jour d'etat
7. **Frontend** affiche les locuteurs distincts : MJ, joueur humain, compagnon, PNJ
8. *(Optionnel)* **TTS** genere l'audio de la narration en arriere-plan

Un dialogue direct avec un compagnon reste conversationnel, mais si ce compagnon choisit une action concrete (`examine`, `move`, `use_item`, `help`), sa parole visible est publiee puis le MJ reprend la main pour arbitrer la transition. Les reactions de compagnons hors combat passent par les agents individuels, y compris en mode `sober`, afin d'eviter les reponses de groupe trop generiques.

En combat :

1. **ActionResolver / ActionPipeline** resolvent l'action via le moteur de regles
2. **CombatGMAgent** narre le tour avec un contexte compact et les jets deja calcules
3. **Event Bus** diffuse `roll_result`, changements de PV/statut et narration MJ

### Services backend extraits

Depuis le Sprint 2 / Lot 2.1, `ws_game.py` reste le routeur temps reel principal,
mais les mutations metier d'equipement et de repos sont sorties dans `app/services/`.

| Service | Role | Consommateurs |
|---------|------|---------------|
| `EquipmentService` | Equiper/retirer, utiliser et lacher les objets ; synchronise DB + `ActiveSession.state_data` | REST personnages + WebSocket |
| `RestService` | Repos court/long, depense des des de vie, restauration PV/sorts/des | WebSocket |

Le modele `Character` expose maintenant `hit_dice` au format :

```json
{ "die": 10, "total": 1, "used": 0 }
```

Les personnages existants dont `hit_dice` est vide sont normalises paresseusement
depuis `char_class` + `level`. La migration Alembic associee ajoute la colonne
JSON, puis les handlers et services remplissent la valeur canonique au premier
passage.

Repos :

- **Repos court** : le frontend choisit combien de des de vie chaque personnage
  depense. Le backend lance `n d{die} + CON*n`, soigne au minimum 1 PV si un de
  est depense, plafonne a `hp_max`, puis increment `hit_dice.used`.
- **Repos long** : restaure tous les PV, remet `spell_slots.*.used = 0`, remet
  `hit_dice.used = 0`, puis repasse la session en exploration.

### Protocole WebSocket

**Endpoint** : `/ws/game/{session_id}`

| Direction | Evenement | Description |
|-----------|-----------|-------------|
| Client → Serveur | `join` | Associe la connexion au personnage humain courant |
| Client → Serveur | `action` | Action libre ou mecanique (`free_text`, `attack`, `cast_spell`, `end_turn`, etc.) |
| Client → Serveur | `action_type=short_rest` | Repos court avec `hit_dice_spend` |
| Client → Serveur | `action_type=long_rest` | Repos long ; `take_rest` reste un alias compatible |
| Client → Serveur | `action.addressed_to` | Optionnel : id ou nom du compagnon IA cible |
| Client → Serveur | `action.audience` | Optionnel : `gm`, `world`, `party`, `companion`, `mixed` |
| Client → Serveur | `action.scene_id` | Optionnel : identifiant d'echange narratif |
| Client → Serveur | `action.hit_dice_spend` | Optionnel : map `{character_id: nombre_de_des}` pour `short_rest` |
| Client → Serveur | `toggle_ai_control` | Passe un personnage en controle IA ou humain |
| Client → Serveur | `trigger_ai_reactions` | Declenchement manuel de reactions IA hors flux normal |
| Client → Serveur | `ping` | Keepalive |
| Serveur → Client | `session_state` | Etat courant de session, phase, tour, journal, quetes, chronique |
| Serveur → Client | `narration` | Narration ou dialogue avec `speaker`, `speaker_kind`, `entry_kind` optionnels |
| Serveur → Client | `roll_result` | Resultat de jet de des avec detail |
| Serveur → Client | `combat_start` / `combat_end` | Debut / fin de combat |
| Serveur → Client | `turn_start` / `turn_end` | Debut / fin de tour |
| Serveur → Client | `hp_changed`, `condition_changed`, `combatant_status_changed` | Mises a jour de combat |
| Serveur → Client | `equipment_updated`, `spell_slot_updated`, `hit_dice_updated` | Mises a jour personnage |
| Serveur → Client | `journal_updated`, `quest_updated`, `chronicle_updated` | Mises a jour canon |
| Serveur → Client | `ai_thinking` | Indique qu'un MJ ou compagnon IA reflechit |
| Serveur → Client | `audio` | Audio TTS (base64) |
| Serveur → Client | `error` / `pong` | Erreur ou reponse keepalive |

### Format de reponse du GM Agent

```json
{
  "narrative": "Le gobelin grogne et se jette sur vous...",
  "mechanical_actions": [
    {"type": "attack_roll", "actor": "goblin_1", "target": "player_1"}
  ],
  "choices_offered": [
    {"id": "fight", "text": "Combattre"},
    {"id": "flee", "text": "Fuir"},
    {"id": "negotiate", "text": "Negocier"}
  ],
  "scene_update": {"mood": "tense", "lighting": "dim"}
}
```

## Multijoueur progressif

| Phase | Description | Infrastructure |
|-------|-------------|---------------|
| Phase 1 (MVP) | 1 joueur humain + compagnons IA | Event bus in-process (`asyncio.Queue`) |
| Phase 2 | Plusieurs joueurs humains, meme serveur | Session manager multi-connexion |
| Phase 3 | Plusieurs joueurs humains via reseau | Event bus Redis pub/sub, authentification |

## Licence

- **Code** : A definir
- **Regles D&D SRD 5.2** : Creative Commons Attribution 4.0 (CC-BY-4.0)
- **Sources SRD** : https://www.dndbeyond.com/srd | [PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf)
