"""Background visual-asset generation service.

Orchestrates the async lifecycle: prompt_ready → generating → ready/failed.
Runs as a fire-and-forget asyncio task after a scene or map layout is created
with a visual_asset in prompt_ready state.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.db.database import async_session
from app.game.event_bus import EventType, event_bus
from app.game.runtime import session_manager
from app.llm.image_client import ImageClient, ImageClientError
from app.services import local_map_service

logger = logging.getLogger(__name__)


async def _update_visual_asset_and_publish(
    session_id: str,
    scope: str,
    asset_key: str,
    visual_asset: dict[str, Any],
) -> None:
    """Write an updated visual_asset into the active session and push a WS event."""
    async with session_manager.session_lock(session_id):
        active = session_manager.get_session(session_id)
        if active is None:
            logger.warning(
                "visual_asset: session %s fermée avant mise à jour.", session_id
            )
            return

        if scope == "scene":
            scene = active.state_data.get("current_scene")
            if isinstance(scene, dict):
                scene["visual_asset"] = visual_asset
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.SCENE_LAYOUT_CHANGED,
                    {"scene": scene},
                    source="visual_asset_service",
                )
        elif scope == "region":
            world_maps = active.state_data.get("world_maps", {})
            region_map = world_maps.get("region_map")
            if isinstance(region_map, dict):
                region_map["visual_asset"] = visual_asset
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.REGION_MAP_UPDATED,
                    {
                        "region_map": region_map,
                        "active_city_id": world_maps.get("active_city_id"),
                    },
                    source="visual_asset_service",
                )
        elif scope == "city":
            world_maps = active.state_data.get("world_maps", {})
            city_id = visual_asset.get("_city_id")
            city_maps = world_maps.get("city_maps", {})
            city_map = city_maps.get(city_id) if city_id else None
            if isinstance(city_map, dict):
                city_map["visual_asset"] = visual_asset
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.CITY_MAP_UPDATED,
                    {
                        "city_map": city_map,
                        "active_city_id": world_maps.get("active_city_id"),
                    },
                    source="visual_asset_service",
                )

    # Persist to DB so the URL survives a server restart
    try:
        async with async_session() as db:
            await session_manager.save_state(session_id, db)
            await db.commit()
    except Exception:
        logger.exception("visual_asset: échec save_state pour session %s", session_id)


async def generate_visual_asset(
    session_id: str,
    scope: str,
    visual_asset: dict[str, Any],
) -> None:
    """Generate an image from a prompt_ready visual_asset and update the session.

    Lifecycle: prompt_ready → generating → ready (or failed).
    This function is meant to be run via ``asyncio.create_task()`` — it must
    never block the caller.
    """
    prompt = visual_asset.get("prompt", "")
    if not prompt:
        logger.warning("visual_asset: prompt vide, génération annulée.")
        return

    # Transition to "generating"
    generating_asset = {**visual_asset, "status": "generating"}
    await _update_visual_asset_and_publish(
        session_id, scope, "visual_asset", generating_asset
    )

    # Call the image API
    client = ImageClient()
    try:
        url = await client.generate(prompt)
    except (ImageClientError, Exception) as exc:
        logger.warning("visual_asset: génération échouée — %s", exc)
        failed_asset = {
            **visual_asset,
            "status": "failed",
            "error": str(exc)[:280],
        }
        await _update_visual_asset_and_publish(
            session_id, scope, "visual_asset", failed_asset
        )
        return

    # Transition to "ready"
    ready_asset = {
        **visual_asset,
        "status": "ready",
        "url": url,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    await _update_visual_asset_and_publish(
        session_id, scope, "visual_asset", ready_asset
    )
    logger.info(
        "visual_asset: image générée pour session %s (scope=%s)", session_id, scope
    )