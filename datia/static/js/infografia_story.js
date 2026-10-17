function qs(k){return new URLSearchParams(location.search).get(k)}
function fmtEur(n){return Number(n||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})+' €'}
function fmtPct(n){return Number(n||0).toFixed(2)+' %'}
function getCSRF(){
  try{
    const name='csrftoken';
    const cookies=document.cookie?document.cookie.split(';'):[];
    for(let c of cookies){
      const k=c.trim();
      if(k.startsWith(name+'=')) return decodeURIComponent(k.split('=')[1]);
    }
  }catch(_){}
  return '';
}
function getCssVar(name,fallback){
  try{
    const v=getComputedStyle(document.documentElement).getPropertyValue(name)
    return v&&v.trim()?v.trim():fallback
  }catch(_){return fallback}
}
function setStoryAccent(){
  const accent=getCssVar('--accent','#be6a15')
  const root=document.documentElement
  root.style.setProperty('--story-accent',accent)
  try{
    const r=parseInt(accent.slice(1,3),16),g=parseInt(accent.slice(3,5),16),b=parseInt(accent.slice(5,7),16)
    root.style.setProperty('--story-accent-soft',`rgba(${r},${g},${b},0.12)`)
    root.style.setProperty('--story-accent-border',`rgba(${r},${g},${b},0.28)`)
    root.style.setProperty('--story-primary',accent)
  }catch(_){}
}
function setLogo(){
  try{
    const h=document.getElementById('header-datia-logo');if(h&&h.src) return h.src;
    const s=localStorage.getItem('datia-selected-logo');if(s) return s;
  }catch(_){}
  return ''
}
async function loadData(){
  const empresa=qs('empresa')||window.currEmpresa||1
  const ejercicio=qs('ejercicio')||window.currEjercicio||new Date().getFullYear()
  const r=await fetch(`/api/financial/infografia?empresa=${empresa}&ejercicio=${ejercicio}`)
  const dto=await r.json()
  if(dto.status!=='ok') throw new Error(dto.message||'Error de datos')
  return dto
}
function mountHero(fin,empresa,ejercicio){
  const logo=setLogo()
  const title=document.getElementById('story-title')
  const subtitle=document.getElementById('story-subtitle')
  const claim=document.getElementById('story-claim')
  const logoEl=document.getElementById('story-logo')
  const meta=fin.meta||{}
  if(logo) logoEl.src=logo
  title.innerText=`${meta.nombre_empresa||'Empresa'} ${ejercicio}: Tradición y Análisis`
  subtitle.innerText=`Empresa ${empresa} • Ejercicio ${ejercicio} • Moneda ${meta.moneda||'EUR'} • Rol ${meta.rol||'Controller Financiero / CFO'}`
  const f=new Date();const d=f.toLocaleDateString('es-ES',{day:'2-digit',month:'long',year:'numeric'})
  claim.innerText=`Basado en JSON de contexto • ${d}`
  const tl=document.getElementById('story-timeline')
  const items=[
    {t:'Trayectoria',d:'Modelo de gestión con esencia familiar'},
    {t:'La Taza 10',d:'Calidad y sabor en cada proceso'},
    {t:'Compromiso',d:'Sostenibilidad y trazabilidad'}
  ]
  tl.innerHTML=items.map(x=>`<div class="story-dot"><span>${x.t}</span><span>${x.d}</span></div>`).join('')
}
function mountKpis(k,fin){
  const ventas=document.getElementById('kpi-ventas')
  const ebitda=document.getElementById('kpi-ebitda')
  const margen=document.getElementById('kpi-margen')
  const series=fin.series_mensuales||{}
  const ebiTotal=(Array.isArray(series.ebitda)?series.ebitda:[]).reduce((a,b)=>a+(b||0),0)
  const ventasTotal=Number(k.ventas_totales||0)
  const yoy=Number(k.yoy_pct_global||0)
  const marginPct=Number(k.margen_op_pct||0)
  const cupVentas=`
    <div class="story-kpi-illustration">
      <svg class="story-svg" viewBox="0 0 120 90" role="img" aria-label="Taza ventas">
        <rect x="20" y="20" width="70" height="50" rx="8" class="story-cup-outline"/>
        <circle cx="95" cy="40" r="14" class="story-cup-outline"/>
        <rect x="21" y="${70- Math.min(45, 36 + yoy*0.2)}" width="68" height="${Math.min(45, 36 + yoy*0.2)}" class="story-cup-fill positive"/>
      </svg>
    </div>`
  const ebPos=ebiTotal>=0
  const ebHeight=Math.max(6, Math.min(45, 20 + (ventasTotal? (ebiTotal/ventasTotal)*80 : 10)))
  const cupEbi=`
    <div class="story-kpi-illustration">
      <svg class="story-svg" viewBox="0 0 120 90" role="img" aria-label="Taza EBITDA">
        <rect x="20" y="20" width="70" height="50" rx="8" class="story-cup-outline"/>
        <circle cx="95" cy="40" r="14" class="story-cup-outline"/>
        <rect x="21" y="${70-ebHeight}" width="68" height="${ebHeight}" class="story-cup-fill ${ebPos?'positive':'negative'}"/>
      </svg>
    </div>`
  const marHeight=Math.max(6, Math.min(45, 20 + ((marginPct+50)/100)*25))
  const cupMar=`
    <div class="story-kpi-illustration">
      <svg class="story-svg" viewBox="0 0 120 90" role="img" aria-label="Taza margen">
        <rect x="20" y="20" width="70" height="50" rx="8" class="story-cup-outline"/>
        <circle cx="95" cy="40" r="14" class="story-cup-outline"/>
        <rect x="21" y="${70-marHeight}" width="68" height="${marHeight}" class="story-cup-fill ${marginPct>=0?'positive':'negative'}"/>
      </svg>
    </div>`
  ventas.innerHTML= cupVentas + `<div class="val">${fmtEur(ventasTotal)}</div><div class="label">Ventas Totales</div>`
  ebitda.innerHTML= cupEbi + `<div class="val">${fmtEur(ebiTotal)}</div><div class="label">EBITDA</div>`
  margen.innerHTML= cupMar + `<div class="val">${fmtPct(marginPct)}</div><div class="label">Margen Operativo</div>`
  document.getElementById('story-growth-hint').innerText='Crecimiento acelerado con foco en rentabilidad operativa'
}
function mountOps(fin){
  const band=document.getElementById('story-ops-band')
  const k=fin.kpis_globales||{}
  const items=[
    {hd:'Compras y Aprovisionamientos',val:k.gastos_compras||0,desc:'Mayor coste operativo'},
    {hd:'Gastos de Personal',val:k.gastos_personal||0,desc:'Inversión en equipo cualificado'},
    {hd:'Otros Gastos de Explotación',val:k.otros_gastos||0,desc:'Costes adicionales de funcionamiento'}
  ]
  band.innerHTML=items.map(x=>`<div class="item"><div class="hd">${x.hd}</div><div class="val">${fmtEur(x.val)}</div><div class="desc">${x.desc}</div></div>`).join('')
}
function mountBalance(fin){
  const bal=fin.balance_situacion||{}
  const tot=bal.totales||{}
  const ra=bal.ratios||{}
  const solv=document.getElementById('col-solvencia')
  const liq=document.getElementById('col-liquidez')
  const pat=document.getElementById('col-patrimonio')
  const solvVal=Number(ra.solvencia||0)
  const liqVal=Number(ra.liquidez||0)
  const patVal=Number(tot.patrimonio||0)
  const sClass=solvVal>=10?'strong':''
  const lClass=liqVal>=5?'strong':(liqVal<1?'warn':'')
  const pClass=patVal>0?'strong':'warn'
  const sH=Math.min(70, 10 + solvVal*5)
  const lH=Math.min(70, 10 + liqVal*8)
  const pH=Math.min(70, 20 + (patVal? 20 : 8))
  const svgCol=(h,cls)=>`
    <svg class="story-column-svg" viewBox="0 0 120 90" role="img" aria-label="Columna">
      <rect x="30" y="${80-h}" width="60" height="${h}" rx="6" class="story-col-rect ${cls}"/>
      <rect x="25" y="${80-h-8}" width="70" height="8" rx="4" class="story-col-rect ${cls}"/>
    </svg>`
  solv.innerHTML= svgCol(sH,sClass) + `<h3 class="big">${solvVal.toFixed(2)}</h3><p class="small">Solvencia</p>`
  liq.innerHTML= svgCol(lH,lClass) + `<h3 class="big">${liqVal.toFixed(2)}</h3><p class="small">Liquidez</p>`
  pat.innerHTML= svgCol(pH,pClass) + `<h3 class="big">${fmtEur(patVal)}</h3><p class="small">Patrimonio Neto</p>`
  const chips=document.getElementById('story-balance-chips')
  chips.innerHTML=`<span class="story-chip">Activo ${fmtEur(tot.activo||0)}</span><span class="story-chip">Pasivo ${fmtEur(tot.pasivo||0)}</span><span class="story-chip">Endeudamiento ${fmtPct(ra.endeudamiento||0)}</span>`
}
function keyMonths(est){
  const all=Array.isArray(est)?est:[]
  const pick=[0,3,6,9,11].map(i=>all[i]).filter(Boolean)
  return pick
}
function mountSeason(fin){
  const meses=['Enero','Abril','Julio','Octubre','Diciembre']
  const grid=document.getElementById('story-season-grid')
  const data=keyMonths(fin.estacionalidad||[])
  grid.innerHTML=data.map((x,i)=>`<div class="story-season-card"><div class="month">${meses[i]}</div><div class="kpis">Cuota ${fmtPct(x.share_pct||0)} • YoY ${fmtPct(x.yoy_pct||0)}</div></div>`).join('')
  const alerts=document.getElementById('story-alerts')
  const al=fin.alertas_sistema||[]
  alerts.innerHTML=al.map(a=>`<div class="story-alert">${a}</div>`).join('')
}
function mountBanner(fin,ven,k){
  const wrap=document.getElementById('story-banner-chips')
  if(!wrap) return
  const yoy=Number(k.yoy_pct_global||0)
  const liq=Number((fin.balance_situacion||{}).ratios?.liquidez||0)
  const p=ven.pareto||{}
  const conc=Number(p.top_share_pct||0)
  const chips=[
    {t:`YoY ${fmtPct(yoy)}`},
    {t:`Liquidez ${liq>=1?'OK':(liq<1?'Riesgo':'')}`,warn:liq<1},
    {t:`Concentración ${fmtPct(conc)}`,warn:conc>60}
  ]
  wrap.innerHTML=chips.map(c=>`<span class="chip${c.warn?' warn':''}">${c.t}</span>`).join('')
}
function mountSales(ven){
  const top=document.getElementById('story-sales-top')
  const risk=document.getElementById('story-sales-risk')
  const pare=document.getElementById('story-sales-pareto')
  const topC=Array.isArray(ven.top_clientes)?ven.top_clientes:[]
  const topP=Array.isArray(ven.top_productos)?ven.top_productos:[]
  const negP=Array.isArray(ven.productos_negativos)?ven.productos_negativos:[]
  const cliR=Array.isArray(ven.clientes_riesgo)?ven.clientes_riesgo:[]
  const p=ven.pareto||{}
  top.innerHTML=`<div class="story-grid-2"><div><h3>Top Clientes</h3><ul class="story-list">${topC.map(c=>`<li>${c.nombre}: ${fmtEur(c.volumen_compras||0)}</li>`).join('')}</ul></div><div><h3>Top Productos</h3><ul class="story-list">${topP.map(x=>`<li>${x.nombre}: ${fmtEur(x.ingresos_generados||0)}</li>`).join('')}</ul></div></div>`
  risk.innerHTML=`<div class="story-grid-2"><div><h3>Clientes en riesgo</h3><ul class="story-list">${cliR.map(c=>`<li>${c.nombre||c.cliente}: YoY ${fmtPct(c.yoy_pct||0)} • Peso ${fmtPct(c.peso_pct||0)}</li>`).join('')}</ul></div><div><h3>Productos con margen negativo</h3><ul class="story-list">${negP.map(p=>`<li>${p.nombre||p.articulo}: ${fmtEur(p.margen||0)}</li>`).join('')}</ul></div></div>`
  if(p.top_share_pct!==undefined) pare.innerHTML=`<h3>Concentración</h3><div class="story-chip ${Number(p.top_share_pct||0)>60?'warn':''}">Top clientes: ${fmtPct(p.top_share_pct||0)}</div>`
}
function mountPL(fin){
  const t=document.getElementById('story-pl-table')
  const rows=Array.isArray(fin.pl_analisis)?fin.pl_analisis:[]
  const head=`<div class="row head"><div class="cell">Concepto</div><div class="cell right">Real</div><div class="cell right">Objetivo</div><div class="cell right">Desviación</div><div class="cell right">Desv. %</div></div>`
  const body=rows.map(r=>`<div class="row"><div class="cell">${r.concepto}</div><div class="cell right">${fmtEur(r.real||0)}</div><div class="cell right">${fmtEur(r.objetivo||0)}</div><div class="cell right">${fmtEur(r.desviacion_importe||0)}</div><div class="cell right">${fmtPct(r.desviacion_pct||0)}</div></div>`).join('')
  t.innerHTML=head+body
}
function animateOnView(){
  const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('show')}})},{threshold:.2})
  document.querySelectorAll('.story-kpi,.story-column').forEach(el=>io.observe(el))
}
function hookPDF(htmlSource){
  const btn=document.getElementById('story-pdf')
  btn.onclick=async()=>{
    btn.disabled=true
    btn.innerText='Generando PDF...'
    try{
      const empresa=qs('empresa')||window.currEmpresa||1
      const ejercicio=qs('ejercicio')||window.currEjercicio||new Date().getFullYear()
      const res=await fetch('/api/ai/report/export/pdf',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCSRF()},body:JSON.stringify({empresa,ejercicio,html:htmlSource||document.documentElement.outerHTML,title:'Infografía Financiera'})})
      if(res.ok){
        const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`Infografia_${empresa}_${ejercicio}.pdf`;document.body.appendChild(a);a.click();a.remove()
      }
    }finally{
      btn.disabled=false
      btn.innerText='Descargar PDF'
    }
  }
}
document.addEventListener('DOMContentLoaded',async()=>{
  setStoryAccent()
  const dto=await loadData()
  const fin=dto.raw_fin||{}
  const ven=dto.raw_ventas||{}
  mountHero(fin,dto.empresa,dto.ejercicio)
  mountKpis(dto.kpis||{},fin)
  mountBanner(fin,ven,dto.kpis||{})
  mountOps(fin)
  mountBalance(fin)
  mountSeason(fin)
  if(Object.keys(ven).length) mountSales(ven)
  mountPL(fin)
  mountFooter(fin,dto)
  animateOnView()
  hookPDF()
  fitToViewport()
  window.addEventListener('resize',fitToViewport)
})

function mountFooter(fin,dto){
  const name=document.getElementById('story-footer-name')
  const meta=document.getElementById('story-footer-meta')
  const m=fin.meta||{}
  const f=new Date();const d=f.toLocaleDateString('es-ES',{day:'2-digit',month:'long',year:'numeric'})
  if(name) name.innerText=m.nombre_empresa||`Empresa ${dto.empresa}`
  if(meta) meta.innerText=`Ejercicio ${dto.ejercicio} • Rol ${m.rol||'Controller Financiero / CFO'} • Generado ${d}`
}

function fitToViewport(){
  const root=document.querySelector('.story-root')
  const cont=document.querySelector('.story-container')
  if(!root||!cont) return
  const vw=root.clientWidth
  const vh=root.clientHeight
  const cw=cont.offsetWidth
  const ch=cont.offsetHeight
  if(!cw||!ch) return
  const scale=Math.min(vw/cw,vh/ch)
  cont.style.transform=`scale(${scale})`
  cont.style.transformOrigin='top left'
}
