document.addEventListener('DOMContentLoaded', () => {
  const kpiYear = document.getElementById('kpi-year');
  const kpiGTI  = document.getElementById('kpi-gti');
  const kpiUpd  = document.getElementById('kpi-updated');

  const years = [1900, 1950, 2000, 2025];
  const vals  = [300, 180, 240, 310];

  if (kpiYear) kpiYear.textContent = '2025';
  if (kpiGTI)  kpiGTI.textContent  = '310';
  if (kpiUpd)  kpiUpd.textContent  = new Date().toUTCString();

  Plotly.newPlot('chart-plot', [{
    x: years, y: vals, type:'scatter', mode:'lines', line:{width:3}
  }], {
    margin:{l:60,r:20,t:50,b:40},
    title:'Good Times Index (GTI) — Smoke Test',
    xaxis:{title:'Year'},
    yaxis:{title:'GTI Index (Unbounded)'}
  }, {displayModeBar:false, responsive:true});
});
