"""Build the Mars cave layer used by mars_maps.nearest_cave_km() -> nearest_skylight_km.

Source: Mars Global Cave Candidate Catalog (MGC3) v1, Cushing & Okubo, USGS Astrogeology / PDS
  https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing  (mars_cave_catalog.zip)
The CSV inside the zip has a mislabelled header (its first column, called "longitude", holds the ID), so the columns
are taken by position, as documented in the PDS4 label: ID, Longitude (0-360 E), Latitude, Type_Code, Priority,
APC_Diameter (m), APC_Depth (m), Comment.

Kept (volcanic cave-entrance candidates useful for siting a base):
  * volcanic types: sky (lava-tube skylight), APC (atypical pit crater on volcano flanks / lava plains; terrestrial
    analogs at Kilauea contain cave entrances), srp (rimless collapse pit), pit, pin, crk, flr, end, rim, lat, irr
    (all from the volcanic-province surveys); dropped: kst (karst / thermokarst) and pol (polar ice) - not volcanic
  * priority 0 (already imaged by HiRISE), 1 (APC or unambiguous void/overhang) and 2 (looks like an entrance in CTX);
    dropped: priority 3 (authors expect 80-90% not to be caves)

Usage:  python prepare_mars_caves.py path/to/mars_cave_catalog.zip [out.csv]
Default output: data/geology/caves/mars_volcanic_caves.csv (the folder mars_maps reads; one CSV only).
"""
import csv, io, os, sys, zipfile

VOLCANIC = {'sky', 'APC', 'srp', 'pit', 'pin', 'crk', 'flr', 'end', 'rim', 'lat', 'irr', 'smrp'}
KEEP_PRIORITY = {'0', '1', '2'}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(zip_path, out):
    with zipfile.ZipFile(zip_path) as z:
        text = z.read('data/Mars_Cave_Catalog.csv').decode('latin-1')
    rows = list(csv.reader(io.StringIO(text)))[1:]          # skip the mislabelled header
    kept, dropped = [], {}
    for r in rows:
        if len(r) < 5: continue
        cid, lon, lat, typ, pri = (x.strip() for x in r[:5])
        dia, dep = (r[5].strip() if len(r) > 5 else ''), (r[6].strip() if len(r) > 6 else '')
        comment = ','.join(r[7:]).strip() if len(r) > 7 else ''
        if typ not in VOLCANIC or pri not in KEEP_PRIORITY:
            dropped[(typ, pri)] = dropped.get((typ, pri), 0) + 1
            continue
        kept.append(dict(id=cid, lat=float(lat), lon_east=float(lon) % 360, type=typ, priority=int(pri),
                         apc_diameter_m=dia, apc_depth_m=dep, comment=comment))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(kept[0].keys())); w.writeheader(); w.writerows(kept)
    by_type = {}
    for k in kept: by_type[k['type']] = by_type.get(k['type'], 0) + 1
    print(f'{len(rows)} candidates in catalog; kept {len(kept)} volcanic, priority 0-2 -> {out}')
    print('kept by type:', dict(sorted(by_type.items(), key=lambda x: -x[1])))
    print('dropped:', sum(dropped.values()), '(priority 3:', sum(v for (t, p), v in dropped.items() if p == '3'),
          '| non-volcanic kst/pol:', sum(v for (t, p), v in dropped.items() if t in ('kst', 'pol') and p != '3'), ')')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'data', 'geology', 'caves',
                                                                         'mars_volcanic_caves.csv'))
