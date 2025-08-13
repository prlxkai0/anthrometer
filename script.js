async function loadData() {
  const url = `./data/gti.json?t=${Date.now()}`;
  const updatedEl = document.getElementById('updated');
  const chartElId = 'chart';
  const chartEl = document.getElementById(chartElId);

  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();

    // Update timestamp
    if (updatedEl) {
      updatedEl.textContent = new Date(json.updated).toUTCString();
    }

    // Parse series
    const years = (json.series || []).map(d => d.year);
    const values = (json.series || []).map(d => d.gti);

    if (!years.length || !values.length) {
      chartEl.innerHTML = `<div style="padding:12px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">
        No GTI data found in <code>data/gti.json</code>. Check the file has a "series" array with {year, gti}.
      </div>`;
      return;
    }

    // Latest readout (optional: attach to header)
    const latestYear = years[years.length - 1];
    const latestVal  = values[values.length - 1];
    const hdr = document.querySelector('header');
    if (hdr && !document.getElementById('latest-gti')) {
      const p = document.createElement('p');
      p.id = 'latest-gti';
      p.className = 'sub';
      p.textContent = `Current GTI (${latestYear}): ${Math.round(latestVal)}`;
      hdr.appendChild(p);
    }

    // Plotly trace & layout
    const trace = {
      x: years,
      y: values,
      type: 'scatter',
      mode: 'lines',
      hovertemplate: 'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
      line: { width: 3 }
    };

    const annotations = [
      { x: 1918, y: values[years.indexOf(1918)], text: '1918: Flu Pandemic', showarrow: true, arrowhead: 2 },
      { x: 1945, y: values[years.indexOf(1945)], text: '1945: WWII Ends', showarrow: true, arrowhead: 2 },
      { x: 2008, y: values[years.indexOf(2008)], text: '2008: Financial Crisis', showarrow: true, arrowhead: 2 },
      { x: 2020, y: values[years.indexOf(2020)], text: '2020: COVID-19', showarrow: true, arrowhead: 2 }
    ].filter(a => years.includes(a.x)); // only keep if that year exists

    const layout = {
      margin: { l: 60, r: 20, t: 60, b: 40 },
      title: 'Good Times Index (GTI) — 1900 to 2025',
      xaxis: { title: 'Year', showgrid: true, gridcolor: '#e2e8f0' },
      yaxis: { title: 'GTI Index (Unbounded)', showgrid: true, gridcolor: '#e2e8f0' },
      annotations
    };

    Plotly.newPlot(chartElId, [trace], layout, { displayModeBar: false, responsive: true });
  } catch (err) {
    console.error('GTI load error:', err);
    document.getElementById('chart').innerHTML = `<div style="padding:12px;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;">
      Failed to load GTI data (${String(err)}). Confirm <code>data/gti.json</code> exists and is valid JSON.
    </div>`;
  }
}

loadData();
