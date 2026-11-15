#!/bin/bash
# Remaining Mars datasets: albedo, caves, hydrated minerals (about 20 MB).
# Optional mineral maps (about 1 GB) only if you add the word "minerals":
#   cd ~/Desktop/"own nasa folder" && bash scripts/fetch_extra.sh            # core, ~20 MB
#   cd ~/Desktop/"own nasa folder" && bash scripts/fetch_extra.sh minerals   # core + mineral maps, ~1 GB
# Safe to re-run: files already present are skipped.
source "$(dirname "$0")/pds_lib.sh"
G="https://pds-geosciences.wustl.edu"
OUT="$DATA/geology"
fetch_list() { local base="$1" dir="$2"; shift 2; mkdir -p "$dir"; for f in "$@"; do get "$base/$f" "$dir/$f"; done; }

echo "1/3 TES albedo, 8 pixels per degree, whole planet; input to the temperature model (17 MB)"
fetch_list "$G/mgs/mgs-m-tes-special-v1" "$OUT/tes_albedo" global_albedo_8ppd.img global_albedo_8ppd.lbl

echo "2/3 Mars Global Cave Candidate Catalog (USGS, about 1,000 candidate cave entrances): nearest_skylight_km (2 MB)"
mkdir -p "$OUT/caves"
Z="$OUT/caves/mars_cave_catalog.zip"
for u in "http://astropedia.astrogeology.usgs.gov/download/Mars/MarsCaveCatalog/mars_cave_catalog.zip"; do
  [ -s "$Z" ] && break
  curl -fsSL --connect-timeout 20 -o "$Z" "$u" || rm -f "$Z"
done
[ -s "$Z" ] && unzip -tq "$Z" >/dev/null 2>&1 || { rm -f "$Z"; false; } || echo "FAILED: cave catalog. Download it by hand from https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing into $OUT/caves/"
[ -s "$OUT/caves/mars_cave_catalog.zip" ] && (cd "$OUT/caves" && unzip -oq mars_cave_catalog.zip && echo "  unpacked")

echo "3/3 OMEGA/CRISM hydrated mineral sites (clays, hydrated salts): mineralogy and past water (0.1 MB)"
O="$G/mex/mex-m-omega-5-ddr-global-maps-v1/mexomg_2000"
fetch_list "$O/data/hydrous" "$OUT/omega_minerals" hydrous_sites_geo_map.csv hydrous_sites_geo_map.lbl
get "$O/aareadme.txt" "$OUT/omega_minerals/aareadme.txt"

if [ "$1" = "minerals" ]; then
  echo "Optional: OMEGA global mineral maps, 32 pixels per degree, 207 MB each (olivine, pyroxene, ferric oxide, surface dust, near-IR albedo)"
  fetch_list "$O/data/olivine"  "$OUT/omega_minerals" olivine_osp1_equ_map.img olivine_osp1_equ_map.lbl
  fetch_list "$O/data/pyroxene" "$OUT/omega_minerals" pyroxene_bd2000_equ_map.img pyroxene_bd2000_equ_map.lbl
  fetch_list "$O/data/ferric"   "$OUT/omega_minerals" ferric_bd530_equ_map.img ferric_bd530_equ_map.lbl ferric_nnphs_equ_map.img ferric_nnphs_equ_map.lbl
  fetch_list "$O/data/albedo"   "$OUT/omega_minerals" albedo_r1080_equ_map.img albedo_r1080_equ_map.lbl
fi
echo "Done. Size on disk:"; du -sh "$OUT"/tes_albedo "$OUT"/caves "$OUT"/omega_minerals
