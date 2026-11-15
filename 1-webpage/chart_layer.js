/**
 * chart_layer.js - a chart sheet that scrolls ONTO the fixed planet view (dual.php, results.php).
 *
 * The globes and the parameter bar stay where they are; the layer is a separate scroll container laid over the
 * planet stage. It starts just below the visible area and slides up over the globes when the user scrolls from the
 * parameter bar (or from the sheet itself). Wheel over a globe still zooms that globe (the layer lets those events
 * through). Below 1025 px the page already scrolls as one column, so the sheet simply sits below the bar.
 *
 * ChartLayer.create({ stage, wheelSources, sections, title, dateText })
 *   stage         element that holds the globes + parameter bar (the layer is laid over it)
 *   wheelSources  elements whose wheel / touch scroll should move the layer (the parameter bar)
 *   sections      any of 'comparison' (radar + 12-month climatogram of the chosen Earth analog) and 'time' (p(t))
 * returns { setSeries(profileWithSeries, dateText), setComparison(targetProfile, candidate), clearSeries(note) }
 */
(() => {
    const FEATURE_ORDER = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture',
                           'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];
    const TIME_LABELS = {
        temp_mean:           ['Mean ground temperature', '°C'],
        temp_diurnal_amp:    ['Diurnal temperature range', 'K'],
        dust_aerosol:        ['Atmospheric dust (AOD)', ''],
        solar_elevation_max: ['Max. noon Sun elevation', '°'],
        radiation_proxy:     ['Atmospheric shielding (column mass)', 'g/cm²'],
    };
    const SOURCE_TEXT = { measured: 'measured at this place', local: 'local model (station history)',
                          global: 'global model', none: 'no data' };
    const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    const TICK = { color: '#94a3b8', font: { size: 9 } };
    const GRID = { color: 'rgba(255,255,255,0.06)' };
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    function create(opts) {
        const stage = opts.stage;
        const sections = opts.sections || ['time'];
        stage.classList.add('has-chart-layer');

        const layer = document.createElement('div');
        layer.className = 'chart-layer';
        layer.innerHTML = `
            <div class="chart-layer-spacer">
                <div class="chart-layer-handle"><button type="button" class="chart-layer-hint" data-role="handle-btn">Charts <span aria-hidden="true">↑</span></button></div>
            </div>
            <div class="chart-sheet" role="region" aria-label="Charts">
                <div class="chart-sheet-head">
                    <span class="chart-sheet-grip" aria-hidden="true"></span>
                    <span class="section-label" style="margin:0;">${esc(opts.title || 'Charts')}</span>
                    <button type="button" class="chart-sheet-close" aria-label="Back to the planet view">↓ Back to globes</button>
                </div>
                ${sections.includes('comparison') ? `
                <div class="chart-sheet-section">
                    <div class="chart-sheet-grid two">
                        <div class="chart-card">
                            <h4 class="time-chart-title">Feature profile comparison</h4>
                            <span class="time-chart-meta" data-role="cmp-meta">target vs. chosen Earth analog · normalised 0–1</span>
                            <div class="chart-wrap"><canvas data-role="radar" height="230"></canvas></div>
                        </div>
                        <div class="chart-card">
                            <h4 class="time-chart-title">12-month climatogram</h4>
                            <span class="time-chart-meta" data-role="clim-meta">chosen Earth analog</span>
                            <div class="chart-wrap"><canvas data-role="climatogram" height="230"></canvas></div>
                        </div>
                    </div>
                </div>` : ''}
                ${sections.includes('time') ? `
                <div class="chart-sheet-section">
                    <span class="section-label">Chosen site · parameters that change over time</span>
                    <p class="time-charts-note" data-role="time-note">Loading…</p>
                    <div class="chart-sheet-grid three" data-role="time-list"></div>
                </div>` : ''}
            </div>`;
        stage.appendChild(layer);
        const sheet = layer.querySelector('.chart-sheet');
        const $ = role => layer.querySelector(`[data-role="${role}"]`);

        // ------------------------------------------------------------------ scrolling
        const stacked = () => window.matchMedia('(max-width: 1024px)').matches;
        function forwardWheel(e) {
            if (stacked() || e.ctrlKey) return;              // ctrl+wheel = browser zoom
            const max = layer.scrollHeight - layer.clientHeight;
            const next = Math.max(0, Math.min(max, layer.scrollTop + e.deltaY * (e.deltaMode === 1 ? 32 : 1)));
            if (next === layer.scrollTop) return;
            e.preventDefault();
            layer.scrollTop = next;
        }
        let touchY = null;
        (opts.wheelSources || []).forEach(el => {
            if (!el) return;
            el.addEventListener('wheel', forwardWheel, { passive: false });
            el.addEventListener('touchstart', e => { touchY = e.touches[0].clientY; }, { passive: true });
            el.addEventListener('touchmove', e => {
                if (touchY === null || stacked()) return;
                const y = e.touches[0].clientY;
                layer.scrollTop += touchY - y; touchY = y;
                e.preventDefault();
            }, { passive: false });
            el.addEventListener('touchend', () => { touchY = null; });
        });
        const covered = () => layer.scrollTop > 4;
        layer.addEventListener('scroll', () => stage.classList.toggle('chart-layer-open', covered()), { passive: true });
        layer.querySelector('.chart-sheet-close').addEventListener('click', () => layer.scrollTo({ top: 0, behavior: 'smooth' }));
        function open() { layer.scrollTo({ top: layer.scrollHeight, behavior: 'smooth' }); }
        // bottom-edge handle (shown by CSS where there is no parameter bar, e.g. dual.php's weights view); wheel over
        // it scrolls the layer directly because it lives inside the layer
        $('handle-btn').addEventListener('click', e => { e.stopPropagation(); open(); });

        // a small "charts below" hint in the parameter bar
        if (opts.hintHost) {
            const hint = document.createElement('button');
            hint.type = 'button'; hint.className = 'chart-layer-hint';
            hint.innerHTML = 'Charts <span aria-hidden="true">↑</span>';
            hint.title = 'Scroll here (or click) to bring up the charts';
            hint.addEventListener('click', e => { e.stopPropagation(); open(); });
            opts.hintHost.appendChild(hint);
        }

        // ------------------------------------------------------------------ comparison charts
        let radar = null, clim = null;
        function initComparison() {
            if (radar || !sections.includes('comparison') || typeof Chart === 'undefined') return;
            radar = new Chart($('radar').getContext('2d'), {
                type: 'radar',
                data: { labels: ['Temp', 'Range', 'Inertia', 'Roughness', 'Ice/Water', 'Dust AOD', 'Sun angle', 'Radiation', 'Slope'],
                        datasets: [
                            { label: 'Target (Moon/Mars)', data: Array(9).fill(0), borderColor: '#60A5FA', backgroundColor: 'rgba(96, 165, 250, 0.16)', borderWidth: 2 },
                            { label: 'Earth analog', data: Array(9).fill(0), borderColor: '#10B981', backgroundColor: 'rgba(16, 185, 129, 0.16)', borderWidth: 2 }] },
                options: { responsive: true, maintainAspectRatio: false, animation: false,
                           plugins: { legend: { labels: { color: '#cbd5e1', font: { size: 10 } } } },
                           scales: { r: { min: 0, max: 1, grid: { color: 'rgba(255,255,255,0.08)' }, angleLines: { color: 'rgba(255,255,255,0.08)' },
                                          pointLabels: { color: '#94a3b8', font: { size: 9 } }, ticks: { display: false } } } }
            });
            clim = new Chart($('climatogram').getContext('2d'), {
                type: 'line',
                data: { labels: MONTHS, datasets: [
                    { label: 'Mean temp. (°C)', data: [], borderColor: '#F97316', backgroundColor: 'rgba(249, 115, 22, 0.15)', tension: 0.35, fill: true },
                    { label: 'Moisture (%)', data: [], borderColor: '#60A5FA', tension: 0.35 }] },
                options: { responsive: true, maintainAspectRatio: false, animation: false,
                           plugins: { legend: { labels: { color: '#cbd5e1', font: { size: 10 } } } },
                           scales: { x: { ticks: TICK, grid: { display: false } }, y: { ticks: TICK, grid: GRID } } }
            });
        }
        function setComparison(target, cand) {
            if (!sections.includes('comparison')) return;
            initComparison();
            if (!radar || !target || !cand) return;
            radar.data.datasets[0].data = (target.features_norm || []).map(v => v ?? 0);
            radar.data.datasets[1].data = (cand.features_norm || []).map(v => v ?? 0);
            radar.update('none');
            const where = cand.name_hint && !/^Land location/.test(cand.name_hint) ? `${cand.name_hint} · ` : '';   // generic hint repeats the coordinates
            $('cmp-meta').innerText = `target vs. Earth analog #${cand.rank ?? ''} (${where}${(+cand.lat).toFixed(1)}°, ${(+cand.lon).toFixed(1)}°) · normalised 0–1`;
            $('clim-meta').innerText = `Earth analog #${cand.rank ?? ''} · ${where}${(+cand.lat).toFixed(1)}°, ${(+cand.lon).toFixed(1)}°`;
            if (cand.climatogram_12m) {
                clim.data.datasets[0].data = cand.climatogram_12m.temp_mean;
                clim.data.datasets[1].data = cand.climatogram_12m.soil_moisture;
                clim.update('none');
            }
        }

        // ------------------------------------------------------------------ p(t) charts
        let timeCharts = [];
        function clearSeries(note) {
            if (!sections.includes('time')) return;
            timeCharts.forEach(c => c.destroy()); timeCharts = [];
            $('time-list').innerHTML = '';
            $('time-note').innerText = note || 'Loading…';
        }
        function setSeries(profile, dateText) {
            if (!sections.includes('time') || typeof Chart === 'undefined') return;
            clearSeries();
            const s = profile && profile.extra && profile.extra.series;
            if (!s || !Object.keys(s.values || {}).length) { $('time-note').innerText = 'No time series for this place.'; return; }
            const isMars = s.axis === 'mars_month';
            const accent = isMars ? '#F97316' : '#60A5FA';
            $('time-note').innerText = isMars
                ? `Time axis: the 12 Mars months of the landing year, labelled with the Earth month in which each begins (a Mars month lasts about 1.5–2 Earth months). Highlighted point = landing date ${dateText || ''}.`
                : `Time axis: the 15th of each month of ${String(dateText || '').slice(0, 4)}. Highlighted point = landing month.`;
            const src = profile.extra.features_source || [];
            const meas = profile.extra.features_measured || [];
            Object.entries(s.values).forEach(([key, values]) => {
                const [label, unit] = TIME_LABELS[key] || [key, ''];
                const i = FEATURE_ORDER.indexOf(key);
                const basis = src[i] || (meas[i] === true ? 'measured' : 'global');
                const block = document.createElement('div');
                block.className = 'chart-card';
                block.innerHTML = `<h4 class="time-chart-title">${esc(label)} – change over time</h4>
                    <span class="time-chart-meta">${unit ? esc(unit) + ' · ' : ''}${SOURCE_TEXT[basis] || basis}</span>
                    <div class="chart-wrap"><canvas height="150"></canvas></div>`;
                $('time-list').appendChild(block);
                const cur = s.current_index;
                timeCharts.push(new Chart(block.querySelector('canvas').getContext('2d'), {
                    type: 'line',
                    data: { labels: s.labels, datasets: [{
                        label, data: values, borderColor: accent, backgroundColor: accent + '22', fill: true, tension: 0.35, borderWidth: 1.5,
                        pointRadius: values.map((_, j) => j === cur ? 4.5 : 1.5),
                        pointBackgroundColor: values.map((_, j) => j === cur ? '#F4F4F6' : accent), pointBorderColor: accent }] },
                    options: { responsive: true, maintainAspectRatio: false, animation: false,
                        plugins: { legend: { display: false },
                                   tooltip: { callbacks: {
                                       title: items => (s.detail_labels || s.labels)[items[0].dataIndex],
                                       label: c => `${c.formattedValue}${unit ? ' ' + unit : ''}${c.dataIndex === cur ? ' (landing date)' : ''}` } } },
                        scales: { x: { ticks: { ...TICK, font: { size: 8 }, maxRotation: 0, autoSkip: true,
                                                callback: function (v) { const [m, y] = this.getLabelForValue(v).split(' '); return y ? `${m} '${String(y).slice(2)}` : m; } },
                                       grid: { display: false } },
                                  y: { ticks: TICK, grid: GRID } } }
                }));
            });
        }

        return { setSeries, setComparison, clearSeries, open, layer };
    }

    window.ChartLayer = { create };
})();
