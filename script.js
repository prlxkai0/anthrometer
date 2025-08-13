async function loadData(){
  const res = await fetch('./data/gti.json', {cache:'no-store'});
  const json = await res.json();
  document.getElementById('updated').textContent = new Date(json.updated).toUTCString();

  const years = json.series.map(d=>d.year);
  const values = json.series.map(d=>d.gti);

  const trace = {
    x: years, y: values, type: 'scatter', mode:'lines',
    hovertemplate: 'Year: %{x}<br>GTI: %{y:.0f}<extra></extra>',
    line: {width: 3}
  };

  const annotations = [
    {x: 1918, y: values[years.indexOf(1918)], text:'1918: Flu Pandemic', showarrow:true, arrowhead:2},
    {x: 1945, y: values[years.indexOf(1945)], text:'1945: WWII Ends', showarrow:true, arrowhead:2},
    {x: 2008, y: values[years.indexOf(2008)], text:'2008: Financial Crisis', showarrow:true, arrowhead:2},
    {x: 2020, y: values[years.indexOf(2020)], text:'2020: COVID-19', showarrow:true, arrowhead:2},
  ];

  const layout = {
    margin:{l:60,r:20,t:60,b:40},
    title:'Good Times Index (GTI) — 1900 to 2025',
    xaxis:{title:'Year', showgrid:true, gridcolor:'#e2e8f0'},
    yaxis:{title:'GTI Index (Unbounded)', showgrid:true, gridcolor:'#e2e8f0'},
    annotations
  };

  Plotly.newPlot('chart', [trace], layout, {displayModeBar:false, responsive:true});
}
loadData();
