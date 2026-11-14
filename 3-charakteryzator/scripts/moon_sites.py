"""Lunar sites for base-suitability characterization. Latitude deg N, longitude deg E (-180..180).

coord_quality:
  'published point'   a specific point published in a study or catalog (source given)
  'landing site'      where a mission actually landed (values from mission reports; entered by hand, ~0.01 deg)
  'region, approx'    NASA names the Artemis regions but has not published coordinates; this is an approximate
                      centre. moon_model.refine_region() replaces it with the best-lit, flat point within
                      search_km once the LOLA and illumination maps are loaded.
"""
SITES = [
    # ---- Artemis candidate landing regions (NASA, Oct 2024 list of nine) ----
    dict(id='nobile_rim_2', name='Nobile Rim 2', kind='Artemis region', lat=-84.2016, lon=60.6999, coord_quality='published point',
         source='optimal point in arXiv:2406.19863 (MCDM study of Artemis III regions)', search_km=15),
    dict(id='nobile_rim_1', name='Nobile Rim 1', kind='Artemis region', lat=-85.4564, lon=36.3607, coord_quality='published point',
         source='candidate site listed in a 2024 Artemis III region evaluation (ResearchGate 396714246)', search_km=15),
    dict(id='haworth', name='Haworth', kind='Artemis region', lat=-86.7262, lon=-21.6387, coord_quality='published point',
         source='candidate site listed in a 2024 Artemis III region evaluation (ResearchGate 396714246)', search_km=15),
    dict(id='slater_plain', name='Slater Plain', kind='Artemis region', lat=-87.4780, lon=124.5210, coord_quality='published point',
         source='landing site SP01, Wueller et al. 2026, JGR Planets, doi:10.1029/2025JE009434', search_km=15),
    dict(id='malapert_massif', name='Malapert Massif', kind='Artemis region', lat=-86.0, lon=0.0, coord_quality='region, approx',
         source='massif summit lies close to 0 deg longitude near 86 S', search_km=20),
    dict(id='de_gerlache_rim_2', name='de Gerlache Rim 2', kind='Artemis region', lat=-88.3, lon=-62.0, coord_quality='region, approx',
         source='rim of de Gerlache crater near its nearby PSR (-88.16, 305.94)', search_km=20),
    dict(id='mons_mouton', name='Mons Mouton', kind='Artemis region', lat=-84.9, lon=31.0, coord_quality='region, approx',
         source='massif formerly Leibnitz Beta, near PSR at -85.22 S', search_km=25),
    dict(id='mons_mouton_plateau', name='Mons Mouton Plateau', kind='Artemis region', lat=-84.6, lon=34.5, coord_quality='region, approx',
         source='plateau north-east of Mons Mouton', search_km=25),
    dict(id='peak_near_cabeus_b', name='Peak near Cabeus B', kind='Artemis region', lat=-82.3, lon=-54.0, coord_quality='region, approx',
         source='peak near Cabeus B crater', search_km=25),
    # ---- best-illuminated terrain (Mazarico et al. 2011, Site 1) ----
    dict(id='shackleton_ridge', name='Shackleton connecting ridge', kind='Polar illumination peak', lat=-89.45, lon=-137.3, coord_quality='region, approx',
         source='ridge between Shackleton and de Gerlache, highest average illumination at the south pole', search_km=10),
    # ---- landed missions (measured ground truth for regolith and temperature) ----
    dict(id='apollo11', name='Mare Tranquillitatis', kind='Landed (Apollo 11)', lat=0.674, lon=23.473, coord_quality='landing site', source='mission report'),
    dict(id='apollo12', name='Oceanus Procellarum', kind='Landed (Apollo 12)', lat=-3.012, lon=-23.422, coord_quality='landing site', source='mission report'),
    dict(id='apollo14', name='Fra Mauro', kind='Landed (Apollo 14)', lat=-3.645, lon=-17.471, coord_quality='landing site', source='mission report'),
    dict(id='apollo15', name='Hadley-Apennine', kind='Landed (Apollo 15)', lat=26.132, lon=3.634, coord_quality='landing site', source='mission report; heat-flow surface temperatures'),
    dict(id='apollo16', name='Descartes Highlands', kind='Landed (Apollo 16)', lat=-8.973, lon=15.500, coord_quality='landing site', source='mission report'),
    dict(id='apollo17', name='Taurus-Littrow', kind='Landed (Apollo 17)', lat=20.191, lon=30.772, coord_quality='landing site', source='mission report; heat-flow surface temperatures'),
    dict(id='change3', name='Mare Imbrium', kind="Landed (Chang'e-3)", lat=44.121, lon=-19.512, coord_quality='landing site', source='mission report'),
    dict(id='change4', name='Von Karman crater', kind="Landed (Chang'e-4, far side)", lat=-45.444, lon=177.599, coord_quality='landing site', source='mission report'),
    dict(id='change5', name='Mons Rumker region', kind="Landed (Chang'e-5)", lat=43.06, lon=-51.92, coord_quality='landing site', source='mission report'),
    dict(id='change6', name='Apollo basin', kind="Landed (Chang'e-6, far side)", lat=-41.64, lon=-153.99, coord_quality='landing site', source='mission report'),
    dict(id='chandrayaan3', name='Near Manzinus/Boguslawsky', kind='Landed (Chandrayaan-3)', lat=-69.373, lon=32.319, coord_quality='landing site', source='mission report'),
    # ---- lava-tube skylights: radiation, micrometeorite and thermal shelter ----
    dict(id='mare_tranquillitatis_pit', name='Mare Tranquillitatis Pit', kind='Lava-tube skylight', lat=8.3355, lon=33.222, coord_quality='published point',
         source='LROC Lunar Pit Atlas'),
    dict(id='marius_hills_pit', name='Marius Hills Pit', kind='Lava-tube skylight', lat=14.09, lon=-56.81, coord_quality='published point',
         source='Haruyama et al. 2009 (SELENE); refined from the LROC pit catalog once downloaded'),
    dict(id='mare_ingenii_pit', name='Mare Ingenii Pit', kind='Lava-tube skylight', lat=-35.95, lon=166.06, coord_quality='published point',
         source='LROC Lunar Pit Atlas; refined from the LROC pit catalog once downloaded'),
]
