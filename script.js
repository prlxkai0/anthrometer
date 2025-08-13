// script.js — AnthroMeter front-end (stable sizing + KPI card + floating summary autohide)
document.addEventListener('DOMContentLoaded', () => {
  // --------- Endpoints (cache-busted) ----------
  const bust = Date.now();
  const dataUrl   = `./data/gti.json?t=${bust}`;
  const catUrl    = `./data/categories.json?t=${bust}`;
  const srcUrl    = `./data/sources.json?t=${bust}`;
  const clUrl     = `./data/changelog.json?t=${bust}`;
  const eventsUrl = `./data/events.json?t=${bust}`;
  const sumUrl    = `./data/summaries.json?t=${bust}`;

  // --------- DOM refs ----------
  // Legacy header status (hidden via CSS, still set)
  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // KPI card
  const kpiYear = document.getElementById('kpi-year');
  const kpiGTI  = document.getElementById('kpi-gti');
  const kpiUpd  = document.getElementById('kpi-updated');

  // Controls
  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const chkDecade = document.getElementById('decade-zoom'); // optional legacy
  const chkDark   = document.getElementById('dark-mode');
  const selRange  = document.getElementById('range-select');
  const btnPNG    = document.getElementById('btn-png');
  const btnCSV    = document.getElementById('btn-csv');

  // Floating Year Summary
  const ys = {
    panel: document.getElementById('year-summary'),
    close: document.getElementById('ys-close'),
    year:  document.getElementById('ys-year'),
    gti:   document.getElementById('ys-gti'),
    hover: document.getElementById('ys-hover'),
    ai:    document.getElementById('ys-ai')
  };
  let ysTimer = null;
  function showSummary() {
    if (!ys.panel) return;
    ys.panel.style.display = 'block';
    if (ysTimer) clearTimeout(ysTimer);
    ysTimer = setTimeout(() => { ys.panel.style.display = 'none'; }, 10000);
  }

  // --------- Preferences ----------
  const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }
  if (typeof prefs.darkMode === 'undefined') {
    const mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    prefs.darkMode = mq ? mq.matches : false;
  }
  document.body.classList.toggle('dark', !!prefs.darkMode);

  // --------- Tabs ----------
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById('tab-' + btn.dataset.tab);
      if (!target) return;
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      target.classList.add('active');
      // Relayout chart when returning to Overview
      if (btn.dataset.tab === 'overview' && window.Plotly && document.getElementById('chart-plot')) {
        try { Plotly.Plots.resize('chart-plot'); } catch(e){}
      }
    }, { passive: true });
  });

  // --------- Helpers ----------
  async function getJSON(url){
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
    return r.json();
  }
  function cssVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }
  function safePlotlyNewPlot(id, data, layout, config){
    const el = document.getElementById(id);
    if (!el) return;
    try { Plotly.newPlot(id, data, layout, config); } catch(e){ console.error('Plotly error for', id, e); }
  }

  // --------- State ----------
  let GTI_SERIES = [];
  let EVENTS = {};
  let SUMMARIES = {};
  let CATS = null;
  const CHART_ID = 'chart-plot';

  // --------- Plotting ----------
  function computeRange(years){
    if (!years || !years.length) return undefined;
    const maxYear = years[years.length - 1];
    const pick = (selRange && selRange.value) || (prefs.decadeZoom ? 'decade' : 'all');
    if (pick === 'decade') return [maxYear - 9, maxYear];
    if (pick === '20y')    return [maxYear - 19, maxYear];
    if (pick === '5y')     return [maxYear - 4,  maxYear];
    return undefined;
  }

  function plotLine(){
    const el = document.getElementById(CHART_ID);
    if (!el) return;

    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) {
      el.innerHTML = '<div style="padding:12px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">No GTI data found.</div>';
      return;
    } else {
      el.innerHTML = '';
    }

    const years = GTI_SERIES.map(d => d.year);
    const vals  = GTI_SERIES.map(d => d.gti);
    const lastIdx = years.length - 1;
    const lastYear = years[lastIdx];
    const lastVal = vals[lastIdx];

    // Update header (hidden) and KPI
    if (elCY) elCY.textContent = lastYear != null ? lastYear : '—';
    if (elCV) elCV.textContent = lastVal  != null ? Math.round(lastVal) : '—';
    if (kpiYear) kpiYear.textContent = elCY.textContent;
    if (kpiGTI)  kpiGTI.textContent  = elCV.textContent;

    // Styling
    const colorMap = { blue:'#2563eb', green:'#059669', purple:'#7c3aed', orange:'#ea580c', red:'#dc2626' };
    const useColor = (prefs.lineColor && prefs.lineColor !== 'auto') ? colorMap[prefs.lineColor] : undefined;
    const useWidth = Number(prefs.lineWeight || 3);

    // Annotations
    const annoLabels = { 1918:'1918: Flu Pandemic', 1945:'1945: WWII Ends', 2008:'2008: Financial Crisis', 2020:'2020: COVID-19' };
    const annotations = Object.keys(annoLabels)
      .map(k => parseInt(k, 10))
      .filter(y => years.includes(y))
      .map(y => ({ x:y, y: vals[years.indexOf(y)], text: annoLabels[y], showarrow:true, arrowhead:2, ax:0, ay:-40 }));

    // Range + optional decade highlight
    const xr = computeRange(years);
    const shapes = (!xr) ? [{
      type:'rect', xref:'x', yref:'paper',
      x0: years[years.length-1] - 9, x1: years[years.length-1],
      y0: 0, y1: 1,
      fillcolor: (document.body.classList.contains('dark') ? 'rgba(148,163,184,0.10)' : 'rgba(2,132,199,0.08)'),
      line:{ width:0 }
    }] : [];

    Plotly.newPlot(CHART_ID, [{
      x: years,
      y: vals,
      type: 'scatter',
      mode: 'lines',
      hovertemplate: 'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line: { width: useWidth, color: useColor }
    }], {
      margin:{ l:60, r:20, t:50, b:40 },
      title: 'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{ title:'Year', showgrid:true, gridcolor: cssVar('--grid'), range: xr },
      yaxis:{ title:'GTI Index (Unbounded)', showgrid:true, gridcolor: cssVar('--grid') },
      annotations, shapes,
      paper_bgcolor: cssVar('--bg'),
      plot_bgcolor: cssVar('--card'),
      font: { color: cssVar('--fg') }
    }, { displayModeBar:false, responsive:true }).then(gd => {
      gd.on('plotly_hover', ev => {
        const year = ev?.points?.[0]?.x;
        if (!year) return;
        const hover = EVENTS[String(year)];
        if (hover && ys.hover) { ys.year && (ys.year.textContent = String(year)); ys.hover.textContent = hover; }
      });

      gd.on('plotly_click', ev => {
        const year = ev?.points?.[0]?.x;
        if (!year) return;

        // GTI value for that year
        let gtiVal = '—';
        for (let i=0;i<GTI_SERIES.length;i++){
          if (GTI_SERIES[i].year === year) {
            const n = GTI_SERIES[i].gti;
            gtiVal = (typeof n === 'number') ? Math.round(n) : '—';
            break;
          }
        }

        // Fill floating card
        ys.year  && (ys.year.textContent = String(year));
        ys.gti   && (ys.gti.textContent  = gtiVal);
        ys.hover && (ys.hover.textContent= EVENTS[String(year)] || '—');
        ys.ai    && (ys.ai.textContent   = SUMMARIES[String(year)] || 'Summary coming soon.');

        // Show with auto-hide
        showSummary();
      });
    }).catch(e => console.error('Plotly newPlot failed:', e));
  }

  function renderCategories(cats){
    if (!cats) return;
    CATS = cats;
    if (kpiUpd && cats.updated) kpiUpd.textContent = new Date(cats.updated).toUTCString();

    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const rows = order.map(k => ({
      name: k,
      score: (cats.scores && typeof cats.scores[k] === 'number') ? cats.scores[k] : 50
    }));

    // Bars
    safePlotlyNewPlot('category-bars', [{
      x: rows.map(r => r.score),
      y: rows.map(r => r.name),
      type: 'bar',
      orientation: 'h',
      hovertemplate: '%{y}: %{x}<extra></extra>'
    }], {
      margin:{ l:170, r:20, t:10, b:30 },
      xaxis:{ range:[0,100], showgrid:true, gridcolor: cssVar('--grid') },
      paper_bgcolor: cssVar('--bg'),
      plot_bgcolor: cssVar('--card'),
      font: { color: cssVar('--fg') }
    }, { displayModeBar:false, responsive:true });

    // Table
    const tbl = document.getElementById('category-table');
    if (tbl) {
      const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
      tbl.innerHTML = `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
    }
  }

  function renderSources(src){
    const listEl = document.getElementById('sources-list');
    const methEl = document.getElementById('methodology');
    if (!src) return;
    if (listEl) {
      const rows = (src.sources || []).map(s =>
        `<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes || ''}</td></tr>`
      ).join('');
      listEl.innerHTML = `<table><tbody>${rows}</tbody></table>`;
    }
    if (methEl) {
      methEl.innerHTML = `<ul class="bullets">${(src.methodology || []).map(m => `<li>${m}</li>`).join('')}</ul>`;
    }
  }

  function renderChangelog(cl){
    const listEl = document.getElementById('changelog-list');
    if (!cl || !listEl) return;
    const rows = (cl.entries || []).map(e =>
      `<li><div class="cl-date">${e.date}</div><div class="cl-change">${e.change}</div></li>`
    ).join('');
    listEl.innerHTML = `<ul>${rows}</ul>`;
  }

  // --------- Init control values ----------
  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (chkDark)   chkDark.checked = !!prefs.darkMode;
  if (selRange)  selRange.value  = prefs.range || 'all';
  if (chkDecade) chkDecade.checked = (prefs.range === 'decade');

  function replot(){ plotLine(); }

  selColor  && selColor.addEventListener('change',  () => { prefs.lineColor  = selColor.value; savePrefs(); replot(); });
  selWeight && selWeight.addEventListener('change', () => { prefs.lineWeight = Number(selWeight.value); savePrefs(); replot(); });
  chkDark   && chkDark.addEventListener('change',   () => { prefs.darkMode   = chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); savePrefs(); replot(); });
  selRange  && selRange.addEventListener('change',  () => { prefs.range      = selRange.value; savePrefs(); replot(); });
  chkDecade && chkDecade.addEventListener('change', () => {
    prefs.range = chkDecade.checked ? 'decade' : 'all';
    if (selRange) selRange.value = prefs.range;
    savePrefs(); replot();
  });

  // Export
  btnPNG && btnPNG.addEventListener('click', async () => {
    try { await Plotly.downloadImage('chart-plot', { format:'png', filename:'anthrometer-gti' }); }
    catch(e){ console.error(e); }
  });
  btnCSV && btnCSV.addEventListener('click', () => {
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) return;
    const rows = ['year,gti'].concat(GTI_SERIES.map(d => `${d.year},${d.gti}`)).join('\n');
    const blob = new Blob([rows], { type:'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'anthrometer-gti.csv'; a.click();
    URL.revokeObjectURL(url);
  });

  // Summary close handlers
  ys.close && ys.close.addEventListener('click', () => { ys.panel && (ys.panel.style.display = 'none'); if (ysTimer) clearTimeout(ysTimer); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && ys.panel && ys.panel.style.display !== 'none') {
      ys.panel.style.display = 'none';
      if (ysTimer) clearTimeout(ysTimer);
    }
  });

  // Window resize → keep chart responsive
  window.addEventListener('resize', () => {
    if (window.Plotly) { try { Plotly.Plots.resize('chart-plot'); } catch(e){} }
  });

  // --------- Load & render everything ----------
  (async () => {
    const [gti, cats, src, cl, evMap, smap] = await Promise.all([
      getJSON(dataUrl),
      getJSON(catUrl).catch(() => null),
      getJSON(srcUrl).catch(() => null),
      getJSON(clUrl).catch(() => null),
      getJSON(eventsUrl).catch(() => ({})),
      getJSON(sumUrl).catch(() => ({}))
    ]);

    // Updated timestamps → header + KPI
    if (gti && gti.updated) {
      const ts = new Date(gti.updated).toUTCString();
      if (elUpdated) elUpdated.textContent = ts;
      if (kpiUpd)    kpiUpd.textContent    = ts;
    }

    GTI_SERIES = (gti && gti.series) ? gti.series : [];
    EVENTS     = evMap || {};
    SUMMARIES  = smap || {};
    CATS       = cats || null;

    plotLine();
    renderCategories(cats);
    renderSources(src);
    renderChangelog(cl);
  })().catch(err => {
    console.error(err);
    const el = document.getElementById(CHART_ID);
    if (el) el.innerHTML = `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
      Failed to load data: ${String(err)}
    </div>`;
  });
});
