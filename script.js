// script.js — AnthroMeter front-end
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
  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // Controls (Overview tab)
  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const chkDecade = document.getElementById('decade-zoom'); // legacy checkbox
  const chkDark   = document.getElementById('dark-mode');
  const selRange  = document.getElementById('range-select');
  const btnPNG    = document.getElementById('btn-png');
  const btnCSV    = document.getElementById('btn-csv');

  // --------- Preferences (persist) ----------
  const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }

  // Dark mode: if user never chose, respect system
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
    }, { passive: true });
  });

  // --------- Helpers ----------
  async function getJSON(url){
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
    return r.json();
  }
  function cssVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }

  // --------- State ----------
  let GTI_SERIES = [];
  let EVENTS = {};
  let SUMMARIES = {};
  let CATS = null; // categories blob

  // --------- Plotting ----------
  function computeRange(years){
    if (!years || !years.length) return undefined;
    const maxYear = years[years.length - 1];
    const pick = (selRange && selRange.value) || (prefs.decadeZoom ? 'decade' : 'all');
    if (pick === 'decade') return [maxYear - 9, maxYear];
    if (pick === '20y')    return [maxYear - 19, maxYear];
    if (pick === '5y')     return [maxYear - 4,  maxYear];
    return undefined; // all time
  }

  function plotLine(){
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) {
      const c = document.getElementById('chart');
      if (c) c.innerHTML = '<div style="padding:12px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">No GTI data found.</div>';
      return;
    }

    const years = GTI_SERIES.map(d => d.year);
    const vals  = GTI_SERIES.map(d => d.gti);
    const lastIdx = years.length - 1;
    elCY.textContent = years[lastIdx] != null ? years[lastIdx] : '—';
    elCV.textContent = vals[lastIdx]  != null ? Math.round(vals[lastIdx]) : '—';

    // styling
    const colorMap = { blue:'#2563eb', green:'#059669', purple:'#7c3aed', orange:'#ea580c', red:'#dc2626' };
    const useColor = (prefs.lineColor && prefs.lineColor !== 'auto') ? colorMap[prefs.lineColor] : undefined;
    const useWidth = Number(prefs.lineWeight || 3);

    // annotations
    const annoLabels = {
      1918:'1918: Flu Pandemic',
      1945:'1945: WWII Ends',
      2008:'2008: Financial Crisis',
      2020:'2020: COVID-19'
    };
    const annotations = Object.keys(annoLabels)
      .map(k => parseInt(k, 10))
      .filter(y => years.indexOf(y) !== -1)
      .map(y => ({ x:y, y: vals[years.indexOf(y)], text: annoLabels[y], showarrow:true, arrowhead:2, ax:0, ay:-40 }));

    // range + decade highlight
    const xr = computeRange(years);
    const shapes = (!xr) ? [{
      type:'rect', xref:'x', yref:'paper',
      x0: years[years.length-1] - 9, x1: years[years.length-1],
      y0: 0, y1: 1,
      fillcolor: (document.body.classList.contains('dark') ? 'rgba(148,163,184,0.10)' : 'rgba(2,132,199,0.08)'),
      line:{ width:0 }
    }] : [];

    Plotly.newPlot('chart', [{
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
        if (hover) {
          document.getElementById('ys-year').textContent = String(year);
          document.getElementById('ys-hover').textContent = hover;
        }
      });
      gd.on('plotly_click', ev => {
        const year = ev?.points?.[0]?.x;
        if (!year) return;
        const hover = EVENTS[String(year)] || '—';
        const ai = SUMMARIES[String(year)] || 'Summary coming soon.';
        document.getElementById('ys-year').textContent = String(year);
        document.getElementById('ys-hover').textContent = hover;
        document.getElementById('ys-ai').textContent = ai;
        const panel = document.getElementById('year-summary');
        if (panel) panel.style.display = 'block';
      });
    });
  }

  function renderCategories(cats){
    if (!cats) return;
    CATS = cats;
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
    Plotly.newPlot('category-bars', [{
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
    const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
    document.getElementById('category-table').innerHTML =
      `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;

    // Inline legend (compact) under the chart
    renderLegend(cats);
  }

  function renderLegend(cats){
    const el = document.getElementById('year-summary'); // reuse this card's bottom area
    if (!el || !cats || !cats.scores) return;
    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const items = order.map(k => {
      const v = (typeof cats.scores[k] === 'number') ? Math.round(cats.scores[k]) : '—';
      return `<li style="display:inline-block;margin:4px 10px 0 0;color:var(--muted)">${k}: <strong style="color:var(--fg)">${v}</strong></li>`;
    }).join('');
    const legend = `<ul style="list-style:none;padding:0;margin:8px 0 0">${items}</ul>`;
    let div = document.getElementById('legend-inline');
    if (!div) { div = document.createElement('div'); div.id = 'legend-inline'; el.appendChild(div); }
    div.innerHTML = legend;
    el.style.display = 'block';
  }

  function renderSources(src){
    const listEl = document.getElementById('sources-list');
    const methEl = document.getElementById('methodology');
    if (!src) return;
    const rows = (src.sources || []).map(s =>
      `<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes || ''}</td></tr>`
    ).join('');
    listEl.innerHTML = `<table><thead><tr><th>Category</th><th>Source</th><th>Notes</th></tr></thead><tbody>${rows}</tbody></table>`;
    methEl.innerHTML = `<ul class="bullets">${(src.methodology || []).map(m => `<li>${m}</li>`).join('')}</ul>`;
  }

  function renderChangelog(cl){
    const listEl = document.getElementById('changelog-list');
    if (!cl) return;
    const rows = (cl.entries || []).map(e => `<tr><td>${e.date}</td><td>${e.change}</td></tr>`).join('');
    listEl.innerHTML = `<table><thead><tr><th>Date</th><th>Change</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  // --------- Bind controls & init values ----------
  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (chkDark)   chkDark.checked = !!prefs.darkMode;
  if (selRange)  selRange.value  = prefs.range || 'all';
  if (chkDecade) chkDecade.checked = (prefs.range === 'decade'); // legacy sync

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
    try { await Plotly.downloadImage('chart', { format:'png', filename:'anthrometer-gti' }); }
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

    if (elUpdated && gti && gti.updated) elUpdated.textContent = new Date(gti.updated).toUTCString();
    GTI_SERIES = (gti && gti.series) ? gti.series : [];
    EVENTS     = evMap || {};
    SUMMARIES  = smap || {};

    plotLine();
    renderCategories(cats);
    renderSources(src);
    renderChangelog(cl);
  })().catch(err => {
    console.error(err);
    const c = document.getElementById('chart');
    if (c) c.innerHTML = `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
      Failed to load data: ${String(err)}
    </div>`;
  });
});
