;(function(){
  const state={pred:null,anat:null}
  function nf(){return new Intl.NumberFormat('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})}
  function pf(){return new Intl.NumberFormat('es-ES',{maximumFractionDigits:1})}
  function palette(){
    return {ing:'#3b82f6',gas:'#ef4444',res:'#10b981',un:'#c08a5c',band:'rgba(192,138,92,0.25)'}
  }
  function ensureDom(id){
    var ana=document.getElementById('sub-anatomia')
    var pred=document.getElementById('sub-prediccion')
    function isVisible(panel){return panel&&(panel.classList.contains('active')||panel.style.display!=='none')}
    if(isVisible(ana)){
      var scoped=ana.querySelector('#'+id)
      if(scoped)return scoped
    }
    if(isVisible(pred)){
      var scoped2=pred.querySelector('#'+id)
      if(scoped2)return scoped2
    }
    return document.getElementById(id)
  }
  function buildTable(headers,rows){
    const thead=`<thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead>`
    const tbody=`<tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>`
    return `<table>${thead}${tbody}</table>`
  }
  function sigma(arr){
    if(!arr||arr.length<2)return 0
    const m=arr.reduce((a,b)=>a+(Number(b)||0),0)/(arr.length||1)
    const v=arr.reduce((a,b)=>{const x=(Number(b)||0)-m;return a+x*x},0)/(arr.length||1)
    return Math.sqrt(v)
  }
  function renderOpPred(){
    const dom=ensureDom('compare-op-pred')
    if(!dom)return
    const p=palette()
    const proj=(state.pred&&state.pred.proj)||[]
    const labels=proj.map((_,i)=>`Periodo ${i+1}`)
    const res=proj.map(x=>Number(x.resultado||0))
    if(typeof echarts==='undefined'){
      dom.innerHTML=''
      const rows=res.map((v,i)=>[`Periodo ${i+1}`,nf().format(v)])
      dom.innerHTML=`<div class="compare-grid">${buildTable(['Periodo','Resultado'],rows)}</div>`
      return
    }
    let chart=echarts.getInstanceByDom(dom); if(chart)chart.clear(); else chart=echarts.init(dom,null,{renderer:'svg'})
    chart.setOption({
      tooltip:{trigger:'axis',formatter:function(params){let s=params[0].name;params.forEach(p=>{s+=`<br/><span style="color:${p.color}">${p.seriesName}:</span> ${nf().format(Number(p.value||0))}`});return s}},
      legend:{textStyle:{color:'#a1a1aa'}},
      grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},
      xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
      yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:v=>nf().format(v)}},
      series:[{name:'Resultado',type:'line',data:res,itemStyle:{color:p.res},lineStyle:{width:2}}]
    })
  }
  function renderOpAnat(){
    const dom=ensureDom('compare-op-anat')
    if(!dom)return
    const p=palette()
    let fc=(state.anat&&state.anat.fc)||[]
    if(!fc||fc.length===0){
      try{
        const yearEl=document.getElementById('sel-ejercicio')
        const year=(yearEl&&yearEl.value)?parseInt(yearEl.value,10):((typeof currEjercicio!=='undefined'&&currEjercicio)?parseInt(currEjercicio,10):new Date().getFullYear())
        let yrs=5
        try{const s=localStorage.getItem('datia-anatomy-years'); if(s)yrs=Math.max(1,parseInt(s,10))}catch(e){}
        const start=Math.max(2008,year-(yrs-1))
        fetch(`/api/financial/anatomy/forecast?empresa=${encodeURIComponent(currEmpresa)}&start_year=${start}&end_year=${year}`).then(r=>r.json()).then(j=>{
          const arr=(Array.isArray(j.forecast)?j.forecast:[])
          if(arr.length){
            state.anat=Object.assign({},state.anat||{}, {fc:arr})
            renderOpAnat(); renderBands(); renderYoY()
          }
        }).catch(function(){})
      }catch(e){}
    }
    const labels=fc.map(x=>`Periodo ${x.quarter||''}`)
    const un=fc.map(x=>Number(x.utilidad_neta||0))
    if(typeof echarts==='undefined'){
      dom.innerHTML=''
      const rows=un.map((v,i)=>[`Periodo ${i+1}`,nf().format(v)])
      dom.innerHTML=`<div class="compare-grid">${buildTable(['Periodo','Utilidad Neta'],rows)}</div>`
      return
    }
    let chart=echarts.getInstanceByDom(dom); if(chart)chart.clear(); else chart=echarts.init(dom,null,{renderer:'svg'})
    chart.setOption({
      tooltip:{trigger:'axis',formatter:function(params){let s=params[0].name;params.forEach(p=>{s+=`<br/><span style="color:${p.color}">${p.seriesName}:</span> ${nf().format(Number(p.value||0))}`});return s}},
      legend:{textStyle:{color:'#a1a1aa'}},
      grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},
      xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
      yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:v=>nf().format(v)}},
      series:[{name:'Utilidad Neta',type:'line',data:un,itemStyle:{color:p.un},lineStyle:{width:2}}]
    })
  }
  function renderBands(){
    const domPred=ensureDom('compare-bands-pred')
    const domAnat=ensureDom('compare-bands-anat')
    const p=palette()
    // Pred: bandas estimadas por sigma histórico del resultado
    if(domPred){
      const proj=(state.pred&&state.pred.proj)||[]
      const res=proj.map(x=>Number(x.resultado||0))
      const labels=proj.map((_,i)=>`Periodo ${i+1}`)
      const s=sigma(res)||0
      const low=res.map(v=>v-s)
      const high=res.map(v=>v+s)
      const band=high.map((h,i)=>h-(low[i]||0))
      if(typeof echarts==='undefined'){
        const rows=res.map((v,i)=>[`Periodo ${i+1}`,nf().format(low[i]||0),nf().format(v||0),nf().format(high[i]||0)])
        domPred.innerHTML=`<div class="compare-grid">${buildTable(['Periodo','Low','Valor','High'],rows)}</div><div class="compare-note">Banda estimada (σ histórica)</div>`
      }else{
        let chart=echarts.getInstanceByDom(domPred); if(chart)chart.clear(); else chart=echarts.init(domPred,null,{renderer:'svg'})
        chart.setOption({
          tooltip:{trigger:'axis'},
          legend:{textStyle:{color:'#a1a1aa'}},
          xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
          yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:v=>nf().format(v)}},
          series:[
            {name:'Low',type:'line',data:low,lineStyle:{width:0},showSymbol:false,stack:'interval'},
            {name:'Banda',type:'line',data:band,lineStyle:{width:0},showSymbol:false,stack:'interval',areaStyle:{color:p.band}},
            {name:'Resultado',type:'line',data:res,itemStyle:{color:p.res},lineStyle:{width:2}}
          ]
        })
      }
    }
    // Anatomía: bandas del backend
    if(domAnat){
      const fc=(state.anat&&state.anat.fc)||[]
      const labels=fc.map(x=>`Periodo ${x.quarter||''}`)
      const base=fc.map(x=>Number(x.utilidad_neta||0))
      const low=fc.map(x=>Number(x.low||0))
      const high=fc.map(x=>Number(x.high||0))
      const band=high.map((h,i)=>h-(low[i]||0))
      if(typeof echarts==='undefined'){
        const rows=base.map((v,i)=>[`Periodo ${labels[i]}`,nf().format(low[i]||0),nf().format(v||0),nf().format(high[i]||0)])
        domAnat.innerHTML=`<div class="compare-grid">${buildTable(['Periodo','Low','Valor','High'],rows)}</div>`
      }else{
        let chart=echarts.getInstanceByDom(domAnat); if(chart)chart.clear(); else chart=echarts.init(domAnat,null,{renderer:'svg'})
        chart.setOption({
          tooltip:{trigger:'axis'},
          legend:{textStyle:{color:'#a1a1aa'}},
          xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
          yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:v=>nf().format(v)}},
          series:[
            {name:'Low',type:'line',data:low,lineStyle:{width:0},showSymbol:false,stack:'interval'},
            {name:'Banda',type:'line',data:band,lineStyle:{width:0},showSymbol:false,stack:'interval',areaStyle:{color:p.band}},
            {name:'Utilidad Neta',type:'line',data:base,itemStyle:{color:p.un},lineStyle:{width:2}}
          ]
        })
      }
    }
  }
  function renderYoY(){
    const wrapPred=ensureDom('compare-yoy-pred')
    const wrapAnat=ensureDom('compare-yoy-anat')
    if(wrapPred){
      const proj=(state.pred&&state.pred.proj)||[]
      const cy=(state.pred&&state.pred.cy)||null
      let html='<div class="compare-grid">'
      if(cy&&proj.length){
        const rows=proj.map((x,i)=>{const cyv=(cy[i]||0);const varpct=cyv?((Number(x.resultado||0)-cyv)/Math.abs(cyv)*100.0):0.0;return [`Periodo ${i+1}`,nf().format(cyv),nf().format(Number(x.resultado||0)),pf().format(varpct)+' %']})
        html+=buildTable(['Periodo','CY','Forecast','Var %'],rows)
      }else{
        html+='<div class="compare-note">Datos YoY no disponibles</div>'
      }
      html+='</div>'
      wrapPred.innerHTML=html
    }
    if(wrapAnat){
      const fc=(state.anat&&state.anat.fc)||[]
      let cyQ=(state.anat&&state.anat.cyQ)||null
      if(!cyQ){
        try{
          if(window.datiaAnatomyQuarters && Array.isArray(window.datiaAnatomyQuarters.cy)){
            cyQ=window.datiaAnatomyQuarters.cy
            state.anat=Object.assign({},state.anat||{}, {cyQ: cyQ})
          }else{
            const yearEl=document.getElementById('sel-ejercicio')
            const year=(yearEl&&yearEl.value)?parseInt(yearEl.value,10):((typeof currEjercicio!=='undefined'&&currEjercicio)?parseInt(currEjercicio,10):new Date().getFullYear())
            const start=Math.max(2008,year-1)
            fetch(`/api/financial/anatomy/utility?empresa=${encodeURIComponent(currEmpresa)}&start_year=${start}&end_year=${year}`).then(r=>r.json()).then(j=>{
              try{
                const data=j&&j.data?j.data:null
                const dCY=data? (data[year]||data[String(year)]):null
                const q=(dCY && Array.isArray(dCY.utilidad_neta))? dCY.utilidad_neta.slice():null
                if(q){ state.anat=Object.assign({},state.anat||{}, {cyQ:q}); renderYoY() }
              }catch(e){}
            }).catch(function(){})
          }
        }catch(e){}
      }
      let html='<div class="compare-grid">'
      if(cyQ&&fc.length){
        const rows=fc.map((x,i)=>{const cyv=(cyQ[i]||0);const varpct=cyv?((Number(x.utilidad_neta||0)-cyv)/Math.abs(cyv)*100.0):0.0;return [`Periodo ${x.quarter||i+1}`,nf().format(cyv),nf().format(Number(x.utilidad_neta||0)),pf().format(varpct)+' %']})
        html+=buildTable(['Periodo','CY','Forecast','Var %'],rows)
      }else{
        html+='<div class="compare-note">Datos YoY no disponibles</div>'
      }
      html+='</div>'
      wrapAnat.innerHTML=html
    }
  }
  function renderLiq(){
    const domPred=ensureDom('compare-liq-pred')
    const domAnat=ensureDom('compare-liq-anat')
    if(domPred){
      const ratios=(state.pred&&state.pred.ratios)||[]
      const labels=ratios.map((x,i)=>`Periodo ${i+1}`)
      const liq=ratios.map(x=>Number(x.ratio||0))
      if(typeof echarts==='undefined'){
        const rows=liq.map((v,i)=>[`Periodo ${i+1}`,v.toFixed(2)])
        domPred.innerHTML=`<div class="compare-grid">${buildTable(['Periodo','Liquidez'],rows)}</div>`
      }else{
        let chart=echarts.getInstanceByDom(domPred); if(chart)chart.clear(); else chart=echarts.init(domPred,null,{renderer:'svg'})
        chart.setOption({
          tooltip:{trigger:'axis'},
          xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
          yAxis:{type:'value',axisLabel:{color:'#a1a1aa'},min:0},
          series:[{name:'Liquidez Corriente',type:'line',data:liq,itemStyle:{color:'#fbbf24'},
            markLine:{data:[{yAxis:1.5,name:'Umbral 1,5'}],label:{formatter:'Umbral 1,5'},lineStyle:{color:'#f87171',type:'dashed'}}}]
        })
      }
    }
    if(domAnat){
      domAnat.innerHTML='<div class="compare-note">No aplica en Anatomía</div>'
    }
  }
  function render(){
    renderOpPred(); renderOpAnat(); renderBands(); renderYoY(); renderLiq()
  }
  function setPred(obj){
    state.pred=obj||null
    render()
  }
  function setAnat(obj){
    state.anat=obj||null
    render()
  }
  window.compareView={setPred,setAnat,render}
})()
