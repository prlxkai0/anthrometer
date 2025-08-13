document.addEventListener('DOMContentLoaded', () => {
  const dataUrl = `./data/gti.json?t=${Date.now()}`;
  const catUrl  = `./data/categories.json?t=${Date.now()}`;

  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // Simple tabs
  document.querySelectorAll('.tab').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
    });
  });

  async function getJSON(url){
    const r = await fetch(url, {cache:'no-store'});
    if(!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
    return r.json();
  }

  function renderLine(series){
    const years = series.map(d=>d.year);
    const vals  = series.map(d=>d.gti);

    // current readout
    elCY.textContent = years.at(-1) ?? '—';
    elCV.textContent = (vals.at(-1) != null) ? Math.round(vals.at(-1)) : '—';

    const trace = {
      x: years, y: vals, type:'scatter', mode:'lines',
      hovertemplate:'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line:{width:3}
    };

    const annYears = [1918,1945,2008,2020].filter(y => years.includes(y));
    const annotations = annYears.map(y => ({
      x:y, y: vals[years.indexOf(y)], text:String(y), showarrow:true, arrowhead:2
    }));

    Plotly.newPlot('chart', [trace], {
      margin:{l:60,r:20,t:50,b:40},
      title:'Good Times Index (GTI) — 1900 to 2025',
      xaxis:{title:'Year', showgrid:true, gridcolor:'#e2e8f0'},
      yaxis:{title:'GTI Index (Unbounded)', showgrid:true, gridcolor:'#e2e8f0'},
      annotations
    }, {displayModeBar:false, responsive:true});
  }

  function renderCategories(cats){
    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const rows = order.map(k => ({
      name:k,
      score: cats?.scores?.[k] ?? 50
    }));

    Plotly.newPlot('category-bars', [{
      x: rows.map(r=>r.score),
      y: rows.map(r=>r.name),
      type:'bar',
      orientation:'h',
      hovertemplate:'%{y}: %{x}<extra></extra>'
    }], {
      margin:{l:170,r:20,t:10,b:30},
      xaxis:{range:[0,100], showgrid:true, gridcolor:'#e2e8f0'}
    }, {displayModeBar:false, responsive:true});

    const tbl = ['<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>']
      .concat(rows.map(r=>`<tr><td>${r.name}</td><td>${r.score}</td></tr>`))
      .concat(['</tbody></table>']).join('');
    document.getElementById('category-table').innerHTML = tbl;
  }

  (async () => {
    const [gti, cats] = await Promise.all([getJSON(dataUrl), getJSON(catUrl).catch(()=>null)]);
    if (elUpdated && gti?.updated) elUpdated.textContent = new Date(gti.updated).toUTCString();
    renderLine(gti?.series || []);
    if (cats) renderCategories(cats);
  })().catch(err => {
    console.error(err);
    document.getElementById('chart').innerHTML =
      `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
        Failed to load data: ${String(err)}
       </div>`;
  });
});
