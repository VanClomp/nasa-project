#!/usr/bin/env bash
# Copy the map files the Charakteryzator service reads at runtime (~1 GB) from this component's
# local data folder into the repo-root data/ volume that docker-compose mounts as /data:
#   3-charakteryzator/data/geology/*  ->  data/mars/      (MARS_DATA_DIR=/data/mars)
#   3-charakteryzator/data/moon/...   ->  data/moon/      (MOON_DATA_DIR=/data/moon)
# Without these folders the service fails and 2-networker falls back to the nearest of the 12/24 known
# sites from outputs/*_sites.json, so a clicked point would never get its own (global-model) answer.
# Station records are not needed: the site models read the reduced tables in outputs/ (baked into the image).
#
# Usage (from anywhere):  bash 3-charakteryzator/scripts/pack_server_data.sh [--dry-run]
# Safe to re-run: rsync only copies files that changed. Both targets are git-ignored.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # 3-charakteryzator/
ROOT="$(cd "$HERE/.." && pwd)"                               # repo root
SRC_MARS="$HERE/data/geology"
SRC_MOON="$HERE/data/moon"
DST_MARS="$ROOT/data/mars"
DST_MOON="$ROOT/data/moon"
RSYNC=(rsync -a --human-readable)
[[ "${1:-}" == "--dry-run" ]] && RSYNC+=(--dry-run --itemize-changes)

# Mars: every folder mars_maps.py reads (caves/ may be empty: nearest_skylight_km is then null).
MARS_DIRS=(mola_meg032 tes_thermal_inertia tes_albedo grs_water grs_neutron omega_minerals caves)

# Moon: exact files moon_maps.py reads. ldrm_* only feed the optional lola_roughness field.
# Deliberately left out: ldsm_* (unused), dgdr_st/std_cf (unused), dlre_prp_*.tab (600 MB each, replaced
# by the prp_*_grid500m_v3.npz cache), older prp_*_grid500m(.npz|_v2.npz), Lunar Prospector 2-deg/fast/therms.
MOON_FILES=(
  lola/ldem_16.img lola/ldem_16.lbl
  lola/ldem_75n_240m.img lola/ldem_75n_240m.lbl lola/ldem_75s_240m.img lola/ldem_75s_240m.lbl
  lola/ldem_85n_40m.img lola/ldem_85n_40m.lbl lola/ldem_85s_40m.img lola/ldem_85s_40m.lbl
  lola/ldrm_75n_240m.img lola/ldrm_75n_240m.lbl lola/ldrm_75s_240m.img lola/ldrm_75s_240m.lbl
  lola/ldrm_85n_40m.img lola/ldrm_85n_40m.lbl lola/ldrm_85s_40m.img lola/ldrm_85s_40m.lbl
  illumination/AVGVISIB_65N_240M_201608.TIF illumination/AVGVISIB_65N_240M_201608.LBL
  illumination/AVGVISIB_65N_240M_201608_EARTH.TIF illumination/AVGVISIB_65N_240M_201608_EARTH.LBL
  illumination/AVGVISIB_65S_240M_201608.TIF illumination/AVGVISIB_65S_240M_201608.LBL
  illumination/AVGVISIB_65S_240M_201608_EARTH.TIF illumination/AVGVISIB_65S_240M_201608_EARTH.LBL
  illumination/AVGVISIB_85N_060M_201608.TIF illumination/AVGVISIB_85N_060M_201608.LBL
  illumination/AVGVISIB_85N_060M_201608_EARTH.TIF illumination/AVGVISIB_85N_060M_201608_EARTH.LBL
  illumination/AVGVISIB_85S_060M_201608.TIF illumination/AVGVISIB_85S_060M_201608.LBL
  illumination/AVGVISIB_85S_060M_201608_EARTH.TIF illumination/AVGVISIB_85S_060M_201608_EARTH.LBL
  diviner/dgdr_ra_avg_cyl_032_img.img diviner/dgdr_ra_avg_cyl_032_img.lbl diviner/dlre_prp.fmt
  diviner/prp_south_grid500m_v3.npz diviner/prp_north_grid500m_v3.npz
  lunar_prospector/epis.txt
  lunar_prospector/lpgrs_high1_elem_abundance_5deg.tab lunar_prospector/lpgrs_high1_elem_abundance_5deg.lbl
  lunar_prospector/lpgrs_elem_abundance.fmt
  pits/LUNAR_PIT_LOCATIONS.CSV
)

missing=0
for d in "${MARS_DIRS[@]}"; do
  [[ -d "$SRC_MARS/$d" ]] || { echo "MISSING (Mars): $SRC_MARS/$d  -> run scripts/fetch_geology.sh"; missing=1; }
done
for f in "${MOON_FILES[@]}"; do
  [[ -f "$SRC_MOON/$f" ]] || { echo "MISSING (Moon): $SRC_MOON/$f  -> run scripts/fetch_moon.sh"; missing=1; }
done
[[ $missing == 0 ]] || { echo "Nothing copied: fetch the missing files first."; exit 1; }

mkdir -p "$DST_MARS" "$DST_MOON"
echo "Mars -> $DST_MARS"
for d in "${MARS_DIRS[@]}"; do "${RSYNC[@]}" "$SRC_MARS/$d" "$DST_MARS/"; done
echo "Moon -> $DST_MOON"
printf '%s\n' "${MOON_FILES[@]}" | "${RSYNC[@]}" --files-from=- "$SRC_MOON/" "$DST_MOON/"

if [[ "${1:-}" != "--dry-run" ]]; then
  du -sh "$DST_MARS" "$DST_MOON"
  echo "Done. Start the stack with: docker compose up --build"
  echo "Check: a clicked point answers with extra.values (real model), not extra.matched_site (fallback)."
fi
