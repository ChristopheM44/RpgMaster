from __future__ import annotations

from typing import Any, Optional

from app.agents.gm_agent import GMAgent
from app.llm.base_client import LLMClient


class CombatGMAgent(GMAgent):
    """MJ spécialisé pour la narration de combat.

    Il réutilise le parsing robuste du GMAgent mais remplace le system prompt
    et compacte l'état transmis au modèle pour réduire le bruit narratif.
    """

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ):
        super().__init__(client=client, model=model)
        self._system_prompt = self._load_system_prompt("gm_combat_system.txt")

    async def run_combat_turn(
        self,
        game_state: dict[str, Any],
        context_manager: Optional[Any] = None,
        player_action: Optional[str] = None,
        messages: Optional[list] = None,
        roll_results: Optional[dict[str, Any]] = None,
    ):
        return await super().run_combat_turn(
            game_state=self._compact_combat_state(game_state),
            context_manager=context_manager,
            player_action=player_action,
            messages=messages,
            roll_results=roll_results,
        )

    @staticmethod
    def _compact_combat_state(game_state: dict[str, Any]) -> dict[str, Any]:
        combatants = game_state.get("combatants", {})
        compact_combatants: dict[str, Any] = {}
        if isinstance(combatants, dict):
            for cid, cdata in combatants.items():
                if not isinstance(cdata, dict):
                    continue
                compact_combatants[str(cid)] = {
                    "name": cdata.get("name", cid),
                    "is_player": cdata.get("is_player", False),
                    "hp": cdata.get("hp", cdata.get("current_hp")),
                    "hp_max": cdata.get("hp_max"),
                    "status": cdata.get("status", "active"),
                    "conditions": cdata.get("conditions", []),
                }

        return {
            "phase": game_state.get("phase", "COMBAT"),
            "round_number": game_state.get("round_number"),
            "combatants": compact_combatants,
            "turn_manager": game_state.get("turn_manager", {}),
        }
