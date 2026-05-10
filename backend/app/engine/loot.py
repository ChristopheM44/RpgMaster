"""Small deterministic loot suggestion tables for encounter aftermath."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.engine.currency import Wealth, normalize_wealth


@dataclass
class LootResult:
    coins: Wealth
    items: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "coins": {"gp": self.coins.gp, "sp": self.coins.sp, "cp": self.coins.cp},
            "items": list(self.items),
        }


def loot_for_encounter(
    *,
    total_cr: float,
    monster_xp: int,
    difficulty: str,
    rng: random.Random,
) -> LootResult:
    """Suggest lightweight loot; the GM still decides what to grant."""
    cr = float(total_cr or 0)
    xp = max(0, int(monster_xp or 0))
    difficulty_factor = {
        "easy": 0.7,
        "medium": 1.0,
        "hard": 1.35,
        "deadly": 1.75,
    }.get(str(difficulty or "medium").lower(), 1.0)
    coin_cp = int((xp / 5 + cr * 35) * difficulty_factor)
    coin_cp += rng.randint(0, max(10, int(25 + cr * 10)))
    coins = normalize_wealth(cp=coin_cp)

    items: list[dict[str, Any]] = []
    if rng.random() < min(0.35, 0.08 + cr * 0.04):
        items.append({"template_id": "healing_potion", "quantity": 1})
    if cr >= 2 and rng.random() < 0.2:
        items.append({"template_id": "rope_50ft", "quantity": 1})
    return LootResult(coins=coins, items=items)
