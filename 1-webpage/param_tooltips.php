<?php
/**
 * param_tooltips.php - Floating tooltip controller for filter/parameter info ("i") icons.
 * Shared by dual.php and explorer.php.
 */
?>
<div id="param-tooltip" class="param-tooltip" role="tooltip" aria-hidden="true"></div>
<script>
(() => {
    const tip = document.getElementById('param-tooltip');
    if (!tip) return;
    let activeBtn = null;

    function positionTooltip(btn) {
        const rect = btn.getBoundingClientRect();
        const tipRect = tip.getBoundingClientRect();
        const margin = 10;

        let left = rect.right + 8;
        if (left + tipRect.width > window.innerWidth - margin) {
            left = Math.max(margin, rect.left - tipRect.width - 8);
        }

        let top = rect.top + rect.height / 2 - tipRect.height / 2;
        top = Math.max(margin, Math.min(window.innerHeight - tipRect.height - margin, top));

        tip.style.left = `${Math.round(left)}px`;
        tip.style.top = `${Math.round(top)}px`;
    }

    function showTooltip(btn) {
        const text = btn.getAttribute('data-tooltip');
        if (!text) return;
        activeBtn = btn;
        tip.textContent = text;
        tip.setAttribute('aria-hidden', 'false');
        tip.classList.add('visible');
        positionTooltip(btn);
    }

    function hideTooltip() {
        activeBtn = null;
        tip.classList.remove('visible');
        tip.setAttribute('aria-hidden', 'true');
    }

    document.querySelectorAll('.info-icon-btn').forEach(btn => {
        btn.addEventListener('mouseenter', () => showTooltip(btn));
        btn.addEventListener('mouseleave', hideTooltip);
        btn.addEventListener('focus', () => showTooltip(btn));
        btn.addEventListener('blur', hideTooltip);
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (activeBtn === btn) {
                hideTooltip();
            } else {
                showTooltip(btn);
            }
        });
    });

    window.addEventListener('scroll', hideTooltip, true);
    window.addEventListener('resize', () => {
        if (activeBtn) positionTooltip(activeBtn);
    });

    window.updateFilterSourceBadges = function(profile) {
        const keys = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness',
                      'soil_moisture', 'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];
        const labels = {
            measured: { text: 'measured', cls: 'measured' },
            local:    { text: 'local model', cls: 'local' },
            global:   { text: 'global model', cls: 'global' },
            none:     { text: 'no data', cls: 'none' },
        };
        const extra = (profile && profile.extra) || {};
        const raw = (profile && profile.features_raw) || {};
        const nullFeats = extra.null_features || [];
        const sources = extra.features_source || [];
        const measured = extra.features_measured || [];

        keys.forEach((k, i) => {
            const el = document.getElementById(`filter-src-${i}`);
            if (!el) return;
            const v = raw[k];
            const isNull = (v === null || v === undefined || (typeof v === 'number' && !isFinite(v)));
            let kind;
            if (isNull || nullFeats.includes(k)) {
                kind = 'none';
            } else if (labels[sources[i]]) {
                kind = sources[i];
            } else {
                kind = measured[i] === true ? 'measured' : 'global';
            }
            const info = labels[kind];
            el.className = `feat-src ${info.cls}`;
            el.textContent = info.text;
        });
    };
})();
</script>
