"""Personas polymorphes pour personnages importants (PNJ, monstres, compagnons).

Voir plan : /Users/christophe/.claude/plans/je-voudrais-reflechir-moonlit-hammock.md
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.agents.schemas import PERSONALITY_TRAITS, PlayerPersonality

# ---------------------------------------------------------------------------
# Sub-models partagés
# ---------------------------------------------------------------------------

PersonaImportance = Literal["light", "standard", "rich"]
PersonaGender = Literal["male", "female", "neutral"]
PersonaAgeRange = Literal["child", "young", "adult", "elder", "ancient"]
PersonaSpeechRegister = Literal["formal", "casual", "archaic", "vulgar"]
PersonaPitch = Literal["very_low", "low", "medium", "high", "very_high"]
PersonaRate = Literal["slow", "normal", "fast"]
PersonaAttitude = Literal["hostile", "unfriendly", "indifferent", "friendly", "helpful"]
RelationshipKind = Literal[
    "ally", "rival", "family", "lover", "enemy", "subordinate", "superior", "neutral"
]
BehaviorPattern = Literal[
    "predatory", "tactical", "frenzied", "cunning", "cowardly", "lawful", "mindless"
]

MAX_RELATIONSHIPS = 10


class PersonaVoice(BaseModel):
    """Profil vocal — exploité par la couche voix (local / hybrid / realtime)."""

    gender: PersonaGender = "neutral"
    age_range: PersonaAgeRange = "adult"
    accent: Optional[str] = Field(None, description="libre : 'noble', 'northern', 'guttural'")
    speech_register: PersonaSpeechRegister = "casual"
    pitch: PersonaPitch = "medium"
    rate: PersonaRate = "normal"
    timbre: Optional[str] = Field(None, description="libre : 'raspy', 'warm', 'metallic'")
    voice_id_local: Optional[str] = Field(None, description="ID voix Kokoro")
    voice_id_realtime: Optional[str] = Field(None, description="ID voix OpenAI Realtime")


class PersonaMotivations(BaseModel):
    """Objectifs visibles et cachés d'une persona."""

    visible: list[str] = Field(default_factory=list, description="objectifs apparents")
    hidden: list[str] = Field(default_factory=list, description="GM-only — révélé sur Insight")
    fears: list[str] = Field(default_factory=list)


class PersonaRelationship(BaseModel):
    """Lien entre une persona et une autre entité (PNJ, faction, PJ)."""

    target_id: str
    target_name: str
    kind: RelationshipKind = "neutral"
    intensity: int = Field(default=3, ge=1, le=5)
    notes: Optional[str] = None


class PersonaKnowledge(BaseModel):
    """Ce que la persona sait, ignore explicitement, ou a entendu sans certitude."""

    knows: list[str] = Field(default_factory=list)
    ignores: list[str] = Field(default_factory=list, description="anti-hallucination")
    rumors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Base et variantes polymorphes
# ---------------------------------------------------------------------------


class BasePersona(BaseModel):
    """Champs communs à toute persona — identité, voix, motivations, savoir."""

    id: str
    name: str
    archetype: str = Field(..., description="ex: 'mentor', 'merchant', 'tyrant', 'predator'")
    short_description: str = Field(..., description="1 phrase pour briefer le MJ")
    voice: PersonaVoice = Field(default_factory=PersonaVoice)
    motivations: PersonaMotivations = Field(default_factory=PersonaMotivations)
    relationships: list[PersonaRelationship] = Field(default_factory=list)
    knowledge: PersonaKnowledge = Field(default_factory=PersonaKnowledge)
    importance: PersonaImportance = "standard"
    persona_type: str = Field(default="base", description="discriminator pour persist/load")

    @field_validator("relationships")
    @classmethod
    def _cap_relationships(cls, v: list[PersonaRelationship]) -> list[PersonaRelationship]:
        if len(v) > MAX_RELATIONSHIPS:
            # Trier par intensité décroissante et garder les MAX plus fortes.
            return sorted(v, key=lambda r: r.intensity, reverse=True)[:MAX_RELATIONSHIPS]
        return v


class NPCPersona(BasePersona):
    """PNJ humain/humanoïde avec capacité de dialogue social."""

    persona_type: Literal["npc"] = "npc"
    attitude_default: PersonaAttitude = "indifferent"
    secrets: list[str] = Field(default_factory=list, description="GM-only")
    quest_hooks: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list, description="tics de langage")


class MonsterPersona(BasePersona):
    """Créature en combat — peut parler (`can_speak`) ou non (juste behavior_pattern)."""

    persona_type: Literal["monster"] = "monster"
    monster_srd_id: str = Field(..., description="référence vers MonsterSchema")
    behavior_pattern: BehaviorPattern = "tactical"
    combat_taunts: list[str] = Field(default_factory=list, description="vide si can_speak=False")
    surrender_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="% HP (None = combat à mort)"
    )
    can_speak: bool = True


class CompanionPersona(BasePersona):
    """Compagnon IA piloté par PlayerAgent — sur-ensemble de PlayerPersonality."""

    persona_type: Literal["companion"] = "companion"
    traits: list[str] = Field(default_factory=list)
    backstory_hook: Optional[str] = None
    speech_style: Optional[str] = Field(
        None, description="formal | casual | gruff | cheerful | mysterious"
    )
    bond_to_party: Optional[str] = None
    fears_in_combat: list[str] = Field(default_factory=list)

    @field_validator("traits")
    @classmethod
    def _validate_traits(cls, v: list[str]) -> list[str]:
        unknown = [t for t in v if t not in PERSONALITY_TRAITS]
        if unknown:
            raise ValueError(f"Unknown traits {unknown}; allowed: {', '.join(PERSONALITY_TRAITS)}")
        return v

    @classmethod
    def from_player_personality(
        cls,
        personality: PlayerPersonality,
        *,
        character_id: str,
        name: str,
    ) -> CompanionPersona:
        """Adapter — wrappe un PlayerPersonality legacy en CompanionPersona light.

        Les traits non reconnus dans ``PERSONALITY_TRAITS`` sont silencieusement
        filtrés pour préserver la compatibilité avec les anciens personnages.
        """
        known_traits = [t for t in personality.traits if t in PERSONALITY_TRAITS]
        return cls(
            id=character_id,
            name=name,
            archetype="companion",
            short_description=personality.backstory_hook or f"{name}, compagnon du groupe.",
            traits=known_traits,
            backstory_hook=personality.backstory_hook,
            speech_style=personality.speech_style,
            importance="light",
        )


# ---------------------------------------------------------------------------
# Helpers de désérialisation polymorphe
# ---------------------------------------------------------------------------

_PERSONA_REGISTRY: dict[str, type[BasePersona]] = {
    "npc": NPCPersona,
    "monster": MonsterPersona,
    "companion": CompanionPersona,
}


def persona_from_dict(data: dict[str, Any]) -> BasePersona:
    """Reconstruit la bonne sous-classe à partir d'un dict (basé sur `persona_type`)."""
    persona_type = data.get("persona_type", "base")
    cls = _PERSONA_REGISTRY.get(persona_type, BasePersona)
    return cls.model_validate(data)


def stub_npc_persona_from_legacy(name: str, personality_hint: str = "") -> NPCPersona:
    """Migration douce — convertit un ancien `npc_states[id].personality_hint` en NPCPersona."""
    safe_id = name.lower().replace(" ", "_")[:60] or "unknown_npc"
    return NPCPersona(
        id=safe_id,
        name=name,
        archetype="figurant",
        short_description=personality_hint or f"{name}, croisé en cours d'aventure.",
        importance="light",
    )
