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

MISSING=0

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

for d in "$ADV" "$SKE" "$DUN" "$NAT"; do
  if [ ! -d "$d" ]; then
    echo "ERROR: expected source dir not found: $d" >&2
    echo "(pack layout may have changed upstream — inspect $CACHE)" >&2
    exit 1
  fi
done

mkdir -p "$MODELS_DIR/adventurers" "$MODELS_DIR/skeletons" \
         "$MODELS_DIR/dungeon" "$MODELS_DIR/nature"

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
copy_model "$DUN/shelf_large"    "$MODELS_DIR/dungeon/shelf_large.glb"
copy_model "$DUN/shelf_small"    "$MODELS_DIR/dungeon/shelf_small.glb"
copy_model "$DUN/pillar"         "$MODELS_DIR/dungeon/pillar.glb"
copy_model "$DUN/rubble_large"   "$MODELS_DIR/dungeon/rubble_large.glb"
# Pruned for size budget (2026-06-10) — re-enable if needed:
# copy_model "$DUN/banner_red"       "$MODELS_DIR/dungeon/banner_red.glb"
# copy_model "$DUN/chest_gold"       "$MODELS_DIR/dungeon/chest_gold.glb"
# copy_model "$DUN/column"           "$MODELS_DIR/dungeon/column.glb"
# copy_model "$DUN/rubble_half"      "$MODELS_DIR/dungeon/rubble_half.glb"
# copy_model "$DUN/bed_frame"        "$MODELS_DIR/dungeon/bed_frame.glb"
# copy_model "$DUN/wall_window_open" "$MODELS_DIR/dungeon/wall_window_open.glb"

# nature/ — Kenney Nature Kit
copy_model "$NAT/tree_pineRoundA.glb"   "$MODELS_DIR/nature/tree_pine_a.glb"
copy_model "$NAT/tree_pineRoundB.glb"   "$MODELS_DIR/nature/tree_pine_b.glb"
copy_model "$NAT/tree_tall_dark.glb"    "$MODELS_DIR/nature/tree_dark.glb"
copy_model "$NAT/tree_palmTall.glb"     "$MODELS_DIR/nature/tree_palm_tall.glb"
copy_model "$NAT/tree_palmBend.glb"     "$MODELS_DIR/nature/tree_palm_bend.glb"
copy_model "$NAT/plant_bush.glb"        "$MODELS_DIR/nature/bush.glb"
copy_model "$NAT/plant_bushLarge.glb"   "$MODELS_DIR/nature/bush_large.glb"
copy_model "$NAT/grass_large.glb"       "$MODELS_DIR/nature/grass_large.glb"
copy_model "$NAT/flower_purpleA.glb"    "$MODELS_DIR/nature/flower_purple.glb"
copy_model "$NAT/mushroom_red.glb"      "$MODELS_DIR/nature/mushroom_red.glb"
copy_model "$NAT/mushroom_tanGroup.glb" "$MODELS_DIR/nature/mushroom_tan.glb"
copy_model "$NAT/rock_largeA.glb"       "$MODELS_DIR/nature/rock_large_a.glb"
copy_model "$NAT/rock_smallA.glb"       "$MODELS_DIR/nature/rock_small_a.glb"
copy_model "$NAT/rock_smallB.glb"       "$MODELS_DIR/nature/rock_small_b.glb"
copy_model "$NAT/stone_largeA.glb"      "$MODELS_DIR/nature/stone_large_a.glb"
copy_model "$NAT/stump_old.glb"         "$MODELS_DIR/nature/stump.glb"
copy_model "$NAT/log.glb"               "$MODELS_DIR/nature/log.glb"
copy_model "$NAT/cactus_short.glb"      "$MODELS_DIR/nature/cactus_short.glb"
copy_model "$NAT/cactus_tall.glb"       "$MODELS_DIR/nature/cactus_tall.glb"
copy_model "$NAT/lily_large.glb"        "$MODELS_DIR/nature/lily.glb"
# Pruned for size budget (2026-06-10) — re-enable if needed:
# copy_model "$NAT/tree_pineRoundC.glb" "$MODELS_DIR/nature/tree_pine_c.glb"
# copy_model "$NAT/rock_largeB.glb"     "$MODELS_DIR/nature/rock_large_b.glb"
# copy_model "$NAT/flower_yellowA.glb"  "$MODELS_DIR/nature/flower_yellow.glb"

# --- 4. Report ------------------------------------------------------------------
echo ""
echo "=== Sizes ==="
du -sh "$MODELS_DIR"/adventurers "$MODELS_DIR"/skeletons \
       "$MODELS_DIR"/dungeon "$MODELS_DIR"/nature "$MODELS_DIR"

echo ""
echo "=== sha256 ==="
find "$MODELS_DIR" -name '*.glb' | sort | while read -r f; do
  shasum -a 256 "$f"
done

if [ "$MISSING" -gt 0 ]; then
  echo ""
  echo "WARNING: $MISSING source file(s) were missing — see WARN lines above." >&2
  exit 1
fi
echo ""
echo "Done."
