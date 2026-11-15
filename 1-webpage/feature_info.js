/**
 * feature_info.js - the target-profile readout shared by explorer.php and results.php:
 *   - writes the nine parameter values ("no data" where the value is missing),
 *   - the per-parameter tags: data source (measured / local model / global model / no data) and date dependence,
 *   - the model badge (local / global),
 *   - an info box for each parameter: what it measures, what its source tag means for this place and where the value
 *     comes from. Opens on hover (mouse) or tap/click (touch), closes on tap elsewhere, Escape or mouse leave.
 *
 * Data: 3-charakteryzator /characterize -> extra.features_source, extra.features_detail, extra.features_time_varying,
 * extra.model, extra.model_basis. Older responses (only extra.features_measured) still work.
 */
(() => {
    const FEATURE_KEYS = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture',
                          'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];

    // What each parameter measures (body-specific text where the meaning differs)
    const FEATURE_INFO = {
        temp_mean: { name: 'Mean surface temperature', unit: '°C',
            what: 'Average ground-surface temperature over one full day at this place on the chosen date (a 24.6 h sol on Mars, a 29.5-day lunar day on the Moon).' },
        temp_diurnal_amp: { name: 'Diurnal temperature range', unit: '°C',
            what: 'Difference between the warmest and the coldest ground temperature in one day. Large swings stress equipment, materials and habitats.' },
        thermal_inertia: { name: 'Thermal inertia', unit: 'TIU',
            what: 'How strongly the ground resists changing temperature (J m⁻² K⁻¹ s⁻½). Low = fine dust or sand that heats and cools quickly; high = rock, bedrock or cemented ground.' },
        surface_roughness: { name: 'Surface roughness', unit: 'm',
            what: 'Local relief: the spread (standard deviation) of the ground height over about 13 km after removing the overall tilt, from laser altimetry. Higher = more rugged, hilly terrain.' },
        soil_moisture: { name: 'Ground water / ice', unit: '%',
            what: { mars: 'Water-equivalent hydrogen in the top few tens of centimetres (weight %), from the Mars Odyssey gamma-ray spectrometer; mostly ground ice or water bound in minerals. Very coarse: 5° × 5° cells (about 300 km).',
                    moon: 'Water in the lunar regolith has no defensible percentage from orbit; the polar ice maps (ice depth, hydrogen index) describe it instead.' } },
        dust_aerosol: { name: 'Atmospheric dust', unit: 'optical depth',
            what: { mars: 'Dust optical depth: how much airborne dust dims the sunlight (about 0.3 = clear Mars sky, above 1 = dusty, global storms 3 or more). Depends on the season.',
                    moon: 'The Moon has no atmosphere, so there is no airborne dust to dim the sunlight (always 0).' } },
        solar_elevation_max: { name: 'Max. Sun elevation', unit: '°',
            what: 'How high the Sun gets above a flat horizon at local noon on the chosen date (0° = it never rises, 90° = straight overhead). Sets the available solar power and heating.' },
        radiation_proxy: { name: 'Radiation shielding', unit: 'g/cm²',
            what: { mars: 'Mass of atmosphere above the ground that shields it from cosmic and solar radiation, in g/cm² (Earth at sea level: about 1033). Lower = more radiation reaches the surface. Follows the seasonal pressure cycle.',
                    moon: 'The Moon has no atmosphere: 0 g/cm² of shielding, so the surface is fully exposed to cosmic and solar radiation.' } },
        slope_deg: { name: 'Terrain slope', unit: '°',
            what: 'Steepest slope of the ground measured by the laser altimeter (over about 1.85 km on Mars, tens of metres on the Moon). Steep ground is unsafe for landing and building.' },
    };

    // What each source tag means
    const SOURCE_INFO = {
        measured: { tag: 'measured', cls: 'measured',
            text: 'Read directly at this exact place: a satellite map pixel (laser altimeter, thermal or neutron spectrometer), exact orbital geometry, or a physical fact such as the Moon having no atmosphere. The most reliable kind of value.' },
        local: { tag: 'local model', cls: 'local',
            text: "Forecast for this date by the local model: a seasonal curve fitted only to this landing site's own weather-station records from past years. More trustworthy than the global model (typically within a few degrees)." },
        global: { tag: 'global model', cls: 'global',
            text: { mars: 'Approximation from the global model: physics (surface energy balance, seasonal pressure and dust climate) calibrated on all stations and applied from latitude, elevation and satellite maps. Used where this place has no station records for the season, so less certain (temperatures about ±5–7 °C).',
                    moon: 'Approximation from the global model: the standard lunar regolith model (Diviner-based, Hayne et al. 2017) applied from latitude, date and satellite maps. The Moon has no surface station records to build a local model from, so this is less certain than a measurement.' } },
        none: { tag: 'no data', cls: 'none',
            text: 'No measurement at this place and no defensible estimate. The Earth search ignores this parameter here.' },
    };
    const TIME_INFO = {
        true:  { tag: '◷ by date', cls: 'varies', text: 'Changes with the landing date (season, Sun position, dust season).' },
        false: { tag: 'fixed', cls: 'fixed', text: 'A fixed property of the place: the landing date does not change it.' },
    };
    const MODEL_LABELS = {
        local:   { text: 'Local model · station history', cls: 'local',
                   info: "This place is a landing site with a weather station: values that change with the date are forecast from that station's own past records." },
        global:  { text: 'Global model · uncertain', cls: 'global',
                   info: 'No station records cover this place and season: values that change with the date come from the global model, an approximation.' },
        orbital: { text: 'Orbital measurements · this point', cls: 'orbital', info: '' },   // older API responses
    };

    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const isNull = v => v === null || v === undefined || (typeof v === 'number' && !isFinite(v));

    function sourceOf(extra, raw, k, i) {
        if (isNull(raw[k]) || (extra.null_features || []).includes(k)) return 'none';
        const s = (extra.features_source || [])[i];
        if (SOURCE_INFO[s]) return s;
        return (extra.features_measured || [])[i] === true ? 'measured' : 'global';
    }

    // ------------------------------------------------------------------ info box
    let box = null, openFor = null, pinned = false;
    function ensureBox() {
        if (box) return box;
        box = document.createElement('div');
        box.className = 'feat-info'; box.id = 'feat-info'; box.setAttribute('role', 'tooltip'); box.hidden = true;
        document.body.appendChild(box);
        return box;
    }
    function place(anchor) {
        const r = anchor.getBoundingClientRect(), b = box.getBoundingClientRect(), m = 8;
        let left = Math.min(Math.max(m, r.left + r.width / 2 - b.width / 2), window.innerWidth - b.width - m);
        let top = r.bottom + 6;
        if (top + b.height > window.innerHeight - m && r.top - b.height - 6 > m) top = r.top - b.height - 6;
        box.style.left = `${Math.round(left)}px`; box.style.top = `${Math.round(Math.max(m, top))}px`;
    }
    function show(anchor, pin) {
        const html = anchor._featInfo && anchor._featInfo();
        if (!html) return;
        ensureBox(); box.innerHTML = html; box.hidden = false;
        openFor = anchor; pinned = !!pin;
        anchor.setAttribute('aria-describedby', 'feat-info'); anchor.setAttribute('aria-expanded', 'true');
        place(anchor);
    }
    function hide() {
        if (!box || box.hidden) return;
        box.hidden = true;
        if (openFor) { openFor.removeAttribute('aria-describedby'); openFor.setAttribute('aria-expanded', 'false'); }
        openFor = null; pinned = false;
    }
    const canHover = () => window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    function attach(anchor, contentFn) {
        anchor._featInfo = contentFn;
        if (anchor._featBound) return;
        anchor._featBound = true;
        anchor.classList.add('has-info');
        anchor.tabIndex = 0;
        anchor.setAttribute('role', 'button');
        anchor.setAttribute('aria-expanded', 'false');
        anchor.addEventListener('mouseenter', () => { if (canHover() && !pinned) show(anchor, false); });
        anchor.addEventListener('mouseleave', () => { if (canHover() && !pinned && openFor === anchor) hide(); });
        anchor.addEventListener('click', e => {
            e.stopPropagation();
            if (openFor === anchor && (pinned || !canHover())) hide(); else show(anchor, true);
        });
        anchor.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFor === anchor ? hide() : show(anchor, true); }
        });
        anchor.addEventListener('focus', () => { if (!openFor) show(anchor, false); });
        anchor.addEventListener('blur', () => { if (openFor === anchor && !pinned) hide(); });
    }
    document.addEventListener('click', e => { if (box && !box.contains(e.target)) hide(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
    window.addEventListener('resize', hide);
    window.addEventListener('scroll', () => { if (openFor && box && !box.hidden) place(openFor); }, true);

    // ------------------------------------------------------------------ rendering
    function fmt(v, unit) { return isNull(v) ? 'no data' : (unit ? `${v} ${unit}` : String(v)); }

    function renderFeatureFlags(profile) {
        const extra = (profile && profile.extra) || {};
        const raw = (profile && profile.features_raw) || {};
        const body = profile && profile.target_body === 'moon' ? 'moon' : 'mars';
        const tv = extra.features_time_varying || [];
        const detail = extra.features_detail || [];
        FEATURE_KEYS.forEach((k, i) => {
            const valueEl = document.getElementById(`raw-${k}`);
            if (!valueEl) return;
            const rb = valueEl.parentElement;
            let flags = rb.querySelector('.feat-flags');
            if (!flags) { flags = document.createElement('span'); flags.className = 'feat-flags'; rb.appendChild(flags); }
            const src = SOURCE_INFO[sourceOf(extra, raw, k, i)];
            const time = TIME_INFO[tv[i]];
            flags.innerHTML = `<i class="feat-src ${src.cls}">${src.tag}</i>` + (time ? `<i class="feat-time ${time.cls}">${time.tag}</i>` : '');
            const fi = FEATURE_INFO[k];
            const what = typeof fi.what === 'string' ? fi.what : fi.what[body];
            attach(rb, () => {
                const s = SOURCE_INFO[sourceOf(extra, raw, k, i)];
                const t = TIME_INFO[tv[i]];
                const d = s.cls !== 'none' || detail[i] ? detail[i] : '';
                return `<strong class="feat-info-title">${esc(fi.name)}</strong>` +
                       `<p>${esc(what)}</p>` +
                       `<p><i class="feat-src ${s.cls}">${s.tag}</i> ${esc(typeof s.text === 'string' ? s.text : s.text[body])}</p>` +
                       (d ? `<p class="feat-info-src">Source here: ${esc(d)}</p>` : '') +
                       (t ? `<p><i class="feat-time ${t.cls}">${t.tag}</i> ${esc(t.text)}</p>` : '');
            });
        });
    }

    function renderModelBadge(profile) {
        const extra = (profile && profile.extra) || {};
        const key = MODEL_LABELS[extra.model] ? extra.model : 'global';
        const m = MODEL_LABELS[key];
        // the bar's badge and, on dual.php, the copy in the sidebar
        [document.getElementById('model-badge'), document.getElementById('side-model-badge')].forEach(badge => {
            if (!badge) return;
            ['local', 'orbital', 'global'].forEach(c => badge.classList.toggle(c, c === m.cls));
            badge.innerText = m.text;
            badge.removeAttribute('title');
            attach(badge, () => `<strong class="feat-info-title">${esc(m.text)}</strong><p>${esc(m.info)}</p>` +
                                 (extra.model_basis ? `<p class="feat-info-src">Here: ${esc(extra.model_basis)}</p>` : ''));
        });
    }

    // dual.php: the same values in the weights sidebar, one per slider row ([data-side-value="key"]), always visible
    const SIDE_UNITS = { temp_mean: '°C', temp_diurnal_amp: '°C', thermal_inertia: 'TIU', surface_roughness: 'm',
                         soil_moisture: '%', dust_aerosol: '', solar_elevation_max: '°', radiation_proxy: 'g/cm²', slope_deg: '°' };
    function renderSideValues(profile) {
        const r = (profile && profile.features_raw) || {};
        const extra = (profile && profile.extra) || {};
        const tv = extra.features_time_varying || [];
        FEATURE_KEYS.forEach((k, i) => {
            const el = document.querySelector(`[data-side-value="${k}"]`);
            if (!el) return;
            const missing = isNull(r[k]) || (extra.null_features || []).includes(k);
            el.innerHTML = `<strong class="${missing ? 'is-missing' : ''}">${esc(missing ? 'no data' : fmt(r[k], SIDE_UNITS[k]))}</strong>` +
                           (tv[i] === true ? '<span class="side-value-time">◷ by date</span>' : (tv[i] === false ? '<span class="side-value-time">fixed</span>' : ''));
        });
        const s = extra.season || null;
        const season = document.getElementById('side-season');
        if (season) season.innerText = s && s.ls !== undefined ? `Ls ${Number(s.ls).toFixed(0)}° · Mars year ${s.mars_year}`
                                     : (s && s.local_lunar_hour !== undefined ? `lunar hour ${Number(s.local_lunar_hour).toFixed(1)}` : '');
        const sky = document.getElementById('side-skylight');
        if (sky) sky.innerText = `Nearest cave: ${fmt(profile.nearest_skylight_km, 'km')}`;
    }

    function renderTargetProfileReadout(profile) {
        const r = profile.features_raw || {};
        const set = (k, txt) => { const el = document.getElementById(`raw-${k}`); if (el) el.innerText = txt; };
        set('temp_mean', fmt(r.temp_mean, '°C'));
        set('temp_diurnal_amp', fmt(r.temp_diurnal_amp, '°C'));
        set('thermal_inertia', fmt(r.thermal_inertia, 'TIU'));
        set('surface_roughness', fmt(r.surface_roughness));
        set('soil_moisture', fmt(r.soil_moisture, '%'));
        set('dust_aerosol', fmt(r.dust_aerosol));
        set('solar_elevation_max', fmt(r.solar_elevation_max, '°'));
        set('radiation_proxy', fmt(r.radiation_proxy));
        set('slope_deg', fmt(r.slope_deg, '°'));
        const sky = document.getElementById('readout-skylight');
        if (sky) sky.innerText = `Nearest cave: ${fmt(profile.nearest_skylight_km, 'km')}`;
        hide();
        renderModelBadge(profile);
        if (typeof window.renderSeason === 'function') window.renderSeason(profile);
        renderFeatureFlags(profile);
        renderSideValues(profile);
    }

    Object.assign(window, { FEATURE_KEYS, FEATURE_INFO, SOURCE_INFO, renderFeatureFlags, renderModelBadge, renderTargetProfileReadout, renderSideValues });
})();
