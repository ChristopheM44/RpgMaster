from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GMAction(BaseModel):
    """Action mécanique demandée par le MJ au moteur de jeu."""

    type: str = Field(
        ...,
        description=(
            "Type d'action : roll_request | damage_apply | "
            "condition_add | condition_remove | state_transition"
        ),
    )
    target: Optional[str] = Field(None, description="ID du personnage cible, ou null")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Paramètres spécifiques à l'action"
    )


class GMResponse(BaseModel):
    """Réponse structurée du MJ, parsée depuis la sortie JSON du LLM."""

    narration: str = Field(..., description="Texte narratif affiché aux joueurs")
    actions: list[GMAction] = Field(
        default_factory=list, description="Actions mécaniques à exécuter par le moteur"
    )
    mood: str = Field(
        default="neutral",
        description="Ambiance : neutral | tense | dramatic | mysterious | humorous | peaceful",
    )
    inner_reasoning: Optional[str] = Field(
        None, description="Réflexion interne du MJ, non affichée aux joueurs"
    )


class ContextMessage(BaseModel):
    """Message simplifié pour la fenêtre de contexte d'un agent."""

    role: str  # "gm" | "player" | "system"
    speaker: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """Contexte complet fourni à un agent pour qu'il prenne une décision."""

    session_id: str
    game_phase: str
    messages: list[ContextMessage] = Field(default_factory=list)
    game_state: dict[str, Any] = Field(default_factory=dict)
    player_action: Optional[str] = None


class AgentResponse(BaseModel):
    """Réponse générique d'un agent (base commune pour MJ, joueurs, etc.)."""

    content: str = Field(..., description="Texte principal de la réponse")
    actions: list[GMAction] = Field(default_factory=list)
    raw_llm_output: Optional[str] = Field(
        None, description="Sortie brute du LLM avant parsing"
    )
