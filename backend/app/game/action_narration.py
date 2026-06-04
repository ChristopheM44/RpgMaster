"""Helpers and constants for tactical block and fallback narrations."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# ---------------------------------------------------------------------------
# Narrations variées pour les blocages tactiques (portée / chemin absent)
# ---------------------------------------------------------------------------
_ATTACK_BLOCK_TEMPLATES = [
    "{name} cherche un angle d'attaque, mais n'est pas à portée.",
    "{name} marque une pause — aucune cible accessible depuis cette position.",
    "{name} pivote, guettant une ouverture qui ne vient pas.",
    "{name} retient son élan : les combattants sont trop éloignés pour frapper.",
    "{name} observe les lignes de mêlée, mais l'angle est fermé.",
    "{name} se repositionne lentement, sans prise immédiate.",
]
_SPELL_BLOCK_TEMPLATES = [
    "{name} amorce un geste runique, mais sa cible est hors de portée.",
    "{name} suspend son incantation — aucune cible dans le rayon d'action.",
    "{name} retient son sort : l'angle magique est trop précaire.",
    "{name} concentre son énergie, cherchant une ligne de vue qui n'existe pas.",
    "{name} murmure les mots du sort, puis les laisse s'éteindre, faute d'ouverture.",
]


# ---------------------------------------------------------------------------
# Garde-fou hors-combat : actions improvisées risquées sans roll_request GM
# ---------------------------------------------------------------------------
# Verbes qui signalent une action physiquement risquée ou à efficacité incertaine.
# Le pattern est volontairement conservateur pour éviter les faux positifs.
_DANGEROUS_OBJECT_PATTERN = (
    r"(?:electr|électr|ardent|brul|brûl|corros|poison|vibr|lumines|instable|"
    r"surchauff|chaud|brillant|lueur|ozone|soufre|siphon)"
)

_RISKY_ACTION_PATTERN = re.compile(
    r"""
    (?:
        (?:trancher|couper|taillader|frapper|poignarder)\s+(?:avec|la|le|son|l'|les)
        |
        (?:enflammer|enflammer|mettre\s+le\s+feu|faire\s+prendre\s+feu|allumer)
        |
        (?:enfoncer|plonger|insérer|glisser)\s+(?:mon|ma|mes|son|sa|l'|la|le)
        |
        (?:escalader|grimper|traverser\s+en\s+courant)
        |
        (?:sauter|bondir|me\s+lancer)\s+(?:par[\s-]dessus|dans|sur)
        |
        (?:crocheter|forcer|fracturer|défoncer)\s+(?:la|le|les)
        |
        (?:toucher|saisir|attraper|empoigner|manipuler|ouvrir)\s+
            (?:la|le|les|l'|un|une|des|mon|ma|mes)\s+
            [^.?!]{0,80}
            """
    + _DANGEROUS_OBJECT_PATTERN
    + r"""
        |
        pose(?:r)?\s+(?:ma|la|une)\s+main\s+sur\s+
            [^.?!]{0,80}
            """
    + _DANGEROUS_OBJECT_PATTERN
    + r"""
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Skills par défaut selon le type de risque détecté (conservateur)
_RISKY_SKILL_DEFAULTS = {
    "trancher": ("Athletics", "str", 13, "check"),
    "enflammer": ("Arcana", "int", 12, "check"),
    "enfoncer": ("Acrobatics", "dex", 13, "check"),
    "escalader": ("Athletics", "str", 12, "check"),
    "grimper": ("Athletics", "str", 12, "check"),
    "sauter": ("Athletics", "str", 12, "check"),
    "bondir": ("Athletics", "str", 12, "check"),
    "crocheter": ("SleightOfHand", "dex", 15, "check"),
    "forcer": ("Athletics", "str", 14, "check"),
    "fracturer": ("Athletics", "str", 14, "check"),
    "toucher": ("Acrobatics", "dex", 14, "save"),
    "saisir": ("Acrobatics", "dex", 14, "save"),
    "attraper": ("Acrobatics", "dex", 14, "save"),
    "empoigner": ("Acrobatics", "dex", 14, "save"),
    "manipuler": ("Acrobatics", "dex", 14, "save"),
    "ouvrir": ("Acrobatics", "dex", 14, "save"),
    "pose": ("Acrobatics", "dex", 14, "save"),
    "poser": ("Acrobatics", "dex", 14, "save"),
}


def _infer_risky_roll_request(content: str) -> dict[str, Any] | None:
    """Si l'action free_text contient un verbe risqué, retourne un roll_request minimal.

    Conservateur : ne tire pas sur les verbes ambigus ni les descriptions passives.
    Retourne None si aucun pattern ne correspond.
    """
    if not content or len(content) < 10:
        return None
    normalized = content.lower()
    # Cherche le premier verbe déclencheur pour adapter le skill
    for keyword, (skill, ability, dc, roll_type) in _RISKY_SKILL_DEFAULTS.items():
        if keyword in normalized:
            if _RISKY_ACTION_PATTERN.search(content):
                return {
                    "type": "roll_request",
                    "target": None,
                    "params": {
                        "skill": skill,
                        "ability": ability,
                        "dc": dc,
                        "type": roll_type,
                        "reason": "action_risquee_libre",
                    },
                }
    return None


def _tactical_block_narration(actor_name: str, action_type: str) -> str:
    """Retourne une phrase variée non-technique décrivant un blocage tactique.

    Le choix est déterministe par (actor_name, action_type) pour éviter les
    changements aléatoires entre appels, tout en variant selon les acteurs.
    """
    templates = _SPELL_BLOCK_TEMPLATES if action_type == "cast_spell" else _ATTACK_BLOCK_TEMPLATES
    seed = int(hashlib.md5(f"{actor_name}:{action_type}".encode()).hexdigest()[:8], 16)
    template = templates[seed % len(templates)]
    return template.format(name=actor_name)


_FALLBACK_NARRATION = ""
