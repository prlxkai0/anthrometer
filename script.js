// script.js — stable UI (no public debug), preserves previous aesthetic/behavior
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

  const fmtN = (v, d=2) => (typeof v==='number' && isFinite(v)) ? v.toFixed(d) : '0.00';
  const nOr  = (v, d=0) => (typeof v==='number' && isFinite(v)) ? v : d;
  const cssVar = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();
  const humanAgo = (ms)=>{ const s=Math.floor(ms/1000); if(s<60)return`${s}s ago`; const m=Math.floor(s/60); if(m<60)return`${m}m ago`; const h=Math.floor(m/60); if(h<24)return`${h}h ago`; const d=Math.floor(h/24); return `${d}d ago`; };

  async function getJSON(url){ try{ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); }catch{ return null; } }

  // Elements
  const elUpdated = qs('#updated');
  const elCY      = qs('#current-year');
  const elCV      = qs('#current-gti');

  const kpiYear   = qs('#kpi-year');
  const kpiGTI    = qs('#kpi-gti');
  const kpiUpd    = qs('#kpi-updated');
  const kpiDelta  = qs('#kpi-delta');

  const selColor  = qs('#line-color');
  const selWeight = qs('#line-weight');
  const selRange  = qs('#range-select');
  const chkDark   = qs('#dark-mode');
  const btnPNG    = qs('#btn-png');
  const btnCSV    = qs('#btn-csv');
  const liveAgo   = qs('#live-ago');
  const autoRF    = qs('#auto-refresh');

  const tabs   = qsa('.tab');
  const panels = qsa('.tabpanel');

  const ys = {
    panel: qs('#year-summary'),
    close: qs('#ys-close'),
    year:  qs('#ys-year'),
    gti:   qs('#ys-gti'),
    hover: qs('#ys-hover'),
    ai:    qs('#ys-ai')
  };
  let ysTimer=null;

  // Tabs
  tabs.forEach(btn=>{
    btn.addEventListener('click', (e)=>{
      e.preventDefault();
      const tgt = qs('#tab-'+btn.dataset.tab);
      if(!tgt) return;
      tabs.forEach(b=>b.classList.remove('active'));
      panels.forEach(p=>p.classList.remove('active'));
      btn.classList.add('active'); tgt.classList.add('active');
      if(btn.dataset.tab==='overview' && window.Plotly){ try{ Plotly.Plots.resize('chart-plot'); }catch{} }
    }, {passive:true});
  });

  // Preferences
  const prefs = JSON.parse(localStorage.getItem('prefs')||'{}');
  if (typeof prefs.darkMode==='undefined'){
    const mq=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)');
    prefs.darkMode = mq? mq.matches : false;
  }
  document.body.classList.toggle('dark', !!prefs.darkMode);
  if (chkDark) chkDark.checked = !!prefs.darkMode;

  if (selColor)  selColor.value  = prefs.lineColor || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (selRange)  selRange.value  = prefs.range || 'all';

  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }

  chkDark?.addEventListener('change', ()=>{
    prefs.darkMode = !!chkDark.checked;
    document.body.classList.toggle('dark', prefs.darkMode);
    savePrefs();
    try{ Plotly.Plots.resize('chart-plot'); }catch{}
  });
  selColor?.addEventListener('change', ()=>{ prefs.lineColor=selColor.value; savePrefs(); plotLine(); });
  selWeight?.addEventListener('change', ()=>{ prefs.lineWeight=Number(selWeight.value); savePrefs(); plotLine(); });
  selRange?.addEventListener('change', ()=>{ prefs.range=selRange.value; savePrefs(); plotLine(); });

  // State
  let GTI_SERIES=[], EVENTS={}, SUMMARIES={}, lastStatusISO=null;

  function computeRange(years){
    const pick=(selRange&&selRange.value)||'all';
    if(!years?.length) return undefined;
    const maxYear=years[years.length-1];
    if(pick==='decade') return [maxYear-9,maxYear];
    if(pick==='20y')    return [maxYear-19,maxYear];
    if(pick==='5y')     return [maxYear-4,maxYear];
    return undefined;
  }

  function plotLine(){
    const el=qs('#chart-plot'); if(!el) return;
    if(!Array.isArray(GTI_SERIES)||GTI_SERIES.length===0){ el.innerHTML='<div class="warn">No GTI data found.</div>'; return; }
    el.innerHTML='';

    const years=GTI_SERIES.map(d=>d.year), vals=GTI_SERIES.map(d=>d.gti);
    const lastYear=years[years.length-1], lastVal=vals[vals.length-1];

    elCY && (elCY.textContent=String(lastYear));
    elCV && (elCV.textContent=String(Math.round(lastVal)));
    kpiYear && (kpiYear.textContent=String(lastYear));
    kpiGTI  && (kpiGTI.textContent=String(Math.round(lastVal)));

    const colorMap={blue:'#2563eb',green:'#059669',purple:'#7c3aed',orange:'#ea580c',red:'#dc2626'};
    const useColor=(prefs.lineColor && prefs.lineColor!=='auto')? colorMap[prefs.lineColor]:undefined;
    const useWidth=Number(prefs.lineWeight||3);

    const anno={1918:'1918: Flu Pandemic',1945:'1945: WWII Ends',2008:'2008: Financial Crisis',2020:'2020: COVID-19'};
    const annotations=Object.keys(anno).map(k=>parseInt(k,10)).filter(y=>years.includes(y)).map(y=>({x:y,y:vals[years.indexOf(y)],text:anno[y],showarrow:true,arrowhead:2,ax:0,ay:-40}));

    const xr=computeRange(years);

    Plotly.newPlot('chart-plot',[{
      x:years,y:vals,type:'scatter',mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{width:useWidth,color:useColor}
    }],{
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year',showgrid:true,gridcolor:cssVar('--grid'),range:xr},
      yaxis:{title:'GTI Index (Unbounded)',showgrid:true,gridcolor:cssVar('--grid')},
      annotations,
      paper_bgcolor:cssVar('--bg'),plot_bgcolor:cssVar('--card'),font:{color:cssVar('--fg')}
    },{displayModeBar:false,responsive:true}).then(gd=>{
      gd.on('plotly_hover', ev=>{
        const year=ev?.points?.[0]?.x; if(!year) return;
        const hover=EVENTS[String(year)];
        if(hover && ys.hover){
          ys.year && (ys.year.textContent=String(year));
          ys.hover.textContent=hover;
        }
      });
      gd.on('plotly_click', ev=>{
        const year=ev?.points?.[0]?.x; if(!year) return;
        let gtiVal='—';
        for (let i=0;i<GTI_SERIES.length;i++){
          if(GTI_SERIES[i].year===year){ const n=GTI_SERIES[i].gti; gtiVal=(typeof n==='number')?Math.round(n):'—'; break; }
        }
        ys.year && (ys.year.textContent=String(year));
        ys.gti  && (ys.gti.textContent=gtiVal);
        ys.hover&& (ys.hover.textContent=EVENTS[String(year)]||'—');
        ys.ai   && (ys.ai.textContent=SUMMARIES[String(year)]||'Summary coming soon.');
        if(ys.panel){ ys.panel.style.display='block'; if(ysTimer) clearTimeout(ysTimer); ysTimer=setTimeout(()=>{ys.panel.style.display='none';},10000); }
      });
    }).catch(()=>{});
  }

  function renderCategories(cats){
    if(!cats) return;
    const order=["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"];
    const rows=order.map(k=>({name:k,score:(cats.scores&&typeof cats.scores[k]==='number')?cats.scores[k]:50}));
    if(qs('#category-bars')){
      Plotly.newPlot('category-bars',[{x:rows.map(r=>r.score),y:rows.map(r=>r.name),type:'bar',orientation:'h',hovertemplate:'%{y}: %{x}<extra></extra>'}],{
        margin:{l:170,r:20,t:10,b:30},xaxis:{range:[0,100],showgrid:true,gridcolor:cssVar('--grid')},paper_bgcolor:cssVar('--bg'),plot_bgcolor:cssVar('--card'),font:{color:cssVar('--fg')}
      },{displayModeBar:false,responsive:true}).catch(()=>{});
    }
    const tbl=qs('#category-table');
    if(tbl){ const cells=rows.map(r=>`<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join(''); tbl.innerHTML=`<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`; }
  }

  function renderSources(src){
    const listEl=qs('#sources-list'); const methEl=qs('#methodology');
    if(listEl){ const rows=((src&&src.sources)||[]).map(s=>`<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes||''}</td></tr>`).join(''); listEl.innerHTML=`<table><tbody>${rows}</tbody></table>`; }
    if(methEl){ methEl.innerHTML=`<ul class="bullets">${((src&&src.methodology)||[]).map(m=>`<li>${m}</li>`).join('')}</ul>`; }
  }

  function renderSignals(status){
    if(!status) return;
    try{
      if(status.updated_iso){
        const t=new Date(status.updated_iso).toUTCString();
        kpiUpd && (kpiUpd.textContent=t);
        elUpdated && (elUpdated.textContent=t);
        liveAgo && (liveAgo.textContent=`updated ${humanAgo(Date.now()-new Date(status.updated_iso).getTime())}`);
      }
      const last=nOr(status.gti_last,null), avg=nOr(status.gti_30d_avg,null);
      if(last!==null && avg!==null && kpiDelta){
        const pct = avg ? ((last-avg)/avg)*100 : 0;
        kpiDelta.textContent = `${pct.toFixed(2)}% vs 30d`;
      }
    }catch{}

    const ul=qs('#signals-list'); if(!ul) return;
    const items=[];
    try{
      if(status.planetary){
        items.push(`<li><span class="sig-name">CO₂ (ppm)</span><span class="sig-val">${fmtN(status.planetary.co2_ppm,2)}</span></li>`);
        items.push(`<li><span class="sig-name">Temp anomaly (°C)</span><span class="sig-val">${fmtN(status.planetary.gistemp_anom_c,2)}</span></li>`);
      }
      if(status.sentiment){
        items.push(`<li><span class="sig-name">News tone (30d avg)</span><span class="sig-val">${fmtN(status.sentiment.avg_tone_30d,2)}</span></li>`);
      }
      if(status.markets){
        items.push(`<li><span class="sig-name">ACWI (30d return)</span><span class="sig-val">${(nOr(status.markets.acwi_ret30,0)*100).toFixed(2)}%</span></li>`);
        items.push(`<li><span class="sig-name">VIX (level)</span><span class="sig-val">${fmtN(status.markets.vix,2)}</span></li>`);
        items.push(`<li><span class="sig-name">Brent 30d vol</span><span class="sig-val">${(nOr(status.markets.brent_vol30,0)*100).toFixed(2)}%</span></li>`);
      }
      ul.innerHTML = items.join('');
      const foot = qs('#signals-foot');
      foot && (foot.textContent = status.note || 'Signals compare to recent baselines.');
    }catch{}
  }

  // Load & poll
  let lastStatusISO=null;
  async function loadAll(){
    const [gti,cats,src,evt,sum,status] = await Promise.all([
      getJSON(urls.gti()),
      getJSON(urls.cat()).catch(()=>null),
      getJSON(urls.src()).catch(()=>null),
      getJSON(urls.evt()).catch(()=>({})),
      getJSON(urls.sum()).catch(()=>({})),
      getJSON(urls.status()).catch(()=>null)
    ]);

    GTI_SERIES=(gti&&Array.isArray(gti.series)&&gti.series.length)? gti.series : [{year:1900,gti:300}];
    if(gti?.updated){ const ts=new Date(gti.updated).toUTCString(); elUpdated&&(elUpdated.textContent=ts); kpiUpd&&(kpiUpd.textContent=ts); }

    renderCategories(cats);
    renderSources(src);
    renderSignals(status);
    plotLine();

    lastStatusISO = status?.updated_iso || lastStatusISO;
  }

  async function poll(){
    try{
      const status=await getJSON(urls.status());
      if(status?.updated_iso){
        if(liveAgo) liveAgo.textContent=`updated ${humanAgo(Date.now()-new Date(status.updated_iso).getTime())}`;
        if(lastStatusISO!==status.updated_iso){ await loadAll(); lastStatusISO=status.updated_iso; }
        else { renderSignals(status); }
      }
    }catch{}
  }

  loadAll().catch(()=>{});
  setInterval(()=>{ if(autoRF?.checked) poll(); }, 60000);
  setInterval(async()=>{ try{ const s=await getJSON(urls.status()); if(s?.updated_iso && liveAgo) liveAgo.textContent=`updated ${humanAgo(Date.now()-new Date(s.updated_iso).getTime())}`; }catch{} }, 10000);

  // Exports
  btnPNG?.addEventListener('click', async()=>{ try{ await Plotly.downloadImage('chart-plot',{format:'png',filename:'anthrometer-gti'});}catch{} });
  btnCSV?.addEventListener('click', ()=>{
    if(!Array.isArray(GTI_SERIES)||GTI_SERIES.length===0) return;
    const rows=['year,gti'].concat(GTI_SERIES.map(d=>`${d.year},${d.gti}`)).join('\n');
    const blob=new Blob([rows],{type:'text/csv'}); const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='anthrometer-gti.csv'; a.click(); URL.revokeObjectURL(url);
  });
});