"""Exporte les fixtures du banc d'essai carte (/dev/map-lab, frontend).

Scènes réelles figées depuis la base locale + scènes synthétiques passées par le
VRAI pipeline backend (normalisation, éléments d'accès, continuité d'arrivée) :

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
from app.services import scene_continuity  # noqa: E402

DB = BACKEND / "rpgmaster.db"
OUT = BACKEND.parent / "frontend" / "src" / "dev" / "mapLab" / "fixtures.generated.ts"

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
    scene = json.loads(row[0])["current_scene"]
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(fixtures, ensure_ascii=False, indent=2)
    OUT.write_text(
        "// FICHIER GÉNÉRÉ — backend/scripts/export_map_lab_fixtures.py. Ne pas éditer.\n"
        "import type { MapLabFixture } from './types'\n\n"
        f"export const MAP_LAB_FIXTURES = {body} as unknown as MapLabFixture[]\n",
        encoding="utf-8",
    )
    print(f"{len(fixtures)} fixtures → {OUT.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()
