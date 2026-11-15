<?php
/**
 * site_picker.php - okno wyboru miejsca lądowania (Księżyc / Mars), wspólne dla explorer.php i dual.php.
 * Lista pochodzi z presets.php (generowany z danych 3-charakteryzatora: regiony Artemis III, lądowiska, kandydaci).
 * Wymaga na stronie: const PRESETS, let currentBody, pól #input-lat / #input-lon i funkcji selectPreset(lat, lon, el).
 * Dołączać PO głównym <script> strony.
 */
?>
<div class="site-picker-overlay" id="site-picker" hidden>
    <div class="site-picker" role="dialog" aria-modal="true" aria-labelledby="site-picker-title">
        <div class="site-picker-head">
            <div>
                <span class="section-label" style="margin:0;">Miejsce lądowania</span>
                <h2 id="site-picker-title">Wybierz miejsce</h2>
            </div>
            <button type="button" class="site-picker-close" aria-label="Zamknij" onclick="SitePicker.close()">✕</button>
        </div>
        <input type="search" id="site-picker-search" class="site-picker-search" autocomplete="off"
               placeholder="Szukaj: Malapert, Apollo 15, Jezero…" aria-label="Szukaj miejsca">
        <div class="site-picker-list" id="site-picker-list" role="listbox" aria-labelledby="site-picker-title"></div>
        <div class="site-picker-foot">Możesz też kliknąć dowolny punkt na globusie albo wpisać współrzędne.</div>
    </div>
</div>
<script>
const SitePicker = (() => {
    const overlay = document.getElementById('site-picker');
    const listEl = document.getElementById('site-picker-list');
    const search = document.getElementById('site-picker-search');
    const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const fmt = v => (Math.round(v * 100) / 100).toFixed(2);

    function current() {
        const lat = parseFloat(document.getElementById('input-lat').value);
        const lon = parseFloat(document.getElementById('input-lon').value);
        const list = PRESETS[currentBody] || [];
        // the same preset if within ~0.05 deg (inputs are rounded to 0.1 when a globe point is clicked)
        const hit = list.find(p => Math.abs(p.lat - lat) < 0.06 && Math.abs(((p.lon - lon + 540) % 360) - 180) < 0.06);
        return { lat, lon, preset: hit || null };
    }

    function sync() {
        const c = current();
        const nameEl = document.getElementById('site-picker-current');
        const metaEl = document.getElementById('site-picker-coords');
        if (!nameEl) return;
        nameEl.innerText = c.preset ? c.preset.name : 'Własny punkt';
        metaEl.innerText = c.preset ? `${c.preset.desc} · ${fmt(c.lat)}°, ${fmt(c.lon)}°`
                                    : `${isFinite(c.lat) ? fmt(c.lat) : '--'}°, ${isFinite(c.lon) ? fmt(c.lon) : '--'}°`;
    }

    function render() {
        const q = search.value.trim().toLowerCase();
        const cur = current().preset;
        let html = '', group = null, n = 0;
        (PRESETS[currentBody] || []).forEach((p, i) => {
            if (q && !(`${p.name} ${p.desc} ${p.group}`.toLowerCase().includes(q))) return;
            if (p.group !== group) { group = p.group; html += `<div class="site-picker-group">${esc(group)}</div>`; }
            n++;
            html += `<button type="button" role="option" class="site-picker-item${cur && cur.id === p.id ? ' active' : ''}"
                        aria-selected="${cur && cur.id === p.id}" data-i="${i}">
                        <span class="site-picker-item-main"><strong>${esc(p.name)}</strong><span>${esc(p.desc)}</span></span>
                        <span class="site-picker-item-side">${p.local ? '<em class="site-picker-tag">dane stacji</em>' : ''}
                        <code>${fmt(p.lat)}°, ${fmt(p.lon)}°</code></span>
                    </button>`;
        });
        listEl.innerHTML = n ? html : '<div class="site-picker-empty">Brak wyników</div>';
    }

    function choose(i) {
        const p = PRESETS[currentBody][i];
        close();
        selectPreset(p.lat, p.lon, null);
    }

    function open() {
        search.value = '';
        render();
        overlay.hidden = false;
        void overlay.offsetWidth;            // apply the closed state first, then fade in (no rAF: throttled in some tabs)
        overlay.classList.add('open');
        const active = listEl.querySelector('.site-picker-item.active');
        if (active) active.scrollIntoView({ block: 'center' });
        search.focus();
    }

    function close() {
        overlay.classList.remove('open');
        overlay.hidden = true;
        // return focus after the current key event has finished, so the same Enter/Space doesn't re-open the window
        const btn = document.getElementById('site-picker-btn');
        if (btn) setTimeout(() => btn.focus(), 0);
    }

    listEl.addEventListener('click', e => {
        const b = e.target.closest('.site-picker-item');
        if (b) choose(parseInt(b.dataset.i, 10));
    });
    search.addEventListener('input', render);
    search.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown') { e.preventDefault(); const f = listEl.querySelector('.site-picker-item'); if (f) f.focus(); }
        if (e.key === 'Enter') { e.preventDefault(); const f = listEl.querySelector('.site-picker-item'); if (f) f.click(); }
    });
    listEl.addEventListener('keydown', e => {
        const items = [...listEl.querySelectorAll('.site-picker-item')];
        const k = items.indexOf(document.activeElement);
        if (e.key === 'ArrowDown' && k < items.length - 1) { e.preventDefault(); items[k + 1].focus(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); (k > 0 ? items[k - 1] : search).focus(); }
    });
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !overlay.hidden) close(); });

    // keep the button label in step with the coordinates (preset, globe click, typed values, body switch)
    ['input-lat', 'input-lon'].forEach(id => document.getElementById(id).addEventListener('input', sync));
    for (const fn of ['triggerCharacterize', 'triggerCharacterizeAndSearch', 'switchCelestialBody']) {
        if (typeof window[fn] === 'function') {
            const orig = window[fn];
            window[fn] = function () { const r = orig.apply(this, arguments); sync(); return r; };
        }
    }
    sync();
    return { open, close, sync };
})();
</script>
