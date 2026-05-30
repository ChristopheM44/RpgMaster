"""Détection déterministe de l'intention de voyage dans le texte joueur.

Ce module identifie quand un joueur exprime une volonté de se déplacer vers
un lieu et extrait la destination mentionnée, en la croisant avec les sorties
de la scène courante et les noeuds de carte régionaux disponibles.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TravelIntent:
    """Intention de voyage détectée dans le texte du joueur."""

    is_travel: bool = False
    destination: str | None = None
    destination_node_id: str | None = None
    confidence: str = "implicit"  # "explicit" ou "implicit"


# --- Marqueurs de voyage en français et anglais ---

_TRAVEL_MARKERS_EXPLICIT: tuple[str, ...] = (
    "je me dirige vers",
    "je me dirige a",
    "je vais a",
    "je vais vers",
    "je vais au",
    "je vais a la",
    "je vais a l",
    "je pars vers",
    "je pars a",
    "je pars pour",
    "je me rends a",
    "je me rends vers",
    "je me rends au",
    "nous allons a",
    "nous allons vers",
    "nous allons au",
    "nous partons vers",
    "nous partons a",
    "nous partons pour",
    "nous nous dirigeons vers",
    "nous nous rendons a",
    "nous nous rends au",
    "je voyage vers",
    "je voyage a",
    "en route vers",
    "en route pour",
    "je prends la route pour",
    "je prends la route vers",
    "je prends le chemin de",
    "nous nous rendons a",
    "nous nous rendons au",
    "heading to",
    "go to",
    "travel to",
    "i walk to",
    "we go to",
    "we travel to",
    "set off for",
    "make my way to",
    "i head to",
    "we head to",
    "i head toward",
    "we head toward",
    "on the way to",
    "on our way to",
)

_TRAVEL_MARKERS_IMPLICIT: tuple[str, ...] = (
    "j avance",
    "je continue",
    "je marche",
    "nous marchons",
    "nous avanc",
    "je suis le chemin",
    "je suis la route",
    "je suis le sentier",
    "i keep walking",
    "i keep going",
    "we keep going",
    "i continue on",
    "we continue on",
)

# Lieux communs qui peuvent apparaître après un marqueur
_PLACE_ARTICLES: tuple[str, ...] = (
    "l ",
    "la ",
    "le ",
    "les ",
    "un ",
    "une ",
    "des ",
    "du ",
    "au ",
    "aux ",
)


def _normalize_text(text: str) -> str:
    """Normalise le texte pour la comparaison : accents, casse, ponctuation."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_accents


def _extract_destination_after_marker(
    normalized_text: str,
    marker: str,
) -> str | None:
    """Extrait la destination mentionnée après un marqueur de voyage."""
    idx = normalized_text.find(marker)
    if idx == -1:
        return None
    after = normalized_text[idx + len(marker) :].strip()
    # Enlever les articles pour obtenir le nom du lieu
    for article in _PLACE_ARTICLES:
        if after.startswith(article):
            after = after[len(article) :].strip()
            break
    if not after:
        return None
    # Prendre jusqu'à la première ponctuation ou fin de phrase
    end = len(after)
    for sep in (".", ",", ";", "!", "?", "—", " et ", " puis ", " avant ", " mais "):
        pos = after.find(sep)
        if pos > 0 and pos < end:
            end = pos
    result = after[:end].strip()
    return result if len(result) >= 2 else None


def _match_destination_to_state(
    destination: str,
    state_data: dict[str, Any],
) -> str | None:
    """Croise la destination avec les sorties de scène et les noeuds de carte.

    Retourne l'ID du noeud/sortie correspondant, ou None si pas de match.
    """
    dest_norm = _normalize_text(destination)
    if not dest_norm:
        return None

    # 1. Chercher dans les sorties de la scène courante
    scene = state_data.get("current_scene") or {}
    if isinstance(scene, dict):
        for exit_data in scene.get("exits") or []:
            if not isinstance(exit_data, dict):
                continue
            exit_label = _normalize_text(str(exit_data.get("label") or ""))
            exit_leads = _normalize_text(str(exit_data.get("leads_to") or ""))
            exit_id = str(exit_data.get("id") or "")
            if dest_norm in exit_label or exit_label in dest_norm:
                return exit_leads or exit_id
            if dest_norm in exit_leads or exit_leads in dest_norm:
                return exit_leads or exit_id

    # 2. Chercher dans les noeuds de la carte régionale
    world_maps = state_data.get("world_maps") or {}
    if isinstance(world_maps, dict):
        region_map = world_maps.get("region_map") or {}
        if isinstance(region_map, dict):
            for node in region_map.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                node_name = _normalize_text(str(node.get("name") or ""))
                node_id = str(node.get("id") or "")
                if dest_norm in node_name or node_name in dest_norm:
                    return node_id

    # 3. Chercher dans les POI de la scène (certains POI sont des sorties)
    if isinstance(scene, dict):
        for poi in scene.get("pois") or []:
            if not isinstance(poi, dict):
                continue
            poi_name = _normalize_text(str(poi.get("name") or ""))
            if dest_norm in poi_name or poi_name in dest_norm:
                # Vérifier si ce POI a une interaction de type "approach" vers une sortie
                for interaction in poi.get("interactions") or []:
                    if not isinstance(interaction, dict):
                        continue
                    intent = str(interaction.get("intent") or "").lower()
                    if intent in ("approach", "use", "custom"):
                        return str(interaction.get("prompt") or poi.get("id") or "")
                return str(poi.get("id") or "")

    return None


def detect_travel_intent(
    player_text: str,
    state_data: dict[str, Any],
) -> TravelIntent:
    """Détecte l'intention de voyage dans le texte du joueur.

    Analyse le texte pour trouver des marqueurs de déplacement explicites ou
    implicites, extrait la destination et la croise avec les données de la
    scène (sorties) et de la carte (noeuds régionaux).

    Args:
        player_text: Texte libre du joueur (non normalisé).
        state_data: État de la session (contient current_scene, world_maps, etc.)

    Returns:
        TravelIntent avec is_travel=True si un déplacement est détecté,
        la destination extraite et optionnellement un destination_node_id
        correspondant à une sortie ou un noeud de carte connu.
    """
    if not player_text:
        return TravelIntent()

    normalized = _normalize_text(player_text)

    # 1. Chercher les marqueurs explicites
    for marker in _TRAVEL_MARKERS_EXPLICIT:
        marker_norm = _normalize_text(marker)
        if marker_norm in normalized:
            destination = _extract_destination_after_marker(normalized, marker_norm)
            destination_node_id = None
            if destination:
                destination_node_id = _match_destination_to_state(destination, state_data)
            # Si la destination est trouvée dans le texte, c'est explicite
            # même si le matching avec l'état échoue
            return TravelIntent(
                is_travel=True,
                destination=destination,
                destination_node_id=destination_node_id,
                confidence="explicit",
            )

    # 2. Chercher les marqueurs implicites + mention de lieu connu
    for marker in _TRAVEL_MARKERS_IMPLICIT:
        marker_norm = _normalize_text(marker)
        if marker_norm not in normalized:
            continue
        # Marqueur implicite trouvé : vérifier si le texte mentionne
        # une sortie ou un noeud de carte connu
        for exit_data in (state_data.get("current_scene") or {}).get("exits") or []:
            if not isinstance(exit_data, dict):
                continue
            exit_label = str(exit_data.get("label") or "")
            exit_leads = str(exit_data.get("leads_to") or "")
            if _normalize_text(exit_label) in normalized or _normalize_text(exit_leads) in normalized:
                return TravelIntent(
                    is_travel=True,
                    destination=exit_label or exit_leads,
                    destination_node_id=str(exit_data.get("leads_to") or exit_data.get("id") or ""),
                    confidence="implicit",
                )
        # Vérifier les noeuds de carte
        world_maps = state_data.get("world_maps") or {}
        if isinstance(world_maps, dict):
            region_map = world_maps.get("region_map") or {}
            if isinstance(region_map, dict):
                for node in region_map.get("nodes") or []:
                    if not isinstance(node, dict):
                        continue
                    node_name = str(node.get("name") or "")
                    if _normalize_text(node_name) in normalized:
                        return TravelIntent(
                            is_travel=True,
                            destination=node_name,
                            destination_node_id=str(node.get("id") or ""),
                            confidence="implicit",
                        )
        # Marqueur implicite sans destination connue : ne pas considérer comme voyage
        # (le joueur pourrait juste avancer dans la scène actuelle)
        break

    return TravelIntent()


def travel_intent_as_dict(intent: TravelIntent) -> dict[str, Any] | None:
    """Convertit un TravelIntent en dict pour injection dans le template Jinja.

    Retourne None si is_travel est False, pour éviter d'injecter du bruit
    dans le prompt lorsque le joueur ne voyage pas.
    """
    if not intent.is_travel:
        return None
    return {
        "is_travel": True,
        "destination": intent.destination,
        "destination_node_id": intent.destination_node_id,
        "confidence": intent.confidence,
    }