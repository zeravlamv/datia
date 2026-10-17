// Dataset de ejemplo (suma 100% aprox.)
const parts = [
  { key: 'costo_ventas', name: 'Coste de Ventas', pct: 73.5, amount: 735000 },
  { key: 'gastos_admin', name: 'Gastos Administrativos', pct: 16.8, amount: 168000 },
  { key: 'impuestos', name: 'Impuestos', pct: 0.2, amount: 2000 },
  { key: 'personal', name: 'Gastos de Personal', pct: 12.9, amount: 129000 },
  { key: 'amort', name: 'Amortizaciones y Deterioros', pct: 4.8, amount: 48000 },
  { key: 'financiero', name: 'Resultado Financiero', pct: 1.9, amount: 19000 },
  { key: 'utilidad_neta', name: 'Utilidad Neta', pct: -9.9, amount: -99000 }
];

const nfPct = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
const nfMoney = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function buildData() {
  const colorBase = '#f472b6';
  function shadeHex(hex, lum) {
    hex = String(hex).replace(/[^0-9a-f]/gi, '');
    if (hex.length < 6) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    let rgb = "#", c, i;
    for (i=0; i<3; i++) {
      c = parseInt(hex.substr(i*2,2), 16);
      c = Math.round(Math.min(Math.max(0, c + (c*lum)), 255)).toString(16);
      rgb += ("00"+c).substr(c.length);
    }
    return rgb;
  }
  const pal = {
    cv: shadeHex(colorBase, -0.15),
    ga: colorBase,
    imp: shadeHex(colorBase, -0.25),
    un: shadeHex(colorBase, -0.4)
  };
  const map = {
    'costo_ventas': pal.cv,
    'gastos_admin': pal.ga,
    'impuestos': pal.imp,
    'personal': shadeHex(pal.ga, -0.1),
    'amort': shadeHex(pal.ga, -0.2),
    'financiero': shadeHex(pal.ga, -0.3),
    'utilidad_neta': pal.un
  };
  return parts.map(p => ({
    key: p.key,
    name: p.name,
    value: Math.max(0, Number(p.pct||0)),
    amount: Number(p.amount||0),
    itemStyle: { color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
      { offset: 0, color: shadeHex(map[p.key] || '#888', 0.22) },
      { offset: 0.7, color: map[p.key] || '#888' },
      { offset: 1, color: shadeHex(map[p.key] || '#888', -0.18) }
    ])}
  }));
}

function render(el) {
  const chart = echarts.init(el, null, { renderer: 'svg' });
  function apply() {
    const isNarrow = (el.clientWidth || 0) < 720;
    const labelFormatter = isNarrow
      ? (p) => nfPct.format(p.value||0)+'%'
      : (p) => p.name + ' ' + nfPct.format(p.value||0)+'%';
    const centerY = isNarrow ? '58%' : '56%';
    let thr = isNarrow ? 6 : 4;
    if ((el.clientWidth || 0) < 420) thr = 100;
    const baseData = buildData();
    const seriesData = baseData.map(d => {
      const forceShow = d.key === 'costo_ventas' || d.key === 'utilidad_neta';
      const show = forceShow || (Number(d.value || 0) >= thr);
      return Object.assign({}, d, { label: { show }, labelLine: { show } });
    });
    const visCount = seriesData.filter(d => d.label && d.label.show).length;
    el.style.height = (isNarrow ? (visCount > 5 ? 520 : 460) : (visCount > 5 ? 480 : 440)) + 'px';
    const option = {
      aria: { enabled: true },
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          const valPct = nfPct.format(params.value||0);
          const amt = nfMoney.format((params.data && params.data.amount) || 0);
          return `${params.name}: ${valPct}% • ${amt} €`;
        }
      },
      legend: {
        type: 'scroll',
        orient: 'horizontal',
        left: 'center',
        top: isNarrow ? null : 6,
        bottom: isNarrow ? 6 : null,
        textStyle: { color: '#a1a1aa' }
      },
      series: [{
        type: 'pie',
        center: ['50%', centerY],
        radius: isNarrow ? ['58%','82%'] : ['65%','88%'],
        top: '6%',
        bottom: '8%',
        avoidLabelOverlap: true,
        minShowLabelAngle: 5,
        startAngle: 90,
        label: {
          show: true,
          position: 'outside',
          formatter: labelFormatter,
          color: '#e4e4e7',
          fontWeight: 600,
          fontSize: isNarrow ? 11 : 12,
          alignTo: 'edge',
          edgeDistance: isNarrow ? '6%' : '8%',
          bleedMargin: 6,
          borderColor: 'rgba(0,0,0,0.4)',
          borderWidth: 2
        },
        labelLine: {
          show: true,
          length: isNarrow ? 10 : 16,
          length2: isNarrow ? 6 : 10,
          lineStyle: { color: '#71717a' }
        },
        labelLayout: () => ({ hideOverlap: true, moveOverlap: 'shiftY' }),
        data: seriesData
      }]
    };
    chart.setOption(option, true);
    chart.resize();
  }
  apply();
  new ResizeObserver(apply).observe(el);
}

['chart-320','chart-768','chart-1366','chart-1920'].forEach(id => {
  const el = document.getElementById(id);
  if (el) render(el);
});
