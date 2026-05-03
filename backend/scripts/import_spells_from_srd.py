"""Import spells from the French SRD 5.2.1 PDF into spells.json.

Reads ``docs/FR_SRD_CC_v5.2.1.pdf`` (pages 115-186 = the alphabetical spell
descriptions section) and produces structured entries that conform to
``SpellSchema``. Existing curated entries in ``spells.json`` are preserved
verbatim — only missing spells are appended.

Usage::

    cd backend
    source .venv/bin/activate
    python -m scripts.import_spells_from_srd          # writes spells.json
    python -m scripts.import_spells_from_srd --dry-run  # only prints summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow ``python scripts/import_spells_from_srd.py`` from backend/.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.srd_data.schemas import SpellSchema  # noqa: E402

PDF_PATH = BACKEND_DIR.parent / "docs" / "FR_SRD_CC_v5.2.1.pdf"
SPELLS_JSON = BACKEND_DIR / "app" / "engine" / "srd_data" / "spells.json"
SPELLS_PAGES = (114, 186)  # 0-indexed inclusive — covers alphabetical descriptions

# --- Mapping tables -------------------------------------------------------

SCHOOL_FR_TO_EN: Dict[str, str] = {
    "Abjuration": "abjuration",
    "Divination": "divination",
    "Enchantement": "enchantment",
    "Évocation": "evocation",
    "Illusion": "illusion",
    "Invocation": "conjuration",  # FR "Invocation" = EN "Conjuration"
    "Nécromancie": "necromancy",
    "Transmutation": "transmutation",
}

CLASS_FR_TO_EN: Dict[str, str] = {
    "Barde": "bard",
    "Clerc": "cleric",
    "Druide": "druid",
    "Ensorceleur": "sorcerer",
    "Magicien": "wizard",
    "Occultiste": "warlock",
    "Paladin": "paladin",
    "Rôdeur": "ranger",
}

# Comprehensive FR→EN spell name mapping for D&D 2024 SRD (5.2.1).
# Seeded from spells already present in spells.json plus standard D&D 5e/2024
# spell name conventions. Spells not in this map fall back to using the FR
# name in `name` and get tagged `parse_status: needs_en_name`.
SPELL_FR_TO_EN: Dict[str, str] = {
    # Existing entries (lock in the canonical EN names)
    "Trait de feu": "Fire Bolt",
    "Flamme sacrée": "Sacred Flame",
    "Lumière": "Light",
    "Main du mage": "Mage Hand",
    "Prestidigitation": "Prestidigitation",
    "Coup au but": "True Strike",
    "Projectile magique": "Magic Missile",
    "Mains brûlantes": "Burning Hands",
    "Soins": "Cure Wounds",
    "Bouclier": "Shield",
    "Vague tonnante": "Thunderwave",
    "Détection de la magie": "Detect Magic",
    "Mot de guérison": "Healing Word",
    "Bénédiction": "Bless",
    "Rayon ardent": "Scorching Ray",
    "Foulée brumeuse": "Misty Step",
    "Immobilisation de personne": "Hold Person",
    "Invisibilité": "Invisibility",
    "Toile d'araignée": "Web",
    "Toile d’araignée": "Web",
    "Arme spirituelle": "Spiritual Weapon",
    "Décharge occulte": "Eldritch Blast",
    "Moquerie cruelle": "Vicious Mockery",
    "Illusion mineure": "Minor Illusion",
    "Lumières dansantes": "Dancing Lights",
    "Bouffée de poison": "Poison Spray",
    "Contact glacial": "Chill Touch",
    "Assistance": "Guidance",
    "Stabilisation": "Spare the Dying",
    "Thaumaturgie": "Thaumaturgy",
    "Flammes": "Produce Flame",
    "Charme-personne": "Charm Person",
    "Sommeil": "Sleep",
    "Rayon traçant": "Guiding Bolt",
    "Blessure": "Inflict Wounds",
    "Marque du chasseur": "Hunter's Mark",
    "Faveur divine": "Divine Favor",
    "Maléfice": "Hex",
    "Enchevêtrement": "Entangle",
    "Lueurs féeriques": "Faerie Fire",
    "Baies nourricières": "Goodberry",
    "Nappe de brouillard": "Fog Cloud",
    "Prière de guérison": "Prayer of Healing",
    "Restauration partielle": "Lesser Restoration",
    "Fracassement": "Shatter",
    "Flou": "Blur",
    "Rayon de lune": "Moonbeam",
    "Passage sans trace": "Pass Without Trace",
    "Suggestion": "Suggestion",
    "Métal brûlant": "Heat Metal",
    "Dissipation de la magie": "Dispel Magic",
    "Boule de feu": "Fireball",
    "Éclair": "Lightning Bolt",
    "Contresort": "Counterspell",
    "Retour à la vie": "Revivify",
    "Appel de la foudre": "Call Lightning",
    "Esprits gardiens": "Spirit Guardians",
    "Vol": "Fly",
    "Motif hypnotique": "Hypnotic Pattern",
    "Animation des morts": "Animate Dead",
    "Bannissement": "Banishment",
    "Métamorphose": "Polymorph",
    "Tempête de grêle": "Ice Storm",
    "Flétrissement": "Blight",
    "Invisibilité suprême": "Greater Invisibility",
    "Protection contre la mort": "Death Ward",
    "Mur de feu": "Wall of Fire",
    "Cône de froid": "Cone of Cold",
    "Immobilisation de monstre": "Hold Monster",
    "Soins de groupe": "Mass Cure Wounds",
    "Colonne de flamme": "Flame Strike",
    "Rappel à la vie": "Raise Dead",
    "Scrutation": "Scrying",
    "Restauration suprême": "Greater Restoration",
    "Fléau d'insectes": "Insect Plague",
    "Fléau d’insectes": "Insect Plague",
    # Cantrips
    "Aspersion acide": "Acid Splash",
    "Druidisme": "Druidcraft",
    "Élémentalisme": "Elementalism",
    "Crosse des druides": "Shillelagh",
    "Main du mage": "Mage Hand",
    "Message": "Message",
    "Poigne électrique": "Shocking Grasp",
    "Poussière d'étoile": "Starry Wisp",
    "Poussière d’étoile": "Starry Wisp",
    "Rayon de givre": "Ray of Frost",
    "Réparation": "Mending",
    "Résistance": "Resistance",
    "Éruption ensorcelée": "Sorcerous Burst",
    # Niveau 1
    "Amitié avec les animaux": "Animal Friendship",
    "Antidétection": "Nondetection",
    "Appel de familier": "Find Familiar",
    "Armure du mage": "Mage Armor",
    "Bouclier de la foi": "Shield of Faith",
    "Châtiment de fournaise": "Searing Smite",
    "Châtiment divin": "Divine Smite",
    "Communication avec les animaux": "Speak with Animals",
    "Compréhension des langues": "Comprehend Languages",
    "Couleurs dansantes": "Color Spray",
    "Couteau de glace": "Ice Knife",
    "Création ou destruction d'eau": "Create or Destroy Water",
    "Création ou destruction d’eau": "Create or Destroy Water",
    "Déguisement": "Disguise Self",
    "Détection des pièges": "Detect Poison and Disease",
    "Détection du mal et du bien": "Detect Evil and Good",
    "Détection du poison et des maladies": "Detect Poison and Disease",
    "Disque flottant": "Tenser's Floating Disk",
    "Feuille morte": "Feather Fall",
    "Fou rire": "Tasha's Hideous Laughter",
    "Frappe piégeuse": "Ensnaring Strike",
    "Graisse": "Grease",
    "Grande foulée": "Longstrider",
    "Héroïsme": "Heroism",
    "Identification": "Identify",
    "Image silencieuse": "Silent Image",
    "Imprécation": "Bane",
    "Injonction": "Command",
    "Murmures dissonants": "Dissonant Whispers",
    "Orbe chromatique": "Chromatic Orb",
    "Protection contre le mal et le bien": "Protection from Evil and Good",
    "Purification de la nourriture et de l'eau": "Purify Food and Drink",
    "Purification de la nourriture et de l’eau": "Purify Food and Drink",
    "Rayon empoisonné": "Ray of Sickness",
    "Repli expéditif": "Expeditious Retreat",
    "Représailles infernales": "Hellish Rebuke",
    "Sanctuaire": "Sanctuary",
    "Saut": "Jump",
    "Serviteur invisible": "Unseen Servant",
    "Simulacre de vie": "False Life",
    "Texte illusoire": "Illusory Script",
    "Détection des pensées": "Detect Thoughts",
    # Niveau 2
    "Aide": "Aid",
    "Amélioration de caractéristique": "Enhance Ability",
    "Apaisement des émotions": "Calm Emotions",
    "Appel de destrier": "Find Steed",
    "Arme magique": "Magic Weapon",
    "Augure": "Augury",
    "Bouche magique": "Magic Mouth",
    "Bourrasque": "Gust of Wind",
    "Cécité/surdité": "Blindness/Deafness",
    "Châtiment de révélation": "Branding Smite",
    "Corde enchantée": "Rope Trick",
    "Croissance d'épines": "Spike Growth",
    "Croissance d’épines": "Spike Growth",
    "Déblocage": "Knock",
    "Détection de l'invisibilité": "See Invisibility",
    "Détection de l’invisibilité": "See Invisibility",
    "Discours captivant": "Enthrall",
    "Doux repos": "Gentle Repose",
    "Épine mentale": "Mind Spike",
    "Flamme éternelle": "Continual Flame",
    "Flèche acide": "Melf's Acid Arrow",
    "Force fantasmagorique": "Phantasmal Force",
    "Image miroir": "Mirror Image",
    "Lame de feu": "Flame Blade",
    "Lévitation": "Levitate",
    "Lien de protection": "Warding Bond",
    "Localisation d'animaux ou de plantes": "Locate Animals or Plants",
    "Localisation d’animaux ou de plantes": "Locate Animals or Plants",
    "Localisation d'objet": "Locate Object",
    "Localisation d’objet": "Locate Object",
    "Messager animal": "Animal Messenger",
    "Modification d'apparence": "Alter Self",
    "Modification d’apparence": "Alter Self",
    "Pattes d'araignée": "Spider Climb",
    "Pattes d’araignée": "Spider Climb",
    "Peau d'écorce": "Barkskin",
    "Peau d’écorce": "Barkskin",
    "Protection contre le poison": "Protection from Poison",
    "Rayon affaiblissant": "Ray of Enfeeblement",
    "Silence": "Silence",
    "Souffle du dragon": "Dragon's Breath",
    "Sphère de feu": "Flaming Sphere",
    "Ténèbres": "Darkness",
    "Vision dans le noir": "Darkvision",
    "Verrou magique": "Arcane Lock",
    "Zone de vérité": "Zone of Truth",
    "Aura magique de l'arcaniste": "Arcanist's Magic Aura",
    "Aura magique de l’arcaniste": "Arcanist's Magic Aura",
    # Niveau 3
    "Cercle magique": "Magic Circle",
    "Caresse du vampire": "Vampiric Touch",
    "Clairvoyance": "Clairvoyance",
    "Clignotement": "Blink",
    "Communication à distance": "Sending",
    "Communication avec les morts": "Speak with Dead",
    "Communication avec les plantes": "Speak with Plants",
    "Création de nourriture et d'eau": "Create Food and Water",
    "Création de nourriture et d’eau": "Create Food and Water",
    "Croissance végétale": "Plant Growth",
    "Délivrance des malédictions": "Remove Curse",
    "Don des langues": "Tongues",
    "Forme gazeuse": "Gaseous Form",
    "Fusion dans la pierre": "Meld into Stone",
    "Glyphe de garde": "Glyph of Warding",
    "Hâte": "Haste",
    "Image majeure": "Major Image",
    "Invocation d'animaux": "Conjure Animals",
    "Invocation d’animaux": "Conjure Animals",
    "Lenteur": "Slow",
    "Lueur d'espoir": "Beacon of Hope",
    "Lueur d’espoir": "Beacon of Hope",
    "Lumière du jour": "Daylight",
    "Malédiction": "Bestow Curse",
    "Marche sur l'onde": "Water Walk",
    "Marche sur l’onde": "Water Walk",
    "Monture fantôme": "Phantom Steed",
    "Mot de guérison de groupe": "Mass Healing Word",
    "Mur de vent": "Wind Wall",
    "Nuage nauséabond": "Stinking Cloud",
    "Petite hutte": "Leomund's Tiny Hut",
    "Protection contre l'énergie": "Protection from Energy",
    "Protection contre l’énergie": "Protection from Energy",
    "Respiration aquatique": "Water Breathing",
    "Tempête de neige": "Sleet Storm",
    "Terreur": "Fear",
    # Niveau 4
    "Assassin imaginaire": "Phantasmal Killer",
    "Aura de vie": "Aura of Life",
    "Bouclier de feu": "Fire Shield",
    "Charme-monstre": "Charm Monster",
    "Chien de garde": "Mordenkainen's Faithful Hound",
    "Coffre secret": "Leomund's Secret Chest",
    "Compulsion": "Compulsion",
    "Confusion": "Confusion",
    "Contrôle de l'eau": "Control Water",
    "Contrôle de l’eau": "Control Water",
    "Divination": "Divination",
    "Domination de bête": "Dominate Beast",
    "Fabrication": "Fabricate",
    "Façonnage de la pierre": "Stone Shape",
    "Gardien de la foi": "Guardian of Faith",
    "Insecte géant": "Giant Insect",
    "Invocation d'élémentaires mineurs": "Conjure Minor Elementals",
    "Invocation d’élémentaires mineurs": "Conjure Minor Elementals",
    "Invocation d'êtres sylvestres": "Conjure Woodland Beings",
    "Invocation d’êtres sylvestres": "Conjure Woodland Beings",
    "Liberté de mouvement": "Freedom of Movement",
    "Localisation de créature": "Locate Creature",
    "Peau de pierre": "Stoneskin",
    "Porte dimensionnelle": "Dimension Door",
    "Protection contre la mort": "Death Ward",
    "Sanctuaire privé": "Private Sanctum",
    "Sphère de vitriol": "Vitriolic Sphere",
    "Sphère résiliente": "Otiluke's Resilient Sphere",
    "Tentacules noirs": "Evard's Black Tentacles",
    "Tempête de grêle": "Ice Storm",
    "Terrain hallucinatoire": "Hallucinatory Terrain",
    # Niveau 5
    "Animation des objets": "Animate Objects",
    "Apparence trompeuse": "Seeming",
    "Brume mortelle": "Cloudkill",
    "Cercle de téléportation": "Teleportation Circle",
    "Communion": "Commune",
    "Communion avec la nature": "Commune with Nature",
    "Contact avec les plans": "Contact Other Plane",
    "Convocation de dragon": "Summon Draconic Spirit",
    "Coquille antivie": "Antilife Shell",
    "Création": "Creation",
    "Domination de personne": "Dominate Person",
    "Double illusoire": "Mislead",
    "Entrave planaire": "Planar Binding",
    "Éveil": "Awaken",
    "Invocation d'élémentaire": "Conjure Elemental",
    "Invocation d’élémentaire": "Conjure Elemental",
    "Lien télépathique": "Rary's Telepathic Bond",
    "Main arcanique": "Bigby's Hand",
    "Modification de mémoire": "Modify Memory",
    "Mur de force": "Wall of Force",
    "Mur de pierre": "Wall of Stone",
    "Mythes et légendes": "Legend Lore",
    "Passage par les arbres": "Tree Stride",
    "Passe-muraille": "Passwall",
    "Quête": "Geas",
    "Réincarnation": "Reincarnate",
    "Sanctification": "Hallow",
    "Songe": "Dream",
    "Télékinésie": "Telekinesis",
    "Téléportation": "Teleport",
    # Niveau 6
    "Barrière de lames": "Blade Barrier",
    "Cercle de mort": "Circle of Death",
    "Chaîne d'éclairs": "Chain Lightning",
    "Chaîne d’éclairs": "Chain Lightning",
    "Contamination": "Harm",
    "Contrôle du climat": "Control Weather",
    "Convocations instantanées": "Drawmij's Instant Summons",
    "Création de mort-vivant": "Create Undead",
    "Danse irrésistible": "Otto's Irresistible Dance",
    "Désintégration": "Disintegrate",
    "Festin des héros": "Heroes' Feast",
    "Glissement de terrain": "Move Earth",
    "Globe d'invulnérabilité": "Globe of Invulnerability",
    "Globe d’invulnérabilité": "Globe of Invulnerability",
    "Guérison": "Heal",
    "Illusion programmée": "Programmed Illusion",
    "Interdiction": "Forbiddance",
    "Invocation de fée": "Summon Fey",
    "Mauvais œil": "Eyebite",
    "Mot de retour": "Word of Recall",
    "Mur d'épines": "Wall of Thorns",
    "Mur d’épines": "Wall of Thorns",
    "Mur de glace": "Wall of Ice",
    "Orientation": "Find the Path",
    "Pétrification": "Flesh to Stone",
    "Possession": "Magic Jar",
    "Préméditation": "Contingency",
    "Protections et sceaux": "Guards and Wards",
    "Rayon de soleil": "Sunbeam",
    "Sphère glacée": "Otiluke's Freezing Sphere",
    "Suggestion de groupe": "Mass Suggestion",
    "Vent divin": "Wind Walk",
    "Vision suprême": "True Seeing",
    "Voie végétale": "Transport via Plants",
    # Niveau 7
    "Boule de feu à retardement": "Delayed Blast Fireball",
    "Cage de force": "Forcecage",
    "Changement de plan": "Plane Shift",
    "Dissimulation suprême": "Mirage Arcane",
    "Embruns prismatiques": "Prismatic Spray",
    "Épée arcanique": "Mordenkainen's Sword",
    "Forme éthérée": "Etherealness",
    "Image projetée": "Project Image",
    "Inversion de la gravité": "Reverse Gravity",
    "Invocation de céleste": "Conjure Celestial",
    "Manoir somptueux": "Mordenkainen's Magnificent Mansion",
    "Mirage": "Mirage Arcane",
    "Parole divine": "Divine Word",
    "Régénération": "Regenerate",
    "Résurrection": "Resurrection",
    "Simulacre": "Simulacrum",
    "Symbole": "Symbol",
    "Tempête de feu": "Fire Storm",
    "Doigt de mort": "Finger of Death",
    # Niveau 8
    "Aura sacrée": "Holy Aura",
    "Aversion/attirance": "Antipathy/Sympathy",
    "Bagou": "Glibness",
    "Champ antimagie": "Antimagic Field",
    "Clone": "Clone",
    "Contrôle du climat": "Control Weather",
    "Dédale": "Maze",
    "Demi-plan": "Demiplane",
    "Domination de monstre": "Dominate Monster",
    "Éclat du soleil": "Sunburst",
    "Esprit impénétrable": "Mind Blank",
    "Métamorphose animale": "Animal Shapes",
    "Mot de pouvoir étourdissant": "Power Word Stun",
    "Nuage incendiaire": "Incendiary Cloud",
    "Tremblement de terre": "Earthquake",
    "Tsunami": "Tsunami",
    # Niveau 9
    "Arrêt du temps": "Time Stop",
    "Changement de forme": "Shapechange",
    "Emprisonnement": "Imprisonment",
    "Ennemi subconscient": "Weird",
    "Guérison de groupe": "Mass Heal",
    "Métamorphose suprême": "True Polymorph",
    "Mot de pouvoir guérisseur": "Power Word Heal",
    "Mot de pouvoir mortel": "Power Word Kill",
    "Mur prismatique": "Prismatic Wall",
    "Nuée de météores": "Meteor Swarm",
    "Portail": "Gate",
    "Prémonition": "Foresight",
    "Projection astrale": "Astral Projection",
    "Résurrection suprême": "True Resurrection",
    "Souhait": "Wish",
    "Tempête vengeresse": "Storm of Vengeance",
    # Late additions (discovered during dry-run)
    "Contagion": "Contagion",
    "Dissipation du mal et du bien": "Dispel Evil and Good",
    "Œil du mage": "Arcane Eye",
    "Œil du Mage": "Arcane Eye",
}

# --- PDF text helpers -----------------------------------------------------


def slugify(text: str) -> str:
    """Convert a French spell name to a snake_case ASCII id."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace("'", "_").replace("’", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def parse_range_to_meters(raw: str) -> Optional[float]:
    """Convert a French range string ('18 m', 'contact', 'personnelle', '1,5 km')
    into a numeric distance in meters. Returns None if not parseable."""
    raw = raw.strip().lower()
    if raw in {"personnelle", "personnel", "soi-même", "soi"}:
        return 0
    if raw in {"contact", "toucher"}:
        return 0
    # Match e.g. "18 m" or "1,5 m"
    m = re.match(r"([\d,\.]+)\s*km", raw)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.match(r"([\d,\.]+)\s*m", raw)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def extract_spell_section_text(pdf_path: Path) -> str:
    """Concatenate the spell description pages, stripping page chrome."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts: List[str] = []
    for i in range(SPELLS_PAGES[0], SPELLS_PAGES[1] + 1):
        text = reader.pages[i].extract_text() or ""
        # Strip recurring page header / footer.
        text = re.sub(
            r"^Document de Référence du Système 5\.2\.1\s*\n\s*\d+\s*\n",
            "",
            text,
            flags=re.MULTILINE,
        )
        parts.append(text)
    return "\n".join(parts)


# Heading regex: spell name on one line, then school + level on next line.
HEADING_RE = re.compile(
    r"^(?P<name>[A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŒ][\w'’/\- ]{1,60}?)\s*\n"
    r"(?P<school>"
    r"Abjuration|Conjuration|Divination|Enchantement|"
    r"Évocation|Illusion|Invocation|Nécromancie|Transmutation"
    r")"
    r"(?:\s+mineure|\s+du\s+(?P<level>\d+)(?:er|e|ᵉ|ème)?\s+niveau)?"
    r"(?:\s*\((?P<classes>[^)]+)\))?\s*\n"
    r"Temps\s+d['’]incantation\s*:\s*(?P<casting>[^\n]+)\n"
    r"Portée\s*:\s*(?P<range>[^\n]+)\n"
    r"Composantes\s*:\s*(?P<components>[^\n]+(?:\n[^\n]+)*?)\n"
    r"Durée\s*:\s*(?P<duration>[^\n]+)",
    re.MULTILINE,
)


def parse_heading_block(match: re.Match[str]) -> Dict[str, Any]:
    """Turn a heading regex match into a structured spell shell."""
    name_fr = match.group("name").strip()
    # Reject runaway captures (the name is typically <= 50 chars).
    if "\n" in name_fr or len(name_fr) > 60:
        return {}
    school_fr = match.group("school")
    level_str = match.group("level")
    classes_raw = (match.group("classes") or "").strip()

    # Determine level (cantrip is identified by "mineure" suffix).
    is_cantrip = "mineure" in match.group(0).split("\n", 2)[1]
    level = 0 if is_cantrip else int(level_str) if level_str else 0

    school = SCHOOL_FR_TO_EN[school_fr]
    classes = []
    if classes_raw:
        for c in re.split(r"[,;]\s*", classes_raw):
            c = c.strip().rstrip(",")
            # Sometimes class line wraps and includes whitespace/newlines.
            c = re.sub(r"\s+", " ", c)
            if c in CLASS_FR_TO_EN:
                classes.append(CLASS_FR_TO_EN[c])

    casting_time_fr = match.group("casting").strip()
    ritual = "rituel" in casting_time_fr.lower()

    range_fr = match.group("range").strip()
    range_m = parse_range_to_meters(range_fr)

    components_str = re.sub(r"\s+", " ", match.group("components")).strip()
    components: List[str] = []
    for c in ["V", "S", "M"]:
        # Look for the letter as a standalone token (followed by , or ( or end).
        if re.search(rf"\b{c}\b", components_str):
            components.append(c)

    duration_fr = match.group("duration").strip()
    concentration = "concentration" in duration_fr.lower()

    return {
        "_name_fr": name_fr,
        "_school_fr": school_fr,
        "level": level,
        "school": school,
        "classes": classes,
        "casting_time": casting_time_fr,
        "range_m": range_m,
        "components": components,
        "duration": duration_fr,
        "concentration": concentration,
        "ritual": ritual,
    }


def extract_spells(pdf_path: Path) -> List[Dict[str, Any]]:
    """Return a list of parsed spell shells from the PDF."""
    text = extract_spell_section_text(pdf_path)
    spells: List[Dict[str, Any]] = []
    matches = list(HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        shell = parse_heading_block(m)
        if not shell:
            continue
        # Description = everything between this match and the next heading.
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        # Strip leading whitespace and the page footer artifact if present.
        body = re.sub(r"^\s*", "", body)
        body = re.sub(
            r"\n?Document de Référence du Système 5\.2\.1\s*\n\s*\d+\s*\n", "\n", body
        )
        # Soft-wrap fix: join hyphenated line breaks like "incanta-\ntion".
        body = re.sub(r"-\s*\n\s*", "", body)
        # Collapse single newlines (paragraph breaks rarely matter for ID lookup).
        description = re.sub(r"\s+", " ", body).strip()
        shell["_description_fr"] = description
        spells.append(shell)
    return spells


# --- Merging --------------------------------------------------------------


def build_spell_entry(parsed: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Materialize a parsed shell into a final entry. Returns (entry, needs_review)."""
    name_fr = parsed["_name_fr"]
    en = SPELL_FR_TO_EN.get(name_fr)
    needs_en = en is None
    name = en or name_fr
    sid = slugify(name_fr)

    entry: Dict[str, Any] = {
        "id": sid,
        "name": name,
        "name_fr": name_fr,
        "level": parsed["level"],
        "school": parsed["school"],
        "casting_time": parsed["casting_time"],
        "components": parsed["components"],
        "duration": parsed["duration"],
        "concentration": parsed["concentration"],
        "classes": parsed["classes"],
        "description": parsed["_description_fr"],
    }
    if parsed["range_m"] is not None:
        entry["range_m"] = parsed["range_m"]
    if parsed["ritual"]:
        entry["ritual"] = True
    # Importer-only stubs: mechanical fields (damage/save/attack/heal) are not
    # extracted from the PDF. They must be filled in by hand or by a follow-up
    # pass before the spell can be resolved mechanically.
    if needs_en:
        entry["parse_status"] = "needs_en_name"
    else:
        entry["parse_status"] = "needs_mechanics"
    return entry, needs_en


def merge_with_existing(
    parsed_spells: List[Dict[str, Any]],
    existing_spells: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int, List[str]]:
    """Combine parsed shells with curated entries.

    Curated entries (already in spells.json) win — we never overwrite their
    rich combat-mechanic fields (damage_dice, save, attack_type, etc.).
    Only new spells are appended.

    Returns ``(merged, added_count, kept_count, needs_en_names)``.
    """
    by_id_existing: Dict[str, Dict[str, Any]] = {s["id"]: s for s in existing_spells}
    by_name_fr_existing: Dict[str, Dict[str, Any]] = {
        s.get("name_fr", "").lower(): s for s in existing_spells
    }

    merged: List[Dict[str, Any]] = list(existing_spells)
    needs_en_names: List[str] = []
    added = 0
    for shell in parsed_spells:
        entry, needs_en = build_spell_entry(shell)
        # Skip if we already curated this spell (by id or by FR name).
        if entry["id"] in by_id_existing:
            continue
        if shell["_name_fr"].lower() in by_name_fr_existing:
            continue
        merged.append(entry)
        added += 1
        if needs_en:
            needs_en_names.append(entry["name_fr"])

    return merged, added, len(existing_spells), needs_en_names


# --- CLI ------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Do not write spells.json")
    args = p.parse_args()

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}", file=sys.stderr)
        return 1

    print(f"Reading {PDF_PATH}...")
    parsed = extract_spells(PDF_PATH)
    print(f"  parsed {len(parsed)} spell blocks from PDF")

    payload = json.loads(SPELLS_JSON.read_text(encoding="utf-8"))
    existing = payload["spells"]

    merged, added, kept, needs_en = merge_with_existing(parsed, existing)
    print(f"  kept {kept} curated entries")
    print(f"  added {added} new spells")
    if needs_en:
        print(f"  ⚠ {len(needs_en)} spells without EN name (parse_status=needs_en_name):")
        for n in needs_en[:25]:
            print(f"      - {n}")
        if len(needs_en) > 25:
            print(f"      ... and {len(needs_en) - 25} more")

    # Validate every entry against the schema.
    errors = []
    for s in merged:
        try:
            SpellSchema.model_validate(s)
        except Exception as e:
            errors.append((s.get("id", "?"), str(e)[:200]))
    if errors:
        print(f"\n✘ {len(errors)} validation errors:")
        for sid, err in errors[:10]:
            print(f"   - {sid}: {err}")
        return 2

    # Sort by level, then by id, for stable diffs.
    merged.sort(key=lambda s: (s["level"], s["id"]))

    if args.dry_run:
        print("Dry run — not writing spells.json")
        return 0

    SPELLS_JSON.write_text(
        json.dumps({"spells": merged}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n✔ Wrote {len(merged)} spells to {SPELLS_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
