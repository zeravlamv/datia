(function(){
let agingCache=null;
function cacheAgingData(a){agingCache=a}
function renderMultiBar(domId, titleText, labels, values, color){
  const dom=document.getElementById(domId); if(!dom||!window.echarts)return
  let chart=echarts.getInstanceByDom(dom); if(chart) chart.dispose()
  chart=echarts.init(dom,null,{renderer:'svg'})
  chart.setOption({
    title:{text:titleText,left:'center',textStyle:{fontSize:12,color:'#ddd'}},
    tooltip:{trigger:'axis'},
    legend:{data:['Importe'],bottom:0,textStyle:{color:'#bbb'}},
    grid:{left:'6%',right:'6%',bottom:'18%',top:'12%',containLabel:true},
    xAxis:{type:'category',data:labels,axisLabel:{fontSize:11}},
    yAxis:{type:'value'},
    series:[{name:'Importe',type:'bar',data:values.map(v=>Number(v||0)),itemStyle:{color},label:{show:true,position:'top',color:'#fff',fontSize:13,fontWeight:'700',backgroundColor:'rgba(0,0,0,0.55)',padding:[3,6],borderRadius:6,textShadowColor:'rgba(0,0,0,0.7)',textShadowBlur:2,formatter:(p)=>new Intl.NumberFormat('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2}).format(p.value)}}]
  })
  new ResizeObserver(()=>chart.resize()).observe(dom)
}
function renderAgingReceivablesChart(aging){
  try{
    const m=(aging&&aging.receivables_cartera)||{}
    const base=['0-30','30-60','60-90','>90']
    const labels=['Vencido']; const values=[Number((aging&&aging.receivables&&aging.receivables['overdue'])||0)]
    base.forEach(k=>{labels.push(k);values.push(Number(m[k]||0))})
    renderMultiBar('chart-aging-cobros','Cobros por periodo',labels,values,'#10b981')
  }catch(e){}
}
function renderAgingPayablesChart(aging){
  try{
    const m=(aging&&aging.payables)||{}
    const base=['overdue','0-30','30-60','60-90','>90']
    const labels=base.map(k=>k==='overdue'?'Vencido':k)
    const values=base.map(k=>Number(m[k]||0))
    renderMultiBar('chart-aging-pagos','Pagos por periodo',labels,values,'#ef4444')
  }catch(e){}
}
function ensureTesoreriaPolling(){
  try{
    if(window.__tesPoll)return
    window.__tesPoll=setInterval(()=>{
      const active=document.getElementById('sub-tesoreria')&&document.getElementById('sub-tesoreria').style.display!=='none'
      if(active&&typeof window.loadTesoreriaData==='function'){window.loadTesoreriaData()}
    },45000)
  }catch(e){}
}
document.addEventListener('datia:subtab-change',e=>{
  if(e.detail&&e.detail.subTabId!=='sub-tesoreria'){
    if(window.__tesPoll){clearInterval(window.__tesPoll);window.__tesPoll=null}
  }else{ensureTesoreriaPolling()}
})
window.cacheAgingData=cacheAgingData
window.renderAgingReceivablesChart=renderAgingReceivablesChart
window.renderAgingPayablesChart=renderAgingPayablesChart
window.ensureTesoreriaPolling=ensureTesoreriaPolling
})()
