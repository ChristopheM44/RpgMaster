// FICHIER GÉNÉRÉ — backend/scripts/export_map_lab_fixtures.py. Ne pas éditer.
import type { MapLabWorldFixture } from './types'

export const MAP_LAB_WORLD_FIXTURES = [
  {
    "id": "sanctuaire",
    "title": "Le Sanctuaire du Crépuscule (critère lot 5)",
    "source": "f45b6d0d",
    "region_map": {
      "id": "region",
      "name": "Carte de campagne",
      "current_node_id": "porche_larmes",
      "nodes": [
        {
          "id": "le_porche_des_larmes",
          "name": "Le Porche des Larmes",
          "kind": "settlement",
          "position": {
            "x": 30.0,
            "y": 58.0
          },
          "status": "current",
          "scene_ids": []
        },
        {
          "id": "le_c_ur_du_sanctuaire",
          "name": "Le Cœur du Sanctuaire",
          "kind": "dungeon",
          "position": {
            "x": 68.0,
            "y": 40.0
          },
          "status": "rumored",
          "scene_ids": []
        },
        {
          "id": "porche_larmes",
          "name": "L'entrée du Sanctuaire (Plaines du Crépuscule)",
          "kind": "settlement",
          "position": {
            "x": 45.0,
            "y": 58.0
          },
          "status": "visited",
          "description": "Point de départ joué en scène.",
          "scene_ids": []
        },
        {
          "id": "recuperer_codex_lunaire_dans",
          "name": "Récupérer le Codex Lunaire dans les profondeurs du Sanctuaire.",
          "kind": "landmark",
          "position": {
            "x": 62.0,
            "y": 42.0
          },
          "status": "rumored",
          "description": "Destination ou piste connue, non encore vérifiée.",
          "scene_ids": []
        }
      ],
      "edges": [
        {
          "id": "vers_le_c_ur_du_sanctuaire",
          "from": "le_porche_des_larmes",
          "to": "le_c_ur_du_sanctuaire",
          "kind": "path",
          "travel_hint": "Suivre les racines pétrifiées qui s'enfoncent vers le point le plus bas du complexe.",
          "hidden": false
        },
        {
          "id": "vers_recuperer_codex_lunaire_dans",
          "from": "porche_larmes",
          "to": "recuperer_codex_lunaire_dans",
          "kind": "path",
          "travel_hint": "Trajet à confirmer par les choix du groupe.",
          "hidden": false
        }
      ],
      "decor": {
        "forests": [
          {
            "x": 69.8,
            "y": 80.7,
            "radius": 3.5,
            "opacity": 0.35
          },
          {
            "x": 89.7,
            "y": 80.0,
            "radius": 4.2,
            "opacity": 0.44
          },
          {
            "x": 62.6,
            "y": 18.1,
            "radius": 3.5,
            "opacity": 0.48
          },
          {
            "x": 59.6,
            "y": 19.3,
            "radius": 3.1,
            "opacity": 0.41
          },
          {
            "x": 11.6,
            "y": 91.6,
            "radius": 4.0,
            "opacity": 0.36
          },
          {
            "x": 18.1,
            "y": 79.5,
            "radius": 2.6,
            "opacity": 0.49
          },
          {
            "x": 75.7,
            "y": 84.5,
            "radius": 2.8,
            "opacity": 0.36
          },
          {
            "x": 46.3,
            "y": 73.1,
            "radius": 2.6,
            "opacity": 0.33
          },
          {
            "x": 60.9,
            "y": 10.8,
            "radius": 2.9,
            "opacity": 0.45
          },
          {
            "x": 15.0,
            "y": 9.1,
            "radius": 2.5,
            "opacity": 0.42
          },
          {
            "x": 12.6,
            "y": 58.1,
            "radius": 3.6,
            "opacity": 0.39
          },
          {
            "x": 61.5,
            "y": 65.8,
            "radius": 2.7,
            "opacity": 0.45
          },
          {
            "x": 79.4,
            "y": 21.1,
            "radius": 3.6,
            "opacity": 0.37
          },
          {
            "x": 10.7,
            "y": 87.5,
            "radius": 3.9,
            "opacity": 0.4
          }
        ],
        "mountains": [
          {
            "x": 78.0,
            "y": 19.6,
            "height": 4.2
          },
          {
            "x": 88.6,
            "y": 42.7,
            "height": 6.5
          },
          {
            "x": 91.9,
            "y": 36.5,
            "height": 6.9
          },
          {
            "x": 88.9,
            "y": 40.1,
            "height": 4.1
          },
          {
            "x": 74.5,
            "y": 25.1,
            "height": 4.8
          },
          {
            "x": 71.9,
            "y": 43.1,
            "height": 7.0
          }
        ],
        "river": {
          "path": "M 0 56 Q 39 64 55 60 T 100 50",
          "width": 1.46
        },
        "decorative_roads": [
          "M 0 77 Q 54 70 91 70",
          "M 23 86 Q 46 55 97 42"
        ]
      },
      "updated_at": "2026-06-21T09:27:42.738850+00:00"
    },
    "city_maps": {
      "porche_larmes": {
        "id": "porche_larmes",
        "region_node_id": "porche_larmes",
        "name": "L'entrée du Sanctuaire (Plaines du Crépuscule)",
        "current_node_id": "point_depart",
        "nodes": [
          {
            "id": "point_depart",
            "name": "Point de départ",
            "kind": "square",
            "position": {
              "x": 45.0,
              "y": 58.0
            },
            "status": "current",
            "scene_ids": []
          },
          {
            "id": "contacts",
            "name": "Contacts et rumeurs",
            "kind": "district",
            "position": {
              "x": 28.0,
              "y": 48.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "sortie",
            "name": "Route de sortie",
            "kind": "gate",
            "position": {
              "x": 70.0,
              "y": 60.0
            },
            "status": "known",
            "scene_ids": []
          }
        ],
        "edges": [
          {
            "id": "rue_depart_contacts",
            "from": "point_depart",
            "to": "contacts",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "rue_depart_sortie",
            "from": "point_depart",
            "to": "sortie",
            "kind": "street",
            "hidden": false
          }
        ],
        "decor": {
          "forests": [
            {
              "x": 82.8,
              "y": 91.6,
              "radius": 4.1,
              "opacity": 0.36
            },
            {
              "x": 27.4,
              "y": 3.3,
              "radius": 4.0,
              "opacity": 0.48
            },
            {
              "x": 70.2,
              "y": 92.9,
              "radius": 2.7,
              "opacity": 0.36
            },
            {
              "x": 7.6,
              "y": 10.6,
              "radius": 2.1,
              "opacity": 0.37
            },
            {
              "x": 3.7,
              "y": 65.0,
              "radius": 2.1,
              "opacity": 0.39
            },
            {
              "x": 10.6,
              "y": 40.9,
              "radius": 2.7,
              "opacity": 0.39
            },
            {
              "x": 94.4,
              "y": 17.2,
              "radius": 2.5,
              "opacity": 0.47
            },
            {
              "x": 89.3,
              "y": 40.0,
              "radius": 3.8,
              "opacity": 0.38
            },
            {
              "x": 10.0,
              "y": 32.2,
              "radius": 2.2,
              "opacity": 0.49
            },
            {
              "x": 6.9,
              "y": 94.1,
              "radius": 2.3,
              "opacity": 0.48
            },
            {
              "x": 19.7,
              "y": 10.8,
              "radius": 3.3,
              "opacity": 0.36
            }
          ],
          "mountains": [],
          "river": {
            "path": "M 0 30 Q 30 27 52 29 T 100 30",
            "width": 1.84
          },
          "decorative_roads": [
            "M 0 50 Q 48 34 100 34",
            "M 10 93 Q 39 85 100 61"
          ]
        },
        "updated_at": "2026-06-21T09:19:16.693112+00:00"
      }
    },
    "active_city_id": "porche_larmes",
    "active_dungeon_id": null
  },
  {
    "id": "mirage",
    "title": "Le Mirage du Sable d'Or",
    "source": "9ae1144b",
    "region_map": {
      "id": "region",
      "name": "Carte de campagne",
      "current_node_id": "col_mirages",
      "nodes": [
        {
          "id": "le_col_des_mirages",
          "name": "Le Col des Mirages",
          "kind": "settlement",
          "position": {
            "x": 30.0,
            "y": 58.0
          },
          "status": "current",
          "scene_ids": []
        },
        {
          "id": "le_c_ur_du_sanctuaire_d_aethelgard",
          "name": "Le Cœur du Sanctuaire d'Aethelgard",
          "kind": "ruin",
          "position": {
            "x": 68.0,
            "y": 40.0
          },
          "status": "rumored",
          "scene_ids": []
        },
        {
          "id": "col_mirages",
          "name": "L'entrée de la Vallée Aride (Désert d'Or)",
          "kind": "landmark",
          "position": {
            "x": 45.0,
            "y": 58.0
          },
          "status": "current",
          "description": "Point de départ joué en scène.",
          "scene_ids": []
        },
        {
          "id": "recuperer_sceau_d_aethelgard",
          "name": "Récupérer le Sceau d'Aethelgard dans les ruines du désert pour le compte d'Althea Thorne.",
          "kind": "landmark",
          "position": {
            "x": 62.0,
            "y": 42.0
          },
          "status": "rumored",
          "description": "Destination ou piste connue, non encore vérifiée.",
          "scene_ids": []
        }
      ],
      "edges": [
        {
          "id": "vers_le_c_ur_du_sanctuaire_d_aethelgard",
          "from": "le_col_des_mirages",
          "to": "le_c_ur_du_sanctuaire_d_aethelgard",
          "kind": "path",
          "travel_hint": "Suivre les alignements de stèles solaires vers le centre de la vallée.",
          "hidden": false
        },
        {
          "id": "vers_recuperer_sceau_d_aethelgard",
          "from": "col_mirages",
          "to": "recuperer_sceau_d_aethelgard",
          "kind": "path",
          "travel_hint": "Trajet à confirmer par les choix du groupe.",
          "hidden": false
        }
      ],
      "updated_at": "2026-06-13T10:12:36.898052+00:00"
    },
    "city_maps": {},
    "active_city_id": null,
    "active_dungeon_id": null
  },
  {
    "id": "nyanzaru",
    "title": "Chronique importée — Port Nyanzaru",
    "source": "ef75d65b",
    "region_map": {
      "id": "region",
      "name": "Carte de campagne",
      "current_node_id": "quartier_port",
      "nodes": [
        {
          "id": "quartier_port",
          "name": "Port Nyanzaru (Chult)",
          "kind": "settlement",
          "position": {
            "x": 45.0,
            "y": 58.0
          },
          "status": "current",
          "description": "Point de départ joué en scène.",
          "scene_ids": []
        },
        {
          "id": "localiser_cite_perdue_d",
          "name": "Localiser la cité perdue d'Omu",
          "kind": "landmark",
          "position": {
            "x": 62.0,
            "y": 42.0
          },
          "status": "rumored",
          "description": "Destination ou piste connue, non encore vérifiée.",
          "scene_ids": []
        }
      ],
      "edges": [
        {
          "id": "route_quartier_port_localiser_cite_perdue_d",
          "from": "quartier_port",
          "to": "localiser_cite_perdue_d",
          "kind": "path",
          "travel_hint": "Trajet à confirmer par les choix du groupe.",
          "hidden": false
        }
      ],
      "updated_at": "2026-05-29T09:37:53.924904+00:00"
    },
    "city_maps": {
      "quartier_port": {
        "id": "quartier_port",
        "region_node_id": "quartier_port",
        "name": "Port Nyanzaru (Chult)",
        "current_node_id": "point_depart",
        "nodes": [
          {
            "id": "point_depart",
            "name": "Point de départ",
            "kind": "square",
            "position": {
              "x": 45.0,
              "y": 58.0
            },
            "status": "current",
            "scene_ids": []
          },
          {
            "id": "contacts",
            "name": "Contacts et rumeurs",
            "kind": "district",
            "position": {
              "x": 28.0,
              "y": 48.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "sortie",
            "name": "Route de sortie",
            "kind": "gate",
            "position": {
              "x": 70.0,
              "y": 60.0
            },
            "status": "known",
            "scene_ids": []
          }
        ],
        "edges": [
          {
            "id": "rue_depart_contacts",
            "from": "point_depart",
            "to": "contacts",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "rue_depart_sortie",
            "from": "point_depart",
            "to": "sortie",
            "kind": "street",
            "hidden": false
          }
        ],
        "updated_at": "2026-05-29T09:37:53.943494+00:00"
      }
    },
    "active_city_id": "quartier_port",
    "active_dungeon_id": null
  },
  {
    "id": "dense",
    "title": "Marches de Brume (dense)",
    "source": "synthétique — collisions, routes typées, échelle",
    "region_map": {
      "id": "region_dense",
      "name": "Marches de Brume (synthétique)",
      "current_node_id": "port_aux_brumes",
      "nodes": [
        {
          "id": "havre_gris",
          "name": "Havre-Gris",
          "kind": "settlement",
          "position": {
            "x": 22.0,
            "y": 62.0
          },
          "status": "visited",
          "scene_ids": []
        },
        {
          "id": "port_aux_brumes",
          "name": "Port-aux-Brumes",
          "kind": "settlement",
          "position": {
            "x": 30.0,
            "y": 66.0
          },
          "status": "current",
          "scene_ids": []
        },
        {
          "id": "foret_murmures",
          "name": "Forêt des Murmures",
          "kind": "wilderness",
          "position": {
            "x": 36.0,
            "y": 48.0
          },
          "status": "known",
          "scene_ids": []
        },
        {
          "id": "tour_veilleur",
          "name": "Tour du Veilleur",
          "kind": "landmark",
          "position": {
            "x": 41.0,
            "y": 52.0
          },
          "status": "visited",
          "scene_ids": []
        },
        {
          "id": "col_des_vents",
          "name": "Col des Vents",
          "kind": "landmark",
          "position": {
            "x": 58.0,
            "y": 30.0
          },
          "status": "known",
          "scene_ids": []
        },
        {
          "id": "mines_de_fer",
          "name": "Mines de Fer-Noir",
          "kind": "dungeon",
          "position": {
            "x": 63.0,
            "y": 34.0
          },
          "status": "known",
          "scene_ids": []
        },
        {
          "id": "ruines_aethel",
          "name": "Ruines d'Aethel",
          "kind": "ruin",
          "position": {
            "x": 74.0,
            "y": 22.0
          },
          "status": "rumored",
          "scene_ids": []
        },
        {
          "id": "carrefour",
          "name": "Carrefour des Pendus",
          "kind": "crossroads",
          "position": {
            "x": 50.0,
            "y": 58.0
          },
          "status": "known",
          "scene_ids": []
        },
        {
          "id": "sanctuaire_lune",
          "name": "Sanctuaire de la Lune pâle, au-delà des marais",
          "kind": "dungeon",
          "position": {
            "x": 80.0,
            "y": 70.0
          },
          "status": "rumored",
          "scene_ids": []
        }
      ],
      "edges": [
        {
          "id": "havre_gris__port_aux_brumes",
          "from": "havre_gris",
          "to": "port_aux_brumes",
          "kind": "road",
          "travel_hint": "Une demi-journée par la route côtière.",
          "hidden": false
        },
        {
          "id": "port_aux_brumes__carrefour",
          "from": "port_aux_brumes",
          "to": "carrefour",
          "kind": "road",
          "travel_hint": "2 jours de marche.",
          "hidden": false
        },
        {
          "id": "carrefour__tour_veilleur",
          "from": "carrefour",
          "to": "tour_veilleur",
          "kind": "path",
          "travel_hint": "1 jour par le sentier.",
          "hidden": false
        },
        {
          "id": "tour_veilleur__foret_murmures",
          "from": "tour_veilleur",
          "to": "foret_murmures",
          "kind": "path",
          "hidden": false
        },
        {
          "id": "carrefour__col_des_vents",
          "from": "carrefour",
          "to": "col_des_vents",
          "kind": "road",
          "travel_hint": "3 jours, la route monte.",
          "hidden": false
        },
        {
          "id": "col_des_vents__mines_de_fer",
          "from": "col_des_vents",
          "to": "mines_de_fer",
          "kind": "path",
          "hidden": false
        },
        {
          "id": "mines_de_fer__ruines_aethel",
          "from": "mines_de_fer",
          "to": "ruines_aethel",
          "kind": "path",
          "hidden": false
        },
        {
          "id": "havre_gris__sanctuaire_lune",
          "from": "havre_gris",
          "to": "sanctuaire_lune",
          "kind": "sea_route",
          "travel_hint": "4 jours de navigation.",
          "hidden": false
        },
        {
          "id": "foret_murmures__ruines_aethel",
          "from": "foret_murmures",
          "to": "ruines_aethel",
          "kind": "secret",
          "hidden": false
        }
      ],
      "updated_at": "2026-10-11T18:15:24.987865+00:00"
    },
    "city_maps": {
      "ville_dense": {
        "id": "ville_dense",
        "region_node_id": "port_aux_brumes",
        "name": "Port-aux-Brumes (synthétique)",
        "current_node_id": "taverne",
        "nodes": [
          {
            "id": "place",
            "name": "Place du Phare",
            "kind": "square",
            "position": {
              "x": 50.0,
              "y": 52.0
            },
            "status": "visited",
            "scene_ids": []
          },
          {
            "id": "taverne",
            "name": "Le Hareng Saur",
            "kind": "tavern",
            "position": {
              "x": 40.0,
              "y": 46.0
            },
            "status": "current",
            "scene_ids": []
          },
          {
            "id": "temple",
            "name": "Temple des Marées",
            "kind": "temple",
            "position": {
              "x": 62.0,
              "y": 40.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "docks",
            "name": "Les Docks",
            "kind": "docks",
            "position": {
              "x": 52.0,
              "y": 74.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "marche",
            "name": "Quartier des Marchands",
            "kind": "district",
            "position": {
              "x": 30.0,
              "y": 60.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "echoppe",
            "name": "Échoppe d'Odran",
            "kind": "shop",
            "position": {
              "x": 33.0,
              "y": 64.0
            },
            "status": "known",
            "scene_ids": []
          },
          {
            "id": "palais",
            "name": "Palais du Prévôt",
            "kind": "palace",
            "position": {
              "x": 68.0,
              "y": 28.0
            },
            "status": "rumored",
            "scene_ids": []
          },
          {
            "id": "porte_nord",
            "name": "Porte du Nord",
            "kind": "gate",
            "position": {
              "x": 52.0,
              "y": 18.0
            },
            "status": "known",
            "scene_ids": []
          }
        ],
        "edges": [
          {
            "id": "e1",
            "from": "place",
            "to": "taverne",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "e2",
            "from": "place",
            "to": "temple",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "e3",
            "from": "place",
            "to": "docks",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "e4",
            "from": "place",
            "to": "marche",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "e5",
            "from": "marche",
            "to": "echoppe",
            "kind": "alley",
            "hidden": false
          },
          {
            "id": "e6",
            "from": "temple",
            "to": "palais",
            "kind": "street",
            "hidden": false
          },
          {
            "id": "e7",
            "from": "temple",
            "to": "porte_nord",
            "kind": "street",
            "hidden": false
          }
        ],
        "updated_at": "2026-10-11T18:15:24.987905+00:00"
      }
    },
    "active_city_id": "ville_dense",
    "active_dungeon_id": null
  }
] as unknown as MapLabWorldFixture[]
