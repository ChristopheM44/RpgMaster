import pytest

from app.engine.currency import (
    InsufficientFundsError,
    Wealth,
    can_afford,
    normalize_wealth,
    subtract_cost,
    total_value_cp,
)


def test_normalize_and_total_value():
    assert normalize_wealth(gp=1, sp=12, cp=25) == Wealth(gp=2, sp=4, cp=5)
    assert total_value_cp(1, 2, 3) == 123


def test_can_afford_decimal_prices():
    wealth = normalize_wealth(gp=0, sp=1, cp=0)
    assert can_afford(wealth, 0.1)
    assert not can_afford(wealth, 0.11)


def test_subtract_cost():
    assert subtract_cost(Wealth(gp=1, sp=0, cp=0), 0.35) == Wealth(gp=0, sp=6, cp=5)
    with pytest.raises(InsufficientFundsError):
        subtract_cost(Wealth(gp=0, sp=0, cp=5), 0.1)
