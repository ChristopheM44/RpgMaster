// FICHIER GÉNÉRÉ — backend/scripts/export_map_lab_fixtures.py. Ne pas éditer.
import type { MapLabFixture } from './types'

export const MAP_LAB_FIXTURES = [
  {
    "id": "jardin",
    "title": "Le Jardin pétrifié",
    "source": "1ab56809-5b6b-4d9a-aee2-914a3f723d84",
    "scene": {
      "cols": 12,
      "rows": 12,
      "cell_size_m": 2.0,
      "terrain": "stone",
      "scene_theme": "dungeon",
      "pois": [
        {
          "id": "feature_1",
          "name": "Arbre pétrifié massif",
          "kind": "cover",
          "position": {
            "col": 3,
            "row": 1
          },
          "icon": "c-half-cover",
          "description": "Offre un couvert partiel contre les attaques.",
          "element_id": "element_feature_1",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Examiner",
              "intent": "examine",
              "prompt": "J'examine Arbre pétrifié massif."
            },
            {
              "id": "custom_2",
              "label": "Se mettre à couvert",
              "intent": "use",
              "prompt": "Je me mets à couvert derrière Arbre pétrifié massif."
            }
          ]
        },
        {
          "id": "feature_2",
          "name": "Ronces de pierre",
          "kind": "hazard",
          "position": {
            "col": 9,
            "row": 8
          },
          "icon": "trap-danger",
          "description": "Des éclats de pierre tranchants dissimulés sous la brume.",
          "element_id": "element_feature_2",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Examiner",
              "intent": "examine",
              "prompt": "J'examine Ronces de pierre avec prudence.",
              "mechanics": {
                "safe_observation": true,
                "roll": {
                  "type": "check",
                  "ability": "int",
                  "skill": "Investigation",
                  "dc": 13,
                  "reason": "scene_poi_hazard_observation"
                },
                "reveal_tier": "interpreted"
              }
            }
          ]
        },
        {
          "id": "feature_3",
          "name": "Stèle effacée",
          "kind": "clue",
          "position": {
            "col": 9,
            "row": 5
          },
          "icon": "clue",
          "description": "Une inscription ancienne partiellement rongée par le temps.",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Examiner",
              "intent": "examine",
              "prompt": "J'examine Stèle effacée de plus près."
            }
          ],
          "element_id": "element_feature_3"
        }
      ],
      "exits": [
        {
          "id": "exit_1",
          "label": "Remonter vers l'escalier",
          "position": {
            "col": 4,
            "row": 0
          },
          "leads_to": "le_escalier_en_colimaçon",
          "description": "Le chemin du retour vers la surface.",
          "placement": "edge",
          "element_id": "element_exit_1_stairs"
        },
        {
          "id": "exit_2",
          "label": "S'enfoncer vers le Caveau",
          "position": {
            "col": 8,
            "row": 11
          },
          "leads_to": "le_caveau_du_codex",
          "description": "Un passage étroit mène vers les profondeurs ultimes.",
          "placement": "edge",
          "element_id": "element_exit_2_stairs"
        }
      ],
      "party_positions": {},
      "description": "Une serre monumentale où la flore est devenue de la pierre grise, créant un labyrinthe oppressant de statues végétales.",
      "ambiance": {
        "light": "torchlit",
        "fog_density": 0.25
      },
      "vegetation_density": 0.0,
      "elements": [
        {
          "id": "element_feature_1",
          "name": "Arbre pétrifié massif",
          "kind": "cover",
          "geometry": {
            "type": "rect",
            "col": 3.1,
            "row": 1.1,
            "width": 0.8,
            "height": 0.8
          },
          "blocks_movement": true,
          "opaque": true,
          "interactive": false,
          "asset_key": "prop/crates_stacked",
          "height_m": 1.0,
          "elevation_m": 0.0
        },
        {
          "id": "element_feature_2",
          "name": "Ronces de pierre",
          "kind": "hazard",
          "geometry": {
            "type": "ellipse",
            "col": 9.5,
            "row": 8.5,
            "radius_col": 0.5,
            "radius_row": 0.5
          },
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "height_m": 0.2,
          "elevation_m": 0.0
        },
        {
          "id": "element_feature_4",
          "name": "Fontaine tarie",
          "kind": "decor",
          "geometry": {
            "type": "rect",
            "col": 5.1,
            "row": 7.1,
            "width": 0.8,
            "height": 0.8
          },
          "blocks_movement": true,
          "opaque": true,
          "interactive": false,
          "asset_key": "prop/barrel_large",
          "height_m": 0.6,
          "elevation_m": 0.0
        },
        {
          "id": "wall_east",
          "name": "Mur est",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12,
              "row": 0
            },
            "to": {
              "col": 12,
              "row": 12
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_west",
          "name": "Mur ouest",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0,
              "row": 12
            },
            "to": {
              "col": 0,
              "row": 0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_nw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_ne",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_se",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_sw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "element_exit_1_stairs",
          "name": "Remonter vers l'escalier",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 4.0,
            "row": 0.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Le chemin du retour vers la surface.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "north",
          "vertical_direction": "up",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_exit_2_stairs",
          "name": "S'enfoncer vers le Caveau",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 8.0,
            "row": 11.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Un passage étroit mène vers les profondeurs ultimes.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "south",
          "vertical_direction": "down",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_feature_3",
          "name": "Stèle effacée",
          "kind": "decor",
          "geometry": {
            "type": "rect",
            "col": 9.15,
            "row": 5.15,
            "width": 0.7,
            "height": 0.7
          },
          "description": "Une inscription ancienne partiellement rongée par le temps.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "height_m": 0.6,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north",
          "name": "Mur nord",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0.0,
              "row": 0.0
            },
            "to": {
              "col": 4.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north_seg_2",
          "name": "Mur nord 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 5.0,
              "row": 0.0
            },
            "to": {
              "col": 12.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south",
          "name": "Mur sud",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 8.0,
              "row": 12.0
            },
            "to": {
              "col": 0.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south_seg_2",
          "name": "Mur sud 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12.0,
              "row": 12.0
            },
            "to": {
              "col": 9.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        }
      ],
      "scene_id": "scene_f6f69c90c091"
    },
    "characters": [
      {
        "id": "2eeb2fef-8353-4c5a-884b-607d8714064b",
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "is_ai": false,
        "hp_current": 12,
        "hp_max": 12
      },
      {
        "id": "bcf7d918-bfd0-4127-aa44-ec1bd33b7dbd",
        "name": "Elara",
        "char_class": "wizard",
        "species": "elf",
        "is_ai": true,
        "hp_current": 7,
        "hp_max": 7
      },
      {
        "id": "d063ed3e-0513-45da-a8ff-17dab143a882",
        "name": "Shade",
        "char_class": "rogue",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      },
      {
        "id": "e879b33a-3b47-4086-a1d4-039304985c24",
        "name": "Solana",
        "char_class": "cleric",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      }
    ]
  },
  {
    "id": "caveau",
    "title": "Le Caveau du Codex (arrivée)",
    "source": "synthétique — continuité depuis le Jardin pétrifié",
    "scene": {
      "cols": 12,
      "rows": 12,
      "cell_size_m": 1.5,
      "terrain": "crypte",
      "scene_theme": "dungeon",
      "pois": [
        {
          "id": "codex",
          "name": "Le Codex Lunaire",
          "kind": "clue",
          "position": {
            "col": 6,
            "row": 9
          },
          "icon": "marker",
          "description": "Posé sur un lutrin, protégé par un sceau.",
          "element_id": "element_codex"
        },
        {
          "id": "gardien",
          "name": "Gardien squelette",
          "kind": "enemy",
          "position": {
            "col": 8,
            "row": 9
          },
          "icon": "marker",
          "description": "Un squelette en armure rouillée."
        }
      ],
      "exits": [
        {
          "id": "retour_jardin",
          "label": "Remonter vers le Jardin pétrifié",
          "position": {
            "col": 8,
            "row": 0
          },
          "leads_to": "scene_f6f69c90c091",
          "placement": "edge",
          "facing": "north",
          "vertical_direction": "up",
          "kind": "stairs",
          "element_id": "element_retour_jardin_stairs"
        }
      ],
      "party_positions": {
        "2eeb2fef-8353-4c5a-884b-607d8714064b": {
          "col": 8,
          "row": 1
        },
        "bcf7d918-bfd0-4127-aa44-ec1bd33b7dbd": {
          "col": 7,
          "row": 1
        },
        "d063ed3e-0513-45da-a8ff-17dab143a882": {
          "col": 9,
          "row": 1
        },
        "e879b33a-3b47-4086-a1d4-039304985c24": {
          "col": 8,
          "row": 2
        }
      },
      "scene_id": "le_caveau_du_codex",
      "description": "Un caveau voûté où repose le Codex Lunaire, gardé par un mort.",
      "vegetation_density": 0.0,
      "ambiance": {
        "light": "torchlit",
        "fog_density": 0.25
      },
      "elements": [
        {
          "id": "wall_east",
          "name": "Mur est",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12,
              "row": 0
            },
            "to": {
              "col": 12,
              "row": 12
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south",
          "name": "Mur sud",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12,
              "row": 12
            },
            "to": {
              "col": 0,
              "row": 12
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_west",
          "name": "Mur ouest",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0,
              "row": 12
            },
            "to": {
              "col": 0,
              "row": 0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_nw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_ne",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_se",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_sw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "element_retour_jardin_stairs",
          "name": "Remonter vers le Jardin pétrifié",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 8.0,
            "row": 0.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "scene_f6f69c90c091",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "north",
          "vertical_direction": "up",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "table_centrale",
          "name": "Table centrale",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 4.75,
            "row": 5.25,
            "width": 2.5,
            "height": 1.5
          },
          "description": "Un meuble massif structure l'espace et peut servir de couvert.",
          "blocks_movement": true,
          "opaque": false,
          "asset_key": "prop/table_medium",
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "etagere_murale",
          "name": "Étagère murale",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 1.0,
            "row": 4.199999999999999,
            "width": 0.7,
            "height": 2.2
          },
          "description": "Un élément de décor assez haut pour masquer une partie de la vue.",
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/shelf_large",
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "element_codex",
          "name": "Le Codex Lunaire",
          "kind": "decor",
          "geometry": {
            "type": "rect",
            "col": 6.15,
            "row": 9.15,
            "width": 0.7,
            "height": 0.7
          },
          "description": "Posé sur un lutrin, protégé par un sceau.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "height_m": 0.6,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north",
          "name": "Mur nord",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0.0,
              "row": 0.0
            },
            "to": {
              "col": 8.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north_seg_2",
          "name": "Mur nord 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 9.0,
              "row": 0.0
            },
            "to": {
              "col": 12.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        }
      ],
      "arrival": {
        "exit_id": "retour_jardin",
        "from_scene_id": "scene_f6f69c90c091",
        "via_exit_id": "exit_2",
        "facing": "north",
        "vertical_direction": "up"
      }
    },
    "characters": [
      {
        "id": "2eeb2fef-8353-4c5a-884b-607d8714064b",
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "is_ai": false,
        "hp_current": 12,
        "hp_max": 12
      },
      {
        "id": "bcf7d918-bfd0-4127-aa44-ec1bd33b7dbd",
        "name": "Elara",
        "char_class": "wizard",
        "species": "elf",
        "is_ai": true,
        "hp_current": 7,
        "hp_max": 7
      },
      {
        "id": "d063ed3e-0513-45da-a8ff-17dab143a882",
        "name": "Shade",
        "char_class": "rogue",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      },
      {
        "id": "e879b33a-3b47-4086-a1d4-039304985c24",
        "name": "Solana",
        "char_class": "cleric",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      }
    ]
  },
  {
    "id": "desert",
    "title": "L'Entrée de la Vallée aride",
    "source": "37b1c4e8-f577-433d-967e-f8552716e38c",
    "scene": {
      "cols": 12,
      "rows": 12,
      "cell_size_m": 1.5,
      "terrain": "landmark",
      "scene_theme": "desert",
      "pois": [
        {
          "id": "rochers_erodes",
          "name": "Rochers érodés",
          "kind": "cover",
          "position": {
            "col": 3,
            "row": 6
          },
          "icon": "c-half-cover",
          "description": "Des blocs chauffés à blanc offrent un rare abri contre le vent de sable.",
          "action_hint": "S'abriter ou observer depuis ce couvert.",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Observer",
              "intent": "examine",
              "prompt": "J'observe rochers érodés et ce qu'on peut en tirer."
            }
          ],
          "element_id": "element_rochers_erodes"
        },
        {
          "id": "sable_traitre",
          "name": "Sable traître",
          "kind": "hazard",
          "position": {
            "col": 8,
            "row": 7
          },
          "icon": "trap-danger",
          "description": "Une nappe de sable plus sombre s'affaisse sous les rafales.",
          "action_hint": "Contourner ou tester la stabilité.",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Examiner",
              "intent": "examine",
              "prompt": "J'examine sable traître sans m'y engager.",
              "mechanics": {
                "safe_observation": true,
                "roll": {
                  "type": "check",
                  "ability": "int",
                  "skill": "Investigation",
                  "dc": 13,
                  "reason": "scene_poi_hazard_observation"
                },
                "reveal_tier": "interpreted"
              }
            }
          ],
          "element_id": "element_sable_traitre"
        },
        {
          "id": "traces_recents",
          "name": "Traces de bottes",
          "kind": "clue",
          "position": {
            "col": 4,
            "row": 4
          },
          "icon": "clue",
          "description": "Des empreintes de bottes militaires lourdes, confirmant le passage d'une troupe organisée.",
          "action_hint": "Chercher cette piste avant d'agir.",
          "interactions": [
            {
              "id": "custom_1",
              "label": "Se renseigner",
              "intent": "search",
              "prompt": "Je cherche à en savoir plus sur : Des empreintes profondes et récentes dans le sable, suggérant le passage d'un groupe armé et organisé.",
              "mechanics": {
                "safe_observation": true,
                "roll": {
                  "type": "check",
                  "ability": "int",
                  "skill": "Investigation",
                  "dc": 14,
                  "reason": "scene_poi_search"
                },
                "reveal_tier": "interpreted"
              }
            }
          ],
          "element_id": "element_traces_recents",
          "state": "discovered",
          "physical_state": "marques profondes et régulières",
          "discovered": true,
          "facts": [
            "Le groupe était armé et équipé pour le combat."
          ]
        },
        {
          "id": "guide_kaelen",
          "name": "Kaelen le Nomade",
          "kind": "npc",
          "position": {
            "col": 5,
            "row": 5
          },
          "icon": "npc",
          "description": "Un homme mince au visage tanné, drapé dans des linges de lin blanc et portant un masque protecteur remonté sur son front.",
          "action_hint": "Lui demander des précisions sur les dangers de la vallée.",
          "interactions": [
            {
              "id": "ask_details",
              "label": "Demander des précisions",
              "intent": "talk",
              "prompt": "Je demande à Kaelen le Nomade des précisions utiles, sans lui faire répéter tout le briefing.",
              "icon": "clue"
            },
            {
              "id": "read_attitude",
              "label": "Jauger le PNJ",
              "intent": "talk",
              "prompt": "J'observe Kaelen le Nomade avec perspicacité pour jauger son état et sa sincérité.",
              "icon": "clue"
            },
            {
              "id": "ask_support",
              "label": "Demander de l'aide",
              "intent": "talk",
              "prompt": "Je demande à Kaelen le Nomade s'il peut fournir une aide concrète ou une avance pour cette mission.",
              "icon": "chest"
            },
            {
              "id": "follow_objective",
              "label": "Suivre l'objectif",
              "intent": "custom",
              "prompt": "Je prends congé de Kaelen le Nomade et me prépare à suivre l'objectif indiqué.",
              "icon": "exit-dir"
            }
          ],
          "known_to_party": true
        }
      ],
      "exits": [
        {
          "id": "exit_valley",
          "label": "S'engager dans la vallée",
          "position": {
            "col": 11,
            "row": 3
          },
          "leads_to": "ruines_centrales",
          "description": "Le chemin descend vers les vestiges de la cité disparue.",
          "placement": "edge"
        },
        {
          "id": "prendre_route_objectif",
          "label": "Vers l'objectif",
          "position": {
            "col": 11,
            "row": 7
          },
          "leads_to": "recuperer_sceau_d_aethelgard",
          "description": "Se diriger vers : Récupérer le Sceau d'Aethelgard dans les ruines du désert pour le compte d'Althea Thorne.",
          "placement": "edge"
        }
      ],
      "party_positions": {
        "58241d80-21e7-4d6d-957b-e6b179f7364d": {
          "col": 5,
          "row": 6
        },
        "5d28fce7-4e03-4ea9-a503-cb92d41de7a6": {
          "col": 4,
          "row": 4
        },
        "e5131a6c-12e4-4f6f-85be-83318b850bd7": {
          "col": 7,
          "row": 6
        },
        "05f606f5-f754-458c-9329-c0324faee1e7": {
          "col": 5,
          "row": 7
        }
      },
      "scene_id": "scene_col_mirages",
      "description": "L'air vibre d'une chaleur écrasante qui fait danser l'horizon, tandis que l'odeur de soufre et de poussière brûlée sature les narines. Devant vous, deux immenses piliers de grès sculptés encadrent l'entrée d'une vallée encaissée où le sable semble couler comme du liquide.",
      "vegetation_density": 0.15,
      "ambiance": {
        "light": "day",
        "fog_density": 0.15
      },
      "elements": [
        {
          "id": "element_rochers_erodes",
          "name": "Rochers érodés",
          "kind": "cover",
          "geometry": {
            "type": "rect",
            "col": 3.15,
            "row": 6.15,
            "width": 0.7,
            "height": 0.7
          },
          "description": "Des blocs chauffés à blanc offrent un rare abri contre le vent de sable.",
          "blocks_movement": true,
          "opaque": true,
          "interactive": true,
          "height_m": 1.0,
          "elevation_m": 0.0
        },
        {
          "id": "element_sable_traitre",
          "name": "Sable traître",
          "kind": "hazard",
          "geometry": {
            "type": "ellipse",
            "col": 8.5,
            "row": 7.5,
            "radius_col": 0.45,
            "radius_row": 0.45
          },
          "description": "Une nappe de sable plus sombre s'affaisse sous les rafales.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "height_m": 0.2,
          "elevation_m": 0.0
        },
        {
          "id": "element_traces_recents",
          "name": "Traces de bottes",
          "kind": "decor",
          "geometry": {
            "type": "rect",
            "col": 4.15,
            "row": 4.15,
            "width": 0.7,
            "height": 0.7
          },
          "description": "Des empreintes profondes et récentes dans le sable, suggérant le passage d'un groupe armé et organisé.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "height_m": 0.6,
          "elevation_m": 0.0
        }
      ]
    },
    "characters": [
      {
        "id": "58241d80-21e7-4d6d-957b-e6b179f7364d",
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "is_ai": false,
        "hp_current": 12,
        "hp_max": 12
      },
      {
        "id": "5d28fce7-4e03-4ea9-a503-cb92d41de7a6",
        "name": "Elara",
        "char_class": "wizard",
        "species": "elf",
        "is_ai": true,
        "hp_current": 7,
        "hp_max": 7
      },
      {
        "id": "e5131a6c-12e4-4f6f-85be-83318b850bd7",
        "name": "Shade",
        "char_class": "rogue",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      },
      {
        "id": "05f606f5-f754-458c-9329-c0324faee1e7",
        "name": "Solana",
        "char_class": "cleric",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      }
    ]
  },
  {
    "id": "bibliotheque",
    "title": "Bibliothèque de Dragon's Rest",
    "source": "d24164e5-43b3-4c99-8c03-3544dae8e031",
    "scene": {
      "cols": 12,
      "rows": 12,
      "cell_size_m": 1.5,
      "terrain": "interior",
      "scene_theme": "dungeon",
      "pois": [
        {
          "id": "lutrin_central",
          "name": "Lutrin du catalogue",
          "kind": "clue",
          "position": {
            "col": 6,
            "row": 6
          },
          "icon": "clue",
          "description": "Un grand registre ouvert listant les fonds de la bibliothèque.",
          "action_hint": "Consulter le catalogue.",
          "element_id": "element_lutrin"
        },
        {
          "id": "rayonnage_histoire",
          "name": "Rayonnage d'Histoire",
          "kind": "clue",
          "position": {
            "col": 2,
            "row": 3
          },
          "icon": "clue",
          "description": "Des volumes traitant des guerres draconiques et de la trêve de Dragon's Rest.",
          "action_hint": "Chercher des informations sur l'île.",
          "element_id": "element_bookshelf_1",
          "state": "discovered",
          "physical_state": "pages cornées, encre pâlie",
          "discovered": true,
          "facts": [
            "Dragon's Rest est un site de trêve sacrée.",
            "La corruption actuelle brise un équilibre séculaire."
          ]
        },
        {
          "id": "archives_scellees",
          "name": "Coffre à rouleaux",
          "kind": "loot",
          "position": {
            "col": 10,
            "row": 8
          },
          "icon": "chest",
          "description": "Un coffre en fer contenant des parchemins scellés.",
          "action_hint": "Tenter d'ouvrir le coffre.",
          "element_id": "element_archives_scellees"
        }
      ],
      "exits": [
        {
          "id": "exit_cloister",
          "label": "Retourner au cloître",
          "position": {
            "col": 11,
            "row": 2
          },
          "leads_to": "dragons_rest",
          "description": "La porte menant à la cour du cloître.",
          "element_id": "door_library",
          "placement": "embedded"
        }
      ],
      "party_positions": {
        "7c56586f-ff1b-4e1f-be94-4e6ba8828a03": {
          "col": 10,
          "row": 3
        },
        "f4b0189c-b382-4c22-b07f-e9eea2a4331e": {
          "col": 10,
          "row": 3
        },
        "f70f3f88-b5a7-435c-acf0-c1e9b0d0e181": {
          "col": 10,
          "row": 8
        },
        "a3667e36-ea6a-4004-8709-9b9644d51451": {
          "col": 6,
          "row": 6
        }
      },
      "ambiance": {
        "light": "overcast",
        "fog_density": 0.1
      },
      "elements": [
        {
          "id": "door_library",
          "name": "Porte de la bibliothèque",
          "kind": "door",
          "geometry": {
            "type": "line",
            "from": {
              "col": 11.0,
              "row": 2.0
            },
            "to": {
              "col": 11.0,
              "row": 3.0
            }
          },
          "description": "Lourde porte en chêne.",
          "blocks_movement": false,
          "opaque": true,
          "interactive": true,
          "height_m": 2.2,
          "elevation_m": 0.0,
          "asset_key": "prop/door",
          "facing": "east",
          "vertical_direction": "level"
        },
        {
          "id": "element_bookshelf_1",
          "name": "Rayonnage",
          "kind": "cover",
          "geometry": {
            "type": "rect",
            "col": 2.0,
            "row": 2.0,
            "width": 0.5,
            "height": 2.0
          },
          "description": "Étagères chargées de livres.",
          "blocks_movement": true,
          "opaque": true,
          "interactive": true,
          "height_m": 1.0,
          "elevation_m": 0.0
        },
        {
          "id": "element_lutrin",
          "name": "Lutrin",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 6.0,
            "row": 6.0,
            "width": 0.5,
            "height": 0.5
          },
          "description": "Support en bois pour livres.",
          "blocks_movement": true,
          "opaque": false,
          "interactive": true,
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north",
          "name": "Mur nord",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0,
              "row": 0
            },
            "to": {
              "col": 12,
              "row": 0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_east",
          "name": "Mur est",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12,
              "row": 0
            },
            "to": {
              "col": 12,
              "row": 12
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south",
          "name": "Mur sud",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12,
              "row": 12
            },
            "to": {
              "col": 0,
              "row": 12
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_west",
          "name": "Mur ouest",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0,
              "row": 12
            },
            "to": {
              "col": 0,
              "row": 0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "element_archives_scellees",
          "name": "Coffre à rouleaux",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 10.15,
            "row": 8.15,
            "width": 0.7,
            "height": 0.7
          },
          "description": "Un coffre en fer contenant des parchemins scellés.",
          "blocks_movement": true,
          "opaque": true,
          "interactive": true,
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_nw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_ne",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_se",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_sw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        }
      ],
      "vegetation_density": 0.0,
      "scene_id": "scene_dd4cda0bb023"
    },
    "characters": [
      {
        "id": "7c56586f-ff1b-4e1f-be94-4e6ba8828a03",
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "is_ai": false,
        "hp_current": 12,
        "hp_max": 12
      },
      {
        "id": "f4b0189c-b382-4c22-b07f-e9eea2a4331e",
        "name": "Elara",
        "char_class": "wizard",
        "species": "elf",
        "is_ai": true,
        "hp_current": 7,
        "hp_max": 7
      },
      {
        "id": "f70f3f88-b5a7-435c-acf0-c1e9b0d0e181",
        "name": "Shade",
        "char_class": "rogue",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      },
      {
        "id": "a3667e36-ea6a-4004-8709-9b9644d51451",
        "name": "Solana",
        "char_class": "cleric",
        "species": "human",
        "is_ai": true,
        "hp_current": 10,
        "hp_max": 10
      }
    ]
  },
  {
    "id": "escaliers",
    "title": "Banc escaliers (4 bords)",
    "source": "synthétique — pipeline enrich_scene_layout",
    "scene": {
      "cols": 12,
      "rows": 12,
      "cell_size_m": 1.5,
      "terrain": "crypte",
      "scene_theme": "dungeon",
      "pois": [],
      "exits": [
        {
          "id": "nord_monte",
          "label": "Monter vers la tour de guet",
          "position": {
            "col": 3,
            "row": 0
          },
          "leads_to": "tour",
          "description": "Un escalier monte vers les remparts.",
          "placement": "edge",
          "element_id": "element_nord_monte_stairs"
        },
        {
          "id": "nord_descend",
          "label": "Descendre à la crypte",
          "position": {
            "col": 8,
            "row": 0
          },
          "leads_to": "crypte",
          "description": "Un escalier descend dans le noir.",
          "placement": "edge",
          "element_id": "element_nord_descend_stairs"
        },
        {
          "id": "sud_remonte",
          "label": "Remonter à la surface par les égouts",
          "position": {
            "col": 4,
            "row": 11
          },
          "leads_to": "surface",
          "description": "Une échelle remonte vers la ville.",
          "placement": "edge",
          "element_id": "element_sud_remonte_stairs"
        },
        {
          "id": "sud_descend",
          "label": "Trappe vers les égouts",
          "position": {
            "col": 9,
            "row": 11
          },
          "leads_to": "egouts",
          "description": "Une trappe s'ouvre sur des marches.",
          "placement": "edge",
          "element_id": "element_sud_descend_stairs"
        },
        {
          "id": "est_descend",
          "label": "Escalier vers le bas",
          "position": {
            "col": 11,
            "row": 5
          },
          "leads_to": "cave",
          "placement": "edge",
          "element_id": "element_est_descend_stairs"
        },
        {
          "id": "ouest_monte",
          "label": "Escalier vers le haut",
          "position": {
            "col": 0,
            "row": 6
          },
          "leads_to": "etage",
          "placement": "edge",
          "element_id": "element_ouest_monte_stairs"
        }
      ],
      "party_positions": {
        "heros": {
          "col": 6,
          "row": 6
        }
      },
      "scene_id": "banc_escaliers",
      "description": "Salle de test : un accès par bord.",
      "vegetation_density": 0.0,
      "ambiance": {
        "light": "torchlit",
        "fog_density": 0.25
      },
      "elements": [
        {
          "id": "wall_corner_nw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_ne",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 0.0,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_se",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 11.4,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_corner_sw",
          "name": "Angle de mur",
          "kind": "wall",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 11.4,
            "width": 0.6,
            "height": 0.6
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall_corner",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "element_nord_monte_stairs",
          "name": "Monter vers la tour de guet",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 3.0,
            "row": 0.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Un escalier monte vers les remparts.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "north",
          "vertical_direction": "up",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_nord_descend_stairs",
          "name": "Descendre à la crypte",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 8.0,
            "row": 0.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Un escalier descend dans le noir.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "north",
          "vertical_direction": "down",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_sud_remonte_stairs",
          "name": "Remonter à la surface par les égouts",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 4.0,
            "row": 11.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Une échelle remonte vers la ville.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "south",
          "vertical_direction": "up",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_sud_descend_stairs",
          "name": "Trappe vers les égouts",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 9.0,
            "row": 11.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "Une trappe s'ouvre sur des marches.",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "south",
          "vertical_direction": "down",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_est_descend_stairs",
          "name": "Escalier vers le bas",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 11.0,
            "row": 5.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "cave",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "east",
          "vertical_direction": "down",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "element_ouest_monte_stairs",
          "name": "Escalier vers le haut",
          "kind": "stairs",
          "geometry": {
            "type": "rect",
            "col": 0.0,
            "row": 6.0,
            "width": 1.0,
            "height": 1.0
          },
          "description": "etage",
          "blocks_movement": false,
          "opaque": false,
          "interactive": true,
          "asset_key": "prop/stairs",
          "facing": "west",
          "vertical_direction": "up",
          "height_m": 0.4,
          "elevation_m": 0.0
        },
        {
          "id": "table_centrale",
          "name": "Table centrale",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 4.75,
            "row": 5.25,
            "width": 2.5,
            "height": 1.5
          },
          "description": "Un meuble massif structure l'espace et peut servir de couvert.",
          "blocks_movement": true,
          "opaque": false,
          "asset_key": "prop/table_medium",
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "etagere_murale",
          "name": "Étagère murale",
          "kind": "furniture",
          "geometry": {
            "type": "rect",
            "col": 1.0,
            "row": 4.199999999999999,
            "width": 0.7,
            "height": 2.2
          },
          "description": "Un élément de décor assez haut pour masquer une partie de la vue.",
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/shelf_large",
          "height_m": 0.8,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north",
          "name": "Mur nord",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0.0,
              "row": 0.0
            },
            "to": {
              "col": 3.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north_seg_2",
          "name": "Mur nord 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 4.0,
              "row": 0.0
            },
            "to": {
              "col": 8.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_north_seg_3",
          "name": "Mur nord 3",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 9.0,
              "row": 0.0
            },
            "to": {
              "col": 12.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_east",
          "name": "Mur est",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12.0,
              "row": 0.0
            },
            "to": {
              "col": 12.0,
              "row": 5.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_east_seg_2",
          "name": "Mur est 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12.0,
              "row": 6.0
            },
            "to": {
              "col": 12.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south",
          "name": "Mur sud",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 4.0,
              "row": 12.0
            },
            "to": {
              "col": 0.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south_seg_2",
          "name": "Mur sud 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 9.0,
              "row": 12.0
            },
            "to": {
              "col": 5.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_south_seg_3",
          "name": "Mur sud 3",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 12.0,
              "row": 12.0
            },
            "to": {
              "col": 10.0,
              "row": 12.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_west",
          "name": "Mur ouest",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0.0,
              "row": 6.0
            },
            "to": {
              "col": 0.0,
              "row": 0.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        },
        {
          "id": "wall_west_seg_2",
          "name": "Mur ouest 2",
          "kind": "wall",
          "geometry": {
            "type": "line",
            "from": {
              "col": 0.0,
              "row": 12.0
            },
            "to": {
              "col": 0.0,
              "row": 7.0
            }
          },
          "blocks_movement": true,
          "opaque": true,
          "asset_key": "prop/wall",
          "height_m": 2.5,
          "elevation_m": 0.0
        }
      ]
    },
    "characters": [
      {
        "id": "heros",
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "is_ai": false,
        "hp_current": 12,
        "hp_max": 12
      }
    ]
  }
] as unknown as MapLabFixture[]
