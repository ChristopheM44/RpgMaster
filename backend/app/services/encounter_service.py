"""Encounter service: loads SRD data and orchestrates preset vs dynamic encounters."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from app.engine.encounter_builder import (
    BuiltEncounter,
    EncounterEntry,
    expand_to_combatants,
    generate_encounter,
)
from app.schemas.campaign_content import (
    materialize_custom_monster,
    normalize_monster_reference,
)

_SRD_DIR = Path(__file__).parent.parent / "engine" / "srd_data"
logger = logging.getLogger(__name__)


class EncounterService:
    """Loads SRD data once and exposes encounter building methods."""

    def __init__(self) -> None:
        self._monsters: list[dict[str, Any]] = []
        self._monsters_by_id: dict[str, dict[str, Any]] = {}
        self._presets: list[dict[str, Any]] = []
        self._presets_by_id: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        monsters_path = _SRD_DIR / "monsters.json"
        with monsters_path.open(encoding="utf-8") as f:
            data = json.load(f)
        self._monsters = data["monsters"]
        self._monsters_by_id = {m["id"]: m for m in self._monsters}

        presets_path = _SRD_DIR / "encounters.json"
        with presets_path.open(encoding="utf-8") as f:
            enc_data = json.load(f)
        self._presets = enc_data["encounters"]
        self._presets_by_id = {e["id"]: e for e in self._presets}

        self._loaded = True

    # ------------------------------------------------------------------
    # Preset encounter access
    # ------------------------------------------------------------------

    def list_presets(
        self,
        min_level: int | None = None,
        max_level: int | None = None,
        terrain: str | None = None,
        difficulty: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return preset encounter metadata, optionally filtered."""
        self._ensure_loaded()
        results = []
        for preset in self._presets:
            if min_level is not None and preset.get("max_level", 99) < min_level:
                continue
            if max_level is not None and preset.get("min_level", 0) > max_level:
                continue
            if terrain is not None and preset.get("terrain") != terrain:
                continue
            if difficulty is not None and preset.get("difficulty") != difficulty:
                continue
            results.append(preset)
        return results

    def get_preset(self, encounter_id: str) -> dict[str, Any] | None:
        """Return a single preset by id, or None if not found."""
        self._ensure_loaded()
        return self._presets_by_id.get(encounter_id)

    def build_from_preset(self, encounter_id: str) -> BuiltEncounter | None:
        """Convert a preset template into a BuiltEncounter.

        Returns None if the encounter_id doesn't exist.
        """
        self._ensure_loaded()
        preset = self._presets_by_id.get(encounter_id)
        if not preset:
            return None

        entries: list[EncounterEntry] = []
        for slot in preset["monsters"]:
            monster = self._monsters_by_id.get(slot["monster_id"])
            if not monster:
                continue
            count = slot.get("count", 1)
            first_action = next((a for a in monster.get("actions", []) if "attack_bonus" in a), {})
            entries.append(
                EncounterEntry(
                    monster_id=monster["id"],
                    count=count,
                    name_fr=monster.get("name_fr", monster["name"]),
                    cr=monster["cr"],
                    xp_each=monster["xp"],
                    ac=monster["ac"],
                    hp=monster["hp"],
                    attack_bonus=first_action.get("attack_bonus", 2),
                    damage_notation=first_action.get("damage_dice", "1d4"),
                )
            )

        all_xp_flat = [e.xp_each for e in entries for _ in range(e.count)]
        return BuiltEncounter(
            entries=entries,
            total_xp_raw=sum(all_xp_flat),
            total_xp_adjusted=sum(all_xp_flat),  # preset: no adjustment
            difficulty=preset.get("difficulty", "medium"),
            xp_budget=0,
        )

    def build_from_monster_ids(
        self,
        monster_ids: list[str],
        *,
        custom_monsters: list[dict[str, Any]] | None = None,
    ) -> BuiltEncounter:
        """Build an encounter from a list of monster IDs (may repeat).

        IDs that don't match a known monster are silently skipped.
        Returns a BuiltEncounter with empty entries if nothing matched.
        """
        self._ensure_loaded()
        monsters_by_id: dict[str, dict[str, Any]] = dict(self._monsters_by_id)
        if custom_monsters:
            monsters_by_id.update(self._materialized_custom_monsters(custom_monsters))

        counter: dict[str, int] = {}
        for mid in monster_ids:
            normalized = normalize_monster_reference(mid)
            if normalized:
                counter[normalized] = counter.get(normalized, 0) + 1

        entries: list[EncounterEntry] = []
        for mid, count in counter.items():
            monster = monsters_by_id.get(mid)
            if not monster:
                logger.warning("EncounterService: monster_id invalide ignore '%s'.", mid)
                continue
            first_action = next((a for a in monster.get("actions", []) if "attack_bonus" in a), {})
            entries.append(
                EncounterEntry(
                    monster_id=monster["id"],
                    count=count,
                    name_fr=monster.get("name_fr", monster["name"]),
                    cr=monster["cr"],
                    xp_each=monster["xp"],
                    ac=monster["ac"],
                    hp=monster["hp"],
                    attack_bonus=first_action.get("attack_bonus", 2),
                    damage_notation=first_action.get("damage_dice", "1d4"),
                )
            )

        all_xp_flat = [e.xp_each for e in entries for _ in range(e.count)]
        return BuiltEncounter(
            entries=entries,
            total_xp_raw=sum(all_xp_flat),
            total_xp_adjusted=sum(all_xp_flat),
            difficulty="custom",
            xp_budget=0,
            monsters_by_id={
                entry.monster_id: monsters_by_id[entry.monster_id]
                for entry in entries
                if entry.monster_id in monsters_by_id
            },
        )

    def _materialized_custom_monsters(
        self,
        custom_monsters: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        materialized: dict[str, dict[str, Any]] = {}
        for template in custom_monsters:
            if not isinstance(template, dict):
                continue
            ref = normalize_monster_reference(f"custom:{template.get('id') or ''}")
            base_id = normalize_monster_reference(template.get("base_srd_id"))
            base = self._monsters_by_id.get(base_id)
            if not ref or not base:
                logger.warning(
                    "EncounterService: custom monster invalide ignore id=%r base=%r.",
                    template.get("id"),
                    template.get("base_srd_id"),
                )
                continue
            try:
                monster = materialize_custom_monster(base, template)
            except Exception as exc:
                logger.warning("EncounterService: custom monster rejeté %r: %s", ref, exc)
                continue
            materialized[ref] = monster
        return materialized

    # ------------------------------------------------------------------
    # Dynamic encounter generation
    # ------------------------------------------------------------------

    def generate(
        self,
        party_levels: list[int],
        difficulty: str = "medium",
        rng: random.Random | None = None,
    ) -> BuiltEncounter:
        """Generate a random encounter balanced for the given party."""
        self._ensure_loaded()
        return generate_encounter(self._monsters, party_levels, difficulty, rng=rng)

    def generate_for_level(
        self,
        avg_level: int,
        party_size: int = 4,
        difficulty: str = "medium",
        rng: random.Random | None = None,
    ) -> BuiltEncounter:
        """Convenience method: generate using a uniform party of avg_level."""
        party_levels = [avg_level] * party_size
        return self.generate(party_levels, difficulty, rng=rng)

    # ------------------------------------------------------------------
    # Expand to combatant dicts (ready for ws_game / state_data)
    # ------------------------------------------------------------------

    def expand(self, encounter: BuiltEncounter) -> list[dict[str, Any]]:
        """Flatten a BuiltEncounter into a list of combatant dicts."""
        self._ensure_loaded()
        return expand_to_combatants(encounter, self._monsters_by_id)

    # ------------------------------------------------------------------
    # Preset selection adapted to party level (for random start_combat)
    # ------------------------------------------------------------------

    def pick_preset_for_party(
        self,
        party_levels: list[int],
        rng: random.Random | None = None,
    ) -> dict[str, Any] | None:
        """Return a random preset suitable for the given party levels, or None."""
        self._ensure_loaded()
        if rng is None:
            rng = random.Random()
        avg = sum(party_levels) / len(party_levels) if party_levels else 1
        candidates = [
            p for p in self._presets if p.get("min_level", 0) <= avg <= p.get("max_level", 99)
        ]
        return rng.choice(candidates) if candidates else None


# Module-level singleton
encounter_service = EncounterService()
