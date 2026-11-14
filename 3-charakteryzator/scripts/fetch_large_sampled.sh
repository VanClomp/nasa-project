#!/bin/bash
# Large datasets, sampled to keep the download near 1.5 GB:
#   Curiosity REMS  : every 10th sol of sols 1-1340 (two Mars years), about 0.6 GB
#   Perseverance MEDA: every 20th sol, pressure + ground/air temperature + wind, about 0.9 GB
# Run in Terminal:  bash ~/Desktop/"nasa project"/scripts/fetch_large_sampled.sh
# Change REMS_STEP / MEDA_STEP below for denser or sparser sampling. Safe to re-run.
source "$(dirname "$0")/pds_lib.sh"
REMS_STEP=10; REMS_LAST=1340; MEDA_STEP=20

echo "1/2 Curiosity REMS"
B="$ROOT/mslrem_1001/DATA"; lbl=0
for r in $(links "$B/" | grep '^SOL_.*/$'); do
  first=$((10#$(echo "$r" | cut -d_ -f2))); [ $first -gt $REMS_LAST ] && continue
  for s in $(links "$B/$r" | grep '^SOL[0-9]*/$'); do
    n=$((10#$(echo "$s" | tr -dc '0-9'))); [ $((n % REMS_STEP)) -ne 0 ] && continue; [ $n -gt $REMS_LAST ] && continue
    fetch_matching "$B/$r$s" "$DATA/curiosity_rems" 'RMD.*\.TAB$'
    [ $lbl -eq 0 ] && fetch_matching "$B/$r$s" "$DATA/curiosity_rems/labels" 'RMD.*\.(LBL|xml)$' && lbl=1
  done
  echo "  $r done"
done

echo "2/2 Perseverance MEDA"
B="$ROOT/PDS4/Mars2020/mars2020_meda/data_derived_env"; lbl=0
for r in $(links "$B/" | grep '^sol_.*/$'); do
  for s in $(links "$B/$r" | grep '^sol_[0-9]*/$'); do
    n=$((10#$(echo "$s" | tr -dc '0-9'))); [ $((n % MEDA_STEP)) -ne 0 ] && continue
    fetch_matching "$B/$r$s" "$DATA/perseverance_meda" 'DER_(PS|TIRS|WS)_.*\.CSV$'
    [ $lbl -eq 0 ] && fetch_matching "$B/$r$s" "$DATA/perseverance_meda/labels" 'DER_(PS|TIRS|WS)_.*\.xml$' && lbl=1
  done
  echo "  $r done"
done
echo "Done. Size on disk:"; du -sh "$DATA/curiosity_rems" "$DATA/perseverance_meda"
