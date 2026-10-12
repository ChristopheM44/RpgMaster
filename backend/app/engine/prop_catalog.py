"""Catalogue sémantique des props de scène — nom → modèle 3D et teinte de matière.

Aucune I/O. SOURCE UNIQUE partagée avec le frontend : ``scripts/export_prop_catalog.py``
génère ``frontend/src/engine3d/assets/propCatalog.generated.ts`` (test de fraîcheur
dans ``tests/test_engine/test_prop_catalog.py``). Modifier ici, puis régénérer.

Règle de correspondance (identique des deux côtés, cf. ``normalize_words``) : le
texte est minusculé, désaccentué, toute ponctuation devient espace, puis entouré
d'espaces. Un mot-clé est une racine qui doit commencer un mot (``" " + kw``) ;
un espace final exige la fin du mot (``"lit "`` ne prend pas « litière »).

Une règle ``any`` + ``requires`` exige un mot de chaque liste. Première règle
qui correspond = gagnante : les règles spécifiques précèdent les génériques.
Pas de correspondance → pas d'``asset_key`` (rendu procédural neutre plutôt
qu'un modèle à contresens, ex. « Arbre pétrifié » → caisses).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class PropRule:
    asset_key: str
    any: tuple[str, ...]
    requires: tuple[str, ...] = ()


# Clés procédurales : dessinées par ``ProceduralFactory`` (pas de GLB).
PROCEDURAL_PROP_KEYS: tuple[str, ...] = (
    "proc/fountain",
    "proc/well",
    "proc/altar",
    "proc/sarcophagus",
    "proc/anvil",
    "proc/lectern",
    "proc/bookcase",
    "proc/mound",
    "proc/footprints",
)

PROP_RULES: tuple[PropRule, ...] = (
    # Coffres précieux avant coffres.
    PropRule(
        "prop/chest_gold",
        ("coffre", "malle", "cassette", "chest"),
        ("d or ", "dore", "tresor", "royal", "precieu", "gold", "treasure"),
    ),
    PropRule("prop/chest_gold", ("tresor", "treasure")),
    PropRule("prop/chest", ("coffre", "malle", "cassette", "chest")),
    # Mobilier de lieu (procédural) avant les génériques table/étagère.
    PropRule("proc/fountain", ("fontaine", "vasque", "bassin", "fountain")),
    PropRule("proc/well", ("puits ", "well ")),
    PropRule("proc/altar", ("autel", "altar", "reliquaire")),
    PropRule(
        "proc/sarcophagus",
        ("sarcophag", "tombeau", "cercueil", "gisant", "tombe ", "sepulture", "coffin", "tomb "),
    ),
    PropRule("proc/anvil", ("enclume", "anvil")),
    PropRule("proc/lectern", ("lutrin", "pupitre", "lectern")),
    PropRule(
        "proc/bookcase",
        (
            "biblioth",
            "rayonnage",
            "bookcase",
            "bookshelf",
            "livres",
            "armoire",
            "vaisselier",
            "buffet",
            "placard",
        ),
    ),
    PropRule(
        "prop/shelf_large",
        ("etager", "rayons ", "shelf", "shelves", "presentoir", "casier"),
    ),
    PropRule(
        "prop/table_medium",
        ("table", "etal ", "etals ", "comptoir", "bureau", "etabli", "desk", "counter", "stall"),
    ),
    PropRule("prop/stool", ("tabouret", "stool")),
    PropRule(
        "prop/chair",
        ("chaise", "fauteuil", "trone", "siege", "banc ", "bancs ", "chair", "throne", "bench"),
    ),
    PropRule("prop/keg", ("tonnelet", "keg")),
    PropRule(
        "prop/barrel_small", ("tonneau", "baril", "barrique", "fut ", "futs ", "baquet", "barrel")
    ),
    PropRule("prop/crates_stacked", ("caisse", "cageot", "caisson", "marchandise", "crate")),
    PropRule(
        "prop/bed_frame",
        ("lit ", "lits ", "couchette", "paillasse", "grabat", "matelas", "hamac", "bed ", "beds "),
    ),
    PropRule("prop/pillar", ("pilier", "colonne", "poteau", "pillar", "column")),
    PropRule("prop/campfire", ("feu de camp", "foyer", "bivouac", "brasier", "campfire")),
    PropRule("prop/tent", ("tente", "chapiteau", "pavillon", "campement", "tent ", "tents ")),
    PropRule(
        "prop/pot",
        (
            "jarre",
            "vase ",
            "vases ",
            "amphore",
            "urne",
            "poterie",
            "cruche",
            "pot ",
            "pots ",
            "jar ",
        ),
    ),
    PropRule(
        "prop/obelisk", ("obelisque", "stele", "menhir", "monolithe", "pierre levee", "obelisk")
    ),
    PropRule("prop/statue", ("statue", "idole", "effigie", "buste", "sculpture", "monument")),
    # Végétation : arbre mort / pétrifié avant tronc couché avant arbre vivant.
    PropRule(
        "nature/tree_dark",
        ("arbre", "tree", "chene", "saule", "if ", "bouleau"),
        (
            "mort",
            "petrifi",
            "sec ",
            "seche",
            "calcin",
            "noueux",
            "fletri",
            "creux",
            "pierre",
            "dead",
            "withered",
            "petrified",
        ),
    ),
    PropRule("nature/log", ("tronc", "rondin", "buche", "bois flotte", "log ", "logs ")),
    PropRule("nature/stump", ("souche", "stump")),
    PropRule("nature/tree_palm_tall", ("palmier", "palm ")),
    PropRule("nature/cactus_tall", ("cactus",)),
    PropRule(
        "nature/tree_pine_a",
        ("arbre", "sapin", "pin ", "pins ", "chene", "saule", "bouleau", "tree", "pine"),
    ),
    PropRule("nature/bush", ("buisson", "fourre", "arbuste", "taillis", "haie ", "bush")),
    PropRule("nature/grass_large", ("roseau", "jonc", "hautes herbes", "reed")),
    # Minéral : éboulement avant rocher avant pierre isolée.
    PropRule(
        "prop/rubble_large",
        ("gravat", "debris", "detritus", "eboulis", "eboulement", "effondr", "decombre", "rubble"),
    ),
    PropRule(
        "nature/rock_large_a",
        (
            "rocher",
            "roche",
            "rocaille",
            "affleurement",
            "stalagmite",
            "stalactite",
            "falaise",
            "bloc ",
            "blocs ",
            "boulder",
            "rock",
        ),
    ),
    PropRule("nature/rock_small_a", ("pierre", "caillou", "galet", "cairn", "stone")),
    PropRule("proc/mound", ("dune", "talus", "butte", "monticule", "tertre", "mound")),
    PropRule("proc/footprints", ("trace", "empreinte", "piste ", "footprint", "track")),
)

# Teinte de matière (réutiliser un modèle : pierre pétrifiée, bois mort, sable…).
TINT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("petrified", ("petrifi", "de pierre", "en pierre", "fossil", "petrified")),
    ("charred", ("calcin", "brule", "carbonis", "noirci", "charred", "burnt")),
    ("frost", ("gele", "givre", "glace", "frozen", "frost")),
    ("moss", ("moussu", "mousse", "lichen", "mossy")),
    ("sand", ("ensable", "erode", "sable", "sandy")),
    ("deadwood", ("mort", "sec ", "seche", "fletri", "pourri", "vermoulu", "dead", "rotten")),
)

# Kinds d'éléments habillés par le catalogue (murs, portes, escaliers, lumières et
# dangers ont leurs propres rendus).
CATALOG_ELEMENT_KINDS: frozenset[str] = frozenset({"furniture", "cover", "decor"})

_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def normalize_words(text: str) -> str:
    """Texte désaccentué, minuscule, mots séparés par une espace, bordé d'espaces."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return f" {_NON_WORD_RE.sub(' ', stripped).strip()} "


def _has(words: str, keywords: tuple[str, ...]) -> bool:
    return any(f" {keyword}" in words for keyword in keywords)


def match_prop(text: str) -> str | None:
    """Clé d'asset du premier mot-clé reconnu dans ``text``, sinon ``None``."""
    words = normalize_words(text)
    for rule in PROP_RULES:
        if _has(words, rule.any) and (not rule.requires or _has(words, rule.requires)):
            return rule.asset_key
    return None


def match_tint(text: str) -> str | None:
    """Teinte de matière évoquée par ``text`` (pétrifié, calciné…), sinon ``None``."""
    words = normalize_words(text)
    for tint, keywords in TINT_RULES:
        if _has(words, keywords):
            return tint
    return None


def catalog_asset_keys() -> set[str]:
    return {rule.asset_key for rule in PROP_RULES}


def render_typescript() -> str:
    """Module TypeScript miroir (``frontend/src/engine3d/assets/propCatalog.generated.ts``)."""

    def words(values: tuple[str, ...]) -> str:
        return "[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"

    lines = [
        "// GÉNÉRÉ par backend/scripts/export_prop_catalog.py depuis",
        "// backend/app/engine/prop_catalog.py — ne pas éditer à la main.",
        "",
        "export interface PropRule {",
        "  assetKey: string",
        "  any: readonly string[]",
        "  requires: readonly string[]",
        "}",
        "",
        "export const PROP_RULES: readonly PropRule[] = [",
    ]
    for rule in PROP_RULES:
        lines.append(
            f"  {{ assetKey: {json.dumps(rule.asset_key)}, any: {words(rule.any)}, "
            f"requires: {words(rule.requires)} }},"
        )
    lines += [
        "]",
        "",
        "export const TINT_RULES: readonly (readonly [string, readonly string[]])[] = [",
    ]
    for tint, keywords in TINT_RULES:
        lines.append(f"  [{json.dumps(tint)}, {words(keywords)}],")
    lines += [
        "]",
        "",
        f"export const PROCEDURAL_PROP_KEYS: readonly string[] = {words(PROCEDURAL_PROP_KEYS)}",
        "",
        "export const CATALOG_ELEMENT_KINDS: readonly string[] = "
        f"{words(tuple(sorted(CATALOG_ELEMENT_KINDS)))}",
        "",
    ]
    return "\n".join(lines)
