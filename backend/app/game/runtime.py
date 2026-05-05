"""Shared runtime singletons for live game sessions."""
from __future__ import annotations

from app.game.session_manager import SessionManager
from app.services.rest_service import RestService

session_manager = SessionManager()
rest_service = RestService(session_manager=session_manager)
