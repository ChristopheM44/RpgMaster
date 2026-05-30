"""Helpers de journalisation pour les dégradations contrôlées (audit §4.3).

Motif visé : remplacer les ``except Exception: pass`` / ``logger.debug`` muets
qui *avalent* une panne récupérée. On veut une trace **exploitable** sans
masquer l'erreur, tout en distinguant deux régimes :

- **optionnel dégradable** (carte, persona, cohérence visuelle) → ``WARNING`` :
  le jeu continue, mais on doit pouvoir mesurer la fréquence.
- **anormal** (JSON LLM invalide, état incohérent) → ``ERROR``.

Usage::

    from app.logging_utils import log_degraded

    try:
        game_state["world_maps"] = await map_context_for_session(...)
    except Exception as exc:
        log_degraded(logger, "contexte cartes (npc_dialogue)", exc, session_id=session_id)
"""

from __future__ import annotations

import logging


def log_degraded(
    logger: logging.Logger,
    operation: str,
    exc: BaseException,
    *,
    level: int = logging.WARNING,
    **context: object,
) -> None:
    """Journalise une panne *récupérée* sur un chemin dégradable.

    :param operation: libellé court de l'opération qui a échoué (greppable).
    :param exc: l'exception capturée.
    :param level: ``logging.WARNING`` (défaut, optionnel dégradable) ou
        ``logging.ERROR`` (anormal).
    :param context: paires clé=valeur ajoutées au message (``session_id``,
        ``character_id``…) pour le diagnostic.
    """
    suffix = "".join(f" {key}={value}" for key, value in context.items())
    logger.log(
        level,
        "dégradé: %s — %s: %s%s",
        operation,
        type(exc).__name__,
        exc,
        suffix,
    )
