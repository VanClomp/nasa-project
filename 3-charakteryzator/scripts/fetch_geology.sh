#!/bin/bash
# Geology and terrain maps for Mars, from the PDS Geosciences Node (about 300 MB in total).
# Run in Terminal from inside the project folder:
#   cd ~/Desktop/"own nasa folder" && bash scripts/fetch_geology.sh
# Safe to re-run: files already present are skipped.
source "$(dirname "$0")/pds_lib.sh"
G="https://pds-geosciences.wustl.edu"
OUT="$DATA/geology"
fetch_list() { local base="$1" dir="$2"; shift 2; mkdir -p "$dir"; for f in "$@"; do get "$base/$f" "$dir/$f"; done; }

echo "1/4 MOLA topography, 32 pixels per degree (about 1.85 km), whole planet: elevation, slope, roughness (133 MB)"
fetch_list "$G/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032" "$OUT/mola_meg032" \
  megt90n000fb.img megt90n000fb.lbl megt90n000fb.xml
get "$G/mgs/urn-nasa-pds-mgs_mola_topography_derived/readme.txt" "$OUT/mola_meg032/readme.txt"

echo "2/4 TES thermal inertia, 20 pixels per degree (about 3 km), night and day maps with infill masks (155 MB)"
fetch_list "$G/mgs/mgs-m-tes-5-timap-v1/mgst_9001/data" "$OUT/tes_thermal_inertia" \
  datainfo.txt global_ti_night_2007.img global_ti_night_2007.lbl global_ti_msk_night_2007.img global_ti_msk_night_2007.lbl \
  global_ti_day_2007.img global_ti_day_2007.lbl global_ti_msk_day_2007.img global_ti_msk_day_2007.lbl
get "$G/mgs/mgs-m-tes-5-timap-v1/mgst_9001/aareadme.txt" "$OUT/tes_thermal_inertia/aareadme.txt"

echo "3/4 Odyssey GRS water content of the top tens of cm, low and mid latitudes (2 MB)"
B="$G/ody/ody-m-grs-5-elements-v1/odgm_xxxx"
fetch_list "$B/data/unsmoothed/2x2" "$OUT/grs_water" h2o_2x2.tab h2o_2x2.lbl h2o_2x2.xml
fetch_list "$B/data/smoothed" "$OUT/grs_water" h2o_sr_5x5.tab h2o_sr_5x5.lbl h2o_sr_5x5.xml
get "$B/aareadme.txt" "$OUT/grs_water/aareadme.txt"

echo "4/4 Odyssey neutron map, whole planet including the poles: hydrogen and ice indicator (7 MB)"
fetch_list "$G/ody/urn-nasa-pds-odyssey_grs_special/data" "$OUT/grs_neutron" \
  ns_epithermal_020917.tab ns_epithermal_020917.xml ns_epithermal_020917.lbl

echo "Done. Size on disk:"; du -sh "$OUT"/*
