import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api import ws_game
from app.agents.schemas import GMResponse, GMAction
from app.models.session import SessionStatus
from app.game.runtime import session_manager
from app.game.action_resolver import ActionResolver

async def test():
    # Make active session
    session_id = "test-session"
    active = MagicMock()
    active.session_id = session_id
    active.state_data = {
        "characters": {
            "hero_1": {
                "name": "Aria",
                "hp": 20,
                "hp_max": 20,
                "is_player": True,
                "ac": 14,
            }
        },
        "combatants": {
            "hero_1": {
                "name": "Aria",
                "hp": 20,
                "hp_max": 20,
                "is_player": True,
            }
        }
    }
    
    mock_response = GMResponse(
        narration="Le silence retombe sur le quai.",
        actions=[
            GMAction(
                type="damage_apply",
                target="hero_1",
                params={"amount": 99, "target": "hero_1"},
            ),
            GMAction(
                type="state_transition",
                params={"new_phase": "COMBAT"},
            ),
            GMAction(
                type="scene_layout",
                params={
                    "cols": 6,
                    "rows": 6,
                    "terrain": "dock_aftermath",
                    "pois": [],
                    "exits": [],
                    "party_positions": {},
                },
            ),
            GMAction(
                type="journal_update",
                params={"location_place": "Quai silencieux"},
            ),
        ],
    )
    
    mock_resolver = MagicMock()
    mock_resolver._gm.run_encounter_end = AsyncMock(return_value=mock_response)
    
    ws_game.action_resolver = mock_resolver
    
    # We call _generate_encounter_end
    db = MagicMock()
    summary = {
        "outcome": "victory",
        "party": [{"id": "hero_1", "hp": 20}],
        "enemies_defeated": [],
        "enemies_fled": [],
        "enemies_surrendered": [],
        "enemies_unresolved": [],
        "total_enemies": 0,
        "total_monster_xp": 0,
        "total_cr": 0,
        "battlefield_location": "dock",
        "round_number": 1,
        "grid_config": {},
        "previous_scene": {},
    }
    
    print("Calling _generate_encounter_end...")
    try:
        await ws_game._generate_encounter_end(session_id, active, db, summary)
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
