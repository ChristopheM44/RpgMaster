"""Exporte les fixtures du banc d'essai carte (/dev/map-lab, frontend).

Scènes réelles figées depuis la base locale (réparées comme au chargement d'une
session) + scènes synthétiques passées par le VRAI pipeline backend (normalisation,
éléments d'accès, continuité d'arrivée) :

    cd backend && .venv/bin/python scripts/export_map_lab_fixtures.py

Écrit ``frontend/src/dev/mapLab/fixtures.generated.ts``. Relancer après un
changement du pipeline de carte pour comparer avant/après à données égales.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.game.gm_response_executor import GMResponseExecutor  # noqa: E402
from app.services import map_service, scene_continuity  # noqa: E402
from app.services.campaign_dossier_service import public_campaign_maps  # noqa: E402
from app.services.visual_coherence_service import repair_state_visual_coherence  # noqa: E402

DB = BACKEND / "rpgmaster.db"
OUT = BACKEND.parent / "frontend" / "src" / "dev" / "mapLab" / "fixtures.generated.ts"
WORLD_OUT = BACKEND.parent / "frontend" / "src" / "dev" / "mapLab" / "worldFixtures.generated.ts"

# Cartes Région/Ville réelles : projection PUBLIQUE (celle que reçoit le joueur).
REAL_WORLD_MAPS = [
    ("sanctuaire", "Le Sanctuaire du Crépuscule (critère lot 5)", "f45b6d0d"),
    ("mirage", "Le Mirage du Sable d'Or", "9ae1144b"),
    ("nyanzaru", "Chronique importée — Port Nyanzaru", "ef75d65b"),
]

REAL_SCENES = [
    ("jardin", "Le Jardin pétrifié", "1ab56809-5b6b-4d9a-aee2-914a3f723d84"),
    ("desert", "L'Entrée de la Vallée aride", "37b1c4e8-f577-433d-967e-f8552716e38c"),
    ("bibliotheque", "Bibliothèque de Dragon's Rest", "d24164e5-43b3-4c99-8c03-3544dae8e031"),
]


def _load(conn: sqlite3.Connection, session_id: str) -> tuple[dict, list[dict]]:
    row = conn.execute(
        "select state_data from game_states where session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"session absente de la base : {session_id}")
    state_data = json.loads(row[0])
    # Même réparation qu'au chargement d'une session (session_state enrichi) :
    # modèles cohérents avec les noms, habillage du lieu (lot 4)…
    repair_state_visual_coherence(state_data)
    scene = state_data["current_scene"]
    characters = [
        {
            "id": cid,
            "name": name,
            "char_class": cls,
            "species": species,
            "is_ai": bool(is_ai),
            "hp_current": hp,
            "hp_max": hp_max,
        }
        for cid, name, cls, species, is_ai, hp, hp_max in conn.execute(
            "select id, name, char_class, species, is_ai, hp_current, hp_max "
            "from characters where session_id = ? order by is_ai, name",
            (session_id,),
        )
    ]
    return scene, characters


def _apply(old_scene: dict | None, raw: dict, party_ids: list[str] | None = None) -> dict:
    """Même chemin que GMResponseExecutor._apply_scene_layout (sans event bus)."""
    arrival = scene_continuity.prepare_arrival(old_scene, raw)
    layout = GMResponseExecutor._normalize_scene_layout({"scene": raw})
    scene_continuity.finalize_arrival(layout, arrival, old_scene, party_ids=party_ids)
    return layout


def _caveau(jardin: dict, party_ids: list[str]) -> dict:
    return _apply(
        jardin,
        {
            "scene_id": "le_caveau_du_codex",
            "scene_theme": "dungeon",
            "terrain": "crypte",
            "description": "Un caveau voûté où repose le Codex Lunaire, gardé par un mort.",
            "exits": [
                {
                    "id": "retour_jardin",
                    "label": "Remonter vers le Jardin pétrifié",
                    "position": {"col": 3, "row": 6},
                    "leads_to": jardin["scene_id"],
                }
            ],
            "pois": [
                {
                    "id": "codex",
                    "name": "Le Codex Lunaire",
                    "kind": "clue",
                    "position": {"col": 6, "row": 9},
                    "description": "Posé sur un lutrin, protégé par un sceau.",
                },
                {
                    "id": "gardien",
                    "name": "Gardien squelette",
                    "kind": "enemy",
                    "position": {"col": 8, "row": 9},
                    "description": "Un squelette en armure rouillée.",
                },
            ],
            "party_positions": copy.deepcopy(jardin.get("party_positions") or {}),
        },
        party_ids,
    )


def _stairs_test() -> dict:
    """Une montée et une descente par bord : le sens doit se lire sans légende."""
    return _apply(
        None,
        {
            "scene_id": "banc_escaliers",
            "scene_theme": "dungeon",
            "terrain": "crypte",
            "description": "Salle de test : un accès par bord.",
            "exits": [
                {
                    "id": "nord_monte",
                    "label": "Monter vers la tour de guet",
                    "position": {"col": 3, "row": 0},
                    "leads_to": "tour",
                    "description": "Un escalier monte vers les remparts.",
                },
                {
                    "id": "nord_descend",
                    "label": "Descendre à la crypte",
                    "position": {"col": 8, "row": 0},
                    "leads_to": "crypte",
                    "description": "Un escalier descend dans le noir.",
                },
                {
                    "id": "sud_remonte",
                    "label": "Remonter à la surface par les égouts",
                    "position": {"col": 4, "row": 11},
                    "leads_to": "surface",
                    "description": "Une échelle remonte vers la ville.",
                },
                {
                    "id": "sud_descend",
                    "label": "Trappe vers les égouts",
                    "position": {"col": 9, "row": 11},
                    "leads_to": "egouts",
                    "description": "Une trappe s'ouvre sur des marches.",
                },
                {
                    "id": "est_descend",
                    "label": "Escalier vers le bas",
                    "position": {"col": 11, "row": 5},
                    "leads_to": "cave",
                },
                {
                    "id": "ouest_monte",
                    "label": "Escalier vers le haut",
                    "position": {"col": 0, "row": 6},
                    "leads_to": "etage",
                },
            ],
            "pois": [],
            "party_positions": {"heros": {"col": 6, "row": 6}},
        },
    )


def _tavern() -> dict:
    """Intérieur en thème « city » : doit être rendu clos (plancher, torches), pas en plein air."""
    return _apply(
        None,
        {
            "scene_id": "taverne_lys_pale",
            "scene_theme": "city",
            "terrain": "taverne",
            "description": "La salle commune enfumée de l'Auberge du Lys pâle.",
            "exits": [
                {
                    "id": "porte_rue",
                    "label": "Sortir dans la rue",
                    "position": {"col": 6, "row": 11},
                    "leads_to": "place_du_marche",
                },
                {
                    "id": "escalier_chambres",
                    "label": "Monter aux chambres",
                    "position": {"col": 0, "row": 3},
                    "leads_to": "chambres",
                    "description": "Un escalier de bois monte à l'étage.",
                },
            ],
            "pois": [
                {
                    "id": "aubergiste",
                    "name": "Maître Odran, l'aubergiste",
                    "kind": "npc",
                    "position": {"col": 8, "row": 4},
                }
            ],
            "party_positions": {"heros": {"col": 6, "row": 8}},
        },
    )


def main() -> None:
    conn = sqlite3.connect(DB)
    fixtures = []
    jardin_scene = None
    for fixture_id, title, session_id in REAL_SCENES:
        scene, characters = _load(conn, session_id)
        fixtures.append(
            {
                "id": fixture_id,
                "title": title,
                "source": session_id,
                "scene": scene,
                "characters": characters,
            }
        )
        if fixture_id == "jardin":
            jardin_scene, jardin_characters = scene, characters
    assert jardin_scene is not None
    fixtures.insert(
        1,
        {
            "id": "caveau",
            "title": "Le Caveau du Codex (arrivée)",
            "source": "synthétique — continuité depuis le Jardin pétrifié",
            "scene": _caveau(jardin_scene, [c["id"] for c in jardin_characters]),
            "characters": jardin_characters,
        },
    )
    fixtures.append(
        {
            "id": "escaliers",
            "title": "Banc escaliers (4 bords)",
            "source": "synthétique — pipeline enrich_scene_layout",
            "scene": _stairs_test(),
            "characters": [
                {
                    "id": "heros",
                    "name": "Thorvald",
                    "char_class": "fighter",
                    "species": "human",
                    "is_ai": False,
                    "hp_current": 12,
                    "hp_max": 12,
                }
            ],
        }
    )
    fixtures.append(
        {
            "id": "taverne",
            "title": "Taverne (thème ville)",
            "source": "synthétique — intérieur en thème city",
            "scene": _tavern(),
            "characters": [
                {
                    "id": "heros",
                    "name": "Thorvald",
                    "char_class": "fighter",
                    "species": "human",
                    "is_ai": False,
                    "hp_current": 12,
                    "hp_max": 12,
                }
            ],
        }
    )
    _export_world_maps(conn)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(fixtures, ensure_ascii=False, indent=2)
    OUT.write_text(
        "// FICHIER GÉNÉRÉ — backend/scripts/export_map_lab_fixtures.py. Ne pas éditer.\n"
        "import type { MapLabFixture } from './types'\n\n"
        f"export const MAP_LAB_FIXTURES = {body} as unknown as MapLabFixture[]\n",
        encoding="utf-8",
    )
    print(f"{len(fixtures)} fixtures → {OUT.relative_to(BACKEND.parent)}")


def _dense_region() -> dict:
    """Région synthétique dense : lieux voisins, noms longs, routes typées et chiffrées."""
    nodes = [
        ("havre_gris", "Havre-Gris", "settlement", "visited", 22, 62),
        ("port_aux_brumes", "Port-aux-Brumes", "settlement", "current", 30, 66),
        ("foret_murmures", "Forêt des Murmures", "wilderness", "known", 36, 48),
        ("tour_veilleur", "Tour du Veilleur", "landmark", "visited", 41, 52),
        ("col_des_vents", "Col des Vents", "landmark", "known", 58, 30),
        ("mines_de_fer", "Mines de Fer-Noir", "dungeon", "known", 63, 34),
        ("ruines_aethel", "Ruines d'Aethel", "ruin", "rumored", 74, 22),
        ("carrefour", "Carrefour des Pendus", "crossroads", "known", 50, 58),
        (
            "sanctuaire_lune",
            "Sanctuaire de la Lune pâle, au-delà des marais",
            "dungeon",
            "rumored",
            80,
            70,
        ),
    ]
    edges = [
        ("havre_gris", "port_aux_brumes", "road", "Une demi-journée par la route côtière."),
        ("port_aux_brumes", "carrefour", "road", "2 jours de marche."),
        ("carrefour", "tour_veilleur", "path", "1 jour par le sentier."),
        ("tour_veilleur", "foret_murmures", "path", None),
        ("carrefour", "col_des_vents", "road", "3 jours, la route monte."),
        ("col_des_vents", "mines_de_fer", "path", None),
        ("mines_de_fer", "ruines_aethel", "path", None),
        ("havre_gris", "sanctuaire_lune", "sea_route", "4 jours de navigation."),
        ("foret_murmures", "ruines_aethel", "secret", None),
    ]
    raw = {
        "id": "region_dense",
        "name": "Marches de Brume (synthétique)",
        "current_node_id": "port_aux_brumes",
        "nodes": [
            {"id": i, "name": n, "kind": k, "status": st, "position": {"x": x, "y": y}}
            for i, n, k, st, x, y in nodes
        ],
        "edges": [
            {"id": f"{a}__{b}", "from": a, "to": b, "kind": kind, "travel_hint": hint}
            for a, b, kind, hint in edges
        ]
        + [{"id": "cache", "from": "tour_veilleur", "to": "mines_de_fer", "hidden": True}],
    }
    return map_service.public_region_map(raw)


def _dense_city() -> dict:
    raw = {
        "id": "ville_dense",
        "region_node_id": "port_aux_brumes",
        "name": "Port-aux-Brumes (synthétique)",
        "current_node_id": "taverne",
        "nodes": [
            {
                "id": "place",
                "name": "Place du Phare",
                "kind": "square",
                "status": "visited",
                "position": {"x": 50, "y": 52},
            },
            {
                "id": "taverne",
                "name": "Le Hareng Saur",
                "kind": "tavern",
                "status": "current",
                "position": {"x": 40, "y": 46},
            },
            {
                "id": "temple",
                "name": "Temple des Marées",
                "kind": "temple",
                "status": "known",
                "position": {"x": 62, "y": 40},
            },
            {
                "id": "docks",
                "name": "Les Docks",
                "kind": "docks",
                "status": "known",
                "position": {"x": 52, "y": 74},
            },
            {
                "id": "marche",
                "name": "Quartier des Marchands",
                "kind": "district",
                "status": "known",
                "position": {"x": 30, "y": 60},
            },
            {
                "id": "echoppe",
                "name": "Échoppe d'Odran",
                "kind": "shop",
                "status": "known",
                "position": {"x": 33, "y": 64},
            },
            {
                "id": "palais",
                "name": "Palais du Prévôt",
                "kind": "palace",
                "status": "rumored",
                "position": {"x": 68, "y": 28},
            },
            {
                "id": "porte_nord",
                "name": "Porte du Nord",
                "kind": "gate",
                "status": "known",
                "position": {"x": 52, "y": 18},
            },
        ],
        "edges": [
            {"id": "e1", "from": "place", "to": "taverne", "kind": "street"},
            {"id": "e2", "from": "place", "to": "temple", "kind": "street"},
            {"id": "e3", "from": "place", "to": "docks", "kind": "street"},
            {"id": "e4", "from": "place", "to": "marche", "kind": "street"},
            {"id": "e5", "from": "marche", "to": "echoppe", "kind": "alley"},
            {"id": "e6", "from": "temple", "to": "palais", "kind": "street"},
            {"id": "e7", "from": "temple", "to": "porte_nord", "kind": "street"},
        ],
    }
    return map_service.public_city_map(raw)


def _export_world_maps(conn: sqlite3.Connection) -> None:
    fixtures = []
    for fixture_id, title, campaign_prefix in REAL_WORLD_MAPS:
        row = conn.execute(
            "select gm_dossier from campaign_dossiers where campaign_id like ?",
            (f"{campaign_prefix}%",),
        ).fetchone()
        if row is None:
            raise SystemExit(f"campagne absente de la base : {campaign_prefix}")
        maps = public_campaign_maps(json.loads(row[0]))
        fixtures.append({"id": fixture_id, "title": title, "source": campaign_prefix, **maps})
    fixtures.append(
        {
            "id": "dense",
            "title": "Marches de Brume (dense)",
            "source": "synthétique — collisions, routes typées, échelle",
            "region_map": _dense_region(),
            "city_maps": {"ville_dense": _dense_city()},
            "active_city_id": "ville_dense",
            "active_dungeon_id": None,
        }
    )
    body = json.dumps(fixtures, ensure_ascii=False, indent=2)
    WORLD_OUT.write_text(
        "// FICHIER GÉNÉRÉ — backend/scripts/export_map_lab_fixtures.py. Ne pas éditer.\n"
        "import type { MapLabWorldFixture } from './types'\n\n"
        f"export const MAP_LAB_WORLD_FIXTURES = {body} as unknown as MapLabWorldFixture[]\n",
        encoding="utf-8",
    )
    print(f"{len(fixtures)} cartes 2D → {WORLD_OUT.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()
