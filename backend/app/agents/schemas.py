from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GMAction(BaseModel):
    """Action mécanique demandée par le MJ au moteur de jeu."""

    type: str = Field(
        ...,
        description=(
            "Type d'action : roll_request | damage_apply | "
            "condition_add | condition_remove | combatant_status | "
            "state_transition | encounter_setup | scene_layout | "
            "journal_update | quest_add | chronicle_add | social_outcome | "
            "region_map_update | city_map_update | node_status_update | "
            "xp_grant | currency_grant | currency_spend | loot_grant | item_remove"
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
    action_intent: Optional[str] = Field(
        None,
        description=(
            "Classification de l'action du joueur : "
            "'social' (adresse aux compagnons), "
            "'environmental' (interaction avec le monde), "
            "'mixed' (les deux)"
        ),
    )
    start_mode: Optional[str] = Field(
        None,
        description=(
            "Pour une intro de rencontre uniquement : 'pause' laisse répondre "
            "les joueurs avant l'initiative, 'combat' lance directement le combat."
        ),
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
    roll_results: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Réponse générique d'un agent (base commune pour MJ, joueurs, etc.)."""

    content: str = Field(..., description="Texte principal de la réponse")
    actions: list[GMAction] = Field(default_factory=list)
    raw_llm_output: Optional[str] = Field(
        None, description="Sortie brute du LLM avant parsing"
    )
    action_intent: Optional[str] = Field(
        None, description="Relayé depuis GMResponse : 'social' | 'environmental' | 'mixed'"
    )


# ---------------------------------------------------------------------------
# Schémas pour les agents joueurs IA (Sprint 5)
# ---------------------------------------------------------------------------

PERSONALITY_TRAITS = (
    "brave",
    "cautious",
    "greedy",
    "noble",
    "vengeful",
    "arcane",
    "reckless",
    "protective",
)

PLAYER_ACTION_TYPES = (
    "attack",
    "cast_spell",
    "dash",
    "dodge",
    "help",
    "use_item",
    "move",
    "talk",
    "wait",
    "disengage",
    "hide",
    "shove",
    "examine",
)


class PlayerActionChoice(BaseModel):
    """Action mécanique choisie par un joueur IA après réflexion."""

    action_type: str = Field(
        ...,
        description=(
            "Type d'action : attack | cast_spell | dash | dodge | help | "
            "use_item | move | talk | wait | disengage | hide | shove | examine"
        ),
    )
    action_description: str = Field(
        ..., description="Description courte de l'action dans le contexte narratif"
    )
    target: Optional[str] = Field(None, description="ID de la cible, ou null")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Paramètres : weapon, spell_name, item_name, move_to…",
    )
    roleplay_text: str = Field(
        ..., description="Ce que le personnage dit ou fait (texte narratif, en français)"
    )
    inner_reasoning: Optional[str] = Field(
        None, description="Réflexion interne du personnage (non affichée aux autres)"
    )
    llm_error: Optional[str] = Field(
        None,
        description=(
            "Défini si l'action est un fallback dû à un échec LLM "
            "(provider injoignable, JSON invalide…). Permet au gestionnaire "
            "de remonter l'erreur à l'utilisateur."
        ),
    )


class PlayerPersonality(BaseModel):
    """Profil de personnalité d'un joueur IA."""

    traits: list[str] = Field(
        default_factory=list,
        description=f"1 à 3 traits parmi : {', '.join(PERSONALITY_TRAITS)}",
    )
    backstory_hook: Optional[str] = Field(
        None, description="Élément de background influençant les décisions (1 phrase)"
    )
    speech_style: Optional[str] = Field(
        None,
        description="Style de discours : formal | casual | gruff | cheerful | mysterious",
    )
