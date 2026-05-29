"""Persona factory — génère des NPCPersona / MonsterPersona à la volée.

Stratégie (cf. plan §3.2) :
- `stub_npc_persona` : synchrone, heuristique, instantané — pour PNJ légers
- `enrich_npc_persona` : async LLM, retry + fallback léger
- `generate_monster_persona` : règles SRD pour mindless, sinon LLM
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.agents.base_agent import _PROMPTS_DIR
from app.agents.persona import (
    BehaviorPattern,
    MonsterPersona,
    NPCPersona,
    PersonaImportance,
    PersonaKnowledge,
    PersonaMotivations,
    PersonaVoice,
    persona_from_dict,
)
from app.llm.base_client import LLMClient
from app.llm.budget import record_llm_call
from app.llm.model_router import router
from app.llm.ollama_client import OllamaError
from app.llm.openai_compatible_client import OpenAICompatibleError

logger = logging.getLogger(__name__)


_BEAST_KEYWORDS = ("beast", "animal", "wolf", "bear", "boar", "spider", "snake")
_OOZE_KEYWORDS = ("ooze", "slime", "jelly", "pudding")
_CONSTRUCT_KEYWORDS = ("construct", "golem", "automaton")
_MINDLESS_UNDEAD = ("zombie", "skeleton")
_FRENZIED_KEYWORDS = ("berserker", "demon", "fiend")
_COWARDLY_KEYWORDS = ("kobold", "goblin_minor")


def _slugify(value: str, max_len: int = 60) -> str:
    """Convertit un texte en kebab-case sûr pour servir d'id."""
    norm = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[\s_]+", "_", norm).strip("_")[:max_len] or "unknown"


def _heuristic_behavior_pattern(
    monster_srd_id: str,
    monster_type: str,
    cr: float | None,
) -> tuple[BehaviorPattern, bool]:
    """Devine (behavior_pattern, can_speak) à partir des métadonnées SRD."""
    haystack = f"{monster_srd_id} {monster_type}".casefold()

    if any(k in haystack for k in _OOZE_KEYWORDS):
        return "mindless", False
    if any(k in haystack for k in _CONSTRUCT_KEYWORDS):
        return "lawful", False
    if any(k in haystack for k in _BEAST_KEYWORDS):
        return "predatory", False
    if any(k in haystack for k in _MINDLESS_UNDEAD) and (cr is None or cr < 1):
        return "mindless", False
    if any(k in haystack for k in _FRENZIED_KEYWORDS):
        return "frenzied", True
    if any(k in haystack for k in _COWARDLY_KEYWORDS):
        return "cowardly", True
    if "dragon" in haystack or "demon_lord" in haystack:
        return "cunning", True
    return "tactical", True


class PersonaFactory:
    """Fabrique de personas — heuristiques rapides + génération LLM async."""

    _jinja_env: Environment | None = None

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client: LLMClient = client or router.get_gm_client()

    # ------------------------------------------------------------------
    # NPC
    # ------------------------------------------------------------------

    def stub_npc_persona(
        self,
        name: str,
        *,
        scene_context: str = "",
        archetype_hint: str = "",
        importance: PersonaImportance = "light",
    ) -> NPCPersona:
        """Crée instantanément une NPCPersona minimale, sans appel LLM."""
        return NPCPersona(
            id=_slugify(name),
            name=name,
            archetype=archetype_hint or "figurant",
            short_description=(scene_context.strip() or f"{name}, croisé en cours d'aventure.")[
                :200
            ],
            importance=importance,
        )

    async def enrich_npc_persona(
        self,
        stub: NPCPersona,
        *,
        narrative_arc: str = "",
        factions_summary: str = "",
        scene_location: str = "",
        scene_mood: str = "",
        context_hint: str = "",
        existing_npcs: list[dict[str, Any]] | None = None,
        target_importance: PersonaImportance = "standard",
    ) -> NPCPersona:
        """Génère une persona enrichie via LLM. Retry une fois, puis fallback sur le stub."""
        prompt = self._render(
            "gm_persona_npc_generate.txt",
            {
                "npc_name": stub.name,
                "importance": target_importance,
                "archetype_hint": stub.archetype if stub.archetype != "figurant" else "",
                "context_hint": context_hint or stub.short_description,
                "narrative_arc": narrative_arc,
                "factions_summary": factions_summary,
                "scene_location": scene_location,
                "scene_mood": scene_mood,
                "existing_npcs": existing_npcs or [],
            },
        )

        for attempt in (1, 2):
            data = await self._call_llm_json(prompt, kind="npc_persona", attempt=attempt)
            if data is None:
                continue
            data.setdefault("id", stub.id)
            data["name"] = stub.name
            data["persona_type"] = "npc"
            data.setdefault("importance", target_importance)
            try:
                persona = persona_from_dict(data)
            except Exception as exc:
                logger.warning(
                    "PersonaFactory: validation NPCPersona échec (tentative %d) : %s",
                    attempt,
                    exc,
                )
                continue
            if isinstance(persona, NPCPersona):
                return persona

        logger.warning(
            "PersonaFactory: enrichissement NPC '%s' échoué, fallback sur stub light.",
            stub.name,
        )
        return stub

    # ------------------------------------------------------------------
    # Monster
    # ------------------------------------------------------------------

    async def generate_monster_persona(
        self,
        monster_srd_id: str,
        *,
        monster_name: str | None = None,
        monster_description: str = "",
        monster_cr: float | None = None,
        monster_type: str = "",
        encounter_context: str = "",
        scene_location: str = "",
        importance: PersonaImportance = "standard",
    ) -> MonsterPersona:
        """Génère une persona monstre. Mindless = règle déterministe, sinon LLM."""
        pattern, can_speak = _heuristic_behavior_pattern(monster_srd_id, monster_type, monster_cr)
        display_name = monster_name or monster_srd_id.replace("_", " ").title()

        # Mindless / muets : pas d'appel LLM, persona déterministe minimale
        if not can_speak or pattern == "mindless":
            return self._build_minimal_monster_persona(
                monster_srd_id=monster_srd_id,
                display_name=display_name,
                behavior_pattern=pattern,
                can_speak=can_speak,
                monster_description=monster_description,
                importance="light",
            )

        prompt = self._render(
            "gm_persona_monster_generate.txt",
            {
                "monster_srd_id": monster_srd_id,
                "monster_type": monster_type,
                "monster_cr": monster_cr,
                "monster_description": monster_description,
                "importance": importance,
                "encounter_context": encounter_context,
                "scene_location": scene_location,
            },
        )

        for attempt in (1, 2):
            data = await self._call_llm_json(prompt, kind="monster_persona", attempt=attempt)
            if data is None:
                continue
            data.setdefault("id", _slugify(f"{monster_srd_id}_{display_name}"))
            data.setdefault("name", display_name)
            data["persona_type"] = "monster"
            data["monster_srd_id"] = monster_srd_id
            data.setdefault("importance", importance)
            try:
                persona = persona_from_dict(data)
            except Exception as exc:
                logger.warning(
                    "PersonaFactory: validation MonsterPersona échec (tentative %d) : %s",
                    attempt,
                    exc,
                )
                continue
            if isinstance(persona, MonsterPersona):
                return persona

        logger.warning(
            "PersonaFactory: génération monstre '%s' échouée, fallback déterministe.",
            monster_srd_id,
        )
        return self._build_minimal_monster_persona(
            monster_srd_id=monster_srd_id,
            display_name=display_name,
            behavior_pattern=pattern,
            can_speak=can_speak,
            monster_description=monster_description,
            importance="light",
        )

    @staticmethod
    def _build_minimal_monster_persona(
        *,
        monster_srd_id: str,
        display_name: str,
        behavior_pattern: BehaviorPattern,
        can_speak: bool,
        monster_description: str = "",
        importance: PersonaImportance = "light",
    ) -> MonsterPersona:
        """Persona minimale déterministe — pour mindless et fallback LLM."""
        return MonsterPersona(
            id=_slugify(f"{monster_srd_id}_{display_name}"),
            name=display_name,
            archetype=behavior_pattern,
            short_description=(monster_description or f"{display_name} ({monster_srd_id}).")[:200],
            voice=PersonaVoice(),
            motivations=PersonaMotivations(visible=["survie"] if can_speak else []),
            knowledge=PersonaKnowledge(),
            importance=importance,
            monster_srd_id=monster_srd_id,
            behavior_pattern=behavior_pattern,
            combat_taunts=[],
            surrender_threshold=None,
            can_speak=can_speak,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _get_jinja_env(cls) -> Environment:
        if cls._jinja_env is None:
            cls._jinja_env = Environment(
                loader=FileSystemLoader(str(_PROMPTS_DIR)),
                autoescape=select_autoescape([]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return cls._jinja_env

    def _render(self, template_name: str, variables: dict[str, Any]) -> str:
        template = self._get_jinja_env().get_template(template_name)
        return template.render(**variables)

    async def _call_llm_json(
        self,
        prompt: str,
        *,
        kind: str,
        attempt: int,
    ) -> dict[str, Any] | None:
        """Appelle le LLM et tente d'extraire un JSON valide. Aucun raise."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un Maître du Jeu D&D rigoureux. "
                    "Tu réponds UNIQUEMENT en JSON valide selon le schéma fourni, "
                    "sans markdown ni texte explicatif."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            record_llm_call("gm")
            raw = await self._client.chat(
                messages=messages,
                temperature=0.7 if attempt == 1 else 0.3,
                max_tokens=2048,
            )
        except (OllamaError, OpenAICompatibleError) as exc:
            logger.warning(
                "PersonaFactory: appel LLM (%s, tentative %d) échoué : %s",
                kind,
                attempt,
                exc,
            )
            return None
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        """Extraction JSON tolérante (parse direct, bloc markdown, ou objet équilibré)."""
        stripped = raw.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        start = stripped.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(stripped[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        return None
