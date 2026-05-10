"""Currency helpers using copper pieces as the canonical value."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Wealth:
    gp: int = 0
    sp: int = 0
    cp: int = 0


class InsufficientFundsError(ValueError):
    """Raised when a character cannot pay a requested cost."""


def total_value_cp(gp: int = 0, sp: int = 0, cp: int = 0) -> int:
    """Return total value in copper pieces."""
    return int(gp) * 100 + int(sp) * 10 + int(cp)


def normalize_wealth(gp: int = 0, sp: int = 0, cp: int = 0) -> Wealth:
    """Normalize coin counts so 10 cp = 1 sp and 10 sp = 1 gp."""
    total = total_value_cp(gp, sp, cp)
    if total < 0:
        raise ValueError("Wealth cannot be negative")
    gp_value, remainder = divmod(total, 100)
    sp_value, cp_value = divmod(remainder, 10)
    return Wealth(gp=gp_value, sp=sp_value, cp=cp_value)


def cost_gp_to_cp(cost_gp: int | float | str | Decimal) -> int:
    """Convert a GP-denominated cost to copper pieces without binary floats."""
    value = Decimal(str(cost_gp)) * Decimal(100)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def can_afford(wealth: Wealth, cost_gp: int | float | str | Decimal) -> bool:
    return total_value_cp(wealth.gp, wealth.sp, wealth.cp) >= cost_gp_to_cp(cost_gp)


def subtract_cost(wealth: Wealth, cost_gp: int | float | str | Decimal) -> Wealth:
    remaining = total_value_cp(wealth.gp, wealth.sp, wealth.cp) - cost_gp_to_cp(cost_gp)
    if remaining < 0:
        raise InsufficientFundsError("Fonds insuffisants")
    return normalize_wealth(cp=remaining)


def add_coins(
    wealth: Wealth,
    *,
    gp: int = 0,
    sp: int = 0,
    cp: int = 0,
) -> Wealth:
    delta = total_value_cp(gp, sp, cp)
    if delta < 0:
        raise ValueError("Coin grants must be non-negative")
    return normalize_wealth(
        gp=wealth.gp + int(gp),
        sp=wealth.sp + int(sp),
        cp=wealth.cp + int(cp),
    )
