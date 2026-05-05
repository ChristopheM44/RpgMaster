"""Mechanical action resolution helpers used by ActionResolver and ActionPipeline."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.engine import combat as combat_engine
from app.engine.ability_checks import ability_modifier, proficiency_bonus
from app.engine.dice import roll
from app.engine.spells import roll_spell_attack, spell_save_dc, upcast_damage
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

_DEFAULT_AC = 10
_DEFAULT_ATTACK_BONUS = 3
_DEFAULT_DAMAGE = "1d6"

_SRD_SPELLS_PATH = Path(__file__).parent.parent / "engine" / "srd_data" / "spells.json"
_SPELLS_CACHE: Optional[dict[str, Any]] = None

_SPELLCASTING_ABILITIES: dict[str, str] = {
    "wizard": "int",
    "cleric": "wis",
    "bard": "cha",
    "sorcerer": "cha",
    "warlock": "cha",
    "druid": "wis",
    "paladin": "cha",
    "ranger": "wis",
    "fighter": "int",
    "rogue": "int",
}


def _load_spells() -> dict[str, Any]:
    global _SPELLS_CACHE
    if _SPELLS_CACHE is None:
        with _SRD_SPELLS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        _SPELLS_CACHE = {s["id"]: s for s in data["spells"]}
    return _SPELLS_CACHE


class ActionMechanics:
    """Legacy mechanical helpers kept behind ActionResolver-compatible names."""

    def _resolve_attack(
        self,
        attacker_id: Optional[str],
        target_id: Optional[str],
        state_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Résout un jet d'attaque + dégâts via engine/combat.py.

        Cherche les stats dans ``state_data["combatants"]`` ; utilise des
        valeurs par défaut si les combattants ne sont pas trouvés.
        """
        combatants: dict[str, Any] = state_data.get("combatants", {})

        attacker = combatants.get(attacker_id, {}) if attacker_id else {}
        target = combatants.get(target_id, {}) if target_id else {}

        attack_bonus = int(attacker.get("attack_bonus", _DEFAULT_ATTACK_BONUS))
        target_ac = int(target.get("ac", _DEFAULT_AC))
        damage_notation: str = attacker.get("damage_notation", _DEFAULT_DAMAGE)

        attack = combat_engine.roll_attack(attack_bonus=attack_bonus, target_ac=target_ac)

        payload: dict[str, Any] = {
            "type": "attack",
            "attacker_id": attacker_id,
            "target_id": target_id,
            "d20_roll": attack.d20_roll,
            "attack_total": attack.total,
            "target_ac": target_ac,
            "hit": attack.hit,
            "critical": attack.critical,
            "fumble": attack.fumble,
            "breakdown": attack.breakdown,
        }

        if attack.hit:
            dmg = combat_engine.roll_damage(notation=damage_notation, critical=attack.critical)
            payload["damage"] = {
                "notation": dmg.notation,
                "rolls": dmg.rolls,
                "modifier": dmg.modifier,
                "total": dmg.total,
                "critical": dmg.critical,
            }
            hit_label = "CRITIQUE" if attack.critical else "touché"
            payload["summary"] = (
                f"Attaque : {attack.total} ({hit_label}) → {dmg.total} dégâts"
            )
        else:
            miss_label = "fumble" if attack.fumble else "raté"
            payload["summary"] = f"Attaque : {attack.total} vs CA {target_ac} ({miss_label})"

        return payload

    def _normalize_roll_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Convertit le payload brut en RollResultPayload attendu par le frontend."""
        roll_type = raw.get("type", "")

        if roll_type in ("death_save", "stabilize"):
            d20 = int(raw.get("d20_roll", 0))
            total = int(raw.get("total", d20))
            return {
                "dice_notation": "1d20",
                "rolls": [d20],
                "total": total,
                "modifier": int(raw.get("modifier", 0)),
                "label": raw.get("label", raw.get("summary", "")),
                "success": raw.get("success"),
            }

        if roll_type == "attack":
            d20 = int(raw.get("d20_roll", 0))
            total = int(raw.get("attack_total", d20))
            return {
                "dice_notation": "1d20",
                "rolls": [d20],
                "total": total,
                "modifier": total - d20,
                "label": raw.get("summary", "Attaque"),
                "success": raw.get("hit"),
            }

        if roll_type == "cast_spell":
            atk = raw.get("attack", {})
            if atk:
                d20 = int(atk.get("d20_roll", 0))
                total = int(atk.get("total", d20))
                return {
                    "dice_notation": "1d20",
                    "rolls": [d20],
                    "total": total,
                    "modifier": total - d20,
                    "label": raw.get("summary", raw.get("spell_name", "Sort")),
                    "success": atk.get("hit"),
                }
            # Sort avec jet de sauvegarde : afficher le jet de la cible
            save_d20 = raw.get("save_d20")
            if save_d20 is not None:
                save_total = int(raw.get("save_total", save_d20))
                return {
                    "dice_notation": "1d20",
                    "rolls": [int(save_d20)],
                    "total": save_total,
                    "modifier": save_total - int(save_d20),
                    "label": raw.get("summary", raw.get("spell_name", "Sort")),
                    "success": raw.get("target_saved"),
                }
            dmg = raw.get("damage", {})
            if dmg:
                return {
                    "dice_notation": str(dmg.get("notation", "")),
                    "rolls": list(dmg.get("rolls", [])),
                    "total": int(dmg.get("total", 0)),
                    "modifier": 0,
                    "label": raw.get("summary", raw.get("spell_name", "Sort")),
                }
            return {
                "dice_notation": "",
                "rolls": [],
                "total": 0,
                "modifier": 0,
                "label": raw.get("summary", "Sort lancé"),
            }

        # generic_roll
        return {
            "dice_notation": str(raw.get("notation", "1d20")),
            "rolls": list(raw.get("rolls", [])),
            "total": int(raw.get("total", 0)),
            "modifier": 0,
            "label": raw.get("summary", ""),
        }

    def _resolve_generic_roll(self, content: Optional[str]) -> dict[str, Any]:
        """Jet de dé générique (d20) pour les sorts ou tests sans contexte."""
        r = roll("d20")
        return {
            "type": "generic_roll",
            "notation": "d20",
            "rolls": r.rolls,
            "total": r.total,
            "summary": f"1d20 → {r.total}",
            "context": content or "",
        }

    async def _resolve_cast_spell(
        self,
        session_id: str,
        character_id: Optional[str],
        spell_id: str,
        slot_level: Optional[int],
        target_id: Optional[str],
        active: ActiveSession,
        db: Any,
    ) -> dict[str, Any]:
        """Résout le lancement d'un sort via le moteur de règles SRD 5.2.

        1. Charge les données du sort depuis le JSON SRD.
        2. Charge le personnage depuis la DB pour lire/mettre à jour ses emplacements.
        3. Consomme l'emplacement et résout l'attaque/save/dégâts selon le type.
        4. Diffuse SPELL_SLOT_UPDATED pour que le frontend rafraîchisse ses emplacements.
        """
        from sqlalchemy import select

        from app.models.character import Character as CharModel

        spells = _load_spells()
        spell = spells.get(spell_id)
        if not spell:
            return {
                "type": "cast_spell",
                "summary": f"Sort inconnu : '{spell_id}'.",
                "error": True,
            }

        spell_level: int = int(spell["level"])
        effective_slot: int = slot_level if slot_level is not None else spell_level
        if effective_slot < spell_level:
            effective_slot = spell_level
        if spell_level == 0:
            effective_slot = 0

        spell_name: str = spell.get("name_fr", spell["name"])

        payload: dict[str, Any] = {
            "type": "cast_spell",
            "spell_id": spell_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "slot_level": effective_slot,
            "target_id": target_id,
            "concentration": bool(spell.get("concentration", False)),
        }

        # ── Chargement du personnage lanceur ──────────────────────────
        char: Optional[Any] = None
        caster_ability_score: int = 10
        prof_bonus_val: int = 2

        if character_id:
            result = await db.execute(
                select(CharModel).where(CharModel.id == character_id)
            )
            char = result.scalar_one_or_none()

        if char:
            ability_key = _SPELLCASTING_ABILITIES.get(char.char_class.lower(), "int")
            caster_ability_score = int(char.ability_scores.get(ability_key, 10))
            prof_bonus_val = proficiency_bonus(char.level)

            # ── Consommation de l'emplacement ─────────────────────────
            if spell_level > 0:
                db_slots: dict[str, Any] = dict(char.spell_slots) if char.spell_slots else {}
                slot_key = str(effective_slot)
                slot_info = db_slots.get(slot_key, {"total": 0, "used": 0})
                total = int(slot_info.get("total", 0))
                used = int(slot_info.get("used", 0))
                remaining = total - used

                if remaining <= 0:
                    return {
                        "type": "cast_spell",
                        "summary": (
                            f"Aucun emplacement de niveau {effective_slot} "
                            "disponible."
                        ),
                        "error": True,
                    }

                new_slots = dict(db_slots)
                new_slots[slot_key] = {"total": total, "used": used + 1}
                char.spell_slots = new_slots
                await db.commit()

                payload["slots_remaining"] = {
                    k: int(v.get("total", 0)) - int(v.get("used", 0))
                    for k, v in new_slots.items()
                }

                # Diffuser la mise à jour des emplacements vers le frontend
                await event_bus.publish_to_session(
                    session_id,
                    EventType.SPELL_SLOT_UPDATED,
                    {
                        "character_id": character_id,
                        "spell_slots": new_slots,
                    },
                    source="action_resolver",
                )

        # ── Résolution mécanique selon le type de sort ────────────────
        attack_type: Optional[str] = spell.get("attack_type")
        damage_dice: Optional[str] = spell.get("damage_dice")
        extra_dice: Optional[str] = spell.get("upcast_extra_dice")

        if attack_type in ("ranged_spell", "melee_spell"):
            # Jet d'attaque de sort
            combatants: dict[str, Any] = active.state_data.get("combatants", {})
            target_data = combatants.get(target_id, {}) if target_id else {}
            target_ac = int(target_data.get("ac", _DEFAULT_AC))

            atk = roll_spell_attack(caster_ability_score, prof_bonus_val, target_ac)
            payload["attack"] = {
                "d20_roll": atk.d20_roll,
                "total": atk.total,
                "target_ac": target_ac,
                "hit": atk.hit,
                "critical": atk.critical,
                "breakdown": atk.breakdown,
            }

            if atk.hit and damage_dice:
                if extra_dice and effective_slot > spell_level:
                    dmg = upcast_damage(
                        damage_dice, extra_dice, spell_level, effective_slot,
                        critical=atk.critical,
                    )
                else:
                    dmg = combat_engine.roll_damage(damage_dice, critical=atk.critical)
                payload["damage"] = {
                    "notation": dmg.notation,
                    "rolls": dmg.rolls,
                    "total": dmg.total,
                    "type": spell.get("damage_type", ""),
                }
                hit_label = "CRITIQUE" if atk.critical else "touche"
                dmg_type = spell.get("damage_type", "")
                payload["summary"] = (
                    f"{spell_name} : {atk.total} ({hit_label}) → "
                    f"{dmg.total} dégâts {dmg_type}"
                )
            elif atk.hit:
                payload["summary"] = f"{spell_name} : touche !"
            else:
                payload["summary"] = f"{spell_name} : raté (CA {target_ac})"

        elif attack_type == "auto_hit" and damage_dice:
            # Projectile magique et assimilés
            darts: int = int(spell.get("darts", 1))
            if effective_slot > spell_level:
                darts += int(spell.get("upcast_extra_darts", 0)) * (
                    effective_slot - spell_level
                )
            total_dmg = 0
            all_rolls: list[int] = []
            for _ in range(darts):
                dmg = combat_engine.roll_damage(damage_dice)
                total_dmg += dmg.total
                all_rolls.extend(dmg.rolls)
            payload["damage"] = {
                "notation": f"{darts}×{damage_dice}",
                "rolls": all_rolls,
                "total": total_dmg,
                "type": spell.get("damage_type", ""),
            }
            payload["darts"] = darts
            payload["summary"] = (
                f"{spell_name} : {darts} fléchette(s) → {total_dmg} dégâts"
            )

        elif spell.get("save") and damage_dice:
            # Sort avec jet de sauvegarde et dégâts
            save_info: dict[str, Any] = spell["save"]
            save_ability: str = save_info.get("ability", "dexterity")
            on_success: str = save_info.get("on_success", "half_damage")
            dc = spell_save_dc(caster_ability_score, prof_bonus_val)
            if extra_dice and effective_slot > spell_level:
                dmg = upcast_damage(damage_dice, extra_dice, spell_level, effective_slot)
            else:
                dmg = combat_engine.roll_damage(damage_dice)

            # Jet de sauvegarde de la cible
            full_damage = dmg.total
            applied_damage = full_damage
            save_d20: Optional[int] = None
            save_total_val: Optional[int] = None
            target_saved = False

            if target_id:
                combatants_sv: dict[str, Any] = active.state_data.get("combatants", {})
                target_data = combatants_sv.get(target_id, {})
                target_ability_score = int(
                    target_data.get("ability_scores", {}).get(save_ability, 10)
                )
                save_mod = ability_modifier(target_ability_score)
                save_r = roll("d20")
                save_d20 = save_r.total
                save_total_val = save_d20 + save_mod
                target_saved = save_total_val >= dc

                if target_saved:
                    if on_success == "half_damage":
                        applied_damage = full_damage // 2
                    elif on_success == "no_damage":
                        applied_damage = 0

            payload["save_dc"] = dc
            payload["save_ability"] = save_ability
            payload["save_d20"] = save_d20
            payload["save_total"] = save_total_val
            payload["target_saved"] = target_saved
            payload["damage"] = {
                "notation": dmg.notation,
                "rolls": dmg.rolls,
                "total": applied_damage,
                "full_total": full_damage,
                "type": spell.get("damage_type", ""),
            }

            save_result_str = ""
            if save_total_val is not None:
                outcome = "réussi" if target_saved else "raté"
                save_result_str = f" (JS {save_total_val} {outcome})"
            payload["summary"] = (
                f"{spell_name} : JS {save_ability.upper()[:3]} DD {dc}"
                f"{save_result_str} → {applied_damage} dégâts"
                + (
                    f" (/{full_damage} moitié)"
                    if target_saved and on_success == "half_damage"
                    else ""
                )
            )

        elif spell.get("save"):
            # Sort avec jet de sauvegarde mais sans dégâts directs
            dc = spell_save_dc(caster_ability_score, prof_bonus_val)
            save_info = spell["save"]
            payload["save_dc"] = dc
            payload["save_ability"] = save_info.get("ability", "dexterity")
            payload["summary"] = (
                f"{spell_name} : JS {save_info.get('ability', 'DEX').upper()} DD {dc}"
            )

        else:
            # Sort utilitaire / buff / déplacement
            slot_label = f"emplacement {effective_slot}" if spell_level > 0 else "cantrip"
            payload["summary"] = f"{spell_name} lancé ({slot_label})"

        return payload

    def _resolve_death_save(
        self,
        character_id: Optional[str],
        state_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Jet de sauvegarde contre la mort (SRD 5.2 §Dying).

        - 20 naturel : succès critique → récupère 1 PV
        - 1 naturel  : échec critique → 2 échecs
        - ≥ 10       : succès
        - 2–9        : échec
        3 succès = stable ; 3 échecs = mort.
        """
        from app.engine.combat import roll_death_save  # noqa: PLC0415
        result = roll_death_save()

        cdata = state_data.get("combatants", {}).get(character_id or "", {})
        ds = cdata.get("death_saves", {"successes": 0, "failures": 0, "stable": False})
        succ = ds.get("successes", 0)
        fail = ds.get("failures", 0)

        if result.critical_success:
            label = "Jet de sauvegarde contre la mort — 20 NATUREL ! Récupère 1 PV !"
        elif result.critical_failure:
            fail = min(3, fail + 2)
            label = f"Jet de sauvegarde contre la mort — 1 NATUREL ! ({fail}/3 échecs)"
        elif result.success:
            succ = min(3, succ + 1)
            label = f"Jet de sauvegarde contre la mort — Succès ({result.d20_roll}) [{succ}/3]"
        else:
            fail = min(3, fail + 1)
            label = f"Jet de sauvegarde contre la mort — Échec ({result.d20_roll}) [{fail}/3]"

        return {
            "type": "death_save",
            "character_id": character_id,
            "d20_roll": result.d20_roll,
            "success": result.success,
            "critical_success": result.critical_success,
            "critical_failure": result.critical_failure,
            "notation": "1d20",
            "rolls": [result.d20_roll],
            "total": result.d20_roll,
            "modifier": 0,
            "label": label,
            "summary": label,
        }

    async def _apply_death_save_outcome(
        self,
        session_id: str,
        character_id: Optional[str],
        roll_results: dict[str, Any],
        active: Any,
    ) -> None:
        """Met à jour les compteurs de jet de sauvegarde et gère les issues (stable / mort)."""
        if not character_id:
            return
        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        cdata = combatants.get(character_id)
        if cdata is None:
            return
        ds: dict[str, Any] = cdata.setdefault(
            "death_saves", {"successes": 0, "failures": 0, "stable": False}
        )

        if roll_results.get("critical_success"):
            cdata["hp"] = 1
            ds["stable"] = True
            conds: list[str] = list(cdata.get("conditions", []))
            if "inconscient" in conds:
                conds.remove("inconscient")
                cdata["conditions"] = conds
                await event_bus.publish_to_session(
                    session_id,
                    EventType.CONDITION_CHANGED,
                    {"combatant_id": character_id, "condition": "inconscient", "added": False},
                    source="action_resolver",
                )
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.HP_CHANGED,
                {"combatant_id": character_id, "hp": 1, "delta": 1},
                source="action_resolver",
            )
        elif roll_results.get("critical_failure"):
            ds["failures"] = min(3, ds.get("failures", 0) + 2)
            active.mark_dirty()
        elif roll_results.get("success"):
            ds["successes"] = min(3, ds.get("successes", 0) + 1)
            if ds["successes"] >= 3:
                ds["stable"] = True
                conds_s: list[str] = list(cdata.get("conditions", []))
                if "inconscient" in conds_s:
                    conds_s.remove("inconscient")
                    cdata["conditions"] = conds_s
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.CONDITION_CHANGED,
                        {"combatant_id": character_id, "condition": "inconscient", "added": False},
                        source="action_resolver",
                    )
            active.mark_dirty()
        else:
            ds["failures"] = min(3, ds.get("failures", 0) + 1)
            active.mark_dirty()

        if ds.get("failures", 0) >= 3 and not ds.get("stable"):
            cdata["dead"] = True
            active.mark_dirty()

        await event_bus.publish_to_session(
            session_id,
            EventType.DEATH_SAVE_UPDATED,
            {"combatant_id": character_id, "death_saves": dict(ds)},
            source="action_resolver",
        )

    def _resolve_stabilize(
        self,
        healer_id: Optional[str],
        target_id: Optional[str],
        state_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Jet de Médecine DD 10 pour stabiliser un personnage inconscient (SRD 5.2)."""
        from app.engine.ability_checks import ability_modifier  # noqa: PLC0415
        combatants: dict[str, Any] = state_data.get("combatants", {})
        healer = combatants.get(healer_id or "", {})
        wis_score = int(healer.get("ability_scores", {}).get("wisdom", 10))
        wis_mod = ability_modifier(wis_score)
        r = roll("d20")
        total = r.total + wis_mod
        dc = 10
        success = total >= dc
        sign = f"+{wis_mod}" if wis_mod >= 0 else str(wis_mod)
        target_name = combatants.get(target_id or "", {}).get("name", target_id or "cible")
        return {
            "type": "stabilize",
            "healer_id": healer_id,
            "target_id": target_id,
            "target_name": target_name,
            "d20_roll": r.total,
            "modifier": wis_mod,
            "total": total,
            "dc": dc,
            "success": success,
            "notation": "1d20",
            "rolls": [r.total],
            "summary": (
                f"Médecine DD {dc} : 1d20[{r.total}]{sign} = {total}"
                f" — {'Stabilisé !' if success else 'Échec'}"
            ),
        }

    # ------------------------------------------------------------------
    # Application des actions GM (dégâts, conditions, etc.)
    # ------------------------------------------------------------------

    def _execute_roll_request(
        self,
        params: dict[str, Any],
        fallback_character_id: Optional[str],
        active: ActiveSession,
    ) -> Optional[dict[str, Any]]:
        """Exécute un jet de compétence/caractéristique/sauvegarde demandé par le GM.

        Retourne un payload prêt à être envoyé comme ROLL_RESULT, ou None si les
        données nécessaires sont manquantes.
        """
        from app.game.roll_executor import execute_roll_request

        return execute_roll_request(params, fallback_character_id, active)
