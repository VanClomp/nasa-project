<?php
/**
 * progress_bar.php - thin progress bar at the top of the page while API requests (/api/v1/...) are running.
 * Shared by explorer.php, dual.php and results.php. Include right after <body>, before the page's own scripts,
 * so the very first requests are covered too.
 *
 * The server does not report partial progress (each step is one request), so the bar is time-based: it moves
 * quickly at first and then ever more slowly towards 90%, and jumps to 100% and fades out when the last
 * running request finishes. Several overlapping requests keep one bar going.
 */
?>
<div class="api-progress" id="api-progress" role="progressbar" aria-label="Loading results" aria-valuemin="0"
     aria-valuemax="100" aria-valuenow="0" aria-hidden="true">
    <div class="api-progress-fill" id="api-progress-fill"></div>
    <span class="api-progress-label" id="api-progress-label"></span>
</div>
<script>
(() => {
    const bar = document.getElementById('api-progress');
    const fill = document.getElementById('api-progress-fill');
    const label = document.getElementById('api-progress-label');
    const LABELS = { characterize: 'Reading the site conditions…', search: 'Searching Earth for analogs…',
                     'error-map': 'Building the error map…' };
    let active = 0, value = 0, timer = null, hideTimer = null, started = 0;
    const pending = new Map();                 // endpoint -> number of running requests

    function set(v) {
        value = v;
        fill.style.transform = `scaleX(${v / 100})`;
        bar.setAttribute('aria-valuenow', String(Math.round(v)));
    }
    function updateLabel() {
        const running = [...pending.entries()].filter(([, n]) => n > 0).map(([e]) => e);
        const ep = running.includes('search') ? 'search' : running[running.length - 1];
        label.textContent = LABELS[ep] || 'Loading…';
    }
    function start() {
        clearTimeout(hideTimer);
        bar.classList.remove('done');
        bar.classList.add('active');
        bar.setAttribute('aria-hidden', 'false');
        if (!timer) {
            started = performance.now();
            set(Math.max(value < 100 ? value : 0, 8));
            // ease towards 90%: fast at first, then slower (half of the remaining distance every ~0.6 s)
            timer = setInterval(() => set(value + (90 - value) * 0.08), 50);
        }
    }
    function finish() {
        clearInterval(timer); timer = null;
        set(100);
        bar.classList.add('done');
        hideTimer = setTimeout(() => {
            bar.classList.remove('active', 'done');
            bar.setAttribute('aria-hidden', 'true');
            set(0);
        }, 450);
    }

    const realFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        const m = url.match(/\/api\/v1\/([a-z-]+)/);
        if (!m) return realFetch(input, init);
        const ep = m[1];
        active++; pending.set(ep, (pending.get(ep) || 0) + 1);
        updateLabel(); start();
        const done = () => {
            active = Math.max(0, active - 1); pending.set(ep, Math.max(0, (pending.get(ep) || 1) - 1));
            if (active === 0) finish(); else updateLabel();
        };
        return realFetch(input, init).then(r => { done(); return r; }, e => { done(); throw e; });
    };
})();
</script>
