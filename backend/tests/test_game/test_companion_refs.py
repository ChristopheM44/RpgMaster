from __future__ import annotations

from types import SimpleNamespace

from app.game import companion_refs


def _active(names: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        ai_players={cid: SimpleNamespace(character_name=name) for cid, name in names.items()}
    )


def test_companion_index_maps_id_to_name() -> None:
    active = _active({"shade": "Shade", "elara": "Elara"})
    assert companion_refs.companion_index(active) == {"shade": "Shade", "elara": "Elara"}


def test_find_mentioned_companion_at_mention() -> None:
    companions = {"shade": "Shade", "elara": "Elara"}
    assert (
        companion_refs.find_mentioned_companion("@shade vas examiner le ruisseau", companions)
        == "shade"
    )


def test_find_mentioned_companion_leading_name() -> None:
    companions = {"shade": "Shade"}
    find = companion_refs.find_mentioned_companion
    assert find("Shade examine le ruisseau", companions) == "shade"
    assert find("Shade, surveille la porte", companions) == "shade"


def test_find_mentioned_companion_conservative_no_match() -> None:
    """« Je demande à X de… » ne matche pas : c'est au MJ de poser roll_request.target."""
    companions = {"shade": "Shade", "elara": "Elara"}
    # Mention non-initiale et sans @ : on n'attribue pas le jet au compagnon.
    assert (
        companion_refs.find_mentioned_companion("Je demande à Elara ce qu'elle ressent", companions)
        is None
    )
    assert companion_refs.find_mentioned_companion("J'examine le ruisseau", companions) is None


def test_resolve_companion_reference_exact_id_or_name() -> None:
    companions = {"shade": "Shade"}
    assert companion_refs.resolve_companion_reference("Shade", companions) == "shade"
    assert companion_refs.resolve_companion_reference("shade", companions) == "shade"
    assert companion_refs.resolve_companion_reference("inconnu", companions) is None
