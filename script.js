document.addEventListener('DOMContentLoaded', () => {
  const bust = () => Date.now();
  const urls = {
    gti:    () => `./data/gti.json?t=${bust()}`,
    status: () => `./data/status.json?t=${bust()}`
  };

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
  const signalsUL = document.getElementById('signals-list');

  const cssVar = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();
  const fmtN = (v,d=2) => (typeof v==='number' && isFinite(v)) ? v.toFixed(d) : '0.00';
  const nOr  = (v,d=0) => (typeof v==='number' && isFinite(v)) ? v : d;
  const humanAgo = (ms)=>{const s=Math.floor(ms/1000); if(s<60)return`${s}s ago`; const m=Math.floor(s/60); if(m<60)return`${m}m ago`; const h=Math.floor(m/60); if(h<24)return`${h}h ago`; const d=Math.floor(h/24); return `${d}d ago`;};

  async function getJSON(url){ try{ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); }catch{ return null; } }

  // Preferences (old behavior)
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

  chkDark?.addEventListener('change', ()=>{ prefs.darkMode = !!chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); savePrefs(); try{ Plotly.Plots.resize('chart-plot'); }catch{} });
  selColor?.addEventListener('change', ()=>{ prefs.lineColor=selColor.value; savePrefs(); plotLine(); });
  selWeight?.addEventListener('change', ()=>{ prefs.lineWeight=Number(selWeight.value); savePrefs(); plotLine(); });
  selRange?.addEventListener('change', ()=>{ prefs.range=selRange.value; savePrefs(); plotLine(); });


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
    const el = document.getElementById('chart-plot'); if(!el) return;
    if(!Array.isArray(SERIES) || SERIES.length===0){
      el.innerHTML = '<div class="warn">No GTI data found.</div>'; return;
    }
    el.innerHTML = '';

    const years = SERIES.map(d=>d.year), vals = SERIES.map(d=>d.gti);
    const lastYear = years[years.length-1]; const lastVal = vals[vals.length-1];

    if (kpiYear) kpiYear.textContent = String(lastYear);
    if (kpiGTI)  kpiGTI.textContent  = String(Math.round(lastVal));

    const colorMap={blue:'#2563eb',green:'#059669',purple:'#7c3aed',orange:'#ea580c',red:'#dc2626'};
    const useColor=(prefs.lineColor && prefs.lineColor!=='auto')? colorMap[prefs.lineColor] : undefined;
    const useWidth= Number(prefs.lineWeight || 3);

    const anno={1918:'1918: Flu Pandemic',1945:'1945: WWII Ends',2008:'2008: Financial Crisis',2020:'2020: COVID-19'};
    const annotations=Object.keys(anno).map(k=>parseInt(k,10)).filter(y=>years.includes(y)).map(y=>({
      x:y, y: vals[years.indexOf(y)], text: anno[y], showarrow:true, arrowhead:2, ax:0, ay:-40
    }));

    const xr = computeRange(years);

    Plotly.newPlot('chart-plot',[{
      x: years, y: vals, type:'scatter', mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{width:useWidth, color:useColor}
    }],{
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year', showgrid:true, gridcolor:cssVar('--grid'), range:xr},
      yaxis:{title:'GTI Index (Unbounded)', showgrid:true, gridcolor:cssVar('--grid')},
      annotations,
      paper_bgcolor:cssVar('--bg'), plot_bgcolor:cssVar('--card'), font:{color:cssVar('--fg')}
    }, {displayModeBar:false, responsive:true}).catch(()=>{});
  }

  function renderSignals(status){
    if(!status) return;
    try{
      if(status.updated_iso){
        const iso = status.updated_iso;
        if (kpiUpd) kpiUpd.textContent = new Date(iso).toUTCString();
        if (liveAgo) liveAgo.textContent = `updated ${humanAgo(Date.now() - new Date(iso).getTime())}`;
      }
      if (typeof status.gti_last==='number' && typeof status.gti_30d_avg==='number' && kpiDelta){
        const pct = status.gti_30d_avg ? ((status.gti_last - status.gti_30d_avg)/status.gti_30d_avg)*100 : 0;
        kpiDelta.textContent = `${pct.toFixed(2)}% vs 30d`;
      }
      if (signalsUL){
        const items=[];
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
        signalsUL.innerHTML = items.join('');
      }
    }catch{}
  }

  // Load + poll
  async function loadAll(){
    const [gti, status] = await Promise.all([ getJSON(urls.gti()), getJSON(urls.status()) ]);

    // gti.json fallback
    let series = (gti && Array.isArray(gti.series)) ? gti.series : [];
    SERIES = series.length ? series : [{year:1900, gti:300}];
    if (gti?.updated && kpiUpd) kpiUpd.textContent = new Date(gti.updated).toUTCString();

    renderSignals(status);
    plotLine();

    LAST_STATUS_ISO = status?.updated_iso || LAST_STATUS_ISO;
  }

  async function poll(){
    try{
      const status=await getJSON(urls.status());
      if(status?.updated_iso){
        if(liveAgo) liveAgo.textContent=`updated ${humanAgo(Date.now() - new Date(status.updated_iso).getTime())}`;
        if(LAST_STATUS_ISO!==status.updated_iso){
          await loadAll();
          LAST_STATUS_ISO = status.updated_iso;
        }else{
          renderSignals(status);
        }
      }
    }catch{}
  }

  loadAll().catch(()=>{});
  setInterval(()=>{ if(autoRF?.checked) poll(); }, 60000);

  // Exports
  btnPNG?.addEventListener('click', async()=>{ try{ await Plotly.downloadImage('chart-plot',{format:'png',filename:'anthrometer-gti'});}catch{} });
  btnCSV?.addEventListener('click', ()=>{
    if(!Array.isArray(SERIES)||SERIES.length===0) return;
    const rows=['year,gti'].concat(SERIES.map(d=>`${d.year},${d.gti}`)).join('\n');
    const blob=new Blob([rows],{type:'text/csv'}); const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='anthrometer-gti.csv'; a.click(); URL.revokeObjectURL(url);
  });
});
