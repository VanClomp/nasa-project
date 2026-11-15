#!/bin/bash
# Downloads Mars Pathfinder calibrated surface weather tables (ASI/MET, volume mpam_0001)
# from the PDS Atmospheres Node into ./pathfinder_met/ next to this script.
# Run in Terminal:  bash fetch_pathfinder_met.sh
# Safe to re-run: files already downloaded are skipped.
BASE="https://pds-atmospheres.nmsu.edu/PDS/data/mpam_0001"
SCI="$BASE/surf_rdr/scidata/"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../pathfinder_met"
mkdir -p "$OUT/scidata"

links() { curl -fsS "$1" | grep -o 'href="[^"?/][^"]*"' | sed 's/^href="//; s/"$//'; }
get()   { [ -s "$2" ] || curl -fsS --retry 3 -o "$2" "$1" || echo "FAILED: $1"; }
export -f get

get "$BASE/aareadme.txt" "$OUT/aareadme.txt"

dirs=$(links "$SCI" | grep '/$')
[ -z "$dirs" ] && { echo "Could not read the folder list at $SCI"; exit 1; }

label_saved=0
for d in $dirs; do
  mkdir -p "$OUT/scidata/$d"
  files=$(links "$SCI$d")
  if [ $label_saved -eq 0 ]; then
    l=$(echo "$files" | grep '\.lbl$' | head -1)
    [ -n "$l" ] && get "$SCI$d$l" "$OUT/column_description_example.lbl" && label_saved=1
  fi
  echo "$files" | grep '\.tab$' | xargs -P 6 -I{} bash -c 'get "$0" "$1"' "$SCI$d{}" "$OUT/scidata/$d{}"
  echo "$d done"
done
echo "Finished: $(find "$OUT/scidata" -name '*.tab' | wc -l | tr -d ' ') data tables in $OUT"
