// script.js — AnthroMeter UI (debug tile + no changelog + saner signal chips)
document.addEventListener('DOMContentLoaded', () => {
  const bust = () => Date.now();
  const urls = {
    gti:    () => `./data/gti.json?t=${bust()}`,
    cat:    () => `./data/categories.json?t=${bust()}`,
    src:    () => `./data/sources.json?t=${bust()}`,
    // chg removed
    evt:    () => `./data/events.json?t=${bust()}`,
    sum:    () => `./data/summaries.json?t=${bust()}`,
    status: () => `./data/status.json?t=${bust()}`
  };

  // Legacy header
  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // KPI card
  const kpiYear  = document.getElementById('kpi-year');
  const kpiGTI   = document.getElementById('kpi-gti');
  const kpiUpd   = document.getElementById('kpi-updated');
  const kpiDelta = document.getElementById('kpi-delta');

  // Controls
  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const chkDark   = document.getElementById('dark-mode');
  const selRange  = document.getElementById('range-select');
  const btnPNG    = document.getElementById('btn-png');
  const btnCSV    = document.getElementById('btn-csv');

  // LIVE strip
  const liveAgo    = document.getElementById('live-ago');
  const autoToggle = document.getElementById('auto-refresh');

  // Signals
  const signalsList = document.getElementById('signals-list');
  const signalsFoot = document.getElementById('signals-foot');

  // Year summary panel
  const CHART_ID = 'chart-plot';
  const ys = {
    panel: document.getElementById('year-summary'),
    close: document.getElementById('ys-close'),
    year:  document.getElementById('ys-year'),
    gti:   document.getElementById('ys-gti'),
    hover: document.getElementById('ys-hover'),
    ai:    document.getElementById('ys-ai')
  };
  let ysTimer=null;
  function showSummary(){ if(!ys.panel) return; ys.panel.style.display='block'; if(ysTimer) clearTimeout(ysTimer); ysTimer=setTimeout(()=>{ys.panel.style.display='none';},10000); }

  // Tabs
  document.querySelectorAll('.tab').forEach(btn=>{
    btn.addEventListener('click', (e)=>{
      e.preventDefault();
      const target = document.getElementById('tab-'+btn.dataset.tab);
      if(!target) return;
      document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('active'));
      btn.classList.add('active'); target.classList.add('active');
      if(btn.dataset.tab==='overview' && window.Plotly){ try{ Plotly.Plots.resize(CHART_ID);}catch(e){} }
    }, {passive:true});
  });

  // Helpers
  async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status} ${url}`); return r.json(); }
  function cssVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }
  function computeRange(years){
    const sel = document.getElementById('range-select');
    const pick = (sel && sel.value) || 'all';
    if(!years || !years.length) return undefined;
    const maxYear = years[years.length-1];
    if (pick === 'decade') return [maxYear-9, maxYear];
    if (pick === '20y') return [maxYear-19, maxYear];
    if (pick === '5y') return [maxYear-4, maxYear];
    return undefined;
  }
  function msAgo(iso){ const t=new Date(iso).getTime(); return Date.now()-(isNaN(t)?Date.now():t); }
  function humanAgo(ms){ const s=Math.floor(ms/1000); if(s<60) return `${s}s ago`; const m=Math.floor(s/60); if(m<60) return `${m}m ago`; const h=Math.floor(m/60); if(h<24) return `${h}h ago`; const d=Math.floor(h/24); return `${d}d ago`; }

  // State
  let GTI_SERIES=[], EVENTS={}, SUMMARIES={}, lastStatusISO=null;

  // Plot
  function plotLine(){
    const el=document.getElementById(CHART_ID); if(!el) return;
    if(!Array.isArray(GTI_SERIES)||GTI_SERIES.length===0){ el.innerHTML='<div class="warn">No GTI data found.</div>'; return; } else { el.innerHTML=''; }
    const years=GTI_SERIES.map(d=>d.year), vals=GTI_SERIES.map(d=>d.gti);
    const lastYear=years[years.length-1], lastVal=vals[vals.length-1];
    if (elCY) elCY.textContent=lastYear; if (elCV) elCV.textContent=Math.round(lastVal);
    if (kpiYear) kpiYear.textContent=String(lastYear); if (kpiGTI) kpiGTI.textContent=String(Math.round(lastVal));

    const prefs=JSON.parse(localStorage.getItem('prefs')||'{}');
    const colorMap={blue:'#2563eb',green:'#059669',purple:'#7c3aed',orange:'#ea580c',red:'#dc2626'};
    const useColor=(prefs.lineColor&&prefs.lineColor!=='auto')?colorMap[prefs.lineColor]:undefined;
    const useWidth=Number(prefs.lineWeight||3);

    const anno={1918:'1918: Flu Pandemic',1945:'1945: WWII Ends',2008:'2008: Financial Crisis',2020:'2020: COVID-19'};
    const annotations=Object.keys(anno).map(k=>parseInt(k,10)).filter(y=>years.includes(y)).map(y=>({x:y,y:vals[years.indexOf(y)],text:anno[y],showarrow:true,arrowhead:2,ax:0,ay:-40}));

    const xr=computeRange(years);
    const shapes=(!xr)?[{type:'rect',xref:'x',yref:'paper',x0:years[years.length-1]-9,x1:years[years.length-1],y0:0,y1:1,fillcolor:(document.body.classList.contains('dark')?'rgba(148,163,184,0.10)':'rgba(2,132,199,0.08)'),line:{width:0}}]:[];

    Plotly.newPlot(CHART_ID,[{x:years,y:vals,type:'scatter',mode:'lines',hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',line:{width:useWidth,color:useColor}}],{
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year',showgrid:true,gridcolor:cssVar('--grid'),range:xr},
      yaxis:{title:'GTI Index (Unbounded)',showgrid:true,gridcolor:cssVar('--grid')},
      annotations,shapes,
      paper_bgcolor:cssVar('--bg'),plot_bgcolor:cssVar('--card'),font:{color:cssVar('--fg')}
    },{displayModeBar:false,responsive:true}).then(gd=>{
      gd.on('plotly_hover', ev=>{ const year=ev?.points?.[0]?.x; if(!year) return; const hover=EVENTS[String(year)]; if(hover&&ys.hover){ ys.year&&(ys.year.textContent=String(year)); ys.hover.textContent=hover; }});
      gd.on('plotly_click', ev=>{ const year=ev?.points?.[0]?.x; if(!year) return; let gtiVal='—'; for(let i=0;i<GTI_SERIES.length;i++){ if(GTI_SERIES[i].year===year){ const n=GTI_SERIES[i].gti; gtiVal=(typeof n==='number')?Math.round(n):'—'; break; } } ys.year&&(ys.year.textContent=String(year)); ys.gti&&(ys.gti.textContent=gtiVal); ys.hover&&(ys.hover.textContent=EVENTS[String(year)]||'—'); ys.ai&&(ys.ai.textContent=SUMMARIES[String(year)]||'Summary coming soon.'); showSummary(); });
    }).catch(console.error);
  }

  // Details
  function renderCategories(cats){
    if(!cats) return;
    const order=["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"];
    const rows=order.map(k=>({name:k,score:(cats.scores&&typeof cats.scores[k]==='number')?cats.scores[k]:50}));
    if(document.getElementById('category-bars')){
      Plotly.newPlot('category-bars',[{x:rows.map(r=>r.score),y:rows.map(r=>r.name),type:'bar',orientation:'h',hovertemplate:'%{y}: %{x}<extra></extra>'}],{
        margin:{l:170,r:20,t:10,b:30},xaxis:{range:[0,100],showgrid:true,gridcolor:cssVar('--grid')},paper_bgcolor:cssVar('--bg'),plot_bgcolor:cssVar('--card'),font:{color:cssVar('--fg')}
      },{displayModeBar:false,responsive:true}).catch(()=>{});
    }
    const tbl=document.getElementById('category-table');
    if(tbl){ const cells=rows.map(r=>`<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join(''); tbl.innerHTML=`<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`; }
  }

  // Sources
  function renderSources(src){
    const listEl=document.getElementById('sources-list'); const methEl=document.getElementById('methodology');
    if(listEl){ const rows=((src&&src.sources)||[]).map(s=>`<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes||''}</td></tr>`).join(''); listEl.innerHTML=`<table><tbody>${rows}</tbody></table>`; }
    if(methEl){ methEl.innerHTML=`<ul class="bullets">${((src&&src.methodology)||[]).map(m=>`<li>${m}</li>`).join('')}</ul>`; }
  }

  // Today’s Signals
  function renderSignals(status){
    if(status?.updated_iso){ const t=new Date(status.updated_iso).toUTCString(); if(kpiUpd) kpiUpd.textContent=t; if(elUpdated) elUpdated.textContent=t; if(liveAgo) liveAgo.textContent=`updated ${humanAgo(msAgo(status.updated_iso))}`; }

    // KPI delta vs 30d avg
    if (typeof status?.gti_last==='number' && typeof status?.gti_30d_avg==='number') {
      const last=status.gti_last, avg=status.gti_30d_avg;
      const pct = avg ? ((last-avg)/avg)*100 : 0;
      const arrow = pct>=0?'▲':'▼'; const cls=pct>=0?'up':'down';
      if (kpiDelta) kpiDelta.innerHTML = `<span class="sig-diff ${cls}">${arrow} ${pct.toFixed(2)}% vs 30d</span>`;
    }

    if(!signalsList || !status) return;
    const items=[];

    // helpers
    const fmt = (v, d=2) => (typeof v==='number' ? v.toFixed(d) : '0.00');

    // Planetary (delta shows direction; value shows level)
    if (status.planetary) {
      items.push(`<li><span class="sig-name">CO₂ (ppm)</span><span class="sig-val">${fmt(status.planetary.co2_ppm,2)}</span></li>`);
      items.push(`<li><span class="sig-name">Temp anomaly (°C)</span><span class="sig-val">${fmt(status.planetary.gistemp_anom_c,2)}</span></li>`);
    }
    // Sentiment (level only)
    if (status.sentiment) {
      items.push(`<li><span class="sig-name">News tone (30d avg)</span><span class="sig-val">${fmt(status.sentiment.avg_tone_30d,2)}</span></li>`);
    }
    // Markets (levels; no bogus deltas)
    if (status.markets) {
      items.push(`<li><span class="sig-name">ACWI (30d return)</span><span class="sig-val">${( (status.markets.acwi_ret30||0)*100 ).toFixed(2)}%</span></li>`);
      items.push(`<li><span class="sig-name">VIX (level)</span><span class="sig-val">${fmt(status.markets.vix,2)}</span></li>`);
      items.push(`<li><span class="sig-name">Brent 30d vol</span><span class="sig-val">${( (status.markets.brent_vol30||0)*100 ).toFixed(2)}%</span></li>`);
    }

    signalsList.innerHTML = items.join('');
    if (signalsFoot) signalsFoot.textContent = status.note || 'Signals compare to recent baselines.';
  }

  // DEBUG TILE — shows exactly what the page read from data/status.json
  function renderDebug(status){
    try{
      const parent = document.getElementById('overview') || document.body;
      let box = document.getElementById('debug-tile');
      if(!box){
        box = document.createElement('details');
        box.id='debug-tile';
        box.open=false;
        box.innerHTML = `<summary>Debug: status.json (click to expand)</summary>
<pre id="debug-pre" style="white-space:pre-wrap;overflow:auto;max-height:240px;margin-top:8px;"></pre>
<div style="margin-top:8px;font-size:12px;">
  <a id="debug-link" href="./data/status.json" target="_blank" rel="noopener">Open raw status.json</a>
</div>`;
        // place under Today's Signals container if present
        const sigWrap = document.getElementById('signals');
        (sigWrap ? sigWrap.parentNode : parent).appendChild(box);
      }
      const pre = document.getElementById('debug-pre');
      if(pre) pre.textContent = JSON.stringify(status || {}, null, 2);
      const a = document.getElementById('debug-link');
      if(a) a.href = `./data/status.json?t=${bust()}`;
    }catch(e){ console.error('debug tile error', e); }
  }

  // Preferences & controls
  const prefs = JSON.parse(localStorage.getItem('prefs')||'{}');
  if (typeof prefs.darkMode==='undefined'){ const mq=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)'); prefs.darkMode = mq? mq.matches : false; }
  document.body.classList.toggle('dark', !!prefs.darkMode);
  const selColor  = document.getElementById('line-color');
  const selWeight = document.getElementById('line-weight');
  const selRange  = document.getElementById('range-select');
  const chkDark   = document.getElementById('dark-mode');

  if (selColor)  selColor.value  = prefs.lineColor  || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (selRange)  selRange.value  = prefs.range || 'all';
  if (chkDark)   chkDark.checked = !!prefs.darkMode;

  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }
  function replot(){ plotLine(); }

  selColor  && selColor.addEventListener('change', ()=>{ prefs.lineColor=selColor.value; savePrefs(); replot(); });
  selWeight && selWeight.addEventListener('change', ()=>{ prefs.lineWeight=Number(selWeight.value); savePrefs(); replot(); });
  selRange  && selRange.addEventListener('change', ()=>{ prefs.range=selRange.value; savePrefs(); replot(); });
  chkDark   && chkDark.addEventListener('change', ()=>{ prefs.darkMode=chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); savePrefs(); replot(); });

  // Export buttons
  const btnPNG=document.getElementById('btn-png'), btnCSV=document.getElementById('btn-csv');
  btnPNG && btnPNG.addEventListener('click', async()=>{ try{ await Plotly.downloadImage(CHART_ID,{format:'png',filename:'anthrometer-gti'}); }catch(e){} });
  btnCSV && btnCSV.addEventListener('click', ()=>{ if(!Array.isArray(GTI_SERIES)||GTI_SERIES.length===0) return; const rows=['year,gti'].concat(GTI_SERIES.map(d=>`${d.year},${d.gti}`)).join('\n'); const blob=new Blob([rows],{type:'text/csv'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='anthrometer-gti.csv'; a.click(); URL.revokeObjectURL(url); });

  // Summary close
  ys.close && ys.close.addEventListener('click', ()=>{ if(ys.panel) ys.panel.style.display='none'; if(ysTimer) clearTimeout(ysTimer); });
  document.addEventListener('keydown', (e)=>{ if(e.key==='Escape' && ys.panel && ys.panel.style.display!=='none'){ ys.panel.style.display='none'; if(ysTimer) clearTimeout(ysTimer);} });

  // Load + polling
  async function loadAll(){
    const [gti,cats,src,evt,sum,status] = await Promise.all([
      getJSON(urls.gti()),
      getJSON(urls.cat()).catch(()=>null),
      getJSON(urls.src()).catch(()=>null),
      getJSON(urls.evt()).catch(()=>({})),
      getJSON(urls.sum()).catch(()=>({})),
      getJSON(urls.status()).catch(()=>null)
    ]);
    GTI_SERIES=(gti&&gti.series)||[];
    EVENTS=evt||{}; SUMMARIES=sum||{};

    if (gti?.updated) { const ts=new Date(gti.updated).toUTCString(); if(elUpdated) elUpdated.textContent=ts; if(kpiUpd) kpiUpd.textContent=ts; }

    plotLine(); renderCategories(cats); renderSources(src);
    renderSignals(status); renderDebug(status);
    lastStatusISO = status?.updated_iso || lastStatusISO;
  }

  async function poll(){
    try{
      const status = await getJSON(urls.status());
      if (status?.updated_iso){
        if(liveAgo) liveAgo.textContent=`updated ${humanAgo(msAgo(status.updated_iso))}`;
        if(lastStatusISO !== status.updated_iso){ await loadAll(); lastStatusISO = status.updated_iso; }
        else { renderDebug(status); }
      }
    }catch{}
  }

  const autoToggleEl = document.getElementById('auto-refresh');
  autoToggleEl?.addEventListener('change', ()=>{ /* polling gate */ });

  loadAll().catch(console.error);
  setInterval(()=>{ if(document.getElementById('auto-refresh')?.checked) poll(); }, 60000);
  setInterval(async()=>{ try{ const s=await getJSON(urls.status()); if(s?.updated_iso && liveAgo) liveAgo.textContent=`updated ${humanAgo(msAgo(s.updated_iso))}`; }catch{} }, 10000);
});
