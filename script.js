document.addEventListener('DOMContentLoaded', () => {
  const dataUrl  = `./data/gti.json?t=${Date.now()}`;
  const catUrl   = `./data/categories.json?t=${Date.now()}`;
  const srcUrl   = `./data/sources.json?t=${Date.now()}`;
  const clUrl    = `./data/changelog.json?t=${Date.now()}`;
  const eventsUrl= `./data/events.json?t=${Date.now()}`;
  const sumUrl   = `./data/summaries.json?t=${Date.now()}`;

  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // Controls
  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const chkDecade = document.getElementById('decade-zoom');
  const chkDark   = document.getElementById('dark-mode');

  // Load saved prefs
  const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }

  // Apply saved theme early
  if (prefs.darkMode === true) document.body.classList.add('dark');

  // Tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById('tab-' + btn.dataset.tab);
      if (!target) return;
      document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('active'));
      btn.classList.add('active');
      target.classList.add('active');
    }, { passive: true });
  });

  async function getJSON(url){ const r = await fetch(url, {cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }

  let GTI_SERIES = []; let EVENTS = {}; let SUMMARIES = {};
  let LAYOUT_THEME = {}; // set per mode

  function plotLine(){
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) return;
    const years = GTI_SERIES.map(d=>d.year);
    const vals  = GTI_SERIES.map(d=>d.gti);
    const lastIdx = years.length - 1;
    elCY.textContent = years[lastIdx] != null ? years[lastIdx] : '—';
    elCV.textContent = vals[lastIdx]  != null ? Math.round(vals[lastIdx]) : '—';

    // map color choice to Plotly color
    const colorMap = { blue:'#2563eb', green:'#059669', purple:'#7c3aed', orange:'#ea580c', red:'#dc2626' };
    const useColor = (prefs.lineColor && prefs.lineColor!=='auto') ? colorMap[prefs.lineColor] : undefined;
    const useWidth = Number(prefs.lineWeight || 3);

    // annotations
    const annoLabels = { 1918:'1918: Flu Pandemic', 1945:'1945: WWII Ends', 2008:'2008: Financial Crisis', 2020:'2020: COVID-19' };
    const annotations = Object.keys(annoLabels).map(k=>parseInt(k,10))
      .filter(y => years.indexOf(y)!==-1)
      .map(y => ({ x:y, y: vals[years.indexOf(y)], text: annoLabels[y], showarrow:true, arrowhead:2, ax:0, ay:-40 }));

    // decade highlight shape (only when NOT zoomed)
    const maxYear = years[years.length-1];
    const minDecade = maxYear - 9;
    const shapes = (!prefs.decadeZoom) ? [{
      type:'rect', xref:'x', yref:'paper', x0:minDecade, x1:maxYear, y0:0, y1:1,
      fillcolor: (document.body.classList.contains('dark') ? 'rgba(148,163,184,0.10)' : 'rgba(2,132,199,0.08)'),
      line:{width:0}
    }] : [];

    // x-range if zoomed
    const xr = (prefs.decadeZoom) ? [minDecade, maxYear] : undefined;

    Plotly.newPlot('chart', [{
      x: years, y: vals, type:'scatter', mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{ width: useWidth, color: useColor }
    }], {
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year', showgrid:true, gridcolor: getVar('--grid'), range: xr},
      yaxis:{title:'GTI Index (Unbounded)', showgrid:true, gridcolor: getVar('--grid')},
      annotations, shapes,
      paper_bgcolor: getVar('--bg'), plot_bgcolor: getVar('--card'), font:{color:getVar('--fg')}
    }, {displayModeBar:false, responsive:true}).then(gd => {
      gd.on('plotly_hover', ev => {
        if (!ev || !ev.points || !ev.points[0]) return;
        const year = String(ev.points[0].x);
        const hover = EVENTS[year];
        if (hover) {
          document.getElementById('ys-year').textContent = year;
          document.getElementById('ys-hover').textContent = hover;
        }
      });
      gd.on('plotly_click', ev => {
        if (!ev || !ev.points || !ev.points[0]) return;
        const year = String(ev.points[0].x);
        const hover = EVENTS[year] || '—';
        const ai = SUMMARIES[year] || 'Summary coming soon.';
        document.getElementById('ys-year').textContent = year;
        document.getElementById('ys-hover').textContent = hover;
        document.getElementById('ys-ai').textContent = ai;
        document.getElementById('year-summary').style.display = 'block';
      });
    });
  }

  function getVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }

  // Render categories/sources/changelog (same as before)
  function renderCategories(cats){
    if (!cats) return;
    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const rows = order.map(k => ({ name:k, score:(cats.scores && typeof cats.scores[k] === 'number') ? cats.scores[k] : 50 }));
    Plotly.newPlot('category-bars', [{
      x: rows.map(r=>r.score), y: rows.map(r=>r.name), type:'bar', orientation:'h',
      hovertemplate:'%{y}: %{x}<extra></extra>'
    }], { margin:{l:170,r:20,t:10,b:30}, xaxis:{range:[0,100], showgrid:true, gridcolor:getVar('--grid')},
          paper_bgcolor:getVar('--bg'), plot_bgcolor:getVar('--card'), font:{color:getVar('--fg')} },
       {displayModeBar:false, responsive:true});

    const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
    document.getElementById('category-table').innerHTML =
      `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
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

  // Bind controls
  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (chkDecade) chkDecade.checked = !!prefs.decadeZoom;
  if (chkDark)   chkDark.checked   = !!prefs.darkMode;

  selColor && selColor.addEventListener('change', ()=>{ prefs.lineColor = selColor.value; savePrefs(); plotLine(); });
  selWeight&& selWeight.addEventListener('change',()=>{ prefs.lineWeight = Number(selWeight.value); savePrefs(); plotLine(); });
  chkDecade && chkDecade.addEventListener('change', ()=>{ prefs.decadeZoom = chkDecade.checked; savePrefs(); plotLine(); });
  chkDark   && chkDark.addEventListener('change',   ()=>{ prefs.darkMode = chkDark.checked; savePrefs(); document.body.classList.toggle('dark', prefs.darkMode); plotLine(); });

  // Load all data then draw
  (async () => {
    const [gti, cats, src, cl, evMap, smap] = await Promise.all([
      getJSON(dataUrl),
      getJSON(catUrl).catch(()=>null),
      getJSON(srcUrl).catch(()=>null),
      getJSON(clUrl).catch(()=>null),
      getJSON(eventsUrl).catch(()=> ({})),
      getJSON(sumUrl).catch(()=> ({}))
    ]);
    if (elUpdated && gti && gti.updated) elUpdated.textContent = new Date(gti.updated).toUTCString();
    GTI_SERIES = (gti && gti.series) ? gti.series : [];
    EVENTS = evMap || {}; SUMMARIES = smap || {};
    plotLine();
    renderCategories(cats);
    renderSources(src);
    renderChangelog(cl);
  })().catch(err => {
    console.error(err);
    const c = document.getElementById('chart');
    if (c) c.innerHTML =
      `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
         Failed to load data: ${String(err)}
       </div>`;
  });
});
