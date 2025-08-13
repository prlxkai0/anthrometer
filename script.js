document.addEventListener('DOMContentLoaded', () => {
  const dataUrl = `./data/gti.json?t=${Date.now()}`;
  const catUrl  = `./data/categories.json?t=${Date.now()}`;

  const elUpdated = document.getElementById('updated');
  const elCY = document.getElementById('current-year');
  const elCV = document.getElementById('current-gti');

  // --- Tabs (robust) ---
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.tabpanel');
  tabs.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById('tab-' + btn.dataset.tab);
      if (!target) return;
      tabs.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      target.classList.add('active');
    }, { passive: true });
  });

  async function getJSON(url){
    const r = await fetch(url, {cache:'no-store'});
    if(!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
    return r.json();
  }

  function renderLine(series){
    if (!Array.isArray(series) || series.length === 0) {
      document.getElementById('chart').innerHTML =
        '<div style="padding:12px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">No GTI data found.</div>';
      return;
    }

    const years = series.map(d => d.year);
    const vals  = series.map(d => d.gti);

    // current readout (no .at() usage)
    const lastIdx = years.length - 1;
    elCY.textContent = years[lastIdx] != null ? years[lastIdx] : '—';
    elCV.textContent = vals[lastIdx]  != null ? Math.round(vals[lastIdx]) : '—';

    // labeled annotations with guards
    const annoLabels = {
      1918: '1918: Flu Pandemic',
      1945: '1945: WWII Ends',
      2008: '2008: Financial Crisis',
      2020: '2020: COVID-19'
    };

    const annotations = Object.keys(annoLabels)
      .map(k => parseInt(k, 10))
      .filter(y => years.indexOf(y) !== -1)
      .map(y => {
        const i = years.indexOf(y);
        const yVal = vals[i];
        if (typeof yVal !== 'number' || isNaN(yVal)) return null;
        return {
          x: y,
          y: yVal,
          text: annoLabels[y],
          showarrow: true,
          arrowhead: 2,
          ax: 0,
          ay: -40      // lift the label so it doesn’t sit on the line
        };
      })
      .filter(Boolean);

    Plotly.newPlot('chart', [{
      x: years,
      y: vals,
      type: 'scatter',
      mode: 'lines',
      hovertemplate: 'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line: { width: 3 }
    }], {
      margin: { l: 60, r: 20, t: 50, b: 40 },
      title: 'Good Times Index (GTI) — 1900 to 2025',
      xaxis: { title: 'Year', showgrid: true, gridcolor: '#e2e8f0' },
      yaxis: { title: 'GTI Index (Unbounded)', showgrid: true, gridcolor: '#e2e8f0' },
      annotations
    }, { displayModeBar: false, responsive: true });
  }

  function renderCategories(cats){
    if (!cats) return;
    const order = [
      "Planetary Health","Economic Wellbeing","Global Peace & Conflict",
      "Public Health","Civic Freedom & Rights","Technological Progress",
      "Sentiment & Culture","Entropy Index"
    ];
    const rows = order.map(k => ({ name: k, score: (cats.scores && typeof cats.scores[k] === 'number') ? cats.scores[k] : 50 }));

    Plotly.newPlot('category-bars', [{
      x: rows.map(r => r.score),
      y: rows.map(r => r.name),
      type: 'bar',
      orientation: 'h',
      hovertemplate: '%{y}: %{x}<extra></extra>'
    }], {
      margin: { l: 170, r: 20, t: 10, b: 30 },
      xaxis: { range: [0, 100], showgrid: true, gridcolor: '#e2e8f0' }
    }, { displayModeBar: false, responsive: true });

    const cells = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td></tr>`).join('');
    document.getElementById('category-table').innerHTML =
      `<table><thead><tr><th>Category</th><th>Score (0–100)</th></tr></thead><tbody>${cells}</tbody></table>`;
  }

  (async () => {
    const [gti, cats] = await Promise.all([
      getJSON(dataUrl),
      getJSON(catUrl).catch(() => null)
    ]);

    if (elUpdated && gti && gti.updated) {
      elUpdated.textContent = new Date(gti.updated).toUTCString();
    }
    renderLine((gti && gti.series) ? gti.series : []);
    renderCategories(cats);
  })().catch(err => {
    console.error(err);
    const c = document.getElementById('chart');
    if (c) c.innerHTML =
      `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
         Failed to load data: ${String(err)}
       </div>`;
  });
});
