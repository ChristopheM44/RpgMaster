// GÉNÉRÉ par backend/scripts/export_prop_catalog.py depuis
// backend/app/engine/prop_catalog.py — ne pas éditer à la main.

export interface PropRule {
  assetKey: string
  any: readonly string[]
  requires: readonly string[]
}

export const PROP_RULES: readonly PropRule[] = [
  { assetKey: "prop/chest_gold", any: ["coffre", "malle", "cassette", "chest"], requires: ["d or ", "dore", "tresor", "royal", "precieu", "gold", "treasure"] },
  { assetKey: "prop/chest_gold", any: ["tresor", "treasure"], requires: [] },
  { assetKey: "prop/chest", any: ["coffre", "malle", "cassette", "chest"], requires: [] },
  { assetKey: "proc/fountain", any: ["fontaine", "vasque", "bassin", "fountain"], requires: [] },
  { assetKey: "proc/well", any: ["puits ", "well "], requires: [] },
  { assetKey: "proc/altar", any: ["autel", "altar", "reliquaire"], requires: [] },
  { assetKey: "proc/sarcophagus", any: ["sarcophag", "tombeau", "cercueil", "gisant", "tombe ", "sepulture", "coffin", "tomb "], requires: [] },
  { assetKey: "proc/anvil", any: ["enclume", "anvil"], requires: [] },
  { assetKey: "proc/lectern", any: ["lutrin", "pupitre", "lectern"], requires: [] },
  { assetKey: "proc/bookcase", any: ["biblioth", "rayonnage", "bookcase", "bookshelf", "livres", "armoire", "vaisselier", "buffet", "placard"], requires: [] },
  { assetKey: "prop/shelf_large", any: ["etager", "rayons ", "shelf", "shelves", "presentoir", "casier"], requires: [] },
  { assetKey: "prop/table_medium", any: ["table", "etal ", "etals ", "comptoir", "bureau", "etabli", "desk", "counter", "stall"], requires: [] },
  { assetKey: "prop/stool", any: ["tabouret", "stool"], requires: [] },
  { assetKey: "prop/chair", any: ["chaise", "fauteuil", "trone", "siege", "banc ", "bancs ", "chair", "throne", "bench"], requires: [] },
  { assetKey: "prop/keg", any: ["tonnelet", "keg"], requires: [] },
  { assetKey: "prop/barrel_small", any: ["tonneau", "baril", "barrique", "fut ", "futs ", "baquet", "barrel"], requires: [] },
  { assetKey: "prop/crates_stacked", any: ["caisse", "cageot", "caisson", "marchandise", "crate"], requires: [] },
  { assetKey: "prop/bed_frame", any: ["lit ", "lits ", "couchette", "paillasse", "grabat", "matelas", "hamac", "bed ", "beds "], requires: [] },
  { assetKey: "prop/pillar", any: ["pilier", "colonne", "poteau", "pillar", "column"], requires: [] },
  { assetKey: "prop/campfire", any: ["feu de camp", "foyer", "bivouac", "brasier", "campfire"], requires: [] },
  { assetKey: "prop/tent", any: ["tente", "chapiteau", "pavillon", "campement", "tent ", "tents "], requires: [] },
  { assetKey: "prop/pot", any: ["jarre", "vase ", "vases ", "amphore", "urne", "poterie", "cruche", "pot ", "pots ", "jar "], requires: [] },
  { assetKey: "prop/obelisk", any: ["obelisque", "stele", "menhir", "monolithe", "pierre levee", "obelisk"], requires: [] },
  { assetKey: "prop/statue", any: ["statue", "idole", "effigie", "buste", "sculpture", "monument"], requires: [] },
  { assetKey: "nature/tree_dark", any: ["arbre", "tree", "chene", "saule", "if ", "bouleau"], requires: ["mort", "petrifi", "sec ", "seche", "calcin", "noueux", "fletri", "creux", "pierre", "dead", "withered", "petrified"] },
  { assetKey: "nature/log", any: ["tronc", "rondin", "buche", "bois flotte", "log ", "logs "], requires: [] },
  { assetKey: "nature/stump", any: ["souche", "stump"], requires: [] },
  { assetKey: "nature/tree_palm_tall", any: ["palmier", "palm "], requires: [] },
  { assetKey: "nature/cactus_tall", any: ["cactus"], requires: [] },
  { assetKey: "nature/tree_pine_a", any: ["arbre", "sapin", "pin ", "pins ", "chene", "saule", "bouleau", "tree", "pine"], requires: [] },
  { assetKey: "nature/bush", any: ["buisson", "fourre", "arbuste", "taillis", "haie ", "bush"], requires: [] },
  { assetKey: "nature/grass_large", any: ["roseau", "jonc", "hautes herbes", "reed"], requires: [] },
  { assetKey: "prop/rubble_large", any: ["gravat", "debris", "detritus", "eboulis", "eboulement", "effondr", "decombre", "rubble"], requires: [] },
  { assetKey: "nature/rock_large_a", any: ["rocher", "roche", "rocaille", "affleurement", "stalagmite", "stalactite", "falaise", "bloc ", "blocs ", "boulder", "rock"], requires: [] },
  { assetKey: "nature/rock_small_a", any: ["pierre", "caillou", "galet", "cairn", "stone"], requires: [] },
  { assetKey: "proc/mound", any: ["dune", "talus", "butte", "monticule", "tertre", "mound"], requires: [] },
  { assetKey: "proc/footprints", any: ["trace", "empreinte", "piste ", "footprint", "track"], requires: [] },
]

export const TINT_RULES: readonly (readonly [string, readonly string[]])[] = [
  ["petrified", ["petrifi", "de pierre", "en pierre", "fossil", "petrified"]],
  ["charred", ["calcin", "brule", "carbonis", "noirci", "charred", "burnt"]],
  ["frost", ["gele", "givre", "glace", "frozen", "frost"]],
  ["moss", ["moussu", "mousse", "lichen", "mossy"]],
  ["sand", ["ensable", "erode", "sable", "sandy"]],
  ["deadwood", ["mort", "sec ", "seche", "fletri", "pourri", "vermoulu", "dead", "rotten"]],
]

export const PROCEDURAL_PROP_KEYS: readonly string[] = ["proc/fountain", "proc/well", "proc/altar", "proc/sarcophagus", "proc/anvil", "proc/lectern", "proc/bookcase", "proc/mound", "proc/footprints"]

export const CATALOG_ELEMENT_KINDS: readonly string[] = ["cover", "decor", "furniture"]
