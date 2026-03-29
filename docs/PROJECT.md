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

1. **Joueur** envoie une action via WebSocket (ex: "J'ouvre la porte")
2. **Game Loop** recoit l'action, determine la phase courante
3. **GM Agent** recoit le contexte du jeu et genere une reponse structuree (JSON)
4. **Rules Engine** resout les mecaniques (jets de des, checks, degats)
5. **Game Loop** met a jour le game state
6. **Event Bus** diffuse les evenements a tous les clients connectes
7. **Frontend** affiche la narration, les resultats de des, et met a jour l'interface
8. *(Optionnel)* **Voxtral** genere l'audio de la narration en arriere-plan

### Protocole WebSocket

**Endpoint** : `/ws/game/{session_id}`

| Direction | Evenement | Description |
|-----------|-----------|-------------|
| Client → Serveur | `player_action` | Action du joueur (attaquer, parler, se deplacer...) |
| Client → Serveur | `player_choice` | Reponse a un choix propose par le MJ |
| Client → Serveur | `player_message` | Texte libre au MJ |
| Client → Serveur | `end_turn` | Fin de tour |
| Serveur → Client | `narrative` | Texte narratif du MJ (+audio optionnel) |
| Serveur → Client | `dice_result` | Resultat de jet de des avec detail |
| Serveur → Client | `combat_update` | Changement d'initiative, PV, conditions |
| Serveur → Client | `character_update` | Mise a jour de fiche (PV, sorts, inventaire) |
| Serveur → Client | `choice_prompt` | Le MJ propose des choix au joueur |
| Serveur → Client | `turn_start` | Debut du tour du joueur |
| Serveur → Client | `phase_change` | Transition de phase (exploration → combat) |
| Serveur → Client | `audio` | Audio Voxtral (base64 ou URL) |

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
