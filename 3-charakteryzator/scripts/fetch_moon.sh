#!/bin/bash
# Moon data for base-site characterization (about 2.6 GB). Run from inside the project folder:
#   cd ~/Desktop/"own nasa folder" && bash scripts/fetch_moon.sh
# Safe to re-run: files already present are skipped. Files go to data/moon/.
HERE="$(cd "$(dirname "$0")/.." && pwd)"; OUT="$HERE/data/moon"
G="https://pds-geosciences.wustl.edu"
LOLA="$G/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr"
DIV="$G/lro/urn-nasa-pds-lro_diviner_derived1"
PGDA="https://pgda.gsfc.nasa.gov/data/MoonIllumination"
IMB="http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG"
# one file at a time, with retries: the Geosciences server briefly refuses bursts of requests
get() { local url="$1" dest="$2"; mkdir -p "$(dirname "$dest")"; [ -s "$dest" ] && return 0
  for i in 1 2 3 4 5; do curl -fsSL --connect-timeout 30 -o "$dest.part" "$url" && mv "$dest.part" "$dest" && return 0; sleep $((i*3)); done
  rm -f "$dest.part"; echo "FAILED: $url"; return 1; }
pair() { get "$1.img" "$2.img"; get "$1.lbl" "$2.lbl"; }

echo "1/7 LOLA terrain, whole Moon, 16 px/deg (~1.9 km): elevation, slope, roughness (100 MB)"
for f in ldem_16 ldsm_16 ldrm_16; do pair "$LOLA/cylindrical/img/$f" "$OUT/lola/$f"; done

echo "2/7 LOLA terrain, polar: 85-90 deg at 40 m and 75-90 deg at 240 m, both poles (690 MB)"
for p in s n; do for f in ldem_85${p}_40m ldsm_85${p}_40m ldrm_85${p}_40m ldem_75${p}_240m ldsm_75${p}_240m ldrm_75${p}_240m; do
  pair "$LOLA/polar/img/$f" "$OUT/lola/$f"; done; done

echo "3/7 Sunlight and Earth visibility, % of time over the 18.6-year cycle (LOLA, Mazarico et al. 2011), both poles"
for p in S N; do for r in 85${p}_060M 65${p}_240M; do for k in "" _EARTH; do
  get "$PGDA/AVGVISIB_${r}_201608${k}.TIF" "$OUT/illumination/AVGVISIB_${r}_201608${k}.TIF"
  get "$IMB/AVGVISIB_${r}_201608${k}.LBL" "$OUT/illumination/AVGVISIB_${r}_201608${k}.LBL" || true   # labels: scaling check only
done; done; done

echo "4/7 Diviner polar resource products: annual mean and max temperature, depth to stable water ice, both poles (1.2 GB)"
for p in south north; do get "$DIV/data_derived_prp/dlre_prp_$p.tab" "$OUT/diviner/dlre_prp_$p.tab"; get "$DIV/data_derived_prp/dlre_prp_$p.lbl" "$OUT/diviner/dlre_prp_$p.lbl"; done
get "$DIV/label/dlre_prp.fmt" "$OUT/diviner/dlre_prp.fmt"

echo "5/7 Diviner global maps 60S-60N, 32 px/deg: rock abundance, regolith temperature anomaly, composition (270 MB)"
for f in dgdr_ra_avg_cyl_032_img dgdr_st_avg_cyl_032_img dgdr_std_cf_clc_cyl_032_img; do pair "$DIV/data_derived_gdr_l3/cylindrical/img/$f" "$OUT/diviner/$f"; done

echo "6/7 Lunar Prospector: hydrogen (epithermal neutrons, 0.5 deg) and element abundances incl. FeO/TiO2 for oxygen extraction (13 MB)"
for f in epis.dat epis.txt therms.dat therms.txt fast.dat fast.txt; do get "$G/missions/lunarp/reduced/$f" "$OUT/lunar_prospector/$f"; done
E="$G/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001"
for f in lpgrs_high1_elem_abundance_2deg.tab lpgrs_high1_elem_abundance_2deg.lbl lpgrs_high1_elem_abundance_5deg.tab lpgrs_high1_elem_abundance_5deg.lbl lpgrs_elem_abundance.fmt; do
  get "$E/data/$f" "$OUT/lunar_prospector/$f"; done
get "$E/aareadme.txt" "$OUT/lunar_prospector/aareadme.txt"

echo "7/7 Lunar pits and lava-tube skylights (LROC, Wagner & Robinson): shelter sites (small)"
P="https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/EXTRAS/SHAPEFILE/LUNAR_PIT_LOCATIONS"
get "$P/LUNAR_PIT_LOCATIONS.CSV" "$OUT/pits/LUNAR_PIT_LOCATIONS.CSV" || echo "  -> download by hand from https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS into $OUT/pits/"
get "$P/LUNAR_PIT_LOCATIONS_README.TXT" "$OUT/pits/LUNAR_PIT_LOCATIONS_README.TXT" || true

echo "Done. Size on disk:"; du -sh "$OUT"/*
