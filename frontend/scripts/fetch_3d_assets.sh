#!/usr/bin/env bash
# =============================================================================
# fetch_3d_assets.sh — MAINTENANCE script (NOT a build step).
#
# Reproduces frontend/public/models/** from scratch:
#   1. Downloads the CC0 source packs (KayKit + Kenney) into a cache dir.
#   2. Extracts them.
#   3. Copies/renames the pruned subset used by the RpgMaster 3D engine.
#   4. Prints sizes + sha256 of every staged file.
#
# Usage:    ./scripts/fetch_3d_assets.sh
# Cache:    CACHE=/some/dir ./scripts/fetch_3d_assets.sh   (default /tmp/rpgmaster_3d_packs)
#
# Licenses: all packs are CC0-1.0 — see frontend/public/models/CREDITS.md
# =============================================================================
set -euo pipefail

CACHE="${CACHE:-/tmp/rpgmaster_3d_packs}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/public/models"

ADVENTURERS_URL="https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0/archive/refs/heads/main.zip"
SKELETONS_URL="https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Skeletons-1.0/archive/refs/heads/main.zip"
DUNGEON_URL="https://github.com/KayKit-Game-Assets/KayKit-Dungeon-Remastered-1.0/archive/refs/heads/main.zip"
NATURE_PAGE_URL="https://kenney.nl/assets/nature-kit"
# KayKit Forest is itch.io-exclusive (no GitHub mirror, no scrapeable direct
# URL like Kenney's) — the FREE pack must be downloaded by hand from this page
# and unzipped into "$CACHE/forest/" so that "$CACHE/forest/Assets/gltf/" exists.
FOREST_HELP_URL="https://kaylousberg.itch.io/kaykit-forest"

MISSING=0
FOREST_MISSING=0

fallback_help() {
  echo "" >&2
  echo "URL failed. Download the packs manually from:" >&2
  echo "  - KayKit packs:      https://kaylousberg.itch.io/" >&2
  echo "  - Kenney Nature Kit: https://kenney.nl/assets/nature-kit" >&2
  echo "then place the zips in $CACHE as <pack>.zip and re-run." >&2
}

# fetch_pack NAME URL — verify URL, download $CACHE/NAME.zip if absent, unzip
# into $CACHE/NAME/. Skipped entirely when the extracted dir already exists.
fetch_pack() {
  local name="$1" url="$2"
  local zip="$CACHE/$name.zip" dest="$CACHE/$name"

  if [ -d "$dest" ] && [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then
    echo "[cache] $name already extracted — skipping download"
    return 0
  fi
  mkdir -p "$CACHE"
  if [ ! -f "$zip" ]; then
    echo "[fetch] verifying $url"
    if ! curl -fsIL -o /dev/null "$url"; then
      echo "ERROR: cannot reach $url" >&2
      fallback_help
      exit 1
    fi
    echo "[fetch] downloading $name.zip"
    curl -fL --retry 2 -o "$zip" "$url"
  fi
  echo "[unzip] $name"
  mkdir -p "$dest"
  unzip -q -o "$zip" -d "$dest"
}

# Kenney's zip lives behind a generated /media/pages/... path — scrape it.
resolve_nature_url() {
  local page zip_path
  if ! page="$(curl -fsL "$NATURE_PAGE_URL")"; then
    echo "ERROR: cannot reach $NATURE_PAGE_URL" >&2
    fallback_help
    exit 1
  fi
  zip_path="$(printf '%s' "$page" \
    | grep -oE '/media/pages/assets/nature-kit/[^"]*kenney_nature-kit\.zip' \
    | head -n 1)"
  if [ -z "$zip_path" ]; then
    echo "ERROR: could not scrape kenney_nature-kit.zip URL from $NATURE_PAGE_URL" >&2
    fallback_help
    exit 1
  fi
  echo "https://kenney.nl$zip_path"
}

# copy_model SRC DST — copies SRC to DST, tolerating KayKit's two naming
# variants: tries SRC as-is, then SRC.gltf.glb, then SRC.glb.
copy_model() {
  local src="$1" dst="$2" base
  base="${src%.glb}"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
  elif [ -f "$base.gltf.glb" ]; then
    cp "$base.gltf.glb" "$dst"
  elif [ -f "$base.glb" ]; then
    cp "$base.glb" "$dst"
  else
    echo "WARN: missing source $src" >&2
    MISSING=$((MISSING + 1))
  fi
}

# copy_gltf_model NAME — copies $FOREST/<NAME>_Color1.gltf + .bin to
# $MODELS_DIR/nature/forest/ as-is (no rename: GLTFLoader resolves the sibling
# .bin and the shared forest_texture.png by relative URI). Tolerates a missing
# $FOREST (manual pack, see FOREST_HELP_URL) by warning instead of failing.
copy_gltf_model() {
  local name="$1"
  if [ ! -f "$FOREST/${name}_Color1.gltf" ]; then
    echo "WARN: missing source $FOREST/${name}_Color1.gltf" >&2
    FOREST_MISSING=$((FOREST_MISSING + 1))
    return 0
  fi
  cp "$FOREST/${name}_Color1.gltf" "$MODELS_DIR/nature/forest/${name}_Color1.gltf"
  cp "$FOREST/${name}_Color1.bin"  "$MODELS_DIR/nature/forest/${name}_Color1.bin"
}

# --- 1. Fetch + extract -------------------------------------------------------
fetch_pack adventurers "$ADVENTURERS_URL"
fetch_pack skeletons   "$SKELETONS_URL"
fetch_pack dungeon     "$DUNGEON_URL"
if [ -d "$CACHE/nature" ] && [ -n "$(ls -A "$CACHE/nature" 2>/dev/null)" ]; then
  echo "[cache] nature already extracted — skipping download"
else
  fetch_pack nature "$(resolve_nature_url)"
fi

# --- 2. Source roots (as extracted from the archives above) -------------------
ADV="$CACHE/adventurers/KayKit-Character-Pack-Adventures-1.0-main/addons/kaykit_character_pack_adventures/Characters/gltf"
SKE="$CACHE/skeletons/KayKit-Character-Pack-Skeletons-1.0-main/addons/kaykit_character_pack_skeletons/Characters/gltf"
DUN="$CACHE/dungeon/KayKit-Dungeon-Remastered-1.0-main/addons/kaykit_dungeon_remastered/Assets/gltf"
NAT="$CACHE/nature/Models/GLTF format"
FOREST="$CACHE/forest/Assets/gltf"

for d in "$ADV" "$SKE" "$DUN" "$NAT"; do
  if [ ! -d "$d" ]; then
    echo "ERROR: expected source dir not found: $d" >&2
    echo "(pack layout may have changed upstream — inspect $CACHE)" >&2
    exit 1
  fi
done

if [ ! -d "$FOREST" ]; then
  echo "" >&2
  echo "WARN: KayKit Forest source not found at $FOREST" >&2
  echo "  Download the FREE pack by hand from $FOREST_HELP_URL" >&2
  echo "  and unzip it into \$CACHE/forest/ (so that $FOREST exists), then re-run" >&2
  echo "  to refresh nature/forest/*. Already-committed files are left untouched." >&2
fi

mkdir -p "$MODELS_DIR/adventurers" "$MODELS_DIR/skeletons" \
         "$MODELS_DIR/dungeon" "$MODELS_DIR/nature" "$MODELS_DIR/nature/forest"

# --- 3. Mapping (pruned subset) -----------------------------------------------
# adventurers/ — KayKit Character Pack: Adventurers
copy_model "$ADV/Knight.glb"       "$MODELS_DIR/adventurers/knight.glb"
copy_model "$ADV/Barbarian.glb"    "$MODELS_DIR/adventurers/barbarian.glb"
copy_model "$ADV/Mage.glb"         "$MODELS_DIR/adventurers/mage.glb"
copy_model "$ADV/Rogue.glb"        "$MODELS_DIR/adventurers/rogue.glb"
copy_model "$ADV/Rogue_Hooded.glb" "$MODELS_DIR/adventurers/rogue_hooded.glb"

# skeletons/ — KayKit Character Pack: Skeletons
copy_model "$SKE/Skeleton_Warrior.glb" "$MODELS_DIR/skeletons/skeleton_warrior.glb"
copy_model "$SKE/Skeleton_Mage.glb"    "$MODELS_DIR/skeletons/skeleton_mage.glb"
copy_model "$SKE/Skeleton_Rogue.glb"   "$MODELS_DIR/skeletons/skeleton_rogue.glb"
copy_model "$SKE/Skeleton_Minion.glb"  "$MODELS_DIR/skeletons/skeleton_minion.glb"

# dungeon/ — KayKit Dungeon Remastered (sources are NAME.gltf.glb or NAME.glb;
# copy_model tries both)
copy_model "$DUN/wall"           "$MODELS_DIR/dungeon/wall.glb"
copy_model "$DUN/wall_corner"    "$MODELS_DIR/dungeon/wall_corner.glb"
copy_model "$DUN/wall_doorway"   "$MODELS_DIR/dungeon/wall_doorway.glb"
copy_model "$DUN/stairs"         "$MODELS_DIR/dungeon/stairs.glb"
copy_model "$DUN/torch_lit"      "$MODELS_DIR/dungeon/torch_lit.glb"
copy_model "$DUN/torch_mounted"  "$MODELS_DIR/dungeon/torch_mounted.glb"
copy_model "$DUN/table_medium"   "$MODELS_DIR/dungeon/table_medium.glb"
copy_model "$DUN/table_long"     "$MODELS_DIR/dungeon/table_long.glb"
copy_model "$DUN/table_small"    "$MODELS_DIR/dungeon/table_small.glb"
copy_model "$DUN/chair"          "$MODELS_DIR/dungeon/chair.glb"
copy_model "$DUN/stool"          "$MODELS_DIR/dungeon/stool.glb"
copy_model "$DUN/keg"            "$MODELS_DIR/dungeon/keg.glb"
copy_model "$DUN/barrel_small"   "$MODELS_DIR/dungeon/barrel_small.glb"
copy_model "$DUN/barrel_large"   "$MODELS_DIR/dungeon/barrel_large.glb"
copy_model "$DUN/crates_stacked" "$MODELS_DIR/dungeon/crates_stacked.glb"
copy_model "$DUN/chest"          "$MODELS_DIR/dungeon/chest.glb"
copy_model "$DUN/chest_gold"     "$MODELS_DIR/dungeon/chest_gold.glb"
copy_model "$DUN/shelf_large"    "$MODELS_DIR/dungeon/shelf_large.glb"
copy_model "$DUN/shelf_small"    "$MODELS_DIR/dungeon/shelf_small.glb"
copy_model "$DUN/pillar"         "$MODELS_DIR/dungeon/pillar.glb"
copy_model "$DUN/rubble_large"   "$MODELS_DIR/dungeon/rubble_large.glb"
copy_model "$DUN/bed_frame"      "$MODELS_DIR/dungeon/bed_frame.glb"
# Pruned for size budget (2026-06-10) — re-enable if needed:
# copy_model "$DUN/banner_red"       "$MODELS_DIR/dungeon/banner_red.glb"
# copy_model "$DUN/chest_gold"       "$MODELS_DIR/dungeon/chest_gold.glb"
# copy_model "$DUN/column"           "$MODELS_DIR/dungeon/column.glb"
# copy_model "$DUN/rubble_half"      "$MODELS_DIR/dungeon/rubble_half.glb"
# copy_model "$DUN/wall_window_open" "$MODELS_DIR/dungeon/wall_window_open.glb"

# nature/ — Kenney Nature Kit (no KayKit Forest equivalent: palmier, fleurs,
# champignons, souche/rondin, cactus, nénuphar, props de décor)
copy_model "$NAT/tree_palmTall.glb"     "$MODELS_DIR/nature/tree_palm_tall.glb"
copy_model "$NAT/tree_palmBend.glb"     "$MODELS_DIR/nature/tree_palm_bend.glb"
copy_model "$NAT/flower_purpleA.glb"    "$MODELS_DIR/nature/flower_purple.glb"
copy_model "$NAT/mushroom_red.glb"      "$MODELS_DIR/nature/mushroom_red.glb"
copy_model "$NAT/mushroom_tanGroup.glb" "$MODELS_DIR/nature/mushroom_tan.glb"
copy_model "$NAT/stump_old.glb"         "$MODELS_DIR/nature/stump.glb"
copy_model "$NAT/log.glb"               "$MODELS_DIR/nature/log.glb"
copy_model "$NAT/cactus_short.glb"      "$MODELS_DIR/nature/cactus_short.glb"
copy_model "$NAT/cactus_tall.glb"       "$MODELS_DIR/nature/cactus_tall.glb"
copy_model "$NAT/lily_large.glb"        "$MODELS_DIR/nature/lily.glb"
copy_model "$NAT/flower_yellowA.glb"    "$MODELS_DIR/nature/flower_yellow.glb"
copy_model "$NAT/campfire_stones.glb"   "$MODELS_DIR/nature/campfire.glb"
copy_model "$NAT/pot_large.glb"         "$MODELS_DIR/nature/pot.glb"
copy_model "$NAT/tent_detailedOpen.glb" "$MODELS_DIR/nature/tent.glb"
copy_model "$NAT/statue_block.glb"      "$MODELS_DIR/nature/statue.glb"
copy_model "$NAT/statue_obelisk.glb"    "$MODELS_DIR/nature/obelisk.glb"
# Pruned for size budget (2026-06-10) — re-enable if needed:
# copy_model "$NAT/tree_pineRoundC.glb" "$MODELS_DIR/nature/tree_pine_c.glb"

# nature/forest/ — KayKit Forest (scatter tempéré : pins, arbre mort, buissons,
# herbe, rochers/pierres). Voir copy_gltf_model + FOREST_HELP_URL ci-dessus.
copy_gltf_model "Tree_4_A"
copy_gltf_model "Tree_4_B"
copy_gltf_model "Tree_Bare_1_A"
copy_gltf_model "Bush_1_A"
copy_gltf_model "Bush_2_A"
copy_gltf_model "Grass_1_A"
copy_gltf_model "Grass_2_A"
copy_gltf_model "Rock_1_A"
copy_gltf_model "Rock_3_A"
copy_gltf_model "Rock_2_A"
copy_gltf_model "Rock_2_B"
if [ -f "$FOREST/forest_texture.png" ]; then
  cp "$FOREST/forest_texture.png" "$MODELS_DIR/nature/forest/forest_texture.png"
elif [ -d "$FOREST" ]; then
  echo "WARN: missing source $FOREST/forest_texture.png" >&2
  FOREST_MISSING=$((FOREST_MISSING + 1))
fi

# --- 4. Report ------------------------------------------------------------------
echo ""
echo "=== Sizes ==="
du -sh "$MODELS_DIR"/adventurers "$MODELS_DIR"/skeletons \
       "$MODELS_DIR"/dungeon "$MODELS_DIR"/nature "$MODELS_DIR"

echo ""
echo "=== sha256 ==="
find "$MODELS_DIR" \( -name '*.glb' -o -name '*.gltf' -o -name '*.bin' -o -path '*/nature/forest/*.png' \) | sort | while read -r f; do
  shasum -a 256 "$f"
done

if [ "$FOREST_MISSING" -gt 0 ]; then
  echo ""
  echo "WARNING: $FOREST_MISSING KayKit Forest source file(s) were missing — see WARN lines above." >&2
  echo "(nature/forest/* already committed in public/models/ were left untouched)" >&2
fi

if [ "$MISSING" -gt 0 ]; then
  echo ""
  echo "WARNING: $MISSING source file(s) were missing — see WARN lines above." >&2
  exit 1
fi
echo ""
echo "Done."
