#!/bin/bash
# Small datasets (roughly 150-250 MB in total). Run in Terminal:
#   bash ~/Desktop/"nasa project"/scripts/fetch_small_sets.sh
# Safe to re-run: files already present are skipped.
source "$(dirname "$0")/pds_lib.sh"

echo "1/7 Viking Lander meteorology, optical depth, footpad temperatures"
fetch_matching "$ROOT/vl_1001/data/" "$DATA/viking_met" '.'
fetch_matching "$ROOT/vl_1002/data/" "$DATA/viking_footpad" '.'
get "$ROOT/vl_1001/aareadme.txt" "$DATA/viking_met/aareadme.txt"

echo "2/7 Phoenix dust opacity and telltale wind"
fetch_matching "$ROOT/phxao_1001/DATA/" "$DATA/phoenix_opacity" '.'
fetch_matching "$ROOT/phxwnd_0001/DATA/" "$DATA/phoenix_wind" '.'

echo "3/7 Phoenix pressure and temperature (low-rate and summary tables only)"
for v in phmt_0001 phmt_0002 phmt_0003; do
  for d in $(links "$ROOT/$v/DATA/" | grep '/$'); do
    fetch_matching "$ROOT/$v/DATA/${d}RDR/" "$DATA/phoenix_met/$v" 'RM[AL]_'
  done
done
get "$ROOT/phmt_0001/AAREADME.TXT" "$DATA/phoenix_met/AAREADME.TXT"

echo "4/7 Global maps: albedo, thermal inertia, topography"
fetch_matching "$ROOT/atmos_0006/data/" "$DATA/global_maps" '.'
get "$ROOT/atmos_0006/aareadme.txt" "$DATA/global_maps/aareadme.txt"

echo "5/7 Ames climate model output"
fetch_matching "$ROOT/mogc_0001/data/" "$DATA/ames_gcm" '.'
get "$ROOT/mogc_0001/aareadme.txt" "$DATA/ames_gcm/aareadme.txt"

echo "6/7 MGS TES visible dust optical depth, Mars years 24-27"
B="$ROOT/PDS4/mgs_tes_atmos_dust-ice"
get "$B/readme.txt" "$DATA/tes_dust/readme.txt"
for y in $(links "$B/data_VIS_Dust_Optical_Depth/" | grep '/$'); do
  fetch_matching "$B/data_VIS_Dust_Optical_Depth/$y" "$DATA/tes_dust/$y" '.'
done

echo "7/7 InSight low-rate pressure, temperature and wind"
B="$ROOT/PDS4/InSight/erp_bundle/data_calibrated"
n=0
for d in $(links "$B/" | grep '/$'); do
  fetch_matching "$B/$d" "$DATA/insight_lowrate/$d" '_lr\.csv$'
  if [ $n -eq 0 ]; then fetch_matching "$B/$d" "$DATA/insight_lowrate/labels" "$(links "$B/$d" | grep '_lr\.xml$' | head -2 | paste -sd'|' -)"; n=1; fi
done
echo "Done. Size on disk:"; du -sh "$DATA"/* 2>/dev/null
