#!/bin/bash
# Fills the two gaps found when the first downloads were processed (roughly 1 GB in total):
#   Perseverance air temperature : MEDA calibrated ATS tables, every 20th sol (same sols as before), about 0.5 GB
#   InSight continuous record    : TWINS derived air temperature and wind, every 20th sol, about 0.6 GB
# Run in Terminal from wherever the project folder now lives:
#   bash scripts/fetch_gap_fill.sh
# Safe to re-run: files already present are skipped.
source "$(dirname "$0")/pds_lib.sh"
MEDA_STEP=20; TWINS_STEP=20

echo "1/2 Perseverance MEDA air temperature"
B="$ROOT/PDS4/Mars2020/mars2020_meda/data_calibrated_env"; lbl=0
for r in $(links "$B/" | grep '^sol_.*/$'); do
  for s in $(links "$B/$r" | grep '^sol_[0-9]*/$'); do
    n=$((10#$(echo "$s" | tr -dc '0-9'))); [ $((n % MEDA_STEP)) -ne 0 ] && continue
    fetch_matching "$B/$r$s" "$DATA/perseverance_meda_ats" 'CAL_ATS_.*\.CSV$'
    [ $lbl -eq 0 ] && fetch_matching "$B/$r$s" "$DATA/perseverance_meda_ats/labels" 'CAL_ATS_.*\.xml$' && lbl=1
  done
  echo "  $r done"
done

echo "2/2 InSight TWINS derived temperature and wind"
B="$ROOT/PDS4/InSight/twins_bundle/data_derived"; lbl=0
for r in $(links "$B/" | grep '^sol_.*/$'); do
  all=$(links "$B/$r" | grep -E '^twins_model_[0-9]{4}_[0-9]+\.csv$' | sort)
  for sol in $(echo "$all" | cut -d_ -f3 | sort -u); do
    [ $((10#$sol % TWINS_STEP)) -ne 0 ] && continue
    f=$(echo "$all" | grep "^twins_model_${sol}_" | tail -1)        # newest version of that sol
    mkdir -p "$DATA/insight_twins_derived"
    get "$B/$r$f" "$DATA/insight_twins_derived/$f"
    [ $lbl -eq 0 ] && get "$B/$r${f%.csv}.xml" "$DATA/insight_twins_derived/labels/${f%.csv}.xml" && lbl=1
  done
  echo "  $r done"
done
echo "Done. Size on disk:"; du -sh "$DATA/perseverance_meda_ats" "$DATA/insight_twins_derived"
