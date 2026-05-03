"""Import monsters from the French SRD 5.2.1 PDF into monsters.json.

Reads ``docs/FR_SRD_CC_v5.2.1.pdf`` (pages 270-380 = the bestiary) and produces
structured entries that conform to ``MonsterSchema``. Existing curated entries
in ``monsters.json`` are preserved verbatim — only missing monsters are
appended.

The PDF stat-block format is highly regular:

    <Name>
    [<Name>]  (sometimes doubled as a caption)
    <Type> [(<subtype>)] de taille <Size>, <alignment>
    CA <ac> Initiative <init>
    Pv <hp> (<hit_dice>)
    Vitesse <speed_str>
    MOD JS  MOD JS  MOD JS
    For <s> <smod> <sjs>  Dex <d> ...  Con <c> ...
    Int <i> ...           Sag <w> ... Cha <ch> ...
    [Compétences <list>]
    [Vulnérabilités <list>]
    [Résistances <list>]
    [Immunités <list>]
    [Équipement <list>]
    Sens <senses_str>
    Langues <lang>
    FP <cr> (<xp> PX [, ou ... dans son antre]; BM +<pb>)
    [Traits]
    <Trait Name>. <body...>
    ...
    Actions
    <Action Name>. <body...>
    ...
    [Actions Bonus]
    [Réactions]
    [Actions Légendaires]

Usage::

    cd backend
    source .venv/bin/activate
    python -m scripts.import_monsters_from_srd          # writes monsters.json
    python -m scripts.import_monsters_from_srd --dry-run  # only prints summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.srd_data.schemas import MonsterSchema  # noqa: E402

PDF_PATH = BACKEND_DIR.parent / "docs" / "FR_SRD_CC_v5.2.1.pdf"
MONSTERS_JSON = BACKEND_DIR / "app" / "engine" / "srd_data" / "monsters.json"
BESTIARY_PAGES = (269, 379)  # 0-indexed inclusive

# --- Mapping tables -------------------------------------------------------

SIZE_FR_TO_EN: Dict[str, str] = {
    "TP": "Tiny",
    "P": "Small",
    "M": "Medium",
    "G": "Large",
    "TG": "Huge",
    "Gig": "Gargantuan",
}

TYPE_FR_TO_EN: Dict[str, str] = {
    "Aberration": "aberration",
    "Bête": "beast",
    "Céleste": "celestial",
    "Construction": "construct",
    "Dragon": "dragon",
    "Élémentaire": "elemental",
    "Fée": "fey",
    "Fiélon": "fiend",
    "Géant": "giant",
    "Humanoïde": "humanoid",
    "Monstruosité": "monstrosity",
    "Mort-vivant": "undead",
    "Plante": "plant",
    "Vase": "ooze",
}

ALIGNMENT_FR_TO_EN: Dict[str, str] = {
    "loyal bon": "lawful good",
    "neutre bon": "neutral good",
    "chaotique bon": "chaotic good",
    "loyal neutre": "lawful neutral",
    "neutre": "neutral",
    "chaotique neutre": "chaotic neutral",
    "loyal mauvais": "lawful evil",
    "neutre mauvais": "neutral evil",
    "chaotique mauvais": "chaotic evil",
    "non aligné": "unaligned",
    "non alignée": "unaligned",
    "selon l'alignement de son invocateur": "any alignment",
    "selon l'alignement": "any alignment",
}

ABILITY_FR_TO_EN: Dict[str, str] = {
    "For": "strength",
    "Dex": "dexterity",
    "Con": "constitution",
    "Int": "intelligence",
    "Sag": "wisdom",
    "Cha": "charisma",
}

SKILL_FR_TO_EN: Dict[str, str] = {
    "Acrobaties": "acrobatics",
    "Arcanes": "arcana",
    "Athlétisme": "athletics",
    "Discrétion": "stealth",
    "Dressage": "animal_handling",
    "Escamotage": "sleight_of_hand",
    "Histoire": "history",
    "Intimidation": "intimidation",
    "Intuition": "insight",
    "Investigation": "investigation",
    "Médecine": "medicine",
    "Nature": "nature",
    "Perception": "perception",
    "Persuasion": "persuasion",
    "Religion": "religion",
    "Représentation": "performance",
    "Survie": "survival",
    "Tromperie": "deception",
}

DAMAGE_FR_TO_EN: Dict[str, str] = {
    "acide": "acid",
    "contondant": "bludgeoning",
    "contondants": "bludgeoning",
    "feu": "fire",
    "force": "force",
    "foudre": "lightning",
    "froid": "cold",
    "nécrotique": "necrotic",
    "nécrotiques": "necrotic",
    "perforant": "piercing",
    "perforants": "piercing",
    "poison": "poison",
    "psychique": "psychic",
    "psychiques": "psychic",
    "radiant": "radiant",
    "radiants": "radiant",
    "tonnerre": "thunder",
    "tranchant": "slashing",
    "tranchants": "slashing",
}

CONDITION_FR_TO_EN: Dict[str, str] = {
    "À terre": "prone",
    "Aveuglé": "blinded",
    "Agrippé": "grappled",
    "Assourdi": "deafened",
    "Charmé": "charmed",
    "Effrayé": "frightened",
    "Empoisonné": "poisoned",
    "Entravé": "restrained",
    "Étourdi": "stunned",
    "Épuisement": "exhaustion",
    "Inconscient": "unconscious",
    "Invisible": "invisible",
    "Métamorphosé": "petrified",
    "Neutralisé": "incapacitated",
    "Paralysé": "paralyzed",
    "Pétrifié": "petrified",
}

# Speed translation ("escalade", "vol", "fouissement", "nage")
SPEED_KEYWORD_FR_TO_EN: Dict[str, str] = {
    "marche": "walk",
    "escalade": "climb",
    "vol": "fly",
    "nage": "swim",
    "fouissement": "burrow",
}

# Sense keywords ("Vision dans le noir 18 m", "Vision aveugle", "Vision lucide", "Perception des vibrations")
SENSE_FR_TO_EN: Dict[str, str] = {
    "vision dans le noir": "darkvision_m",
    "vision aveugle": "blindsight_m",
    "vision lucide": "truesight_m",
    "perception des vibrations": "tremorsense_m",
}

# Comprehensive FR→EN monster name mapping. Seeded from the existing 32
# entries plus standard D&D 2024 SRD names. Falls back to FR if unknown.
MONSTER_FR_TO_EN: Dict[str, str] = {
    # Existing curated entries
    "Rat": "Rat",
    "Serpent venimeux": "Poisonous Snake",
    "Bandit": "Bandit",
    "Sectateur": "Cultist",
    "Squelette": "Skeleton",
    "Zombi": "Zombie",
    "Ogre": "Ogre",
    "Hibours": "Owlbear",
    "Troll": "Troll",
    "Loup": "Wolf",
    "Goule": "Ghoul",
    "Loup-garou": "Werewolf",
    "Gargouille": "Gargoyle",
    "Blême": "Ghast",
    "Manticore": "Manticore",
    "Momie": "Mummy",
    "Vampirien": "Vampire Spawn",
    "Géant des collines": "Hill Giant",
    "Tertre errant": "Shambling Mound",
    "Vouivre": "Wyvern",
    "Géant du givre": "Frost Giant",
    "Géant du feu": "Fire Giant",
    "Jeune dragon rouge": "Young Red Dragon",
    "Golem de pierre": "Stone Golem",
    "Vampire": "Vampire",
    "Loup sanguinaire": "Dire Wolf",
    # Common SRD monsters
    "Aigle": "Eagle",
    "Aigle géant": "Giant Eagle",
    "Allosaure": "Allosaurus",
    "Âne": "Donkey",
    "Araignée de phase": "Phase Spider",
    "Archélon": "Archelon",
    "Archimage": "Archmage",
    "Armure animée": "Animated Armor",
    "Assassin": "Assassin",
    "Autrache": "Axe Beak",
    "Babélien": "Aboleth",
    "Babouin": "Baboon",
    "Balor": "Balor",
    "Basilic": "Basilisk",
    "Béhir": "Behir",
    "Belette": "Weasel",
    "Belette géante": "Giant Weasel",
    "Berserker": "Berserker",
    "Blaireau": "Badger",
    "Blaireau géant": "Giant Badger",
    "Bulette": "Bulette",
    "Capitaine de la garde": "Guard Captain",
    "Capitaine hobgobelin": "Hobgoblin Captain",
    "Capitaine pirate": "Pirate Captain",
    "Cervidé géant": "Giant Elk",
    "Chacal": "Jackal",
    "Chameau": "Camel",
    "Chat": "Cat",
    "Chauve-souris": "Bat",
    "Chauve-souris géante": "Giant Bat",
    "Chef de bande": "Bandit Captain",
    "Chef gobelin": "Goblin Boss",
    "Chef gros-bras": "Bugbear Chief",
    "Cheval de selle": "Riding Horse",
    "Cheval de trait": "Draft Horse",
    "Chevalier": "Knight",
    "Chèvre": "Goat",
    "Chèvre géante": "Giant Goat",
    "Chien du trépas": "Death Dog",
    "Chien esquiveur": "Blink Dog",
    "Chimère": "Chimera",
    "Chouette": "Owl",
    "Chouette géante": "Giant Owl",
    "Chtuul": "Chuul",
    "Cockatrice": "Cockatrice",
    "Combattant gnoll": "Gnoll Warrior",
    "Combattant gobelin": "Goblin Warrior",
    "Combattant gobelours": "Bugbear Warrior",
    "Combattant hobgobelin": "Hobgoblin Warrior",
    "Combattant kobold": "Kobold Warrior",
    "Combattant sahuagin": "Sahuagin Warrior",
    "Corbeau": "Raven",
    "Couatl": "Couatl",
    "Crabe": "Crab",
    "Crabe géant": "Giant Crab",
    "Crapaud géant": "Giant Toad",
    "Criard": "Shrieker",
    "Crocodile": "Crocodile",
    "Crocodile géant": "Giant Crocodile",
    "Cube gélatineux": "Gelatinous Cube",
    "Demi-dragon": "Half-Dragon",
    "Destrier": "Warhorse",
    "Destrier squelette": "Skeletal Warhorse",
    "Déva": "Deva",
    "Diable barbelé": "Barbed Devil",
    "Diable barbu": "Bearded Devil",
    "Diable cornu": "Horned Devil",
    "Diable des chaînes": "Chain Devil",
    "Diable gelé": "Ice Devil",
    "Diable osseux": "Bone Devil",
    "Diablotin": "Imp",
    "Diantrefosse": "Pit Fiend",
    "Djinn": "Djinni",
    "Doppelganger": "Doppelganger",
    "Dragon blanc adulte": "Adult White Dragon",
    "Dragon blanc vénérable": "Ancient White Dragon",
    "Dragon bleu adulte": "Adult Blue Dragon",
    "Dragon bleu vénérable": "Ancient Blue Dragon",
    "Dragon d'airain adulte": "Adult Brass Dragon",
    "Dragon d'airain vénérable": "Ancient Brass Dragon",
    "Dragon d'argent adulte": "Adult Silver Dragon",
    "Dragon d'argent vénérable": "Ancient Silver Dragon",
    "Dragon d'or adulte": "Adult Gold Dragon",
    "Dragon d'or vénérable": "Ancient Gold Dragon",
    "Dragon de bronze adulte": "Adult Bronze Dragon",
    "Dragon de bronze vénérable": "Ancient Bronze Dragon",
    "Dragon de cuivre adulte": "Adult Copper Dragon",
    "Dragon de cuivre vénérable": "Ancient Copper Dragon",
    "Dragon noir adulte": "Adult Black Dragon",
    "Dragon noir vénérable": "Ancient Black Dragon",
    "Dragon rouge adulte": "Adult Red Dragon",
    "Dragon rouge vénérable": "Ancient Red Dragon",
    "Dragon vert adulte": "Adult Green Dragon",
    "Dragon vert vénérable": "Ancient Green Dragon",
    "Dragonnet blanc": "White Dragon Wyrmling",
    "Dragonnet bleu": "Blue Dragon Wyrmling",
    "Dragonnet d'airain": "Brass Dragon Wyrmling",
    "Dragonnet d'argent": "Silver Dragon Wyrmling",
    "Dragonnet d'or": "Gold Dragon Wyrmling",
    "Dragonnet de bronze": "Bronze Dragon Wyrmling",
    "Dragonnet de cuivre": "Copper Dragon Wyrmling",
    "Dragonnet noir": "Black Dragon Wyrmling",
    "Dragonnet rouge": "Red Dragon Wyrmling",
    "Dragonnet vert": "Green Dragon Wyrmling",
    "Dragon-tortue": "Dragon Turtle",
    "Dretch": "Dretch",
    "Drider": "Drider",
    "Druide": "Druid",
    "Dryade": "Dryad",
    "Éclaireur": "Scout",
    "Éfrit": "Efreeti",
    "Élémentaire de l'air": "Air Elemental",
    "Élémentaire de la terre": "Earth Elemental",
    "Élémentaire de l'eau": "Water Elemental",
    "Élémentaire du feu": "Fire Elemental",
    "Éléphant": "Elephant",
    "Enlaceur": "Roper",
    "Épaulard": "Killer Whale",
    "Épée volante": "Flying Sword",
    "Érinye": "Erinyes",
    "Espion": "Spy",
    "Esprit follet": "Sprite",
    "Ettercap": "Ettercap",
    "Ettin": "Ettin",
    "Familier de vampire": "Vampire Familiar",
    "Fanatique de secte": "Cult Fanatic",
    "Fantassin": "Soldier",
    "Fantôme": "Ghost",
    "Faucon": "Hawk",
    "Faucon de sang": "Blood Hawk",
    "Feu follet": "Will-o'-Wisp",
    "Garde": "Guard",
    "Garde animé": "Animated Guard",
    "Géant des nuages": "Cloud Giant",
    "Géant des pierres": "Stone Giant",
    "Géant des tempêtes": "Storm Giant",
    "Gelée ocre": "Ochre Jelly",
    "Glabrezu": "Glabrezu",
    "Gladiateur": "Gladiator",
    "Golem d'argile": "Clay Golem",
    "Golem de chair": "Flesh Golem",
    "Golem de fer": "Iron Golem",
    "Gorgone": "Gorgon",
    "Grand cervidé": "Stag",
    "Grand singe": "Ape",
    "Grenouille": "Frog",
    "Grenouille géante": "Giant Frog",
    "Grick": "Grick",
    "Griffon": "Griffon",
    "Gros-bras": "Bugbear",
    "Guenaude marine": "Sea Hag",
    "Guenaude nocturne": "Night Hag",
    "Guenaude verte": "Green Hag",
    "Guêpe géante": "Giant Wasp",
    "Harpie": "Harpy",
    "Hezrou": "Hezrou",
    "Hippocampe": "Seahorse",
    "Hippocampe géant": "Giant Seahorse",
    "Hippogriffe": "Hippogriff",
    "Hippopotame": "Hippopotamus",
    "Homoncule": "Homunculus",
    "Horriflamme": "Hell Hound",
    "Hydre": "Hydra",
    "Hyène": "Hyena",
    "Hyène géante": "Giant Hyena",
    "Incube": "Incubus",
    "Jeune dragon blanc": "Young White Dragon",
    "Jeune dragon bleu": "Young Blue Dragon",
    "Jeune dragon d'airain": "Young Brass Dragon",
    "Jeune dragon d'argent": "Young Silver Dragon",
    "Jeune dragon d'or": "Young Gold Dragon",
    "Jeune dragon de bronze": "Young Bronze Dragon",
    "Jeune dragon de cuivre": "Young Copper Dragon",
    "Jeune dragon noir": "Young Black Dragon",
    "Jeune dragon vert": "Young Green Dragon",
    "Kraken": "Kraken",
    "Lamie": "Lamia",
    "Lémure": "Lemure",
    "Lézard": "Lizard",
    "Lézard géant": "Giant Lizard",
    "Liche": "Lich",
    "Licorne": "Unicorn",
    "Lion": "Lion",
    "Loup arctique": "Winter Wolf",
    "Mage": "Mage",
    "Magmatique": "Magmin",
    "Mammouth": "Mammoth",
    "Manteleur": "Cloaker",
    "Mante obscure": "Darkmantle",
    "Marilith": "Marilith",
    "Méduse": "Medusa",
    "Méphite gelé": "Ice Mephit",
    "Méphite magmatique": "Magma Mephit",
    "Méphite poussiéreux": "Dust Mephit",
    "Méphite vaporeux": "Steam Mephit",
    "Merrow": "Merrow",
    "Mille-pattes géant": "Giant Centipede",
    "Mimique": "Mimic",
    "Minotaure de Baphomet": "Minotaur",
    "Minotaure squelette": "Minotaur Skeleton",
    "Molosse": "Mastiff",
    "Molosse infernal": "Hell Hound",
    "Momie auguste": "Mummy Lord",
    "Mule": "Mule",
    "Naga corrupteur": "Spirit Naga",
    "Naga gardien": "Guardian Naga",
    "Nalfeshnie": "Nalfeshnee",
    "Nécronte": "Necronte",
    "Noble": "Noble",
    "Nuée de chauves-souris": "Swarm of Bats",
    "Nuée de corbeaux": "Swarm of Ravens",
    "Nuée de piranhas": "Swarm of Piranhas",
    "Nuée de rats": "Swarm of Rats",
    "Nuée de sénestres": "Swarm of Quippers",
    "Nuée de serpents venimeux": "Swarm of Poisonous Snakes",
    "Nuée d'insectes": "Swarm of Insects",
    "Ogre zombi": "Ogre Zombie",
    "Ombre": "Shadow",
    "Oni": "Oni",
    "Otyugh": "Otyugh",
    "Ours brun": "Brown Bear",
    "Ours-garou": "Werebear",
    "Ours noir": "Black Bear",
    "Ours polaire": "Polar Bear",
    "Oxydeur": "Rust Monster",
    "Panthère": "Panther",
    "Pégase": "Pegasus",
    "Petit cervidé": "Deer",
    "Pieuvre": "Octopus",
    "Pieuvre géante": "Giant Octopus",
    "Piranha": "Quipper",
    "Pirate": "Pirate",
    "Planétar": "Planetar",
    "Plésiosaure": "Plesiosaurus",
    "Poney": "Pony",
    "Pouding noir": "Black Pudding",
    "Prêtre": "Priest",
    "Pseudodragon": "Pseudodragon",
    "Ptéranodon": "Pteranodon",
    "Quasit": "Quasit",
    "Rakshasa": "Rakshasa",
    "Rat-garou": "Wererat",
    "Rat géant": "Giant Rat",
    "Remorhaz": "Remorhaz",
    "Requin-chasseur": "Hunter Shark",
    "Requin de récif": "Reef Shark",
    "Requin géant": "Giant Shark",
    "Rhinocéros": "Rhinoceros",
    "Roturier": "Commoner",
    "Rukh": "Roc",
    "Salamandre": "Salamander",
    "Sanglier": "Boar",
    "Sanglier-garou": "Wereboar",
    "Sanglier géant": "Giant Boar",
    "Satyre": "Satyr",
    "Sbire gobelin": "Goblin Minion",
    "Scarabée de feu géant": "Giant Fire Beetle",
    "Scorpion": "Scorpion",
    "Scorpion géant": "Giant Scorpion",
    "Sentinelle azer": "Azer Sentinel",
    "Serpent constricteur": "Constrictor Snake",
    "Serpent constricteur géant": "Giant Constrictor Snake",
    "Serpent venimeux géant": "Giant Poisonous Snake",
    "Serpent volant": "Flying Snake",
    "Singe géant": "Giant Ape",
    "Solar": "Solar",
    "Soldat centaure": "Centaur Trooper",
    "Spectre": "Specter",
    "Sphinx érudit": "Lore Sphinx",
    "Sphinx merveilleux": "Wonder Sphinx",
    "Sphinx valeureux": "Valor Sphinx",
    "Strige": "Stirge",
    "Succube": "Succubus",
    "Sylvanien": "Treant",
    "Tapis étrangleur": "Rug of Smothering",
    "Tarasque": "Tarrasque",
    "Thallophyte violette": "Violet Fungus",
    "Tigre": "Tiger",
    "Tigre à dents de sabre": "Saber-Toothed Tiger",
    "Tigre-garou": "Weretiger",
    "Tirailleur thalasséen": "Sahuagin Skirmisher",
    "Torve": "Grimlock",
    "Traqueur gobelours": "Bugbear Stalker",
    "Traqueur invisible": "Invisible Stalker",
    "Tricératops": "Triceratops",
    "Tyrannosaure": "Tyrannosaurus Rex",
    "Vase grise": "Gray Ooze",
    "Vautour": "Vulture",
    "Vautour géant": "Giant Vulture",
    "Ver pourpre": "Purple Worm",
    "Vétéran": "Veteran",
    "Vrock": "Vrock",
    "Worg": "Worg",
    "Xorn": "Xorn",
    # Late additions discovered during dry-run
    "Aboleth": "Aboleth",
    "Ankheg": "Ankheg",
    "Arbre éveillé": "Awakened Tree",
    "Arbuste éveillé": "Awakened Shrub",
    "Abattis de troll": "Troll Brute",
    "Ankylosaure": "Ankylosaurus",
    "Araignée": "Spider",
    "Araignée-loup géante": "Giant Wolf Spider",
}

# --- Utilities ------------------------------------------------------------


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace("'", "_").replace("’", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def parse_int(s: str, default: Optional[int] = None) -> Optional[int]:
    s = (s or "").strip().replace("−", "-").replace("−", "-")
    try:
        return int(s)
    except ValueError:
        return default


# --- PDF reading ----------------------------------------------------------


def extract_bestiary_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts: List[str] = []
    for i in range(BESTIARY_PAGES[0], BESTIARY_PAGES[1] + 1):
        text = reader.pages[i].extract_text() or ""
        # Strip recurring page chrome, in either order.
        text = re.sub(
            r"^\s*(?:Document de Référence du Système 5\.2\.1\s*\n\s*\d+|\d+\s*\n\s*Document de Référence du Système 5\.2\.1)\s*\n",
            "",
            text,
            flags=re.MULTILINE,
        )
        parts.append(text)
    return "\n".join(parts)


# --- Stat-block detection -------------------------------------------------

# Matches the type/size/alignment line that anchors every stat-block.
TYPE_LINE_RE = re.compile(
    r"^(?P<type>"
    + "|".join(re.escape(k) for k in TYPE_FR_TO_EN)
    + r")(?:\s*\((?P<subtype>[^)]+)\))?"
    r"\s+de taille\s+(?P<size>TP|P|M|G|TG|Gig)"
    r"\s*,\s*(?P<align>[^\n]+?)$",
    re.MULTILINE,
)


def find_block_starts(text: str) -> List[Tuple[int, re.Match[str]]]:
    """Return the (start_index, match) of every type-line in text."""
    return [(m.start(), m) for m in TYPE_LINE_RE.finditer(text)]


def find_name_above(text: str, type_line_start: int) -> Optional[str]:
    """Walk backwards from a type-line start to find the monster name.

    The PDF often duplicates the name (caption + heading), so we may see two
    consecutive identical lines. We accept a 1-3 word title-case line that is
    not itself a structural keyword.
    """
    # Take the 2 non-empty lines just above the type-line.
    head = text[:type_line_start].rstrip("\n")
    lines = [ln.strip() for ln in head.split("\n") if ln.strip()]
    if not lines:
        return None
    # Discard the immediate previous line if it's just a duplicate of the
    # closer-to-type-line one.
    candidate = lines[-1]
    if len(lines) >= 2 and lines[-1] == lines[-2]:
        candidate = lines[-1]
    # Reject "Actions", "Traits", etc. that may appear right above when a
    # stat-block follows another.
    if candidate in {"Actions", "Traits", "Réactions", "Actions Bonus",
                     "Actions Légendaires", "Repaire"}:
        if len(lines) >= 2:
            candidate = lines[-2]
        else:
            return None
    # Strip trailing parenthetical (e.g. "Hibours (ours-hibou)" → "Hibours")
    candidate = re.sub(r"\s*\([^)]*\)\s*$", "", candidate).strip()
    # The PDF sometimes uses a plural caption like "Squelettes" above the
    # singular block. Drop a trailing "s" only if it makes the result match the
    # mapping table — handled later by the caller via fallback.
    return candidate or None


# --- Field extractors -----------------------------------------------------


def parse_speed(speed_str: str) -> Dict[str, int]:
    """Parse 'Vitesse 9 m, escalade 6 m, vol 12 m' → {walk:9, climb:6, fly:12}."""
    out: Dict[str, int] = {}
    s = speed_str.lower()
    # First chunk before comma is the walking speed (no keyword).
    chunks = [c.strip() for c in s.split(",")]
    if not chunks:
        return out
    first = chunks[0]
    m = re.match(r"([\d,\.]+)\s*m", first)
    if m:
        out["walk"] = int(float(m.group(1).replace(",", ".")))
    for chunk in chunks[1:]:
        for kw_fr, kw_en in SPEED_KEYWORD_FR_TO_EN.items():
            if chunk.startswith(kw_fr):
                m = re.search(r"([\d,\.]+)\s*m", chunk)
                if m:
                    out[kw_en] = int(float(m.group(1).replace(",", ".")))
                break
    return out


def parse_ability_block(text: str) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Parse the For/Dex/.../Cha block.

    The PDF lays it out as two lines like::

        For 30 +10 +10 Dex 11 +0 +9 Con 30 +10 +10
        Int 3 −4 +5 Sag 11 +0 +9 Cha 11 +0 +9

    Returns ``(scores, saving_throws_with_proficiency_only)`` — the saving
    throws dict only contains abilities whose JS bonus differs from the raw
    modifier (i.e. the monster has proficiency in that save).
    """
    scores: Dict[str, int] = {}
    saves: Dict[str, int] = {}
    # Iterate ability triples: (ability, score, mod, save)
    pattern = re.compile(
        r"(For|Dex|Con|Int|Sag|Cha)\s+(-?\d+)\s+([+-]?[\d−\-]+)\s+([+-]?[\d−\-]+)"
    )
    for m in pattern.finditer(text):
        ab_fr, score, mod, save = m.group(1), m.group(2), m.group(3), m.group(4)
        ab_en = ABILITY_FR_TO_EN[ab_fr]
        scores[ab_en] = parse_int(score, 10) or 10
        mod_v = parse_int(mod)
        save_v = parse_int(save)
        if mod_v is not None and save_v is not None and save_v != mod_v:
            saves[ab_en] = save_v
    return scores, saves


def parse_skills(line: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    # "Compétences Perception +5, Discrétion +3"
    body = re.sub(r"^Compétences\s*", "", line).strip()
    for part in re.split(r"[,;]\s*", body):
        m = re.match(r"([A-ZÉÈ][\wéèêâàç' ]+?)\s+([+-]\d+)", part.strip())
        if not m:
            continue
        skill_fr = m.group(1).strip()
        if skill_fr in SKILL_FR_TO_EN:
            out[SKILL_FR_TO_EN[skill_fr]] = parse_int(m.group(2)) or 0
    return out


def parse_damage_list(body: str) -> List[str]:
    """Split a comma/semicolon list of FR damage types and translate."""
    out: List[str] = []
    for part in re.split(r"[,;]\s*", body):
        key = part.strip().lower()
        if key in DAMAGE_FR_TO_EN:
            out.append(DAMAGE_FR_TO_EN[key])
    return out


def parse_condition_list(body: str) -> List[str]:
    out: List[str] = []
    for part in re.split(r"[,;]\s*", body):
        key = part.strip()
        if key in CONDITION_FR_TO_EN:
            out.append(CONDITION_FR_TO_EN[key])
    return out


def parse_immunities_line(line: str) -> Tuple[List[str], List[str]]:
    """'Immunités feu, poison ; Charmé, Effrayé' → (damage_imm, condition_imm)."""
    body = re.sub(r"^Immunités\s*", "", line).strip()
    if ";" in body:
        damage_part, cond_part = body.split(";", 1)
    else:
        # Heuristic: if any token matches a condition, treat the whole line as conditions.
        if any(c in CONDITION_FR_TO_EN for c in re.split(r"[,;]\s*", body)):
            damage_part, cond_part = "", body
        else:
            damage_part, cond_part = body, ""
    return parse_damage_list(damage_part), parse_condition_list(cond_part)


def parse_senses(line: str) -> Dict[str, Any]:
    """'Sens Vision dans le noir 18 m ; Perception passive 17' → senses dict."""
    body = re.sub(r"^Sens\s*", "", line).strip()
    out: Dict[str, Any] = {}
    # Passive perception
    m = re.search(r"Perception passive\s+(\d+)", body)
    out["passive_perception"] = parse_int(m.group(1), 10) if m else 10
    # Other senses
    for kw_fr, key_en in SENSE_FR_TO_EN.items():
        rx = re.compile(re.escape(kw_fr) + r"\s+(\d+)\s*m", re.IGNORECASE)
        m = rx.search(body)
        if m:
            out[key_en] = parse_int(m.group(1), 0)
    return out


def parse_languages(line: str) -> List[str]:
    body = re.sub(r"^Langues\s*", "", line).strip()
    if not body or body.lower() in {"aucune", "—", "-"}:
        return []
    # Keep as raw FR strings — translation can come later.
    return [p.strip() for p in re.split(r"[,;]\s*", body) if p.strip()]


def parse_cr_line(line: str) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    """'FP 13 (10 000 PX ; BM +5)' → (cr, xp, pb)."""
    cr = xp = pb = None
    m = re.match(
        r"FP\s+(?P<cr>1/8|1/4|1/2|\d+)\s*\((?:[^)]*?)?(?P<xp>[\d\s]+)\s*PX[^)]*?BM\s*\+?(?P<pb>\d+)",
        line,
    )
    if m:
        cr_raw = m.group("cr")
        cr = (
            1 / 8
            if cr_raw == "1/8"
            else 1 / 4
            if cr_raw == "1/4"
            else 1 / 2
            if cr_raw == "1/2"
            else float(cr_raw)
        )
        xp = parse_int(m.group("xp").replace(" ", "").replace(" ", ""))
        pb = parse_int(m.group("pb"))
    return cr, xp, pb


# --- Action / trait parsing -----------------------------------------------

SECTION_HEADERS = ["Traits", "Actions", "Actions Bonus", "Réactions",
                   "Actions Légendaires", "Repaire"]


def split_into_sections(body: str) -> Dict[str, str]:
    """Split the post-header content into named sections."""
    out: Dict[str, str] = {"_lead": ""}
    # Build a regex that matches any section header on its own line.
    rx = re.compile(
        r"^(?P<hdr>" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*$",
        re.MULTILINE,
    )
    matches = list(rx.finditer(body))
    if not matches:
        out["_lead"] = body
        return out
    out["_lead"] = body[: matches[0].start()]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[m.group("hdr")] = body[m.end():end]
    return out


def split_named_paragraphs(text: str) -> List[Tuple[str, str]]:
    """Split a section's text into [(name, body), ...] using the bold-name pattern.

    Each entry begins with a name in title case followed by a period, e.g.::

        Carapace réfléchissante. Si la tarasque est ...

    We treat the first sentence ending with '.' followed by a capital letter
    or newline as the entry boundary.
    """
    text = text.strip()
    if not text:
        return []
    # Pattern: a line that begins with a Title-Case phrase, then ". "
    # Use re.split capturing groups.
    parts = re.split(
        r"(?m)^(?P<name>[A-ZÉÀÂÔÛÊÎÇ][\wÀ-ÿ’'\-/ ]{1,80}?)\.\s+",
        text,
    )
    # parts[0] is preamble, then alternating name/body.
    out: List[Tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        # Reject false positives that are too short or contain newlines/colons.
        if "\n" in name or len(name) > 80 or ":" in name:
            continue
        out.append((name, body))
    return out


# Action body parsing -----------------------------------------------------

ATTACK_RE = re.compile(
    r"(?:Corps\s+à\s+corps(?:\s+ou\s+à\s+distance)?|À\s+distance)\s*:\s*"
    r"\+?(?P<bonus>-?\d+)"
    r"(?:\s*,\s*(?:allonge\s+(?P<reach>[\d,\.]+)\s*m)?\s*"
    r"(?:\s*ou\s*portée\s+(?P<range>[\d,\.]+(?:\s*/\s*[\d,\.]+)?)\s*m)?"
    r"(?:\s*,\s*portée\s+(?P<range2>[\d,\.]+(?:\s*/\s*[\d,\.]+)?)\s*m)?"
    r")?",
    re.IGNORECASE,
)
DAMAGE_RE = re.compile(
    r"Touché\s*:\s*\d+\s*\((?P<dice>\d+d\d+(?:\s*[+-]\s*\d+)?)\)\s*dégâts\s+(?P<dtype>[\wéèêç]+)",
    re.IGNORECASE,
)
SAVE_RE = re.compile(
    r"JS\s+(?P<ab>For|Dex|Con|Int|Sag|Cha)\s*:\s*DD\s*(?P<dd>\d+)",
    re.IGNORECASE,
)


def parse_action_body(name: str, body: str) -> Dict[str, Any]:
    """Best-effort parse of a single action's body text into structured fields."""
    out: Dict[str, Any] = {
        "name": name,  # EN name unknown — kept as FR (will be reset later).
        "name_fr": name,
        "type": "save",  # default; overwritten below
        "description": body,
    }
    name_l = name.lower()
    if name_l == "attaques multiples" or "attaques multiples" in name_l:
        out["type"] = "multiattack"
        return out
    atk = ATTACK_RE.search(body)
    if atk:
        bonus = parse_int(atk.group("bonus"))
        out["attack_bonus"] = bonus if bonus is not None else 0
        if "À distance" in atk.group(0) or "ou à distance" in atk.group(0):
            out["type"] = (
                "melee_or_ranged_attack"
                if "ou à distance" in atk.group(0)
                else "ranged_attack"
            )
        else:
            out["type"] = "melee_attack"
        if atk.group("reach"):
            out["reach_m"] = float(atk.group("reach").replace(",", "."))
        rng = atk.group("range") or atk.group("range2")
        if rng:
            parts = [p.strip().replace(",", ".") for p in rng.split("/")]
            try:
                out["range_normal_m"] = float(parts[0])
                if len(parts) > 1:
                    out["range_long_m"] = float(parts[1])
            except ValueError:
                pass
        out["targets"] = 1
    elif SAVE_RE.search(body):
        out["type"] = "save"
        sm = SAVE_RE.search(body)
        out["save"] = {
            "ability": ABILITY_FR_TO_EN[sm.group("ab")],
            "dd": parse_int(sm.group("dd")),
        }
    dmg = DAMAGE_RE.search(body)
    if dmg:
        out["damage_dice"] = re.sub(r"\s+", "", dmg.group("dice"))
        dtype_fr = dmg.group("dtype").lower()
        out["damage_type"] = DAMAGE_FR_TO_EN.get(dtype_fr, dtype_fr)
    return out


# --- Block → entry --------------------------------------------------------


def parse_stat_block(name_fr: str, type_match: re.Match[str], body: str) -> Optional[Dict[str, Any]]:
    """Build a structured monster entry from a single stat-block.

    `body` is the text from immediately after the type-line up to the next
    stat-block boundary.
    """
    # Header fields from the type line.
    type_fr = type_match.group("type")
    subtype_fr = type_match.group("subtype")
    size_fr = type_match.group("size")
    alignment_fr = type_match.group("align").strip().rstrip(".")

    # Read field-by-field by line patterns.
    ac = init_bonus = hp = pb = xp = None
    cr: Optional[float] = None
    hit_dice = ""
    speed_dict: Dict[str, int] = {}
    skills: Dict[str, int] = {}
    damage_immunities: List[str] = []
    damage_resistances: List[str] = []
    damage_vulnerabilities: List[str] = []
    condition_immunities: List[str] = []
    senses: Dict[str, Any] = {}
    languages: List[str] = []
    ability_scores: Dict[str, int] = {}
    saving_throws: Dict[str, int] = {}

    # Walk lines until we hit the first section header (Traits/Actions/...).
    head_lines: List[str] = []
    section_text = ""
    section_split = re.search(
        r"(?m)^(?:Traits|Actions|Actions Bonus|Réactions|Actions Légendaires|Repaire)\s*$",
        body,
    )
    if section_split:
        head_lines = body[: section_split.start()].splitlines()
        section_text = body[section_split.start():]
    else:
        head_lines = body.splitlines()

    head_text = "\n".join(head_lines)

    # CA + Pv + Vitesse, then ability block, then Compétences/Sens/etc.
    for line in head_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("CA "):
            m = re.match(r"CA\s+(\d+)(?:.*Initiative\s*([+-]\d+))?", line)
            if m:
                ac = parse_int(m.group(1))
                if m.group(2):
                    init_bonus = parse_int(m.group(2))
        elif line.startswith("Pv "):
            m = re.match(r"Pv\s+(\d+)\s*\(([^)]+)\)", line)
            if m:
                hp = parse_int(m.group(1))
                hit_dice = m.group(2).strip().replace(" ", "")
        elif line.startswith("Vitesse"):
            speed_dict = parse_speed(line.replace("Vitesse", "").strip())
        elif line.startswith("Compétences"):
            skills = parse_skills(line)
        elif line.startswith("Vulnérabilités"):
            damage_vulnerabilities = parse_damage_list(line.replace("Vulnérabilités", "").strip())
        elif line.startswith("Résistances"):
            damage_resistances = parse_damage_list(line.replace("Résistances", "").strip())
        elif line.startswith("Immunités"):
            damage_immunities, condition_immunities = parse_immunities_line(line)
        elif line.startswith("Sens"):
            senses = parse_senses(line)
        elif line.startswith("Langues"):
            languages = parse_languages(line)
        elif line.startswith("FP"):
            cr, xp, pb = parse_cr_line(line)

    # Ability scores: parse the entire head_text at once.
    ability_scores, saving_throws = parse_ability_block(head_text)

    # Sanity gates — every monster must have these or we skip.
    required = (ac, hp, hit_dice, cr, xp, pb, ability_scores, senses)
    if not all(x not in (None, "", {}) for x in required[:7]):
        return None
    if not ability_scores:
        return None

    # Sections: traits, actions, legendary_actions
    sections = split_into_sections(section_text)
    traits_raw = sections.get("Traits", "")
    actions_raw = sections.get("Actions", "")
    bonus_actions_raw = sections.get("Actions Bonus", "")
    reactions_raw = sections.get("Réactions", "")
    legendary_raw = sections.get("Actions Légendaires", "")

    traits_list: List[Dict[str, Any]] = []
    for n, b in split_named_paragraphs(traits_raw):
        traits_list.append({"name": n, "name_fr": n, "description": b})

    actions_list: List[Dict[str, Any]] = []
    for n, b in split_named_paragraphs(actions_raw):
        actions_list.append(parse_action_body(n, b))
    # Bonus actions and reactions are tagged in the description; skip
    # structuring for now and store them as traits-with-context.
    for label, raw in [("(Action bonus) ", bonus_actions_raw),
                       ("(Réaction) ", reactions_raw)]:
        for n, b in split_named_paragraphs(raw):
            actions_list.append(parse_action_body(label + n, b))

    legendary_list: List[Dict[str, Any]] = []
    for n, b in split_named_paragraphs(legendary_raw):
        legendary_list.append({
            "name": n,
            "name_fr": n,
            "type": "save",  # default; many legendary actions don't fit one type cleanly
            "description": b,
        })

    # Normalize curly quotes to straight ones for lookup robustness.
    lookup_name = name_fr.replace("’", "'").replace("‘", "'")
    en_name = MONSTER_FR_TO_EN.get(lookup_name) or MONSTER_FR_TO_EN.get(name_fr)
    needs_en = en_name is None
    name = en_name or name_fr
    sid = slugify(name_fr)

    entry: Dict[str, Any] = {
        "id": sid,
        "name": name,
        "name_fr": name_fr,
        "cr": cr if cr is not None else 0,
        "xp": xp if xp is not None else 0,
        "size": SIZE_FR_TO_EN[size_fr],
        "type": TYPE_FR_TO_EN[type_fr],
        "alignment": ALIGNMENT_FR_TO_EN.get(alignment_fr.lower(), alignment_fr.lower()),
        "ac": ac if ac is not None else 10,
        "hp": hp if hp is not None else 1,
        "hit_dice": hit_dice or "1d4",
        "speed": speed_dict if speed_dict else {"walk": 6},
        "ability_scores": ability_scores,
        "saving_throws": saving_throws,
        "skills": skills,
        "damage_immunities": damage_immunities,
        "damage_resistances": damage_resistances,
        "damage_vulnerabilities": damage_vulnerabilities,
        "condition_immunities": condition_immunities,
        "senses": senses,
        "languages": languages,
        "proficiency_bonus": pb if pb is not None else 2,
        "traits": traits_list,
        "actions": actions_list,
        "legendary_actions": legendary_list,
    }
    if subtype_fr:
        entry["subtype"] = subtype_fr.strip()

    flags: List[str] = []
    if needs_en:
        flags.append("needs_en_name")
    # Mark needs_review when actions or traits couldn't be structured.
    if not actions_list and (actions_raw.strip() or traits_raw.strip()):
        flags.append("needs_review")
    if flags:
        entry["parse_status"] = flags[0]

    return entry


# --- Driver ---------------------------------------------------------------


def extract_monsters(pdf_path: Path) -> List[Dict[str, Any]]:
    text = extract_bestiary_text(pdf_path)
    starts = find_block_starts(text)
    monsters: List[Dict[str, Any]] = []
    for i, (idx, m) in enumerate(starts):
        name_fr = find_name_above(text, idx)
        if not name_fr:
            continue
        # Body runs from the start of the next line after the type-line up to
        # the start of the next stat-block.
        body_start = m.end()
        body_end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        body = text[body_start:body_end]
        # The name itself may sit at the very start of `body` if the header
        # block contained the doubled-name pattern; strip leading blank lines.
        body = body.lstrip("\n")
        entry = parse_stat_block(name_fr, m, body)
        if entry:
            monsters.append(entry)
    return monsters


def merge_with_existing(
    parsed: List[Dict[str, Any]], existing: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int, int]:
    by_id = {m["id"]: m for m in existing}
    by_fr = {m.get("name_fr", "").lower(): m for m in existing}
    merged = list(existing)
    added = 0
    for m in parsed:
        if m["id"] in by_id or m["name_fr"].lower() in by_fr:
            continue
        merged.append(m)
        added += 1
    return merged, added, len(existing)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}", file=sys.stderr)
        return 1

    print(f"Reading {PDF_PATH}...")
    parsed = extract_monsters(PDF_PATH)
    print(f"  parsed {len(parsed)} stat-blocks from PDF")

    payload = json.loads(MONSTERS_JSON.read_text(encoding="utf-8"))
    existing = payload["monsters"]

    merged, added, kept = merge_with_existing(parsed, existing)
    print(f"  kept {kept} curated entries")
    print(f"  added {added} new monsters")

    # Validate
    errors = []
    needs_en = []
    needs_review = []
    for m in merged:
        try:
            MonsterSchema.model_validate(m)
        except Exception as e:
            errors.append((m.get("id", "?"), str(e)[:200]))
        if m.get("parse_status") == "needs_en_name":
            needs_en.append(m["name_fr"])
        elif m.get("parse_status") == "needs_review":
            needs_review.append(m["name_fr"])
    if errors:
        print(f"\n✘ {len(errors)} validation errors:")
        for sid, err in errors[:15]:
            print(f"   - {sid}: {err}")
        return 2
    if needs_en:
        print(f"  ⚠ {len(needs_en)} monsters need EN name:")
        for n in needs_en[:15]:
            print(f"      - {n}")
        if len(needs_en) > 15:
            print(f"      ... and {len(needs_en) - 15} more")
    if needs_review:
        print(f"  ⚠ {len(needs_review)} monsters flagged needs_review (actions unparsed)")

    merged.sort(key=lambda m: (m.get("cr", 0), m["id"]))

    if args.dry_run:
        print("Dry run — not writing monsters.json")
        return 0

    MONSTERS_JSON.write_text(
        json.dumps({"monsters": merged}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n✔ Wrote {len(merged)} monsters to {MONSTERS_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
