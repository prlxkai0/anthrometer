// script.js — decade highlight, dark-mode repaint, robust signal display ("—" for nulls)
document.addEventListener('DOMContentLoaded', () => {
  const bust = () => Date.now();
  const urls = {
    gti:     () => `./data/gti.json?t=${bust()}`,
    status:  () => `./data/status.json?t=${bust()}`,
    cats:    () => `./data/categories.json?t=${bust()}`,
    sources: () => `./data/sources.json?t=${bust()}`,
    events:  () => `./data/events.json?t=${bust()}`,
    sums:    () => `./data/summaries.json?t=${bust()}`
  };
  const cssVar = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();

  // === display helpers (never print 0.00 for nulls) ===
  const isNum = (v) => (typeof v === 'number' && isFinite(v));
  const dNum  = (v, d=2) => (isNum(v) ? v.toFixed(d) : '—');
  const dPct  = (v, d=2) => (isNum(v) ? (v*100).toFixed(d)+'%' : '—');
  const nOr   = (v, d=0) => (isNum(v) ? v : d);

  const humanAgo = (ms)=>{ const s=Math.floor(ms/1000); if(s<60)return`${s}s ago`; const m=Math.floor(s/60); if(m<60)return`${m}m ago`; const h=Math.floor(m/60); if(h<24)return`${h}h ago`; const d=Math.floor(h/24); return `${d}d ago`; };
  async function getJSON(url){ try{ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); }catch{ return null; } }

  // Elements
  const kpiYear = document.getElementById('kpi-year');
  const kpiGTI  = document.getElementById('kpi-gti');
  const kpiUpd  = document.getElementById('kpi-updated');
  const kpiDelta= document.getElementById('kpi-delta');
  const liveAgo = document.getElementById('live-ago');

  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const selRange  = document.getElementById('range-select');
  const chkDark   = document.getElementById('dark-mode');
  const btnPNG    = document.getElementById('btn-png');
  const btnCSV    = document.getElementById('btn-csv');
  const autoRF    = document.getElementById('auto-refresh');

  const tabs   = Array.from(document.querySelectorAll('.tab'));
  const panels = Array.from(document.querySelectorAll('.tabpanel'));

  // Add decade highlight control
  const controls = document.querySelector('.controls');
  let chkDecade = null;
  if (controls && !document.getElementById('decade-highlight')) {
    const lab = document.createElement('label');
    lab.innerHTML = `Highlight decade <input id="decade-highlight" type="checkbox" checked />`;
    lab.style.marginLeft = '6px';
    controls.appendChild(lab);
    chkDecade = lab.querySelector('#decade-highlight');
  } else chkDecade = document.getElementById('decade-highlight');

  // Year summary popup
  const ys = {
    panel: document.getElementById('year-summary'),
    close: document.getElementById('ys-close'),
    year:  document.getElementById('ys-year'),
    gti:   document.getElementById('ys-gti'),
    hover: document.getElementById('ys-hover'),
    ai:    document.getElementById('ys-ai'),
  };
  let ysTimer = null;

  // Prefs
  const prefs = JSON.parse(localStorage.getItem('prefs')||'{}');
  if (typeof prefs.darkMode==='undefined'){ prefs.darkMode = false; }
  if (typeof prefs.decade==='undefined'){ prefs.decade = true; }
  document.body.classList.toggle('dark', !!prefs.darkMode);
  chkDark && (chkDark.checked = !!prefs.darkMode);
  chkDecade && (chkDecade.checked = !!prefs.decade);
  selColor  && (selColor.value  = prefs.lineColor || 'auto');
  selWeight && (selWeight.value = String(prefs.lineWeight || 3));
  selRange  && (selRange.value  = prefs.range || 'all');
  const savePrefs = ()=>localStorage.setItem('prefs', JSON.stringify(prefs));

  chkDark?.addEventListener('change', ()=>{ prefs.darkMode = !!chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); savePrefs(); plotLine(true); });
  chkDecade?.addEventListener('change', ()=>{ prefs.decade = !!chkDecade.checked; savePrefs(); plotLine(true); });
  selColor?.addEventListener('change', ()=>{ prefs.lineColor = selColor.value; savePrefs(); plotLine(true); });
  selWeight?.addEventListener('change', ()=>{ prefs.lineWeight = Number(selWeight.value); savePrefs(); plotLine(true); });
  selRange?.addEventListener('change', ()=>{ prefs.range = selRange.value; savePrefs(); plotLine(true); });

  tabs.forEach(btn=>{
    btn.addEventListener('click', (e)=>{
      e.preventDefault();
      const tgt = document.getElementById('tab-'+btn.dataset.tab);
      if(!tgt) return;
      tabs.forEach(b=>b.classList.remove('active'));
      panels.forEach(p=>p.classList.remove('active'));
      btn.classList.add('active'); tgt.classList.add('active');
      if(btn.dataset.tab==='overview' && window.Plotly){ try{ Plotly.Plots.resize('chart-plot'); }catch{} }
    }, {passive:true});
  });

  let SERIES = []; let EVENTS = {}; let SUMS = {}; let LAST_STATUS_ISO = null;

  function computeRange(years){
    const pick=(selRange&&selRange.value)||'all';
    if(!years?.length) return undefined;
    const maxYear=years[years.length-1];
    if(pick==='decade') return [maxYear-9,maxYear];
    if(pick==='20y')    return [maxYear-19,maxYear];
    if(pick==='5y')     return [maxYear-4,maxYear];
    return undefined;
  }

  function decadeShape(years, vals){
    if(!prefs.decade || !years?.length) return [];
    const lastYear=years[years.length-1];
    const start=lastYear-9, end=lastYear+0.99;
    const yMin=Math.min(...vals), yMax=Math.max(...vals);
    return [{
      type:'rect', xref:'x', yref:'y',
      x0:start, x1:end, y0:yMin, y1:yMax,
      fillcolor: cssVar('--accent') || '#2563eb',
      opacity: 0.17, line:{width:0}
    }];
  }

  function plotLine(force=false){
    const el = document.getElementById('chart-plot'); if(!el) return;
    if(!Array.isArray(SERIES)||SERIES.length===0){ el.innerHTML='<div class="warn">No GTI data found.</div>'; return; }
    el.innerHTML='';
    const years = SERIES.map(d=>d.year);
    const vals  = SERIES.map(d=>d.gti);
    const lastYear = years.at(-1), lastVal = vals.at(-1);
    kpiYear && (kpiYear.textContent = String(lastYear));
    kpiGTI  && (kpiGTI.textContent  = String(Math.round(nOr(lastVal,0))));

    const colorMap={blue:'#2563eb',green:'#059669',purple:'#7c3aed',orange:'#ea580c',red:'#dc2626'};
    const useColor=(prefs.lineColor && prefs.lineColor!=='auto')? colorMap[prefs.lineColor] : undefined;
    const useWidth= Number(prefs.lineWeight || 3);
    const anno={1918:'1918: Flu Pandemic',1945:'1945: WWII Ends',2008:'2008: Financial Crisis',2020:'2020: COVID-19'};
    const annotations=Object.keys(anno).map(k=>parseInt(k,10)).filter(y=>years.includes(y)).map(y=>({
      x:y, y: vals[years.indexOf(y)], text: anno[y], showarrow:true, arrowhead:2, ax:0, ay:-40
    }));

    const layout = {
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year', showgrid:true, gridcolor:cssVar('--grid'), range:computeRange(years)},
      yaxis:{title:'GTI Score (Unbounded)', showgrid:true, gridcolor:cssVar('--grid')},
      annotations, shapes: decadeShape(years, vals),
      paper_bgcolor:cssVar('--card'), plot_bgcolor:cssVar('--card'), font:{color:cssVar('--fg')}
    };

    Plotly.newPlot('chart-plot',[{ x:years, y:vals, type:'scatter', mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{width:useWidth, color:useColor}
    }], layout, {displayModeBar:false, responsive:true}).then(gd=>{
      if(force){ try{ Plotly.relayout(gd, layout); }catch{} }
      gd.on('plotly_click', ev=>{
        const year=ev?.points?.[0]?.x; if(!year) return;
        const val = SERIES.find(s=>s.year===year)?.gti;
        const panel=document.getElementById('year-summary');
        document.getElementById('ys-year').textContent = String(year);
        document.getElementById('ys-gti').textContent  = isNum(val)? Math.round(val) : '—';
        document.getElementById('ys-hover').textContent= (EVENTS[String(year)]||'—');
        document.getElementById('ys-ai').textContent   = (SUMS[String(year)]||'Summary coming soon.');
        panel.style.display='block';
        if(ysTimer) clearTimeout(ysTimer);
        ysTimer=setTimeout(()=>{ panel.style.display='none'; }, 10000);
      });
    }).catch(()=>{});
  }

  function renderSignals(status){
    if(!status) return;
    try{
      if(status.updated_iso){
        const t=new Date(status.updated_iso).toUTCString();
        kpiUpd && (kpiUpd.textContent=t);
        liveAgo && (liveAgo.textContent=`updated ${humanAgo(Date.now()-new Date(status.updated_iso).getTime())}`);
      }
      const last=isNum(status.gti_last)? status.gti_last : null;
      const avg =isNum(status.gti_30d_avg)? status.gti_30d_avg : null;
      if(last!==null && avg!==null && kpiDelta){
        const pct = avg ? ((last-avg)/avg)*100 : 0;
        kpiDelta.textContent = `${pct.toFixed(2)}% vs 30d`;
      } else {
        kpiDelta.textContent = '—';
      }
    }catch{}
    const ul=document.getElementById('signals-list'); if(!ul) return;
    const items=[];
    try{
      if(status.planetary){
        items.push(`<li><span class="sig-name">CO₂ (ppm)</span><span class="sig-val">${dNum(status.planetary.co2_ppm,2)}</span></li>`);
        items.push(`<li><span class="sig-name">Temp anomaly (°C)</span><span class="sig-val">${dNum(status.planetary.gistemp_anom_c,2)}</span></li>`);
      }
      if(status.food){
        const mom = isNum(status.food.fpi_mom) ? dNum(status.food.fpi_mom,2) : '—';
        items.push(`<li><span class="sig-name">Food price index</span><span class="sig-val">${dNum(status.food.fpi_last,2)} (${mom} m/m)</span></li>`);
      }
      if(status.food_access){
        const d = isNum(status.food_access.delta_pct) ? dNum(status.food_access.delta_pct,2) : '—';
        items.push(`<li><span class="sig-name">Undernourished (World)</span><span class="sig-val">${dNum(status.food_access.undernourished_pct,2)}% (${d} Δ)</span></li>`);
      }
      if(status.employment){
        const d = isNum(status.employment.delta_pct) ? dNum(status.employment.delta_pct,2) : '—';
        items.push(`<li><span class="sig-name">Unemployment (World)</span><span class="sig-val">${dNum(status.employment.unemployment_rate,2)}% (${d} Δ)</span></li>`);
      }
      if(status.sentiment){
        items.push(`<li><span class="sig-name">News tone (30d avg)</span><span class="sig-val">${dNum(status.sentiment.avg_tone_30d,2)}</span></li>`);
      }
      if(status.conflict){
        const d30 = isNum(status.conflict.delta_30) ? dNum(status.conflict.delta_30,2) : '—';
        items.push(`<li><span class="sig-name">Conflict pulse (30d)</span><span class="sig-val">${dNum(status.conflict.avg_last30,2)} (${d30} vs prev 30d)</span></li>`);
      }
      if(status.markets){
        items.push(`<li><span class="sig-name">ACWI (30d return)</span><span class="sig-val">${isNum(status.markets.acwi_ret30)? (status.markets.acwi_ret30*100).toFixed(2)+'%' : '—'}</span></li>`);
        items.push(`<li><span class="sig-name">VIX (level)</span><span class="sig-val">${dNum(status.markets.vix,2)}</span></li>`);
        items.push(`<li><span class="sig-name">Brent 30d vol</span><span class="sig-val">${isNum(status.markets.brent_vol30)? (status.markets.brent_vol30*100).toFixed(2)+'%' : '—'}</span></li>`);
      }
      ul.innerHTML = items.join('');
    }catch{}
  }

  function renderCategories(cats){
    if(!cats) return;
    const order=["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"];
    const rows=order.map(k=>({name:k,score:(cats.scores && typeof cats.scores[k]==='number')? cats.scores[k] : 50}));
    const barsEl=document.getElementById('category-bars');
    if(barsEl){
      Plotly.newPlot('category-bars',[{x:rows.map(r=>r.score),y:rows.map(r=>r.name),type:'bar',orientation:'h',hovertemplate:'%{y}: %{x}<extra></extra>'}],{
        margin:{l:170,r:20,t:10,b:30}, xaxis:{range:[0,100], showgrid:true, gridcolor:cssVar('--grid')},
        paper_bgcolor:cssVar('--card'), plot_bgcolor:cssVar('--card'), font:{color:cssVar('--fg')}
      },{displayModeBar:false,responsive:true}).catch(()=>{});
    }
    const tbl=document.getElementById('category-table');
    if(tbl){
      const cells=rows.map(r=>`<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
      tbl.innerHTML=`<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
    }
  }

  function renderSources(src){
    const listEl=document.getElementById('sources-list');
    const methEl=document.getElementById('methodology');
    if(methEl){
      const bullets = ((src && src.methodology) || []).map(m=>`<li>${m}</li>`).join('');
      methEl.innerHTML = `<h3>Methodology (snapshot)</h3><ul class="bullets">${bullets}</ul>`;
    }
    if(listEl){
      const rows = ((src && src.sources) || []).map(s =>
        `<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes||''}</td></tr>`
      ).join('');
      listEl.innerHTML = `<table><thead><tr><th>Category</th><th>Source</th><th>Notes</th></tr></thead><tbody>${rows}</tbody></table>`;
    }
  }

  async function loadAll(){
    const [gti, status, cats, src, ev, sums] = await Promise.all([
      getJSON(urls.gti()),
      getJSON(urls.status()),
      getJSON(urls.cats()),
      getJSON(urls.sources()),
      getJSON(urls.events()),
      getJSON(urls.sums())
    ]);
    const series = (gti && Array.isArray(gti.series)) ? gti.series : [];
    SERIES = series.length ? series : [{year:1900, gti:300}];
    if (gti?.updated && kpiUpd) kpiUpd.textContent = new Date(gti.updated).toUTCString();
    EVENTS = ev || {}; SUMS = sums || {};
    renderSignals(status); renderCategories(cats); renderSources(src); plotLine();
    LAST_STATUS_ISO = status?.updated_iso || LAST_STATUS_ISO;
  }

  async function poll(){
    try{
      const status=await getJSON(urls.status());
      if(status?.updated_iso){
        if(liveAgo) liveAgo.textContent = `updated ${humanAgo(Date.now() - new Date(status.updated_iso).getTime())}`;
        if(LAST_STATUS_ISO !== status.updated_iso){ await loadAll(); LAST_STATUS_ISO = status.updated_iso; }
        else { renderSignals(status); }
      }
    }catch{}
  }

  loadAll().catch(()=>{});
  setInterval(()=>{ if(autoRF?.checked) poll(); }, 60000);

  btnPNG?.addEventListener('click', async()=>{ try{ await Plotly.downloadImage('chart-plot',{format:'png',filename:'anthrometer-gti'});}catch{} });
  btnCSV?.addEventListener('click', ()=>{
    if(!Array.isArray(SERIES)||SERIES.length===0) return;
    const rows=['year,gti'].concat(SERIES.map(d=>`${d.year},${d.gti}`)).join('\n');
    const blob=new Blob([rows],{type:'text/csv'}); const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='anthrometer-gti.csv'; a.click(); URL.revokeObjectURL(url);
  });
});
