"""Inférence d'orientation des sorties (facing, sens vertical, type d'accès).

Régression 2026-10 : des sous-chaînes faisaient lire « c'est » comme l'est,
« haut/bas » comme nord/sud et « bassin » comme une descente. Les 6 premiers
cas sont ceux mesurés dans l'analyse (docs/plans/refonte-visuelle-cartes-2026-10.md).
"""

from __future__ import annotations

import pytest

from app.services import local_map_service as lms


def _exit(col: int, row: int, label: str, description: str = "") -> dict:
    return {
        "id": "e",
        "label": label,
        "position": {"col": col, "row": row},
        "description": description,
    }


@pytest.mark.parametrize(
    ("exit_", "facing", "kind", "vertical"),
    [
        (_exit(4, 0, "Passage", "Le passage est étroit"), "north", "door", "level"),
        (_exit(0, 6, "Escalier vers le haut", "On monte à la tour"), "west", "stairs", "up"),
        (_exit(11, 6, "Descendre au sous-sol", "Escalier vers le bas"), "east", "stairs", "down"),
        (
            _exit(6, 11, "Remonter à la surface", "Quitter les égouts par l'échelle"),
            "south",
            "stairs",
            "up",
        ),
        (
            _exit(6, 0, "Bassin de basalte", "Un escalier mène au bassin"),
            "north",
            "stairs",
            "level",
        ),
        (_exit(6, 0, "Sentier forestier", "Le chemin reste praticable"), "north", "door", "level"),
        (
            _exit(4, 11, "S'enfoncer vers le Caveau", "Un passage vers les profondeurs"),
            "south",
            "door",
            "down",
        ),
        (_exit(0, 0, "Porte", "La sortie vers l'ouest"), "west", "door", "level"),
        (_exit(11, 11, "Portail", "Au sud, la route"), "south", "door", "level"),
    ],
)
def test_exit_orientation_inference(exit_: dict, facing: str, kind: str, vertical: str) -> None:
    corpus = lms._exit_corpus(exit_)
    assert lms.infer_exit_facing(exit_, 12, 12) == facing
    assert lms._exit_access_kind(corpus) == kind
    assert lms.infer_vertical_direction(corpus) == vertical


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("vers l'est", "east"),
        ("la porte est entrouverte", None),
        ("plein est", "east"),
        ("c'est par ici", None),
        ("le chemin qui reste", None),
        ("un sentier forestier", None),
        ("plein nord", "north"),
        ("vers le haut", None),
        ("vers le bas", None),
        ("côté ouest", "west"),
    ],
)
def test_cardinal_from_text_uses_whole_words(text: str, expected: str | None) -> None:
    assert lms.cardinal_from_text(text) == expected


def test_interior_exit_without_text_has_no_facing() -> None:
    assert lms.infer_exit_facing(_exit(5, 5, "Trappe"), 12, 12) is None


def test_explicit_facing_wins() -> None:
    exit_ = _exit(0, 5, "Porte") | {"facing": "east"}
    assert lms.infer_exit_facing(exit_, 12, 12) == "east"


def test_edge_exit_position_snaps_with_whole_words() -> None:
    # Avant : « c'est » envoyait la sortie sur le bord est.
    assert lms._edge_exit_position({"col": 5, "row": 2}, "c'est au nord", 12, 12) == {
        "col": 5,
        "row": 0,
    }
