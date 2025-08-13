// script.js — Live feel: auto-refresh, LIVE strip, signals, KPI delta, replot in place
document.addEventListener('DOMContentLoaded', () => {
  const bust = () => Date.now();
  const urls = {
    gti: () => `./data/gti.json?t=${bust()}`,
    cat: () => `./data/categories.json?t=${bust()}`,
    src: () => `./data/sources.json?t=${bust()}`,
    chg: () => `./data/changelog.json?t=${bust()}`,
    evt: () => `./data/events.json?t=${bust()}`,
    sum: () => `./data/summaries.json?t=${bust()}`,
    status: () => `./data/status.json?t=${bust()}`
  };

  // DOM refs
  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  const kpiYear = document.getElementById('kpi-year');
  const kpiGTI  = document.getElementById('kpi-gti');
  const kpiUpd  = document.getElementById('kpi-updated');
  const kpiDelta= document.getElementById('kpi-delta');

  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const chkDark   = document.getElementById('dark-mode');
  const selRange  = document.getElementById('range-select');
  const btnPNG    = document.getElementById('btn-png');
  const btnCSV    = document.getElementById('btn-csv');

  const CHART_ID = 'chart-plot';
  const liveAgo = document.getElementById('live-ago');
  const autoToggle = document.getElementById('auto-refresh');

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

  // Tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById('tab-' + btn.dataset.tab);
      if (!target) return;
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      target.classList.add('active');
      if (btn.dataset.tab === 'overview' && window.Plotly) {
        try { Plotly.Plots.resize(CHART_ID); } catch(e){}
      }
    }, { passive: true });
  });

  // Helpers
  async function getJSON(url){ const r = await fetch(url, { cache: 'no-store' }); if(!r.ok) throw new Error(url + ' → ' + r.status); return r.json(); }
  function cssVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }
  function computeRange(years){
    const pick = (selRange && selRange.value) || 'all';
    if (!years || !years.length) return undefined;
    const maxYear = years[years.length - 1];
    if (pick === 'decade') return [maxYear - 9, maxYear];
    if (pick === '20y')    return [maxYear - 19, maxYear];
    if (pick === '5y')     return [maxYear - 4,  maxYear];
    return undefined;
  }

  // State
  let GTI_SERIES = [];
  let EVENTS = {};
  let SUMMARIES = {};
  let lastStatusISO = null; // last status updated timestamp

  // Plot
  function plotLine(){
    const el = document.getElementById(CHART_ID);
    if (!el) return;
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) {
      el.innerHTML = '<div style="padding:12px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">No GTI data found.</div>';
      return;
    } else { el.innerHTML = ''; }

    const years = GTI_SERIES.map(d => d.year);
    const vals  = GTI_SERIES.map(d => d.gti);
    const lastIdx = years.length - 1;
    const lastYear = years[lastIdx];
    const lastVal = vals[lastIdx];

    if (elCY) elCY.textContent = lastYear ?? '—';
    if (elCV) elCV.textContent = (lastVal!=null) ? Math.round(lastVal) : '—';
    if (kpiYear) kpiYear.textContent = elCY.textContent;
    if (kpiGTI)  kpiGTI.textContent  = elCV.textContent;

    const colorMap = { blue:'#2563eb', green:'#059669', purple:'#7c3aed', orange:'#ea580c', red:'#dc2626' };
    const lineColor = (localStorage.getItem('prefs') && JSON.parse(localStorage.getItem('prefs')).lineColor) || 'auto';
    const useColor = (lineColor !== 'auto') ? colorMap[lineColor] : undefined;
    const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
    const useWidth = Number(prefs.lineWeight || 3);

    const anno = { 1918:'1918: Flu Pandemic', 1945:'1945: WWII Ends', 2008:'2008: Financial Crisis', 2020:'2020: COVID-19' };
    const annotations = Object.keys(anno).map(k => parseInt(k,10))
      .filter(y => years.includes(y))
      .map(y => ({ x:y, y: vals[years.indexOf(y)], text: anno[y], showarrow:true, arrowhead:2, ax:0, ay:-40 }));

    const xr = computeRange(years);
    const shapes = (!xr) ? [{
      type:'rect', xref:'x', yref:'paper',
      x0: years[years.length-1] - 9, x1: years[years.length-1],
      y0: 0, y1: 1,
      fillcolor: (document.body.classList.contains('dark') ? 'rgba(148,163,184,0.10)' : 'rgba(2,132,199,0.08)'),
      line:{ width:0 }
    }] : [];

    Plotly.newPlot(CHART_ID, [{
      x: years, y: vals, type:'scatter', mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{ width:useWidth, color:useColor }
    }], {
      margin:{ l:60, r:20, t:50, b:40 },
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{ title:'Year', showgrid:true, gridcolor:cssVar('--grid'), range:xr },
      yaxis:{ title:'GTI Index (Unbounded)', showgrid:true, gridcolor:cssVar('--grid') },
      annotations, shapes,
      paper_bgcolor:cssVar('--bg'), plot_bgcolor:cssVar('--card'),
      font:{ color:cssVar('--fg') }
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
        let gtiVal = '—';
        for (let i=0;i<GTI_SERIES.length;i++){
          if (GTI_SERIES[i].year === year) {
            const n = GTI_SERIES[i].gti;
            gtiVal = (typeof n === 'number') ? Math.round(n) : '—';
            break;
          }
        }
        ys.year  && (ys.year.textContent = String(year));
        ys.gti   && (ys.gti.textContent  = gtiVal);
        ys.hover && (ys.hover.textContent= EVENTS[String(year)] || '—');
        ys.ai    && (ys.ai.textContent   = SUMMARIES[String(year)] || 'Summary coming soon.');
        showSummary();
      });
    }).catch(console.error);
  }

  function renderCategories(cats){
    if (!cats) return;
    // Bars
    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const rows = order.map(k => ({ name:k, score: (cats.scores && typeof cats.scores[k]==='number') ? cats.scores[k] : 50 }));
    if (document.getElementById('category-bars')) {
      Plotly.newPlot('category-bars', [{
        x: rows.map(r=>r.score), y: rows.map(r=>r.name),
        type:'bar', orientation:'h', hovertemplate:'%{y}: %{x}<extra></extra>'
      }], {
        margin:{ l:170, r:20, t:10, b:30 }, xaxis:{ range:[0,100], showgrid:true, gridcolor:cssVar('--grid') },
        paper_bgcolor:cssVar('--bg'), plot_bgcolor:cssVar('--card'), font:{ color:cssVar('--fg') }
      }, { displayModeBar:false, responsive:true }).catch(()=>{});
    }
    const tbl = document.getElementById('category-table');
    if (tbl) {
      const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
      tbl.innerHTML = `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
    }
  }

  function renderSources(src){
    const listEl = document.getElementById('sources-list');
    const methEl = document.getElementById('methodology');
    if (listEl) {
      const rows = ((src && src.sources) || []).map(s =>
        `<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes || ''}</td></tr>`
      ).join('');
      listEl.innerHTML = `<table><tbody>${rows}</tbody></table>`;
    }
    if (methEl) {
      methEl.innerHTML = `<ul class="bullets">${((src && src.methodology) || []).map(m => `<li>${m}</li>`).join('')}</ul>`;
    }
  }

  function renderChangelog(cl){
    const listEl = document.getElementById('changelog-list');
    if (!listEl) return;
    const rows = ((cl && cl.entries) || []).map(e => `<li><div class="cl-date">${e.date}</div><div class="cl-change">${e.change}</div></li>`).join('');
    listEl.innerHTML = `<ul>${rows}</ul>`;
  }

  // Signals panel + LIVE strip
  function msAgo(iso){ const t = new Date(iso).getTime(); return Date.now() - (isNaN(t)?Date.now():t); }
  function humanAgo(ms){
    const s = Math.floor(ms/1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s/60); if (m < 60) return `${m}m ago`;
    const h = Math.floor(m/60); if (h < 24) return `${h}h ago`;
    const d = Math.floor(h/24); return `${d}d ago`;
  }
  function renderSignals(status){
    // Live strip
    if (status && status.updated_iso) {
      const t = new Date(status.updated_iso).toUTCString();
      if (kpiUpd) kpiUpd.textContent = t;
      if (elUpdated) elUpdated.textContent = t;
      if (liveAgo) liveAgo.textContent = `updated ${humanAgo(msAgo(status.updated_iso))}`;
    }

    // KPI delta
    if (status && typeof status.gti_last === 'number' && typeof status.gti_30d_avg === 'number') {
      const last = status.gti_last, avg = status.gti_30d_avg;
      const pct = avg ? ((last - avg)/avg)*100 : 0;
      const arrow = pct >= 0 ? '▲' : '▼';
      const cls = pct >= 0 ? 'up' : 'down';
      if (kpiDelta) kpiDelta.innerHTML = `<span class="sig-diff ${cls}">${arrow} ${pct.toFixed(2)}% vs 30d</span>`;
    }

    // Today’s Signals list
    const ul = document.getElementById('signals-list');
    if (!ul || !status) return;
    function diffSpan(v){ return v >= 0 ? `<span class="sig-diff up">▲ ${v.toFixed(2)}</span>` : `<span class="sig-diff down">▼ ${Math.abs(v).toFixed(2)}</span>`; }

    const items = [];
    if (status.planetary) {
      items.push(`<li>
        <span class="sig-name">CO₂ (ppm)</span>
        <span class="sig-val">${status.planetary.co2_ppm?.toFixed?.(2) ?? '—'} ${diffSpan(status.planetary.delta_ppm || 0)}</span>
      </li>
      <li>
        <span class="sig-name">Temp anomaly (°C)</span>
        <span class="sig-val">${status.planetary.gistemp_anom_c?.toFixed?.(2) ?? '—'} ${diffSpan(status.planetary.delta_anom || 0)}</span>
      </li>`);
    }
    if (status.sentiment) {
      items.push(`<li>
        <span class="sig-name">News tone (30d avg)</span>
        <span class="sig-val">${(status.sentiment.avg_tone_30d ?? 0).toFixed(2)} ${diffSpan(status.sentiment.delta_tone || 0)}</span>
      </li>`);
    }
    ul.innerHTML = items.join('');

    const foot = document.getElementById('signals-foot');
    if (foot) {
      foot.textContent = status.note || 'Signals compare to their recent baselines.';
    }
  }

  // Preferences + controls
  const prefs = JSON.parse(localStorage.getItem('prefs') || '{}');
  if (typeof prefs.darkMode === 'undefined') {
    const mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    prefs.darkMode = mq ? mq.matches : false;
  }
  document.body.classList.toggle('dark', !!prefs.darkMode);

  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (chkDark)   chkDark.checked = !!prefs.darkMode;
  if (selRange)  selRange.value  = prefs.range || 'all';

  function replot(){ plotLine(); }

  selColor  && selColor.addEventListener('change',  () => { prefs.lineColor  = selColor.value; localStorage.setItem('prefs', JSON.stringify(prefs)); replot(); });
  selWeight && selWeight.addEventListener('change', () => { prefs.lineWeight = Number(selWeight.value); localStorage.setItem('prefs', JSON.stringify(prefs)); replot(); });
  chkDark   && chkDark.addEventListener('change',   () => { prefs.darkMode   = chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); localStorage.setItem('prefs', JSON.stringify(prefs)); replot(); });
  selRange  && selRange.addEventListener('change',  () => { prefs.range      = selRange.value; localStorage.setItem('prefs', JSON.stringify(prefs)); replot(); });

  document.getElementById('btn-png')?.addEventListener('click', async ()=> {
    try { await Plotly.downloadImage(CHART_ID, { format:'png', filename:'anthrometer-gti' }); } catch(e){}
  });
  document.getElementById('btn-csv')?.addEventListener('click', () => {
    if (!Array.isArray(GTI_SERIES) || GTI_SERIES.length === 0) return;
    const rows = ['year,gti'].concat(GTI_SERIES.map(d => `${d.year},${d.gti}`)).join('\n');
    const blob = new Blob([rows], { type:'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'anthrometer-gti.csv'; a.click();
    URL.revokeObjectURL(url);
  });

  ys.close && ys.close.addEventListener('click', () => { ys.panel && (ys.panel.style.display = 'none'); if (ysTimer) clearTimeout(ysTimer); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ys.panel && ys.panel.style.display !== 'none') { ys.panel.style.display = 'none'; if (ysTimer) clearTimeout(ysTimer);} });

  window.addEventListener('resize', () => { if (window.Plotly) { try { Plotly.Plots.resize(CHART_ID); } catch(e){} } });

  // Initial load + polling
  async function loadAll(){
    const [gti, cats, src, chg, evt, sum, status] = await Promise.all([
      getJSON(urls.gti()),
      getJSON(urls.cat()).catch(()=>null),
      getJSON(urls.src()).catch(()=>null),
      getJSON(urls.chg()).catch(()=>null),
      getJSON(urls.evt()).catch(()=>({})),
      getJSON(urls.sum()).catch(()=>({})),
      getJSON(urls.status()).catch(()=>null)
    ]);
    GTI_SERIES = (gti && gti.series) ? gti.series : [];
    EVENTS     = evt || {};
    SUMMARIES  = sum || {};
    if (gti && gti.updated) {
      const ts = new Date(gti.updated).toUTCString();
      if (elUpdated) elUpdated.textContent = ts;
      if (kpiUpd)    kpiUpd.textContent    = ts;
    }
    plotLine();
    renderCategories(cats);
    renderSources(src);
    renderChangelog(chg);
    renderSignals(status);
    lastStatusISO = status?.updated_iso || lastStatusISO;
  }

  // Poll every 60s if auto-refresh is on; also update "updated X ago" every 10s
  async function poll(){
    try {
      const status = await getJSON(urls.status());
      if (status?.updated_iso) {
        if (liveAgo) liveAgo.textContent = `updated ${humanAgo(msAgo(status.updated_iso))}`;
        if (lastStatusISO !== status.updated_iso) {
          // data changed → reload all JSONs and re-render
          await loadAll();
          lastStatusISO = status.updated_iso;
        }
      }
    } catch { /* ignore transient */ }
  }

  autoToggle?.addEventListener('change', ()=>{ /* state is read in intervals below */ });

  loadAll().catch(console.error);

  setInterval(()=>{ if (autoToggle?.checked) poll(); }, 60000);
  setInterval(async ()=>{ // refresh the "ago" clock even if no new data
    try {
      const s = await getJSON(urls.status());
      if (s?.updated_iso && liveAgo) liveAgo.textContent = `updated ${humanAgo(msAgo(s.updated_iso))}`;
    } catch {}
  }, 10000);
});
