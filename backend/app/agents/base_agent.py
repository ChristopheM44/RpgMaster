from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.agents.schemas import AgentContext, AgentResponse

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class BaseAgent(ABC):
    """Interface abstraite pour tous les agents IA (MJ, joueurs IA, etc.).

    Fournit :
    - Rendu de templates Jinja2 depuis ``agents/prompts/``
    - Extraction de JSON depuis les sorties LLM (avec fallback)
    - Point d'extension ``think()`` à implémenter par chaque agent
    """

    _jinja_env: Optional[Environment] = None

    # -------------------------------------------------------------------------
    # Templates Jinja2
    # -------------------------------------------------------------------------

    @classmethod
    def _get_jinja_env(cls) -> Environment:
        """Lazy-init de l'environnement Jinja2 partagé entre les agents."""
        if cls._jinja_env is None:
            cls._jinja_env = Environment(
                loader=FileSystemLoader(str(_PROMPTS_DIR)),
                autoescape=select_autoescape([]),  # Pas d'échappement HTML pour les prompts
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return cls._jinja_env

    def _render_prompt(self, template_name: str, variables: dict[str, Any]) -> str:
        """Rend un template Jinja2 depuis le dossier ``agents/prompts/``."""
        env = self._get_jinja_env()
        template = env.get_template(template_name)
        return template.render(**variables)

    def _load_system_prompt(self, filename: str) -> str:
        """Charge un fichier de prompt statique (sans variables Jinja2)."""
        path = _PROMPTS_DIR / filename
        return path.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Extraction JSON
    # -------------------------------------------------------------------------

    def _extract_json(self, text: str) -> Optional[dict[str, Any]]:
        """Extrait le premier objet JSON valide depuis la sortie brute du LLM.

        Tente dans l'ordre :
        1. Parse direct (si le modèle a bien suivi les instructions)
        2. Extraction depuis un bloc ```json … ```
        3. Premier bloc ``{…}`` équilibré (résistant aux doubles réponses du LLM)
        """
        stripped = text.strip()

        # 1 — Parse direct
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 2 — Bloc markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3 — Premier objet JSON équilibré (tracking de profondeur)
        # Évite le piège du regex greedy quand le LLM retourne plusieurs blocs JSON
        start = stripped.find("{")
        if start != -1:
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
                        candidate = stripped[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

        logger.warning("Impossible d'extraire du JSON depuis la sortie LLM : %s…", stripped[:200])
        return None

    # -------------------------------------------------------------------------
    # Interface abstraite
    # -------------------------------------------------------------------------

    @abstractmethod
    async def think(self, context: AgentContext) -> AgentResponse:
        """Traite un contexte et retourne une réponse structurée."""
