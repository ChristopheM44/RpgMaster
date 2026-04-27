"""Action resolver — pipeline : action joueur → moteur → agent GM → événements.

Pipeline complet pour une action joueur :
1. Résolution mécanique via le moteur (engine/) selon le type d'action
2. Construction du contexte et appel du GMAgent pour la narration
3. Publication des événements sur le bus (roll_result, narration, hp_changed…)

Pure orchestration : ce module ne contient pas de logique de règles.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.gm_agent import GMAgent
from app.agents.schemas import AgentContext, AgentResponse, GMResponse
from app.engine import combat as combat_engine
from app.engine.ability_checks import ability_modifier, proficiency_bonus
from app.engine.dice import roll
from app.engine.spells import (
    roll_spell_attack,
    spell_save_dc,
    upcast_damage,
)
from app.game.combat_triggers import prime_combat_from_hostile_narration
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.llm.voxtral_client import tts_router

logger = logging.getLogger(__name__)

_DEFAULT_AC = 10
_DEFAULT_ATTACK_BONUS = 3
_DEFAULT_DAMAGE = "1d6"

_SRD_SPELLS_PATH = Path(__file__).parent.parent / "engine" / "srd_data" / "spells.json"
_SPELLS_CACHE: Optional[Dict[str, Any]] = None

_SPELLCASTING_ABILITIES: Dict[str, str] = {
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


def _load_spells() -> Dict[str, Any]:
    global _SPELLS_CACHE
    if _SPELLS_CACHE is None:
        with _SRD_SPELLS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        _SPELLS_CACHE = {s["id"]: s for s in data["spells"]}
    return _SPELLS_CACHE

_FALLBACK_NARRATION = (
    "Le Maître du Jeu observe la situation… "
    "(Le système de narration est temporairement indisponible.)"
)


class ActionResolver:
    """Orchestre le traitement complet d'une action joueur.

    Injectez un *gm_agent* personnalisé pour les tests (mock).

    Usage::

        resolver = ActionResolver()
        await resolver.resolve(
            session_id="abc",
            action_type="attack",
            content="J'attaque le gobelin",
            character_id="hero-1",
            target_id="goblin-1",
            active=active_session,
        )
    """

    def __init__(self, gm_agent: Optional[GMAgent] = None) -> None:
        self._gm: GMAgent = gm_agent or GMAgent()

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    async def resolve(
        self,
        session_id: str,
        action_type: str,
        content: Optional[str],
        character_id: Optional[str],
        target_id: Optional[str],
        active: ActiveSession,
        db: Optional[Any] = None,
        spell_id: Optional[str] = None,
        slot_level: Optional[int] = None,
    ) -> None:
        """Exécute le pipeline complet pour une action joueur.

        Args:
            session_id: Identifiant de la session active.
            action_type: Type d'action (free_text, attack, cast_spell, …).
            content: Texte libre décrivant l'action.
            character_id: ID du personnage qui agit.
            target_id: ID de la cible (optionnel).
            active: Session active en mémoire.
        """
        roll_results: Optional[Dict[str, Any]] = None

        # ----------------------------------------------------------------
        # 1. Résolution mécanique (moteur pur, pas de LLM)
        # ----------------------------------------------------------------
        if action_type == "attack":
            roll_results = self._resolve_attack(character_id, target_id, active.state_data)
            # Le moteur fait autorité : appliquer les dégâts immédiatement, sans attendre le GM.
            if roll_results and roll_results.get("hit") and target_id:
                damage_amount = roll_results.get("damage", {}).get("total", 0)
                if damage_amount > 0:
                    await self._apply_gm_action(
                        session_id,
                        "damage_apply",
                        {"target": target_id, "amount": damage_amount},
                        active,
                    )
        elif action_type == "death_save":
            roll_results = self._resolve_death_save(character_id, active.state_data)
            await self._apply_death_save_outcome(session_id, character_id, roll_results, active)
        elif action_type == "stabilize":
            roll_results = self._resolve_stabilize(character_id, target_id, active.state_data)
            if roll_results.get("success") and target_id:
                combatants_st: Dict[str, Any] = active.state_data.setdefault("combatants", {})
                if target_id in combatants_st:
                    ds_st = combatants_st[target_id].setdefault(
                        "death_saves", {"successes": 0, "failures": 0, "stable": False}
                    )
                    ds_st["stable"] = True
                    conds_st: List[str] = list(combatants_st[target_id].get("conditions", []))
                    if "inconscient" in conds_st:
                        conds_st.remove("inconscient")
                        combatants_st[target_id]["conditions"] = conds_st
                        await event_bus.publish_to_session(
                            session_id,
                            EventType.CONDITION_CHANGED,
                            {"combatant_id": target_id, "condition": "inconscient", "added": False},
                            source="action_resolver",
                        )
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.DEATH_SAVE_UPDATED,
                        {"combatant_id": target_id, "death_saves": dict(ds_st)},
                        source="action_resolver",
                    )
                    active.mark_dirty()
        elif action_type == "cast_spell":
            if spell_id is not None and db is not None:
                roll_results = await self._resolve_cast_spell(
                    session_id, character_id, spell_id, slot_level, target_id, active, db
                )
                # Le moteur fait autorité : appliquer les dégâts immédiatement.
                if roll_results and not roll_results.get("error") and target_id:
                    atk = roll_results.get("attack", {})
                    dmg = roll_results.get("damage", {})
                    # Sorts avec jet d'attaque : appliquer si touche
                    # Sorts auto_hit ou save : appliquer directement
                    if dmg:
                        hit = atk.get("hit", True) if atk else True
                        if hit:
                            damage_amount = dmg.get("total", 0)
                            if damage_amount > 0:
                                await self._apply_gm_action(
                                    session_id,
                                    "damage_apply",
                                    {"target": target_id, "amount": damage_amount},
                                    active,
                                )
            else:
                roll_results = self._resolve_generic_roll(content)

        # ----------------------------------------------------------------
        # 2. Construction du contexte pour le GMAgent
        # ----------------------------------------------------------------
        player_action_text = content or action_type
        if roll_results:
            player_action_text = (
                f"{player_action_text} [Résultat mécanique : {roll_results.get('summary', '')}]"
            )

        # 2.a Persister l'action du joueur AVANT de relire l'historique,
        #     afin qu'elle fasse partie du contexte envoyé au MJ (cohérence
        #     bilatérale de la conversation).
        speaker_name = "Joueur"
        characters_data = active.state_data.get("characters", {}) if active.state_data else {}
        if character_id and isinstance(characters_data, dict):
            speaker_name = characters_data.get(character_id, {}).get("name") or "Joueur"

        if db is not None:
            from app.models.message import MessageRole, MessageType
            from app.services.message_service import persist_narration

            await persist_narration(
                session_id,
                player_action_text,
                speaker_name,
                db,
                role=MessageRole.PLAYER,
                message_type=MessageType.ACTION,
                metadata={"action_type": action_type, "character_id": character_id},
            )

        # 2.b Relire l'historique récent pour alimenter le prompt du MJ.
        recent_messages: list = []
        if db is not None:
            from app.services.message_service import load_recent_messages
            recent_messages = await load_recent_messages(session_id, db)

        context = AgentContext(
            session_id=session_id,
            game_phase=active.phase.value.upper(),
            game_state=active.state_data,
            player_action=player_action_text,
            roll_results=roll_results or {},
            messages=recent_messages,
        )

        gm_response: Optional[AgentResponse] = None
        try:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": True},
                source="action_resolver",
            )
            gm_response = await self._gm.think(context)
        except Exception as exc:
            logger.error("ActionResolver : GMAgent échoué : %s", exc)
        finally:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": False},
                source="action_resolver",
            )

        # Stocker l'intent classifié pour que ws_game puisse orchestrer
        # l'ordre d'exécution (social : compagnons d'abord, MJ conclut).
        active.last_gm_intent = gm_response.action_intent if gm_response else None

        has_gm_roll_request = bool(
            gm_response
            and any(gm_action.type == "roll_request" for gm_action in gm_response.actions)
        )

        if gm_response and not has_gm_roll_request:
            prime_combat_from_hostile_narration(
                active,
                gm_response.content,
                source="gm_narration",
            )

        # ----------------------------------------------------------------
        # 3. Publication des événements sur le bus
        # ----------------------------------------------------------------
        if roll_results:
            await event_bus.publish_to_session(
                session_id,
                EventType.ROLL_RESULT,
                self._normalize_roll_event(roll_results),
                source="action_resolver",
            )

        narration_text = gm_response.content if gm_response else _FALLBACK_NARRATION
        if not has_gm_roll_request:
            await self._publish_gm_narration(session_id, narration_text, db)

        # ----------------------------------------------------------------
        # 4. Traitement des actions mécaniques demandées par le GM
        # ----------------------------------------------------------------
        pending_rolls: List[Dict[str, Any]] = []
        canon_dirty = False
        if gm_response:
            for gm_action in gm_response.actions:
                # Fusionner gm_action.target dans params pour simplifier les handlers
                merged_params: Dict[str, Any] = dict(gm_action.params)
                if gm_action.target and "target" not in merged_params:
                    merged_params["target"] = gm_action.target

                if gm_action.type == "roll_request":
                    roll_evt = self._execute_roll_request(merged_params, character_id, active)
                    if roll_evt:
                        pending_rolls.append(roll_evt)
                        await event_bus.publish_to_session(
                            session_id, EventType.ROLL_RESULT, roll_evt, source="action_resolver"
                        )
                else:
                    await self._apply_gm_action(
                        session_id, gm_action.type, merged_params, active
                    )
                    if gm_action.type in {
                        "journal_update",
                        "quest_add",
                        "chronicle_add",
                        "state_transition",
                    }:
                        canon_dirty = True

        if has_gm_roll_request and not pending_rolls:
            prime_combat_from_hostile_narration(
                active,
                narration_text,
                source="gm_narration",
            )
            await self._publish_gm_narration(session_id, narration_text, db)

        # ----------------------------------------------------------------
        # 5. Narration de l'issue si des jets ont été effectués
        # ----------------------------------------------------------------
        if pending_rolls:
            outcome_response: Optional[GMResponse] = None
            try:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.AI_THINKING,
                    {"agent_kind": "gm", "thinking": True},
                    source="action_resolver",
                )
                try:
                    outcome_candidate = await self._gm.narrate_outcome_response(
                        context, pending_rolls
                    )
                except (AttributeError, TypeError):
                    outcome_candidate = await self._gm.narrate_outcome(context, pending_rolls)

                if isinstance(outcome_candidate, GMResponse):
                    outcome_response = outcome_candidate
                elif isinstance(outcome_candidate, AgentResponse):
                    outcome_response = GMResponse(
                        narration=outcome_candidate.content,
                        actions=outcome_candidate.actions,
                        action_intent=outcome_candidate.action_intent,
                    )
                elif outcome_candidate is not None:
                    outcome_response = GMResponse(narration=str(outcome_candidate))
            except Exception as exc:
                logger.error("ActionResolver : narrate_outcome échoué : %s", exc)
            finally:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.AI_THINKING,
                    {"agent_kind": "gm", "thinking": False},
                    source="action_resolver",
                )

            if outcome_response and outcome_response.narration:
                outcome_text = outcome_response.narration
                prime_combat_from_hostile_narration(
                    active,
                    outcome_text,
                    source="gm_roll_outcome",
                )
                await self._publish_gm_narration(session_id, outcome_text, db)
                for gm_action in outcome_response.actions:
                    merged_params: Dict[str, Any] = dict(gm_action.params)
                    if gm_action.target and "target" not in merged_params:
                        merged_params["target"] = gm_action.target
                    await self._apply_gm_action(
                        session_id, gm_action.type, merged_params, active
                    )
                    if gm_action.type in {
                        "journal_update",
                        "quest_add",
                        "chronicle_add",
                        "state_transition",
                    }:
                        canon_dirty = True

        if canon_dirty and db is not None:
            try:
                from app.services import campaign_dossier_service

                await campaign_dossier_service.synthesize_canon_for_session(
                    session_id,
                    active.state_data,
                    [],
                    db,
                )
            except Exception as exc:
                logger.warning("Synthèse canon campagne ignorée : %s", exc)

    async def _publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Optional[Any],
    ) -> None:
        """Publie, persiste et lance le TTS pour une narration visible du MJ."""
        narration_id = str(uuid.uuid4())
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": narration_text, "speaker": "Maître du Jeu", "narration_id": narration_id},
            source="action_resolver",
        )

        if db is not None:
            from app.services.message_service import persist_narration

            await persist_narration(session_id, narration_text, "Maître du Jeu", db)

        asyncio.create_task(
            tts_router.synthesize_and_broadcast(narration_text, session_id, narration_id)
        )

    # ------------------------------------------------------------------
    # Conclusion sociale (compagnons ont déjà parlé)
    # ------------------------------------------------------------------

    async def social_conclude(
        self,
        session_id: str,
        active: ActiveSession,
        player_action: str,
        companion_responses: "List[Dict[str, str]]",
        db: Optional[Any] = None,
    ) -> None:
        """Appelle le MJ pour conclure une scène sociale après les réponses des compagnons.

        Publie et persiste la narration de conclusion, sans ré-exécuter
        la mécanique (les jets et transitions ont déjà été traités).
        """
        try:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": True},
                source="action_resolver",
            )
            gm_resp = await self._gm.narrate_social_conclude(
                game_state=active.state_data,
                player_action=player_action,
                companion_responses=companion_responses,
            )
        except Exception as exc:
            logger.error("ActionResolver.social_conclude : GMAgent échoué : %s", exc)
            gm_resp = None
        finally:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": False},
                source="action_resolver",
            )

        if gm_resp is None:
            return

        narration_id = str(uuid.uuid4())
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": gm_resp.narration, "speaker": "Maître du Jeu", "narration_id": narration_id},
            source="action_resolver",
        )
        if db is not None:
            from app.services.message_service import persist_narration
            await persist_narration(session_id, gm_resp.narration, "Maître du Jeu", db)
        asyncio.create_task(
            tts_router.synthesize_and_broadcast(gm_resp.narration, session_id, narration_id)
        )

    # ------------------------------------------------------------------
    # Résolution mécanique (délègue au moteur)
    # ------------------------------------------------------------------

    def _resolve_attack(
        self,
        attacker_id: Optional[str],
        target_id: Optional[str],
        state_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Résout un jet d'attaque + dégâts via engine/combat.py.

        Cherche les stats dans ``state_data["combatants"]`` ; utilise des
        valeurs par défaut si les combattants ne sont pas trouvés.
        """
        combatants: Dict[str, Any] = state_data.get("combatants", {})

        attacker = combatants.get(attacker_id, {}) if attacker_id else {}
        target = combatants.get(target_id, {}) if target_id else {}

        attack_bonus = int(attacker.get("attack_bonus", _DEFAULT_ATTACK_BONUS))
        target_ac = int(target.get("ac", _DEFAULT_AC))
        damage_notation: str = attacker.get("damage_notation", _DEFAULT_DAMAGE)

        attack = combat_engine.roll_attack(attack_bonus=attack_bonus, target_ac=target_ac)

        payload: Dict[str, Any] = {
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

    def _normalize_roll_event(self, raw: Dict[str, Any]) -> Dict[str, Any]:
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

    def _resolve_generic_roll(self, content: Optional[str]) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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

        payload: Dict[str, Any] = {
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
                db_slots: Dict[str, Any] = dict(char.spell_slots) if char.spell_slots else {}
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
            combatants: Dict[str, Any] = active.state_data.get("combatants", {})
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
            all_rolls: List[int] = []
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
            save_info: Dict[str, Any] = spell["save"]
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
                combatants_sv: Dict[str, Any] = active.state_data.get("combatants", {})
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
                + (f" (/{full_damage} moitié)" if target_saved and on_success == "half_damage" else "")
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
        state_data: Dict[str, Any],
    ) -> Dict[str, Any]:
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
        roll_results: Dict[str, Any],
        active: Any,
    ) -> None:
        """Met à jour les compteurs de jet de sauvegarde et gère les issues (stable / mort)."""
        if not character_id:
            return
        combatants: Dict[str, Any] = active.state_data.setdefault("combatants", {})
        cdata = combatants.get(character_id)
        if cdata is None:
            return
        ds: Dict[str, Any] = cdata.setdefault(
            "death_saves", {"successes": 0, "failures": 0, "stable": False}
        )

        if roll_results.get("critical_success"):
            cdata["hp"] = 1
            ds["stable"] = True
            conds: List[str] = list(cdata.get("conditions", []))
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
                conds_s: List[str] = list(cdata.get("conditions", []))
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
        state_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Jet de Médecine DD 10 pour stabiliser un personnage inconscient (SRD 5.2)."""
        from app.engine.ability_checks import ability_modifier  # noqa: PLC0415
        combatants: Dict[str, Any] = state_data.get("combatants", {})
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
        params: Dict[str, Any],
        fallback_character_id: Optional[str],
        active: ActiveSession,
    ) -> Optional[Dict[str, Any]]:
        """Exécute un jet de compétence/caractéristique/sauvegarde demandé par le GM.

        Retourne un payload prêt à être envoyé comme ROLL_RESULT, ou None si les
        données nécessaires sont manquantes.
        """
        from app.engine.ability_checks import (
            Ability,
            Proficiency,
            SKILL_ABILITY,
            ability_check,
            saving_throw,
            skill_check,
        )

        ability_long_map: dict[str, str] = {
            "strength": "str", "dexterity": "dex", "constitution": "con",
            "intelligence": "int", "wisdom": "wis", "charisma": "cha",
        }
        ability_enum_map = {a.value: a for a in Ability}

        skill_name = params.get("skill", "").lower().replace(" ", "_").replace("-", "_")
        ability_str = params.get("ability", "").lower()
        check_type = params.get("type", "check")
        dc = params.get("dc")
        target_id = params.get("target") or fallback_character_id

        characters = active.state_data.get("characters", {})
        combatants = active.state_data.get("combatants", {})
        char_data = characters.get(target_id) or combatants.get(target_id)
        if char_data is None and characters:
            char_data = next(iter(characters.values()))
        if not char_data:
            logger.warning("roll_request: personnage '%s' introuvable dans state_data", target_id)
            return None

        ab_scores: dict[str, int] = char_data.get("ability_scores") or {
            "str": int(char_data.get("str", 10)),
            "dex": int(char_data.get("dex", 10)),
            "con": 10, "int": 10, "wis": 10, "cha": 10,
        }
        level: int = int(char_data.get("level", 1))
        skill_profs: list[str] = list(char_data.get("skill_proficiencies", []))
        save_profs: list[str] = list(char_data.get("save_proficiencies", []))

        # Normalise ability_str vers forme courte ("wisdom" → "wis")
        ability_short: Optional[str] = (
            ability_long_map.get(ability_str, ability_str[:3] if ability_str else None)
            if ability_str else None
        )

        long_from_short = {v: k for k, v in ability_long_map.items()}

        try:
            if check_type == "save":
                long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
                ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
                score = ab_scores.get(ability_short or "wis", 10)
                result = saving_throw(score, ability_enum, level, long_ab in save_profs, dc)

            elif skill_name and skill_name in SKILL_ABILITY:
                gov = SKILL_ABILITY[skill_name]           # ex. Ability.WIS
                ab_key = gov.value[:3]                    # "wis" depuis "wisdom"
                score = ab_scores.get(ab_key, 10)
                prof = Proficiency.PROFICIENT if skill_name in skill_profs else Proficiency.NONE
                result = skill_check(score, skill_name, level, prof, dc)

            else:
                long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
                ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
                score = ab_scores.get(ability_short or "wis", 10)
                result = ability_check(score, dc, ability=ability_enum)

        except Exception as exc:
            logger.error("roll_request: calcul du jet échoué : %s", exc)
            return None

        return {
            "dice_notation": "1d20",
            "rolls": result.all_rolls,
            "d20": result.d20_roll,
            "modifier": result.modifier,
            "total": result.total,
            "dc": result.dc,
            "success": result.success,
            "label": result.label,
            "breakdown": result.breakdown,
            "character_id": target_id,
            "character_name": char_data.get("name", target_id or ""),
        }

    # ------------------------------------------------------------------

    async def _apply_gm_action(
        self,
        session_id: str,
        action_type: str,
        params: Dict[str, Any],
        active: ActiveSession,
    ) -> None:
        """Applique une action mécanique demandée par le GM.

        Les types supportés :
        - ``damage_apply`` : réduit les PV d'un combattant dans state_data.
        - ``condition_add`` / ``condition_remove`` : publie un événement de condition.
        - ``combatant_status`` : marque un PNJ comme actif, vaincu, rendu ou en fuite.
        - ``state_transition`` : ignoré ici (géré par SessionManager).
        """
        if action_type == "damage_apply":
            target_id = params.get("target")
            amount = int(params.get("amount", 0))
            combatants: Dict[str, Any] = active.state_data.setdefault("combatants", {})
            if target_id and target_id in combatants:
                old_hp = int(combatants[target_id].get("hp", 0))
                new_hp = max(0, old_hp - amount)
                combatants[target_id]["hp"] = new_hp
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.HP_CHANGED,
                    {
                        "combatant_id": target_id,
                        "delta": -amount,
                        "hp": new_hp,
                    },
                    source="action_resolver",
                )
                # Si un joueur tombe à 0 PV : init jets de sauvegarde contre la mort
                if new_hp == 0 and combatants[target_id].get("is_player", False):
                    cdata = combatants[target_id]
                    if "death_saves" not in cdata:
                        cdata["death_saves"] = {"successes": 0, "failures": 0, "stable": False}
                    conds: List[str] = list(cdata.get("conditions", []))
                    if "inconscient" not in conds:
                        conds.append("inconscient")
                        cdata["conditions"] = conds
                        await event_bus.publish_to_session(
                            session_id,
                            EventType.CONDITION_CHANGED,
                            {"combatant_id": target_id, "condition": "inconscient", "added": True},
                            source="action_resolver",
                        )
            else:
                logger.debug(
                    "damage_apply : cible '%s' non trouvée dans state_data.", target_id
                )

        elif action_type in ("condition_add", "condition_remove"):
            target_id = params.get("target")
            condition = params.get("condition", "")
            combatants: Dict[str, Any] = active.state_data.setdefault("combatants", {})
            if target_id and target_id in combatants and condition:
                conditions: List[str] = list(combatants[target_id].get("conditions", []))
                if action_type == "condition_add" and condition not in conditions:
                    conditions.append(condition)
                elif action_type == "condition_remove":
                    conditions = [c for c in conditions if c != condition]
                combatants[target_id]["conditions"] = conditions
                active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.CONDITION_CHANGED,
                {
                    "combatant_id": target_id,
                    "condition": condition,
                    "added": action_type == "condition_add",
                },
                source="action_resolver",
            )

        elif action_type == "combatant_status":
            target_id = params.get("target")
            status = str(params.get("status", "")).strip().lower()
            reason = str(params.get("reason", status or "resolved"))
            valid_statuses = {"active", "defeated", "surrendered", "fled"}
            if status not in valid_statuses:
                logger.warning(
                    "combatant_status ignoré : statut invalide '%s' — params=%s",
                    status,
                    params,
                )
                return

            combatants: Dict[str, Any] = active.state_data.setdefault("combatants", {})
            if not target_id or target_id not in combatants:
                logger.warning(
                    "combatant_status ignoré : cible '%s' introuvable — params=%s",
                    target_id,
                    params,
                )
                return

            combatants[target_id]["status"] = status
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.COMBATANT_STATUS_CHANGED,
                {
                    "combatant_id": target_id,
                    "combatant_name": combatants[target_id].get("name", target_id),
                    "status": status,
                    "reason": reason,
                },
                source="action_resolver",
            )

        elif action_type == "encounter_setup":
            monster_ids = params.get("monster_ids", [])
            context = params.get("context", "")
            if monster_ids:
                active.state_data["pending_encounter"] = {
                    "monster_ids": monster_ids,
                    "context": context,
                }
                active.mark_dirty()
                logger.info(
                    "encounter_setup : pending_encounter défini avec %s",
                    monster_ids,
                )

        elif action_type == "state_transition":
            # Le MJ demande un changement de phase. On pose un drapeau que
            # ws_game._dispatch_action consommera après le retour de resolve()
            # pour déclencher effectivement la transition (le resolver n'a pas
            # accès à la session DB ni au WebSocket).
            target_phase = (
                params.get("to")
                or params.get("target")
                or params.get("phase")
                or ""
            )
            target_phase = str(target_phase).upper()

            if target_phase == "COMBAT":
                if active.state_data.get("pending_encounter"):
                    active.state_data["pending_phase_transition"] = "COMBAT"
                    active.mark_dirty()
                    logger.info(
                        "state_transition : passage en COMBAT programmé (pending_encounter=%s)",
                        active.state_data["pending_encounter"].get("monster_ids"),
                    )
                else:
                    logger.warning(
                        "state_transition COMBAT ignoré : aucun pending_encounter défini "
                        "(le MJ devrait émettre encounter_setup avant state_transition)."
                    )
            elif target_phase:
                logger.info(
                    "state_transition %s : non implémenté (scope actuel : COMBAT uniquement).",
                    target_phase,
                )
            else:
                logger.debug("state_transition reçue sans phase cible : %s", params)

        elif action_type == "journal_update":
            journal: dict[str, Any] = active.state_data.setdefault("adventure_journal", {
                "location_region": None,
                "location_place": None,
                "time_of_day": "morning",
                "day_number": 1,
                "calendar_date": None,
                "weather": None,
            })
            for key in ("location_region", "location_place", "time_of_day",
                        "day_number", "calendar_date", "weather"):
                if key in params and params[key] is not None:
                    journal[key] = params[key]
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.JOURNAL_UPDATED,
                {"journal": dict(journal)},
                source="action_resolver",
            )

        elif action_type == "quest_add":
            quest_id = params.get("id")
            if not quest_id:
                logger.warning("quest_add ignoré : id manquant — params=%s", params)
                return
            quests: list[dict[str, Any]] = active.state_data.setdefault("quests", [])
            idx = next((i for i, q in enumerate(quests) if q.get("id") == quest_id), -1)
            quest_entry: dict[str, Any] = {
                "id": quest_id,
                "category": params.get("category", "secondaire"),
                "title": params.get("title", quest_id),
                "summary": params.get("summary", ""),
                "urgency": params.get("urgency"),
                "status": params.get("status", "active"),
            }
            if idx >= 0:
                quests[idx] = {**quests[idx], **quest_entry}
            else:
                quests.append(quest_entry)
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.QUEST_UPDATED,
                {"quests": list(quests)},
                source="action_resolver",
            )

        elif action_type == "chronicle_add":
            chron_id = params.get("id")
            kind = params.get("kind")
            if not chron_id or kind not in ("npc", "location"):
                logger.warning(
                    "chronicle_add ignoré : id ou kind invalide — params=%s", params
                )
                return
            chronicle: list[dict[str, Any]] = active.state_data.setdefault("chronicle", [])
            idx = next((i for i, e in enumerate(chronicle) if e.get("id") == chron_id), -1)
            entry: dict[str, Any] = {
                "id": chron_id,
                "kind": kind,
                "name": params.get("name", chron_id),
                "note": params.get("note", ""),
            }
            if idx >= 0:
                chronicle[idx] = {**chronicle[idx], **entry}
            else:
                chronicle.append(entry)
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.CHRONICLE_UPDATED,
                {"chronicle": list(chronicle)},
                source="action_resolver",
            )

        else:
            logger.warning("ActionResolver : type d'action GM inconnu '%s'.", action_type)
