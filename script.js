// script.js — stable UI (no public debug), previous aesthetic preserved
// Works with your existing HTML/CSS structure and IDs/classes.

// ---------------------- UTILITIES ----------------------
document.addEventListener('DOMContentLoaded', () => {
  const qs  = (sel, root=document) => root.querySelector(sel);
  const qsa = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const bust = () => Date.now();

  const urls = {
    gti:    () => `./data/gti.json?t=${bust()}`,
    cat:    () => `./data/categories.json?t=${bust()}`,
    src:    () => `./data/sources.json?t=${bust()}`,
    evt:    () => `./data/events.json?t=${bust()}`,
    sum:    () => `./data/summaries.json?t=${bust()}`,
    status: () => `./data/status.json?t=${bust()}`
  };

  const clampNum = (v, d=0) => (typeof v === 'number' && isFinite(v)) ? v : d;
  const fmtN = (v, dec=2) => (typeof v === 'number' && isFinite(v)) ? v.toFixed(dec) : '0.00';
  const humanAgo = (ms) => {
    const s = Math.floor(ms/1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s/60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m/60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h/24);
    return `${d}d ago`;
  };
  const cssVar = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();

  async function getJSON(url) {
    try {
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
      return await r.json();
    } catch (e) {
      console.warn('getJSON failed:', e.message || e, url);
      return null;
    }
  }

  // ---------------------- ELEMENTS ----------------------
  // Header (legacy spans retained)
  const elUpdated = qs('#updated');
  const elCY      = qs('#current-year');
  const elCV      = qs('#current-gti');

  // KPI cards
  const kpiYear   = qs('#kpi-year');
  const kpiGTI    = qs('#kpi-gti');
  const kpiUpd    = qs('#kpi-updated');
  const kpiDelta  = qs('#kpi-delta');

  // Controls
  const selColor  = qs('#line-color');
  const selWeight = qs('#line-weight');
  const chkDark   = qs('#dark-mode');
  const selRange  = qs('#range-select');
  const btnPNG    = qs('#btn-png');
  const btnCSV    = qs('#btn-csv');

  // LIVE strip
  const liveAgo   = qs('#live-ago');
  const autoRF    = qs('#auto-refresh');

  // Signals
  const signalsList = qs('#signals-list');
  const signalsFoot = qs('#signals-foot');

  // Tabs
  const tabs      = qsa('.tab');
  const panels    = qsa('.tabpanel');

  // Year summary bubble
  const ys = {
    panel: qs('#year-summary'),
    close: qs('#ys-close'),
    year:  qs('#ys-year'),
    gti:   qs('#ys-gti'),
    hover: qs('#ys-hover'),
    ai:    qs('#ys-ai')
  };
  let ysTimer = null;

  // Private dev overlay (only if ?dev=1 AND Shift+D)
  const devEnabled = new URLSearchParams(location.search).get('dev') === '1';
  let devBox = null;
  function showDev(data) {
    if (!devEnabled) return;
    if (!devBox) {
      devBox = document.createElement('div');
      devBox.style.cssText = 'position:fixed;bottom:16px;left:16px;max-width:70ch;z-index:9999;background:#111827;color:#e5e7eb;border:1px solid #374151;border-radius:8px;padding:10px;display:none;white-space:pre-wrap;font-size:12px;';
      document.body.appendChild(devBox);
    }
    devBox.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    devBox.style.display = 'block';
  }
  function hideDev(){ if (devBox) devBox.style.display = 'none'; }
  document.addEventListener('keydown', (e) => {
    if (devEnabled && e.key.toLowerCase() === 'd' && e.shiftKey) {
      if (devBox && devBox.style.display === 'block') hideDev();
      else showDev({hint:'Private debug', time:new Date().toISOString()});
    }
  });

  // ---------------------- STATE ----------------------
  let GTI_SERIES = [];
  let EVENTS = {};
  let SUMMARIES = {};
  let lastStatusISO = null;

  // ---------------------- TABS ----------------------
  tabs.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const tgt = qs('#tab-' + btn.dataset.tab);
      if (!tgt) return;
      tabs.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      tgt.classList.add('active');
      if (btn.dataset.tab === 'overview' && window.Plotly) {
        try { Plotly.Plots.resize('chart-plot'); } catch {}
      }
    }, { passive: true });
  });

  // ---------------------- PREFERENCES ----------------------
  const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
  if (typeof prefs.darkMode === 'undefined') {
    const mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    prefs.darkMode = mq ? mq.matches : false;
  }
  document.body.classList.toggle('dark', !!prefs.darkMode);
  if (chkDark) chkDark.checked = !!prefs.darkMode;

  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (selRange)  selRange.value  = prefs.range || 'all';

  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }

  chkDark?.addEventListener('change', () => {
    prefs.darkMode = chkDark.checked;
    document.body.classList.toggle('dark', !!prefs.darkMode);
    savePrefs();
    try { Plotly.Plots.resize('chart-plot'); } catch {}
  });
  selColor?.addEventListener('change', () => { prefs.lineColor = selColor.value; savePrefs(); plotLine(); });
  selWeight?.addEventListener('change', () => { prefs.lineWeight = Number(selWeight.value); savePrefs(); plotLine(); });
  selRange?.addEventListener('change', () => { prefs.range = selRange.value; savePrefs(); plotLine(); });

  // ---------------------- PLOT ----------------------
  function computeRange(years) {
    const pick = (selRange && selRange.value) || 'all';
    if (!years || !years.length) return undefined;
    const maxYear = years[years.length - 1];
    if (pick === 'decade') return [maxYear - 9, maxYear];
    if (pick === '20y')    return [maxYear - 19, maxYear];
    if (pick === '5y')     return [maxYear - 4, maxYear];
    return undefined;
  }

  function plotLine() {
    const el = qs('#chart-plot');
    if (!el) return;

    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) {
      el.innerHTML = '<div class="warn">No GTI data found.</div>';
      return;
    } else {
      el.innerHTML = '';
    }

    const years = GTI_SERIES.map(d => d.year);
    const vals  = GTI_SERIES.map(d => d.gti);
    const lastYear = years[years.length - 1];
    const lastVal  = vals[vals.length - 1];

    elCY && (elCY.textContent = String(lastYear));
    elCV && (elCV.textContent = String(Math.round(lastVal)));
    kpiYear && (kpiYear.textContent = String(lastYear));
    kpiGTI  && (kpiGTI.textContent  = String(Math.round(lastVal)));

    const colorMap = { blue:'#2563eb', green:'#059669', purple:'#7c3aed', orange:'#ea580c', red:'#dc2626' };
    const useColor = (prefs.lineColor && prefs.lineColor !== 'auto') ? colorMap[prefs.lineColor] : undefined;
    const useWidth = Number(prefs.lineWeight || 3);

    // Annotations (stay the same as before)
    const anno = { 1918:'1918: Flu Pandemic', 1945:'1945: WWII Ends', 2008:'2008: Financial Crisis', 2020:'2020: COVID-19' };
    const annotations = Object.keys(anno)
      .map(k => parseInt(k, 10))
      .filter(y => years.includes(y))
      .map(y => ({
        x:y, y: vals[years.indexOf(y)], text: anno[y],
        showarrow:true, arrowhead:2, ax:0, ay:-40
      }));

    const xr = computeRange(years);

    Plotly.newPlot('chart-plot', [{
      x: years,
      y: vals,
      type: 'scatter',
      mode: 'lines',
      hovertemplate: 'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line: { width: useWidth, color: useColor }
    }], {
      margin: { l:60, r:20, t:50, b:40 },
      title: 'Good Times Index (GTI) — 1900 to 2025',
      xaxis: { title:'Year', showgrid:true, gridcolor:cssVar('--grid'), range: xr },
      yaxis: { title:'GTI Index (Unbounded)', showgrid:true, gridcolor:cssVar('--grid') },
      annotations,
      paper_bgcolor: cssVar('--bg'),
      plot_bgcolor:  cssVar('--card'),
      font: { color: cssVar('--fg') }
    }, { displayModeBar:false, responsive:true })
    .then(gd => {
      gd.on('plotly_hover', ev => {
        const year = ev?.points?.[0]?.x;
        if (!year) return;
        const hover = EVENTS[String(year)];
        if (hover && ys.hover) {
          ys.year && (ys.year.textContent = String(year));
          ys.hover.textContent = hover;
        }
      });
      gd.on('plotly_click', ev => {
        const year = ev?.points?.[0]?.x;
        if (!year) return;
        let gtiVal = '—';
        for (let i=0;i<GTI_SERIES.length;i++){
          if (GTI_SERIES[i].year === year) {
            const n = GTI_SERIES[i].gti;
            gtiVal = (typeof n === 'number') ? Math.round(n) : '—';
            break;
          }
        }
        ys.year && (ys.year.textContent = String(year));
        ys.gti  && (ys.gti.textContent  = gtiVal);
        ys.hover&& (ys.hover.textContent = EVENTS[String(year)] || '—');
        ys.ai   && (ys.ai.textContent    = SUMMARIES[String(year)] || 'Summary coming soon.');
        if (ys.panel){
          ys.panel.style.display = 'block';
          if (ysTimer) clearTimeout(ysTimer);
          ysTimer = setTimeout(() => { ys.panel.style.display = 'none'; }, 10000);
        }
      });
    })
    .catch(err => console.error('Plot error:', err));
  }

  ys.close?.addEventListener('click', () => {
    if (ys.panel) ys.panel.style.display = 'none';
    if (ysTimer) clearTimeout(ysTimer);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && ys.panel && ys.panel.style.display !== 'none') {
      ys.panel.style.display = 'none';
      if (ysTimer) clearTimeout(ysTimer);
    }
  });

  // ---------------------- DETAILS & SOURCES ----------------------
  function renderCategories(cats) {
    if (!cats) return;
    const order = [
      'Planetary Health','Economic Wellbeing','Global Peace & Conflict','Public Health',
      'Civic Freedom & Rights','Technological Progress','Sentiment & Culture','Entropy Index'
    ];
    const rows = order.map(k => ({ name:k, score:(cats.scores && typeof cats.scores[k] === 'number') ? cats.scores[k] : 50 }));
    // Bars (if exists)
    if (qs('#category-bars')) {
      Plotly.newPlot('category-bars', [{
        x: rows.map(r => r.score),
        y: rows.map(r => r.name),
        type: 'bar', orientation: 'h',
        hovertemplate: '%{y}: %{x}<extra></extra>'
      }], {
        margin:{ l:170, r:20, t:10, b:30 },
        xaxis:{ range:[0,100], showgrid:true, gridcolor:cssVar('--grid') },
        paper_bgcolor: cssVar('--bg'),
        plot_bgcolor:  cssVar('--card'),
        font: { color: cssVar('--fg') }
      }, { displayModeBar:false, responsive:true }).catch(()=>{});
    }
    // Table (if exists)
    const tbl = qs('#category-table');
    if (tbl) {
      const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
      tbl.innerHTML = `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
    }
  }

  function renderSources(src) {
    const listEl = qs('#sources-list');
    const methEl = qs('#methodology');
    if (listEl) {
      const rows = ((src && src.sources) || []).map(s =>
        `<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes||''}</td></tr>`
      ).join('');
      listEl.innerHTML = `<table><tbody>${rows}</tbody></table>`;
    }
    if (methEl) {
      methEl.innerHTML = `<ul class="bullets">${((src && src.methodology) || []).map(m => `<li>${m}</li>`).join('')}</ul>`;
    }
  }

  // ---------------------- TODAY'S SIGNALS ----------------------
  function renderSignals(status) {
    if (!status) return;

    // Last updated (header + LIVE strip)
    try {
      if (status.updated_iso) {
        const t = new Date(status.updated_iso).toUTCString();
        kpiUpd && (kpiUpd.textContent = t);
        elUpdated && (elUpdated.textContent = t);
        liveAgo && (liveAgo.textContent = `updated ${humanAgo(Date.now() - new Date(status.updated_iso).getTime())}`);
      }
    } catch {}

    // KPI delta vs 30d avg
    try {
      const last = clampNum(status.gti_last, null);
      const avg  = clampNum(status.gti_30d_avg, null);
      if (last !== null && avg !== null && kpiDelta) {
        const pct = avg ? ((last - avg) / avg) * 100 : 0;
        kpiDelta.textContent = `${pct.toFixed(2)}% vs 30d`;
      }
    } catch {}

    // The chips
    if (!signalsList) return;
    const items = [];
    try {
      if (status.planetary) {
        items.push(`<li><span class="sig-name">CO₂ (ppm)</span><span class="sig-val">${fmtN(status.planetary.co2_ppm, 2)}</span></li>`);
        items.push(`<li><span class="sig-name">Temp anomaly (°C)</span><span class="sig-val">${fmtN(status.planetary.gistemp_anom_c, 2)}</span></li>`);
      }
      if (status.sentiment) {
        items.push(`<li><span class="sig-name">News tone (30d avg)</span><span class="sig-val">${fmtN(status.sentiment.avg_tone_30d, 2)}</span></li>`);
      }
      if (status.markets) {
        const r30 = clampNum(status.markets.acwi_ret30, 0) * 100;
        items.push(`<li><span class="sig-name">ACWI (30d return)</span><span class="sig-val">${fmtN(r30, 2)}%</span></li>`);
        items.push(`<li><span class="sig-name">VIX (level)</span><span class="sig-val">${fmtN(status.markets.vix, 2)}</span></li>`);
        const vol = clampNum(status.markets.brent_vol30, 0) * 100;
        items.push(`<li><span class="sig-name">Brent 30d vol</span><span class="sig-val">${fmtN(vol, 2)}%</span></li>`);
      }
      signalsList.innerHTML = items.join('');
      signalsFoot && (signalsFoot.textContent = status.note || 'Signals compare to recent baselines.');
    } catch (e) {
      console.warn('renderSignals error:', e);
    }
  }

  // ---------------------- LOAD & POLL ----------------------
  async function loadAll() {
    const [gti, cats, src, evt, sum, status] = await Promise.all([
      getJSON(urls.gti()),
      getJSON(urls.cat()).catch(() => null),
      getJSON(urls.src()).catch(() => null),
      getJSON(urls.evt()).catch(() => ({})),
      getJSON(urls.sum()).catch(() => ({})),
      getJSON(urls.status()).catch(() => null)
    ]);

    GTI_SERIES = (gti && Array.isArray(gti.series) && gti.series.length) ? gti.series : [{ year:1900, gti:300 }];
    EVENTS     = evt || {};
    SUMMARIES  = sum || {};

    if (gti?.updated) {
      const ts = new Date(gti.updated).toUTCString();
      elUpdated && (elUpdated.textContent = ts);
      kpiUpd    && (kpiUpd.textContent    = ts);
    }

    plotLine();
    renderCategories(cats);
    renderSources(src);
    renderSignals(status);

    lastStatusISO = status?.updated_iso || lastStatusISO;

    // Private console debug
    console.log('GTI data loaded:', { updated:gti?.updated, points: GTI_SERIES.length });
    if (devEnabled) showDev({ status, cats, seriesPoints: GTI_SERIES.length });
  }

  async function poll() {
    try {
      const status = await getJSON(urls.status());
      if (status?.updated_iso) {
        if (liveAgo) liveAgo.textContent = `updated ${humanAgo(Date.now() - new Date(status.updated_iso).getTime())}`;
        if (lastStatusISO !== status.updated_iso) {
          await loadAll();
          lastStatusISO = status.updated_iso;
        } else {
          renderSignals(status);
        }
      }
    } catch {}
  }

  loadAll().catch(e => console.error('Initial load failed:', e));
  setInterval(() => { if (autoRF?.checked) poll(); }, 60000);
  setInterval(async () => {
    try {
      const s = await getJSON(urls.status());
      if (s?.updated_iso && liveAgo) {
        liveAgo.textContent = `updated ${humanAgo(Date.now() - new Date(s.updated_iso).getTime())}`;
      }
    } catch {}
  }, 10000);

  // ---------------------- EXPORTS ----------------------
  btnPNG?.addEventListener('click', async () => {
    try { await Plotly.downloadImage('chart-plot', { format:'png', filename:'anthrometer-gti' }); } catch {}
  });
  btnCSV?.addEventListener('click', () => {
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) return;
    const rows = ['year,gti'].concat(GTI_SERIES.map(d => `${d.year},${d.gti}`)).join('\n');
    const blob = new Blob([rows], { type:'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'anthrometer-gti.csv'; a.click();
    URL.revokeObjectURL(url);
  });
});
