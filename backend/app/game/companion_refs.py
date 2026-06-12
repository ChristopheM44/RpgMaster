"""Résolution partagée des références aux compagnons IA (« @nom », « Nom … »).

Source UNIQUE utilisée à la fois par le routage de narration
(``narrative_flow_service``) et par l'attribution des jets
(``gm_response_executor``). Les deux chemins DOIVENT désigner le même compagnon :
sinon le MJ narre l'action de Shade pendant que le jet de dé retombe sur l'humain
émetteur (bug #3 « jet fait au nom de Thorvald »). Garder une seule implémentation
évite que les deux détecteurs divergent.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_ref(value: Any) -> str:
    """Minuscule + sans accents, en conservant ``@`` et ``_`` (mentions/ids)."""
    normalized = unicodedata.normalize("NFKD", str(value).lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9_@]+", " ", without_accents).strip()


def companion_index(active: Any) -> dict[str, str]:
    """``{character_id: character_name}`` des compagnons IA de la session."""
    ai_players = getattr(active, "ai_players", {}) or {}
    return {
        str(char_id): str(getattr(agent, "character_name", char_id))
        for char_id, agent in ai_players.items()
    }


def resolve_companion_reference(reference: str | None, companions: dict[str, str]) -> str | None:
    """Résout une référence explicite (id ou nom exact) vers un id de compagnon."""
    if not reference:
        return None
    normalized_ref = normalize_ref(reference)
    for char_id, name in companions.items():
        if normalized_ref in {normalize_ref(char_id), normalize_ref(name)}:
            return char_id
    return None


def find_mentioned_companion(text: str, companions: dict[str, str]) -> str | None:
    """Détecte un compagnon adressé dans un texte joueur.

    Reconnaît « @nom »/« @id » n'importe où, ou le nom du compagnon en tête de
    phrase (« Shade examine… », « Shade, … », « Shade que… »). Volontairement
    conservateur : « Je demande à Shade de… » ne matche pas (c'est au MJ de poser
    ``roll_request.target`` dans ce cas).
    """
    raw = text or ""
    normalized = normalize_ref(raw)
    for char_id, name in companions.items():
        name_norm = normalize_ref(name)
        id_norm = normalize_ref(char_id)
        if re.search(rf"(^|\s)@{re.escape(name_norm)}(\s|$)", normalized):
            return char_id
        if re.search(rf"(^|\s)@{re.escape(id_norm)}(\s|$)", normalized):
            return char_id
        if normalized.startswith(f"{name_norm} ") or normalized.startswith(f"{name_norm},"):
            return char_id
        if normalized.startswith(f"{name_norm} que") or normalized.startswith(f"{name_norm} qu"):
            return char_id
    return None
