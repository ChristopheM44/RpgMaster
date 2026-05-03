# RPGMaster Icon Set — Référence d'implémentation

## Palette
| Token | Hex | Usage |
|---|---|---|
| parchment | `#f7ecd0` | Neutre, portes, obstacles |
| gold | `#f0c764` | POI, joueur, sélection, tour actif |
| ember | `#ff8247` | Cibles attaque, ennemis élite |
| arcane | `#c090ff` | IA, sorts, AoE |
| teal | `#4fd8c0` | Alliés explo, déplacement, couvert |
| blood | `#e84545` | Danger, ennemis, zone dangereuse |
| green | `#6fd96f` | Alliés combat, zone sûre |
| dim | `#6b6580` | Brouillard, zone inconnue, désactivé |

## Propriétés SVG communes
- ViewBox: `0 0 24 24`
- Stroke-width: 1.5–2px
- Stroke-linecap: round
- Fond transparent, format 1:1

## États d'interaction
| État | Style |
|---|---|
| Normal | Couleur catégorie, fond transparent |
| Hover | Fond `rgba(247,236,208,0.08)` |
| Active/Selected | Fond `rgba(240,199,100,0.12)` + box-shadow `0 0 0 2px #f0c764` + `filter: drop-shadow(0 0 4px currentColor)` |
| Disabled | `opacity: 0.3` |

## Fichiers
- `icons/color/{id}.svg` — version colorée par catégorie
- `icons/mono/{id}.svg` — version monochrome parchemin (#f7ecd0)
- `icons/icons-reference.json` — index JSON complet

## Icônes

### Exploration (16)
| # | ID | Nom | Couleur |
|---|---|---|---|
| 1 | `player-pos` | Position du joueur | `#f0c764` |
| 2 | `ally-member` | Membre du groupe | `#4fd8c0` |
| 3 | `ai-companion` | Compagnon IA | `#c090ff` |
| 4 | `exit-dir` | Sortie / direction | `#4fd8c0` |
| 5 | `secret-passage` | Passage secret | `#f0c764` |
| 6 | `door` | Porte | `#f7ecd0` |
| 7 | `poi` | Point d'intérêt | `#f0c764` |
| 8 | `clue` | Indice / examiner | `#f0c764` |
| 9 | `trap-danger` | Danger / piège | `#e84545` |
| 10 | `fog` | Brume / brouillard | `#6b6580` |
| 11 | `light` | Lumière / lanterne | `#f0c764` |
| 12 | `ruins` | Ruines / obstacle | `#f7ecd0` |
| 13 | `chest` | Coffre / objet | `#f0c764` |
| 14 | `npc` | PNJ visible | `#4fd8c0` |
| 15 | `safe-zone` | Zone sûre / refuge | `#6fd96f` |
| 16 | `unknown-zone` | Zone inconnue | `#6b6580` |

### Combat — Alliés & Tactique
| # | ID | Nom | Couleur |
|---|---|---|---|
| 1 | `c-ally` | Personnage allié | `#6fd96f` |
| 2 | `c-active-turn` | Tour actif | `#f0c764` |
| 3 | `c-selection` | Sélection courante | `#f0c764` |
| 4 | `c-move-tile` | Case accessible | `#4fd8c0` |
| 5 | `c-move-dest` | Destination déplacement | `#4fd8c0` |
| 6 | `c-atk-target` | Cible d'attaque | `#ff8247` |
| 7 | `c-spell-target` | Cible de sort | `#c090ff` |

### Combat — Ennemis
| # | ID | Nom | Couleur |
|---|---|---|---|
| 1 | `c-enemy` | Ennemi standard | `#e84545` |
| 2 | `c-enemy-elite` | Ennemi élite | `#ff8247` |
| 3 | `c-enemy-defeated` | Ennemi vaincu | `#6b6580` |
| 4 | `c-enemy-flee` | Ennemi en fuite | `#ff8247` |
| 5 | `c-enemy-surrender` | Ennemi rendu | `#f0c764` |
| 6 | `c-body-down` | Corps à terre | `#e84545` |

### Combat — Terrain & Zones
| # | ID | Nom | Couleur |
|---|---|---|---|
| 1 | `c-obstacle` | Obstacle bloquant | `#f7ecd0` |
| 2 | `c-half-cover` | Couvert partiel | `#4fd8c0` |
| 3 | `c-full-cover` | Couvert lourd | `#4fd8c0` |
| 4 | `c-difficult` | Terrain difficile | `#ff8247` |
| 5 | `c-danger-zone` | Zone dangereuse | `#e84545` |
| 6 | `c-aoe` | Zone d'effet / AoE | `#c090ff` |
| 7 | `c-los` | Ligne de vue | `#f0c764` |

## Intégration rapide
```html
<!-- Inline SVG -->
<img src="icons/color/player-pos.svg" width="24" height="24" alt="Position du joueur">

<!-- Ou en CSS -->
.icon-player { background: url('icons/color/player-pos.svg') center/contain no-repeat; width: 24px; height: 24px; }

<!-- Changement de couleur dynamique : utiliser les SVG mono + CSS filter, ou injecter le SVG inline -->
```
