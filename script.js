// script.js — stabilized UI (null-safe, tabs, dark mode, debug tile)
document.addEventListener('DOMContentLoaded', () => {
  const bust = () => Date.now();
  const urls = {
    gti:    () => `./data/gti.json?t=${bust()}`,
    cat:    () => `./data/categories.json?t=${bust()}`,
    src:    () => `./data/sources.json?t=${bust()}`,
    evt:    () => `./data/events.json?t=${bust()}`,
    sum:    () => `./data/summaries.json?t=${bust()}`,
    status: () => `./data/status.json?t=${bust()}`
  };

  // elements
  const kpiYear=document.getElementById('kpi-year');
  const kpiGTI=document.getElementById('kpi-gti');
  const kpiUpd=document.getElementById('kpi-updated');
  const kpiDelta=document.getElementById('kpi-delta');
  const liveAgo=document.getElementById('live-ago');
  const selColor=document.getElementById('line-color');
  const selWeight=document.getElementById('line-weight');
  const selRange=document.getElementById('range-select');
  const chkDark=document.getElementById('dark-mode');
  const btnPNG=document.getElementById('btn-png');
  const btnCSV=document.getElementById('btn-csv');

  // tabs
  document.querySelectorAll('.tab').forEach(el=>{
    el.addEventListener('click', (e)=>{
      e.preventDefault();
      document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('active'));
      el.classList.add('active');
      const panel = document.getElementById('tab-'+el.dataset.tab);
      if(panel) panel.classList.add('active');
      if (el.dataset.tab==='overview' && window.Plotly) { try{ Plotly.Plots.resize('chart-plot'); }catch(e){} }
    });
  });

  // prefs
  const prefs = JSON.parse(localStorage.getItem('prefs')||'{}');
  if (typeof prefs.darkMode==='undefined') {
    const mq=window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    prefs.darkMode = mq ? mq.matches : true;
  }
  document.body.classList.toggle('dark', !!prefs.darkMode);
  if (chkDark) chkDark.checked = !!prefs.darkMode;
  if (selColor)  selColor.value  = prefs.lineColor || 'auto';
  if (selWeight) selWeight.value = String(prefs.lineWeight || 3);
  if (selRange)  selRange.value  = prefs.range || 'all';

  function savePrefs(){ localStorage.setItem('prefs', JSON.stringify(prefs)); }
  function cssVar(name){ return getComputedStyle(document.body).getPropertyValue(name).trim(); }
  function humanAgo(ms){ const s=Math.floor(ms/1000); if(s<60)return`${s}s ago`; const m=Math.floor(s/60); if(m<60)return`${m}m ago`; const h=Math.floor(m/60); if(h<24)return`${h}h ago`; const d=Math.floor(h/24); return `${d}d ago`; }

  chkDark?.addEventListener('change', ()=>{ prefs.darkMode=chkDark.checked; document.body.classList.toggle('dark', prefs.darkMode); savePrefs(); });
  selColor?.addEventListener('change', ()=>{ prefs.lineColor=selColor.value; savePrefs(); plotLine(); });
  selWeight?.addEventListener('change', ()=>{ prefs.lineWeight=Number(selWeight.value); savePrefs(); plotLine(); });
  selRange?.addEventListener('change', ()=>{ prefs.range=selRange.value; savePrefs(); plotLine(); });

  // state
  let GTI_SERIES=[], EVENTS={}, SUMMARIES={}, lastStatusISO=null;

  // fetch helper
  async function getJSON(url){ try{ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); } catch{ return null; } }

  // plot
  function plotLine(){
    const el = document.getElementById('chart-plot');
    if(!el) return;
    if(!GTI_SERIES || GTI_SERIES.length===0){ el.innerHTML='<div class="warn">No GTI data found.</div>'; return; }
    const years=GTI_SERIES.map(d=>d.year), vals=GTI_SERIES.map(d=>d.gti);
    const lastYear=years[years.length-1]||'—', lastVal=vals[vals.length-1]||0;
    kpiYear && (kpiYear.textContent=String(lastYear));
    kpiGTI && (kpiGTI.textContent=String(Math.round(lastVal)));

    const prefs = JSON.parse(localStorage.getItem('prefs')||'{}');
    const colorMap={blue:'#2563eb',green:'#059669',purple:'#7c3aed',orange:'#ea580c',red:'#dc2626'};
    const useColor=(prefs.lineColor && prefs.lineColor!=='auto')?colorMap[prefs.lineColor]:undefined;
    const useWidth=Number(prefs.lineWeight||3);

    const sel = document.getElementById('range-select'); const pick = (sel && sel.value) || 'all';
    const xr = (pick==='decade')?[lastYear-9,lastYear] : (pick==='20y')?[lastYear-19,lastYear] : (pick==='5y')?[lastYear-4,lastYear] : undefined;

    Plotly.newPlot('chart-plot',[{
      x:years, y:vals, type:'scatter', mode:'lines', line:{width:useWidth,color:useColor},
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>'
    }],{
      margin:{l:60,r:20,t:40,b:40}, xaxis:{title:'Year',gridcolor:cssVar('--grid'),range:xr},
      yaxis:{title:'GTI (unbounded)',gridcolor:cssVar('--grid')},
      paper_bgcolor:cssVar('--bg'), plot_bgcolor:cssVar('--card'), font:{color:cssVar('--fg')}
    },{displayModeBar:false,responsive:true}).catch(()=>{});
  }

  // details
  function renderCategories(cats){
    if(!cats) return;
    const order=["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"];
    const rows=order.map(k=>({name:k,score:(cats.scores&&typeof cats.scores[k]==='number')?cats.scores[k]:50}));
    if (document.getElementById('category-bars')) {
      Plotly.newPlot('category-bars',[{x:rows.map(r=>r.score),y:rows.map(r=>r.name),type:'bar',orientation:'h'}],{
        margin:{l:170,r:20,t:10,b:30}, xaxis:{range:[0,100],gridcolor:cssVar('--grid')},
        paper_bgcolor:cssVar('--bg'), plot_bgcolor:cssVar('--card'), font:{color:cssVar('--fg')}
      },{displayModeBar:false,responsive:true}).catch(()=>{});
    }
    const tbl=document.getElementById('category-table');
    if(tbl){ tbl.innerHTML='<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('')+'</tbody></table>'; }
  }

  // sources
  function renderSources(src){
    const meth=document.getElementById('methodology'); const list=document.getElementById('sources-list');
    if(meth) meth.innerHTML = `<ul class="bullets">${((src&&src.methodology)||[]).map(m=>`<li>${m}</li>`).join('')}</ul>`;
    if(list) list.innerHTML = `<table><tbody>${((src&&src.sources)||[]).map(s=>`<tr><td>${s.category}</td><td><a href="${s.link}" target="_blank" rel="noopener">${s.name}</a></td><td>${s.notes||''}</td></tr>`).join('')}</tbody></table>`;
  }

  // signals + debug
  function renderSignals(status){
    if(!status) return;
    const ago = status.updated_iso ? humanAgo(Date.now()-new Date(status.updated_iso).getTime()) : '—';
    liveAgo && (liveAgo.textContent = `updated ${ago}`);

    // KPI delta
    if(typeof status.gti_last==='number' && typeof status.gti_30d_avg==='number'){
      const pct = status.gti_30d_avg ? ((status.gti_last-status.gti_30d_avg)/status.gti_30d_avg)*100 : 0;
      kpiDelta && (kpiDelta.textContent = `${pct.toFixed(2)}% vs 30d`);
    }

    const ul=document.getElementById('signals-list'); if(!ul) return;
    const fmt = (v,d=2)=> (typeof v==='number' ? v.toFixed(d) : '0.00');
    const items=[];
    if(status.planetary){
      items.push(`<li><span class="sig-name">CO₂ (ppm)</span><span class="sig-val">${fmt(status.planetary.co2_ppm,2)}</span></li>`);
      items.push(`<li><span class="sig-name">Temp anomaly (°C)</span><span class="sig-val">${fmt(status.planetary.gistemp_anom_c,2)}</span></li>`);
    }
    if(status.sentiment){
      items.push(`<li><span class="sig-name">News tone (30d avg)</span><span class="sig-val">${fmt(status.sentiment.avg_tone_30d,2)}</span></li>`);
    }
    if(status.markets){
      items.push(`<li><span class="sig-name">ACWI (30d return)</span><span class="sig-val">${((status.markets.acwi_ret30||0)*100).toFixed(2)}%</span></li>`);
      items.push(`<li><span class="sig-name">VIX (level)</span><span class="sig-val">${fmt(status.markets.vix,2)}</span></li>`);
      items.push(`<li><span class="sig-name">Brent 30d vol</span><span class="sig-val">${((status.markets.brent_vol30||0)*100).toFixed(2)}%</span></li>`);
    }
    ul.innerHTML = items.join('');

    // Debug tile
    const pre=document.getElementById('debug-pre'); const a=document.getElementById('debug-link');
    if(pre) pre.textContent = JSON.stringify(status, null, 2);
    if(a) a.href = `./data/status.json?t=${bust()}`;
  }

  // load & poll
  async function loadAll(){
    const [gti, cats, src, evt, sum, status] = await Promise.all([
      getJSON(urls.gti()), getJSON(urls.cat()), getJSON(urls.src()).catch(()=>null),
      getJSON(urls.evt()).catch(()=>({})), getJSON(urls.sum()).catch(()=>({})),
      getJSON(urls.status()).catch(()=>null)
    ]);
    // series
    const series = (gti && Array.isArray(gti.series)) ? gti.series : [];
    // hard fallback so page never blanks
    GTI_SERIES = series.length ? series : [{year:1900,gti:300}];
    renderCategories(cats||null);
    renderSources(src||{sources:[],methodology:[]});
    renderSignals(status||{});
    plotLine();
  }

  loadAll();

  // auto refresh
  setInterval(async()=>{
    if (!document.getElementById('auto-refresh')?.checked) return;
    try{
      const status = await getJSON(urls.status());
      renderSignals(status||{});
    }catch{}
  }, 60000);

  // exports
  btnPNG?.addEventListener('click', async()=>{ try{ await Plotly.downloadImage('chart-plot',{format:'png',filename:'anthrometer-gti'});}catch(e){} });
  btnCSV?.addEventListener('click', ()=>{
    if(!GTI_SERIES || GTI_SERIES.length===0) return;
    const rows=['year,gti'].concat(GTI_SERIES.map(d=>`${d.year},${d.gti}`)).join('\n');
    const blob=new Blob([rows],{type:'text/csv'}); const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='anthrometer-gti.csv'; a.click(); URL.revokeObjectURL(url);
  });
});
