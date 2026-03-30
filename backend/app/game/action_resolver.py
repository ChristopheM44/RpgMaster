"""Action resolver — pipeline : action joueur → moteur → agent GM → événements.

Pipeline complet pour une action joueur :
1. Résolution mécanique via le moteur (engine/) selon le type d'action
2. Construction du contexte et appel du GMAgent pour la narration
3. Publication des événements sur le bus (roll_result, narration, hp_changed…)

Pure orchestration : ce module ne contient pas de logique de règles.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.agents.gm_agent import GMAgent
from app.agents.schemas import AgentContext, AgentResponse
from app.engine import combat as combat_engine
from app.engine.dice import roll
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

_DEFAULT_AC = 10
_DEFAULT_ATTACK_BONUS = 3
_DEFAULT_DAMAGE = "1d6"

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
        elif action_type == "cast_spell":
            roll_results = self._resolve_generic_roll(content)

        # ----------------------------------------------------------------
        # 2. Construction du contexte pour le GMAgent
        # ----------------------------------------------------------------
        player_action_text = content or action_type
        if roll_results:
            player_action_text = (
                f"{player_action_text} [Résultat mécanique : {roll_results.get('summary', '')}]"
            )

        context = AgentContext(
            session_id=session_id,
            game_phase=active.phase.value.upper(),
            game_state=active.state_data,
            player_action=player_action_text,
        )

        gm_response: Optional[AgentResponse] = None
        try:
            gm_response = await self._gm.think(context)
        except Exception as exc:
            logger.error("ActionResolver : GMAgent échoué : %s", exc)

        # ----------------------------------------------------------------
        # 3. Publication des événements sur le bus
        # ----------------------------------------------------------------
        if roll_results:
            await event_bus.publish_to_session(
                session_id,
                EventType.ROLL_RESULT,
                roll_results,
                source="action_resolver",
            )

        narration_text = gm_response.content if gm_response else _FALLBACK_NARRATION
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": narration_text, "speaker": "Maître du Jeu"},
            source="action_resolver",
        )

        # ----------------------------------------------------------------
        # 4. Traitement des actions mécaniques demandées par le GM
        # ----------------------------------------------------------------
        if gm_response:
            for gm_action in gm_response.actions:
                # Fusionner gm_action.target dans params pour simplifier _apply_gm_action
                merged_params: Dict[str, Any] = dict(gm_action.params)
                if gm_action.target and "target" not in merged_params:
                    merged_params["target"] = gm_action.target
                await self._apply_gm_action(
                    session_id, gm_action.type, merged_params, active
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

    # ------------------------------------------------------------------
    # Application des actions GM (dégâts, conditions, etc.)
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
            else:
                logger.debug(
                    "damage_apply : cible '%s' non trouvée dans state_data.", target_id
                )

        elif action_type in ("condition_add", "condition_remove"):
            target_id = params.get("target")
            condition = params.get("condition", "")
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

        elif action_type == "state_transition":
            # La transition de phase est déléguée au SessionManager via ws_game.py.
            logger.debug("state_transition demandée par le GM : %s", params)

        else:
            logger.warning("ActionResolver : type d'action GM inconnu '%s'.", action_type)
