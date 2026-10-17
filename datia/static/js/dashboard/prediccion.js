(function(){
    let initialized=false
    let tipsActive=false
    let tipsCurrentId=null
    let tipsVariantIndex=0
    let tipsLastVariantAt=0
    let tipsInterval=null

    const predTips = [
        { id:'data', min:0, max:30, icon:'fas fa-database', title:'Recopilando histórico', variants:[
            'Consultando histórico contable y evolución mensual.',
            'Este paso prepara la base: ingresos, gastos y resultado.',
            'Si tarda, suele ser por volumen de datos o agregaciones.'
        ]},
        { id:'treasury', min:30, max:55, icon:'fas fa-coins', title:'Proyección de tesorería', variants:[
            'Calculando caja, cobros y pagos para el horizonte seleccionado.',
            'Aquí impactan “Cobro anticipado”, “Diferir pagos” y “Prob. default”.',
            'El objetivo es detectar meses de estrés de liquidez.'
        ]},
        { id:'prophet', min:55, max:90, icon:'fas fa-robot', title:'Prophet (forecast)', variants:[
            'Prophet aprende tendencia y estacionalidad del histórico.',
            'No “adivina” eventos futuros: proyecta patrones pasados.',
            'Más histórico = bandas más estables; menos histórico = más sensibilidad.'
        ]},
        { id:'bands', min:90, max:100, icon:'fas fa-chart-line', title:'Bandas y alertas', variants:[
            'Generando bandas Low/High para estimar incertidumbre.',
            'Bandas anchas = más ruido o cambios estructurales.',
            'Cuando termina, se actualizan alertas y recomendaciones.'
        ]}
    ]

    function shouldShowPredTips(){
        try{
            return localStorage.getItem('datia-hide-prediccion-prophet-tips')!=='true'
        }catch(e){return true}
    }

    function setPredTipsIndeterminate(on){
        const bar=document.getElementById('pred-tips-progress-bar')
        if(bar) bar.classList.toggle('indeterminate',!!on)
    }

    function setPredTipsProgress(pct){
        if(!tipsActive) return
        const bar=document.getElementById('pred-tips-progress-bar')
        if(bar) bar.style.width=String(Math.max(0,Math.min(100,pct)))+'%'

        const tip=predTips.find(t=>pct>=t.min && pct<=t.max) || predTips[predTips.length-1]
        if(!tip) return

        const now=Date.now()
        const icon=document.getElementById('pred-tip-icon')
        const title=document.getElementById('pred-tip-title')
        const text=document.getElementById('pred-tip-text')
        const variants=(tip.variants&&tip.variants.length)?tip.variants:[]

        if(tipsCurrentId!==tip.id){
            tipsCurrentId=tip.id
            tipsVariantIndex=0
            tipsLastVariantAt=now
            if(icon) icon.className=tip.icon
            if(title) title.innerText=tip.title
            if(text) text.innerText=variants[0]||''
            if(title){ title.style.animation='none'; title.offsetHeight; title.style.animation=null }
            if(text){ text.style.animation='none'; text.offsetHeight; text.style.animation=null }
        }else if(variants.length>1 && (now-tipsLastVariantAt)>6500){
            tipsVariantIndex=(tipsVariantIndex+1)%variants.length
            tipsLastVariantAt=now
            if(text){
                text.innerText=variants[tipsVariantIndex]||''
                text.style.animation='none'; text.offsetHeight; text.style.animation=null
            }
        }
    }

    function openPredTips(){
        if(!shouldShowPredTips()) return
        const overlay=document.getElementById('pred-tips-overlay')
        if(!overlay) return
        overlay.style.display='flex'
        void overlay.offsetWidth
        overlay.classList.add('show')
        tipsActive=true
        tipsCurrentId=null
        tipsVariantIndex=0
        tipsLastVariantAt=0

        const closeBtn=document.getElementById('pred-tips-close')
        const skipBtn=document.getElementById('pred-tips-skip')
        if(closeBtn) closeBtn.onclick=function(){ closePredTips(false) }
        if(skipBtn) skipBtn.onclick=function(){ closePredTips(true) }

        overlay.onclick=function(e){
            if(e && e.target===overlay) closePredTips(false)
        }

        const onKey=function(e){
            if(!e) return
            if(e.key==='Escape'){
                closePredTips(false)
                try{ document.removeEventListener('keydown',onKey) }catch(_){}
            }
        }
        document.addEventListener('keydown',onKey)
        setPredTipsIndeterminate(true)
        setPredTipsProgress(3)
    }

    function closePredTips(persist){
        const overlay=document.getElementById('pred-tips-overlay')
        const cb=document.getElementById('pred-tips-dont-show')
        if(cb && cb.checked){
            try{ localStorage.setItem('datia-hide-prediccion-prophet-tips','true') }catch(e){}
        }
        if(overlay){
            overlay.classList.remove('show')
            setTimeout(function(){ overlay.style.display='none' },300)
        }
        tipsActive=false
        tipsCurrentId=null
        setPredTipsIndeterminate(false)
        if(tipsInterval){ clearInterval(tipsInterval); tipsInterval=null }
    }

    function startPredTipsSmooth(startPct,capPct){
        if(!tipsActive) return
        if(tipsInterval){ clearInterval(tipsInterval); tipsInterval=null }
        setPredTipsIndeterminate(true)
        let current=startPct
        let cap=capPct
        let startedAt=Date.now()
        setPredTipsProgress(current)
        tipsInterval=setInterval(function(){
            if(!tipsActive){ clearInterval(tipsInterval); tipsInterval=null; return }
            if(current<cap){
                let remaining=cap-current
                let delta=Math.max(0.08,Math.min(0.9,remaining*0.08))
                current=Math.min(cap,current+delta)
            }else{
                let t=(Date.now()-startedAt)/1000
                current=cap-0.6+((Math.sin(t*2.2)+1)*0.3)
            }
            setPredTipsProgress(current)
        },250)
    }

    function stopPredTipsSmooth(){
        if(tipsInterval){ clearInterval(tipsInterval); tipsInterval=null }
        setPredTipsIndeterminate(false)
    }

    function initPrediccion(){
        if(initialized)return
        initialized=true
        const btn=document.getElementById('pred-refresh')
        if(btn){btn.onclick=loadPrediccion}
        const hz=document.getElementById('pred-horizon')
        const sc=document.getElementById('pred-scenario')
        const lv=document.getElementById('pred-level')
        const co=document.getElementById('pred-cobro')
        const pa=document.getElementById('pred-pagos')
        const df=document.getElementById('pred-default')
        const expCsv=document.getElementById('pred-export-csv')
        const expPdf=document.getElementById('pred-export-pdf')
        if(expCsv){expCsv.onclick=exportTreasuryForecast.bind(null,'csv')}
        if(expPdf){expPdf.onclick=exportTreasuryForecast.bind(null,'pdf')}
        if(hz&&sc&&lv){
            lv.onchange=loadPrediccion
            if(hz)hz.onchange=loadPrediccion
            if(sc)sc.onchange=loadPrediccion
            if(co)co.onchange=loadPrediccion
            if(pa)pa.onchange=loadPrediccion
            if(df)df.onchange=loadPrediccion
            loadPrediccion()
        }
    }
    async function loadPrediccion(){
        openPredTips()
        startPredTipsSmooth(4,22)
        const horizon=parseInt(document.getElementById('pred-horizon').value||'4',10)
        const scenario=(document.getElementById('pred-scenario').value||'base')
        const level=(document.getElementById('pred-level').value||'basico')
        const cobroPct=parseFloat(document.getElementById('pred-cobro')?.value||'0')
        const pagosPct=parseFloat(document.getElementById('pred-pagos')?.value||'0')
        const defaultPct=parseFloat(document.getElementById('pred-default')?.value||'0')
        const evo=await fetchEvolution()
        stopPredTipsSmooth()
        setPredTipsProgress(30)
        startPredTipsSmooth(30,52)
        const tf=await fetchTreasuryForecast(horizon,cobroPct,pagosPct,defaultPct)
        stopPredTipsSmooth()
        setPredTipsProgress(58)
        startPredTipsSmooth(58,70)
        const bs=await fetchBalanceSummary()
        stopPredTipsSmooth()
        setPredTipsProgress(74)
        startPredTipsSmooth(74,95)
        const pf=await fetchPredictForecast(horizon,scenario)
        stopPredTipsSmooth()
        setPredTipsProgress(98)
        if(!evo||evo.length<3){
            renderSummaryLevel(level,{confidence:'Baja',text:'Datos insuficientes para estimación fiable.'})
            renderTable([],horizon,[],[],level)
            renderAlerts({risk:null})
            renderReco(level==='basico'?'Reforzar cobros y ajustar pagos del mes próximo.':level==='tecnico'?'Reforzar captura mensual y ampliar histórico mínimo a 12 meses.':'Completar histórico y ajustar ventanas de forecast por estacionalidad.')
            setPredTipsProgress(100)
            setTimeout(function(){ closePredTips(false) },800)
            return
        }
        const lastMonths=getLastMonths(evo,12)
        const last6=getLastMonths(evo,6)
        const inc6=last6.map(d=>Number(d.ingresos||0))
        const gas6=last6.map(d=>Number(d.gastos||0))
        const cmgrInc=calcCmgr(inc6)
        const cmgrGas=calcCmgr(gas6)
        const baseInc=weightedMean(inc6)
        const baseGas=weightedMean(gas6)
        const proj=buildProjection(baseInc,baseGas,horizon,cmgrInc,cmgrGas,scenario)
        const cashStart=(tf&&typeof tf.start_cash==='number')?Number(tf.start_cash):0
        const acBase=(bs&&bs.desglose&&bs.desglose.activo)?Number(bs.desglose.activo.corriente||0):0
        const pcBase=(bs&&bs.desglose&&bs.desglose.pasivo)?Number(bs.desglose.pasivo.corriente||0):1
        const cf=alignTreasury(tf,horizon,cashStart)
        let ratios=computeLiquidityRatios(cf,cashStart,acBase,pcBase)
        let riskIdx=findRiskMonth(ratios,1.5)
        const br = computeBurnRate(cf, proj)
        const rw = computeRunway(cashStart, br)
        const dirInc = computeTrendDirection(inc6)
        const dirGas = computeTrendDirection(gas6)
        const marginStat = computeMarginStatus(cmgrInc, cmgrGas)
        let trendTxt=buildTrendText(cmgrInc,cmgrGas,riskIdx,br,rw,dirInc,dirGas,marginStat)
        if(pf&&pf.status==='ok'){
            trendTxt=pf.summary||trendTxt
            if(Array.isArray(pf.liquidez)){ratios=pf.liquidez}
            if(pf.alerts&&pf.alerts.risk_month){riskIdx=pf.alerts.risk_month}
        }
        renderSummaryLevel(level,{confidence:'Alta',text:trendTxt,cmgrInc,cmgrGas,riskMonth:riskIdx})
        renderReportByLevel(level,proj,cf,ratios,{cmgrInc,cmgrGas,burnRate:br,runway:rw,riskMonth:riskIdx,cashStart})
        renderTable(proj,horizon,cf,ratios,level)
        renderChartsByLevel(level,proj,cf,ratios)
        renderCombinedChart(proj,cf,ratios)
        renderFlujoCaja(cf)
        renderDataPanels(proj,cf,ratios)
        attachToggleHandlers()
        renderAlerts({risk:riskIdx})
        renderReco(buildReco(riskIdx))
        setPredTipsProgress(100)
        setTimeout(function(){ closePredTips(false) },800)
        try{
            const year=(typeof currEjercicio!=='undefined' && currEjercicio)?parseInt(currEjercicio,10):new Date().getFullYear()
            const cyMonths=filterYearMonths(evo,year).slice(0,horizon).map(x=>x.resultado||0)
            if(window.compareView&&typeof window.compareView.setPred==='function'){
                window.compareView.setPred({proj,ratios,cy:cyMonths})
            }
        }catch(e){}
    }
    function getSafeEmpresaEje() {
        let empVal = typeof currEmpresa !== 'undefined' ? currEmpresa : null;
        let ejeVal = typeof currEjercicio !== 'undefined' ? currEjercicio : null;
        const selEmp = document.getElementById('sel-empresa');
        const selEje = document.getElementById('sel-ejercicio');
        if ((!empVal || empVal === '' || empVal === 'undefined') && selEmp && selEmp.value) {
            empVal = selEmp.value;
        }
        if ((!ejeVal || ejeVal === '' || ejeVal === 'undefined') && selEje && selEje.value) {
            ejeVal = selEje.value;
        }
        return { empVal, ejeVal };
    }

    async function fetchEvolution(){
        try{
            const safe = getSafeEmpresaEje()
            const ejeBase = safe.ejeVal ? parseInt(safe.ejeVal,10) : (typeof currEjercicio!=='undefined' && currEjercicio)?parseInt(currEjercicio,10):new Date().getFullYear()
            const yEnd=ejeBase
            const yStart=yEnd-1
            const emp = safe.empVal || currEmpresa
            if(!emp) return []
            const url=`/api/financial/evolution/evolution?empresa=${encodeURIComponent(emp)}&start_year=${yStart}&end_year=${yEnd}&group_by=month`
            const r=await fetch(url)
            const j=await r.json()
            if(j&&j.status==='ok'){return j.data||[]}
            return []
        }catch(e){return []}
    }
    function filterYearMonths(data,year){
        const arr=(data||[]).filter(d=>parseInt(d.anio||d.year||0,10)===parseInt(year,10)).sort((a,b)=>Number(a.mes||a.periodo||0)-Number(b.mes||b.periodo||0))
        return arr.map(d=>({mes:Number(d.mes||d.periodo||0),ingresos:Number(d.ingresos||0),gastos:Number(d.gastos||0),resultado:Number(d.resultado||0)}))
    }
    async function fetchTreasuryForecast(horizon,cobroPct,pagosPct,defaultPct){
        try{
            const params=new URLSearchParams()
            const safe = getSafeEmpresaEje()
            const emp = safe.empVal || currEmpresa
            const eje = safe.ejeVal || currEjercicio
            if(!emp || !eje) return null
            params.set('empresa',String(emp))
            params.set('ejercicio',String(eje))
            params.set('horizon',String(horizon||6))
            params.set('cobro_anticipado_pct',String(cobroPct||0))
            params.set('diferir_pagos_pct',String(pagosPct||0))
            params.set('prob_default_pct',String(defaultPct||0))
            const url=`/api/financial/treasury/forecast?${params.toString()}`
            const r=await fetch(url)
            const j=await r.json()
            return j
        }catch(e){return null}
    }
    function exportTreasuryForecast(fmt){
        try{
            const horizon=parseInt(document.getElementById('pred-horizon').value||'4',10)
            const cobroPct=parseFloat(document.getElementById('pred-cobro')?.value||'0')
            const pagosPct=parseFloat(document.getElementById('pred-pagos')?.value||'0')
            const defaultPct=parseFloat(document.getElementById('pred-default')?.value||'0')
            const params=new URLSearchParams()
            const safe = getSafeEmpresaEje()
            const emp = safe.empVal || currEmpresa
            const eje = safe.ejeVal || currEjercicio
            if(!emp || !eje) return
            params.set('empresa',String(emp))
            params.set('ejercicio',String(eje))
            params.set('horizon',String(horizon||6))
            params.set('cobro_anticipado_pct',String(cobroPct||0))
            params.set('diferir_pagos_pct',String(pagosPct||0))
            params.set('prob_default_pct',String(defaultPct||0))
            params.set('format',fmt||'csv')
            const url=`/api/financial/treasury/forecast/export?${params.toString()}`
            window.location.href=url
        }catch(e){}
    }
    async function fetchPredictForecast(horizon,scenario){
        try{
            const safe = getSafeEmpresaEje()
            const yEnd = safe.ejeVal ? parseInt(safe.ejeVal,10) : new Date().getFullYear()
            const yStart=yEnd-9
            const emp = safe.empVal || currEmpresa
            if(!emp) return null
            const url=`/api/financial/predict/forecast?empresa=${encodeURIComponent(emp)}&start_year=${yStart}&end_year=${yEnd}&horizon=${encodeURIComponent(horizon)}&scenario=${encodeURIComponent(scenario)}`
            const r=await fetch(url)
            if(!r.ok){return null}
            const j=await r.json()
            return j
        }catch(e){return null}
    }
    async function fetchBalanceSummary(){
        try{
            const safe = getSafeEmpresaEje()
            const emp = safe.empVal || currEmpresa
            const eje = safe.ejeVal || currEjercicio
            if(!emp || !eje) return null
            const url=`/api/financial/balance/summary?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(eje)}`
            const r=await fetch(url)
            const j=await r.json()
            return j
        }catch(e){return null}
    }
    function getLastMonths(data,n){
        const arr=[...data].sort((a,b)=>String(a.periodo).localeCompare(String(b.periodo)))
        return arr.slice(Math.max(0,arr.length-n))
    }
    function calcCmgr(arr){
        if(!arr||arr.length<3)return 0
        const first=arr[0]
        const last=arr[arr.length-1]
        if(first<=0)return 0
        const n=arr.length-1
        return Math.pow(last/first,1/n)-1
    }
    function weightedMean(arr){
        if(!arr||arr.length===0)return 0
        let w=0,s=0
        for(let i=0;i<arr.length;i++){const weight=i+1;w+=weight;s+=arr[i]*weight}
        return s/(w||1)
    }
    function buildProjection(baseInc,baseGas,h,cmgrInc,cmgrGas,scenario){
        const out=[]
        for(let i=1;i<=h;i++){
            let inc=baseInc*Math.pow(1+(cmgrInc||0),i)
            let gas=baseGas
            if(scenario==='pesimista'){inc=inc*0.9;gas=baseGas}
            else{gas=baseGas*Math.pow(1+(cmgrGas||0),i)}
            const res=inc-gas
            out.push({mes:i,ingresos:inc,gastos:gas,resultado:res})
        }
        return out
    }
    function alignTreasury(tf,h,cashStart){
        const seq=[]
        for(let i=1;i<=h;i++){seq.push({mes:i,inflow:0,outflow:0,balance:i===1?cashStart:cashStart})}
        if(!tf||!tf.forecast)return seq.map((x,idx)=>{const bal=cashStart;return{mes:idx+1,inflow:0,outflow:0,balance:bal}})
        const today=new Date()
        const keys=tf.forecast.map(x=>x.period)
        const map={}
        tf.forecast.forEach(x=>{map[x.period]={in:x.inflow||0,out:x.outflow||0,balance:x.balance||cashStart}})
        const out=[]
        for(let i=0;i<h;i++){
            const d=new Date(today.getFullYear(),today.getMonth()+i,1)
            const key=d.toISOString().slice(0,7)
            const m=map[key]||{in:0,out:0,balance:(i===0?cashStart:out[i-1].balance)}
            out.push({mes:i+1,inflow:m.in,outflow:m.out,balance:m.balance})
        }
        return out
    }
    function computeLiquidityRatios(cf,cashStart,ac,pc){
        const out=[]
        const acBase=Math.abs(ac||0)
        const pcBase=Math.abs(pc||0)||1
        for(let i=0;i<cf.length;i++){
            const delta=cf[i].balance-cashStart
            const ratio=(acBase+delta)/(pcBase)
            out.push({mes:i+1,ratio:ratio})
        }
        return out
    }
    function findRiskMonth(ratios,thr){
        for(let i=0;i<ratios.length;i++){
            if(ratios[i].ratio<thr)return i+1
        }
        return null
    }
    function buildTrendText(cmgrInc,cmgrGas,riskIdx,burnRate,runway,dirInc,dirGas,marginStat){
        const gi=Math.round((cmgrInc||0)*10000)/100
        const gg=Math.round((cmgrGas||0)*10000)/100
        const risk=riskIdx?` Liquidez proyectada bajo 1,5 en Mes ${riskIdx}.`:` Liquidez proyectada estable ≥1,5.`
        const brTxt = (typeof burnRate==='number')?` Burn Rate ${fmtMoneySimple.format(burnRate)}/mes`:''
        const rwTxt = (typeof runway==='number')?` Runway ${runway} meses`:''
        const dirTxt = (dirInc&&dirGas)?` Tendencia: Ingresos ${dirInc} / Gastos ${dirGas}.`:''
        const mTxt = marginStat?` Margen: ${marginStat}.`:''
        return `Ingresos CMGR ${gi}% y Gastos CMGR ${gg}%.${risk}${dirTxt}${mTxt}${brTxt?'. '+brTxt:''}${rwTxt?' · '+rwTxt:''}`
    }
    function buildReco(riskIdx){
        if(riskIdx){return 'Adelantar cobros y renegociar pagos para superar 1,5 de liquidez.'}
        return 'Optimizar ciclo de caja y mantener control de gastos operativos.'
    }
    function computeBurnRate(cf,proj){
        if(!cf||cf.length===0)return 0
        // Preferir datos de tesorería si existen
        let burns=[]
        for(let i=0;i<cf.length;i++){
            const inflow = Number(cf[i].inflow||0)
            const outflow = Number(cf[i].outflow||0)
            if(inflow>0||outflow>0){
                burns.push(Math.max(0,outflow - inflow))
            }else{
                // Fallback: usar resultado operativo estimado (negativo implica consumo de caja)
                const res = proj && proj[i] ? Number(proj[i].resultado||0) : 0
                burns.push(res<0?Math.abs(res):0)
            }
        }
        if(burns.length===0)return 0
        const avg = burns.reduce((a,b)=>a+b,0)/burns.length
        return avg
    }
    function computeRunway(cashStart,burnRate){
        const c = Number(cashStart||0)
        const b = Number(burnRate||0)
        if(!b||b<=0)return Infinity
        const months = Math.floor(c/b)
        return months
    }
    function computeTrendDirection(arr){
        if(!arr||arr.length<2)return '→'
        const n=arr.length
        let xSum=0,ySum=0,xySum=0,xxSum=0
        for(let i=0;i<n;i++){
            const x=i
            const y=Number(arr[i]||0)
            xSum+=x;ySum+=y;xySum+=x*y;xxSum+=x*x
        }
        const denom=(n*xxSum)-(xSum*xSum)
        const slope=denom!==0?((n*xySum)-(xSum*ySum))/denom:0
        const mean=ySum/n
        const thr=Math.abs(mean)*0.05
        if(slope>thr)return '↑'
        if(slope<-thr)return '↓'
        return '→'
    }
    function computeMarginStatus(cmgrInc,cmgrGas){
        const eps=0.002
        if((cmgrGas||0)>(cmgrInc||0)+eps)return 'en erosión'
        if((cmgrInc||0)>(cmgrGas||0)+eps)return 'en mejora'
        return 'estable'
    }
    function renderSummaryLevel(level,obj){
        const el=document.getElementById('pred-summary')
        if(!el)return
        const conf=obj.confidence||'Alta'
        const txt=obj.text||''
        if(level==='basico'){
            el.textContent=`${txt.replace('CMGR','Crecimiento compuesto mensual').replace('Runway','Autonomía operativa').replace('Burn Rate','Consumo de caja')} (Confianza: ${conf}).`
            return
        }
        if(level==='tecnico'){
            const gi=Math.round((obj.cmgrInc||0)*10000)/100
            const gg=Math.round((obj.cmgrGas||0)*10000)/100
            const risk=obj.riskMonth?` Riesgo de liquidez en Mes ${obj.riskMonth}.`:' Liquidez estable ≥1,5.'
            el.innerHTML=`${txt}${risk} CMGR Ingresos ${gi}% · CMGR Gastos ${gg}%. (${confianzaLabel(conf)})`
            return
        }
        el.textContent=`${txt} (Confianza: ${conf}).`
    }
    function confianzaLabel(c){return c||'Alta'}
    function renderTable(proj,h,cf,ratios,level){
        const el=document.getElementById('pred-table')
        if(!el)return
        const cols=[]
        for(let i=1;i<=h;i++){cols.push(`Mes ${i}`)}
        const mkRow=(label,vals)=>`<tr><td>${label}</td>${vals.map(v=>`<td>${v}</td>`).join('')}</tr>`
        const ingresos=(proj||[]).map(x=>fmtMoneySimple.format(x.ingresos||0))
        const gastos=(proj||[]).map(x=>fmtMoneySimple.format(x.gastos||0))
        const resultado=(proj||[]).map(x=>fmtMoneySimple.format(x.resultado||0))
        const cobros=(cf||[]).map(x=>fmtMoneySimple.format(x.inflow||0))
        const pagos=(cf||[]).map(x=>fmtMoneySimple.format(x.outflow||0))
        const caja=(cf||[]).map(x=>fmtMoneySimple.format(x.balance||0))
        const liq=(ratios||[]).map(x=>(x.ratio||0).toFixed(2))
        const burnsNum=[]
        for(let i=0;i<h;i++){
            const inflow=Number(((cf||[])[i]&& (cf||[])[i].inflow)||0)
            const outflow=Number(((cf||[])[i]&& (cf||[])[i].outflow)||0)
            let b=0
            if(inflow>0||outflow>0){b=Math.max(0,outflow-inflow)}
            else{
                const res=(proj&&proj[i])?Number(proj[i].resultado||0):0
                b=res<0?Math.abs(res):0
            }
            burnsNum.push(b)
        }
        const burns=burnsNum.map(x=>fmtMoneySimple.format(x||0))
        const runways=[]
        for(let i=0;i<h;i++){
            const bal=Number(((cf||[])[i]&& (cf||[])[i].balance)||0)
            const b=Number(burnsNum[i]||0)
            runways.push(b>0?String(Math.floor(bal/b)):'∞')
        }
        let rows=`${mkRow('Ingresos',ingresos)}${mkRow('Gastos',gastos)}${mkRow('Resultado',resultado)}${mkRow('Caja y Bancos',caja)}${mkRow('Liquidez',liq)}`
        if(level!=='basico'){rows=`${mkRow('Ingresos',ingresos)}${mkRow('Gastos',gastos)}${mkRow('Resultado',resultado)}${mkRow('Cobros',cobros)}${mkRow('Pagos',pagos)}${mkRow('Caja y Bancos',caja)}${mkRow('Liquidez',liq)}${mkRow('Burn Rate',burns)}${mkRow('Runway (meses)',runways)}`}
        const html=`<table><thead><tr><th></th>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`
        el.innerHTML=html
    }
    function renderAlerts(obj){
        const el=document.getElementById('pred-alerts')
        if(!el)return
        if(obj.risk){el.innerHTML=`Riesgo de liquidez en Mes ${obj.risk} <span class="pred-badge-risk">Alerta</span>`}
        else{el.textContent='Sin gaps críticos de caja detectados.'}
    }
    function renderReco(text){
        const el=document.getElementById('pred-reco')
        if(!el)return
        el.textContent=text||''
    }
    const TERMS={
        'CMGR':'Crecimiento Compuesto Mensual: variación promedio mensual',
        'CAGR':'Tasa de Crecimiento Anual Compuesta: crecimiento medio anual',
        'Liquidez Corriente':'Activo Corriente / Pasivo Corriente',
        'Burn Rate':'Consumo medio de caja mensual',
        'Runway':'Autonomía operativa con la caja actual',
        'DSO':'Días de ventas pendientes de cobro'
    }
    function term(label){const def=TERMS[label]||'';return `<span class="term" title="${def}">${label}</span>`}
    function buildGlossary(keys){if(!keys||keys.length===0)return '';const items=keys.map(k=>`<div class="glossary-item"><strong>${k}:</strong> ${TERMS[k]}</div>`).join('');return `<div class="pred-glossary"><div class="glossary-title">Glosario</div>${items}</div>`}
    function renderReportByLevel(level,proj,cf,ratios,meta){
        const el=document.getElementById('pred-report')
        if(!el)return
        const h=(proj||[]).length||0
        const m1={
            ingresos:(proj&&proj[0])?Number(proj[0].ingresos||0):0,
            gastos:(proj&&proj[0])?Number(proj[0].gastos||0):0,
            resultado:(proj&&proj[0])?Number(proj[0].resultado||0):0,
            inflow:(cf&&cf[0])?Number(cf[0].inflow||0):0,
            outflow:(cf&&cf[0])?Number(cf[0].outflow||0):0,
            caja:(cf&&cf[0])?Number(cf[0].balance||0):0,
            liquidez:(ratios&&ratios[0])?Number(ratios[0].ratio||0):0
        }
        const liqs=(ratios||[]).map(x=>Number(x.ratio||0))
        const minLiq=liqs.length?Math.min.apply(null,liqs):0
        const minIdx=liqs.length?liqs.indexOf(minLiq)+1:null
        const totalInc=(proj||[]).reduce((a,b)=>a+Number(b.ingresos||0),0)
        const totalGas=(proj||[]).reduce((a,b)=>a+Number(b.gastos||0),0)
        const fmt=fmtMoneySimple
        if(level==='basico'){
            const b1=`<div class="report-block"><div class="report-title">Visión general</div><div class="report-text">Proyección a ${h} meses. Caja inicial ${fmt.format(Number(meta.cashStart||0))}. Mes 1: Ingresos ${fmt.format(m1.ingresos)}, Gastos ${fmt.format(m1.gastos)}, Resultado ${fmt.format(m1.resultado)}.</div></div>`
            const b2=`<div class="report-block"><div class="report-title">Tesorería y liquidez</div><div class="report-text">Cobros ${fmt.format(m1.inflow)}, Pagos ${fmt.format(m1.outflow)}. Caja proyectada ${fmt.format(m1.caja)}. Liquidez ${Number(m1.liquidez||0).toFixed(2)}${minIdx?`, mínimo ${minLiq.toFixed(2)} en mes ${minIdx}`:''}. ${meta.riskMonth?`Existe riesgo de liquidez en mes ${meta.riskMonth}.`:'Sin alertas críticas.'}</div></div>`
            const b3=`<div class="report-block"><div class="report-title">Conclusión</div><div class="report-text">Ingresos acumulados ${fmt.format(totalInc)} y gastos ${fmt.format(totalGas)} en ${h} meses. Priorizar cobros y ajustar pagos si aparece riesgo.</div></div>`
            el.innerHTML=b1+b2+b3
            return
        }
        if(level==='tecnico'){
            const b1=`<div class="report-block"><div class="report-title">Visión general</div><div class="report-text">Proyección a ${h} meses con caja inicial ${fmt.format(Number(meta.cashStart||0))}. Mes 1: Ingresos ${fmt.format(m1.ingresos)}, Gastos ${fmt.format(m1.gastos)}, Resultado ${fmt.format(m1.resultado)}.</div></div>`
            const b2=`<div class="report-block"><div class="report-title">Tesorería y ${term('Liquidez Corriente')}</div><div class="report-text">Cobros ${fmt.format(m1.inflow)}, Pagos ${fmt.format(m1.outflow)}. Caja ${fmt.format(m1.caja)}. Liquidez ${Number(m1.liquidez||0).toFixed(2)}${minIdx?`, mínimo ${minLiq.toFixed(2)} en mes ${minIdx}`:''}. ${meta.riskMonth?`Riesgo < 1,5 en mes ${meta.riskMonth}.`:'Sin alertas críticas.'}</div></div>`
            const gi=(Number(meta.cmgrInc||0)*100).toFixed(2)
            const gg=(Number(meta.cmgrGas||0)*100).toFixed(2)
            const b3=`<div class="report-block"><div class="report-title">${term('CMGR')} y márgenes</div><div class="report-text">CMGR Ingresos ${gi}% · CMGR Gastos ${gg}%. Consumo de caja (${term('Burn Rate')}) ${fmt.format(Number(meta.burnRate||0))}/mes. Autonomía (${term('Runway')}) ${meta.runway===Infinity?'∞':Number(meta.runway||0)} meses.</div></div>`
            const b4=`<div class="report-block"><div class="report-title">Conclusión</div><div class="report-text">Ingresos acumulados ${fmt.format(totalInc)} y gastos ${fmt.format(totalGas)} en ${h} meses. Reprogramar pagos y optimizar ciclo de cobros.</div></div>`
            el.innerHTML=b1+b2+b3+b4+buildGlossary(['Liquidez Corriente','CMGR','Burn Rate','Runway'])
            return
        }
        const gi=(Number(meta.cmgrInc||0)*100).toFixed(2)
        const gg=(Number(meta.cmgrGas||0)*100).toFixed(2)
        const b1=`<div class="report-block"><div class="report-title">Visión general</div><div class="report-text">Proyección a ${h} meses. Caja inicial ${fmt.format(Number(meta.cashStart||0))}. Mes 1: Ingresos ${fmt.format(m1.ingresos)}, Gastos ${fmt.format(m1.gastos)}, Resultado ${fmt.format(m1.resultado)}.</div></div>`
        const b2=`<div class="report-block"><div class="report-title">Tesorería</div><div class="report-text">Inflow ${fmt.format(m1.inflow)} · Outflow ${fmt.format(m1.outflow)} · Balance ${fmt.format(m1.caja)} · ${term('Liquidez Corriente')} ${Number(m1.liquidez||0).toFixed(2)}${minIdx?`, mínimo ${minLiq.toFixed(2)} en mes ${minIdx}`:''}.</div></div>`
        const b3=`<div class="report-block"><div class="report-title">Crecimiento y márgenes</div><div class="report-text">${term('CMGR')} Ingresos ${gi}% · ${term('CMGR')} Gastos ${gg}%. ${term('Burn Rate')} ${fmt.format(Number(meta.burnRate||0))}/mes · ${term('Runway')} ${meta.runway===Infinity?'∞':Number(meta.runway||0)} meses.</div></div>`
        const b4=`<div class="report-block"><div class="report-title">Conclusión ejecutiva</div><div class="report-text">Acumulado: Ingresos ${fmt.format(totalInc)} · Gastos ${fmt.format(totalGas)}. ${meta.riskMonth?'Reprogramar pagos y adelantar cobros en mes crítico identificado.':'Mantener disciplina de gasto y optimizar ciclo de caja; evaluar escenario pesimista para sensibilidad.'}</div></div>`
        el.innerHTML=b1+b2+b3+b4+buildGlossary(['Liquidez Corriente','CMGR','Burn Rate','Runway','DSO'])
    }
    function renderChartsByLevel(level,proj,cf,ratios){
        try{
            const h=(proj||[]).length||0
            const labels=[]
            for(let i=1;i<=h;i++){labels.push(`Mes ${i}`)}
            const ing=(proj||[]).map(x=>Number(x.ingresos||0))
            const gas=(proj||[]).map(x=>Number(x.gastos||0))
            const res=(proj||[]).map(x=>Number(x.resultado||0))
            const inflow=(cf||[]).map(x=>Number(x.inflow||0))
            const outflow=(cf||[]).map(x=>Number(x.outflow||0))
            const balance=(cf||[]).map(x=>Number(x.balance||0))
            const liq=(ratios||[]).map(x=>Number(x.ratio||0))
            const domOp=document.getElementById('pred-chart-operativa')
            const domTes=document.getElementById('pred-chart-tesoreria')
            const domLiq=document.getElementById('pred-chart-liquidez')
            if(!domOp||!domTes||!domLiq||typeof echarts==='undefined'){return}
            let c1=echarts.getInstanceByDom(domOp); if(c1)c1.dispose(); c1=echarts.init(domOp,null,{renderer:'svg'})
            let c2=echarts.getInstanceByDom(domTes); if(c2)c2.dispose(); c2=echarts.init(domTes,null,{renderer:'svg'})
            let c3=echarts.getInstanceByDom(domLiq); if(c3)c3.dispose(); c3=echarts.init(domLiq,null,{renderer:'svg'})
            const optOp=(level==='basico')?{
                tooltip:{trigger:'axis'},
                legend:{textStyle:{color:'#a1a1aa'}},
                xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
                yAxis:{type:'value',axisLabel:{color:'#a1a1aa'}},
                series:[
                    {name:'Ingresos',type:'bar',data:ing,itemStyle:{color:'#38bdf8'}},
                    {name:'Gastos',type:'bar',data:gas,itemStyle:{color:'#f59e0b'}},
                    {name:'Caja',type:'line',data:balance,itemStyle:{color:'#a855f7'}}
                ]
            }:{
                tooltip:{trigger:'axis'},
                legend:{textStyle:{color:'#a1a1aa'}},
                xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
                yAxis:{type:'value',axisLabel:{color:'#a1a1aa'}},
                series:[
                    {name:'Ingresos',type:'line',data:ing,itemStyle:{color:'#38bdf8'}},
                    {name:'Gastos',type:'line',data:gas,itemStyle:{color:'#f59e0b'}},
                    {name:'Resultado',type:'line',data:res,itemStyle:{color:'#34d399'}}
                ]
            }
            const optTes={
                tooltip:{trigger:'axis'},
                legend:{textStyle:{color:'#a1a1aa',fontSize:12}},
                xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
                yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:(v)=>fmtMoneySimple.format(v)}},
                series:[
                    {name:'Cobros',type:'bar',data:inflow,itemStyle:{color:'#34d399'}},
                    {name:'Pagos',type:'bar',data:outflow,itemStyle:{color:'#f87171'}},
                    {name:'Balance',type:'line',data:balance,itemStyle:{color:'#a855f7'}}
                ]
            }
            const optLiq={
                tooltip:{trigger:'axis'},
                xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
                yAxis:{type:'value',axisLabel:{color:'#a1a1aa'},min:0},
                series:[{name:'Liquidez Corriente',type:'line',data:liq,itemStyle:{color:'#fbbf24'},
                    markLine:{data:[{yAxis:1.5,name:'Umbral 1,5'}],label:{formatter:'Umbral 1,5'},lineStyle:{color:'#f87171',type:'dashed'}}}]
            }
            c1.setOption(optOp)
            c2.setOption(optTes)
            c3.setOption(optLiq)
            window.addEventListener('resize',function(){try{c1&&c1.resize();c2&&c2.resize();c3&&c3.resize()}catch(e){}})
        }catch(e){
            // Fallback simple text
        }
    }
    function renderFlujoCaja(cf){
        const dom=document.getElementById('pred-chart-flujocaja')
        if(!dom||typeof echarts==='undefined')return
        let chart=echarts.getInstanceByDom(dom); if(chart)chart.dispose(); chart=echarts.init(dom,null,{renderer:'svg'})
        const labels=[]; const net=[]; const balance=[]; const inflowArr=[]; const outflowArr=[]
        for(let i=0;i<(cf||[]).length;i++){
            labels.push(`Mes ${i+1}`)
            const inflow=Number((cf[i]&&cf[i].inflow)||0)
            const outflow=Number((cf[i]&&cf[i].outflow)||0)
            inflowArr.push(inflow)
            outflowArr.push(outflow)
            net.push(inflow-outflow)
            balance.push(Number((cf[i]&&cf[i].balance)||0))
        }
        const option={
            tooltip:{trigger:'axis'},
            legend:{textStyle:{color:'#a1a1aa'}},
            xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
            yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:function(v){return fmtMoneySimple.format(v)}}},
            series:[
                {name:'Cobros',type:'bar',data:inflowArr,itemStyle:{color:'#34d399'}},
                {name:'Pagos',type:'bar',data:outflowArr,itemStyle:{color:'#f87171'}},
                {name:'Flujo Neto',type:'bar',data:net,itemStyle:{color:'#22c55e'}},
                {name:'Balance',type:'line',data:balance,itemStyle:{color:'#a855f7'}}
            ]
        }
        chart.setOption(option)
        window.addEventListener('resize',function(){try{chart&&chart.resize()}catch(e){}})
    }
    function renderCombinedChart(proj,cf,ratios){
        const dom=document.getElementById('pred-chart-combinado')
        if(!dom||typeof echarts==='undefined')return
        let chart=echarts.getInstanceByDom(dom); if(chart)chart.dispose(); chart=echarts.init(dom,null,{renderer:'svg'})
        const h=(proj||[]).length||0
        const labels=[]
        for(let i=1;i<=h;i++){labels.push(`Mes ${i}`)}
        const ing=(proj||[]).map(x=>Number(x.ingresos||0))
        const gas=(proj||[]).map(x=>Number(x.gastos||0))
        const res=(proj||[]).map(x=>Number(x.resultado||0))
        const option={
            backgroundColor:'transparent',
            tooltip:{trigger:'axis',formatter:function(params){let s=`${params[0].name}`;params.forEach(p=>{s+=`<br/><span style="color:${p.color}">${p.seriesName}:</span> ${fmtMoneySimple.format(p.value)}`});return s}},
            legend:{textStyle:{color:'#a1a1aa'}},
            grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:labels,axisLabel:{color:'#a1a1aa'}},
            yAxis:{type:'value',axisLabel:{color:'#a1a1aa',formatter:function(v){return fmtMoneySimple.format(v)}}},
            series:[
                {name:'Ingresos',type:'bar',data:ing,itemStyle:{color:'#3b82f6'}},
                {name:'Gastos',type:'bar',data:gas,itemStyle:{color:'#ef4444'}},
                {name:'Resultado',type:'line',data:res,itemStyle:{color:'#10b981'},lineStyle:{width:2}}
            ]
        }
        chart.setOption(option)
        window.addEventListener('resize',function(){try{chart&&chart.resize()}catch(e){}})
    }
    function renderDataPanels(proj,cf,ratios){
        const mkTable=(headers,rows)=>{
            const thead=`<thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead>`
            const tbody=`<tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>`
            return `<table>${thead}${tbody}</table>`
        }
        const labels=(proj||[]).map((_,i)=>`Mes ${i+1}`)
        const operRows=[]
        for(let i=0;i<labels.length;i++){
            const p=proj[i]||{}
            operRows.push([labels[i],fmtMoneySimple.format(p.ingresos||0),fmtMoneySimple.format(p.gastos||0),fmtMoneySimple.format(p.resultado||0)])
        }
        const tesRows=[]
        for(let i=0;i<labels.length;i++){
            const t=cf[i]||{}
            tesRows.push([labels[i],fmtMoneySimple.format(t.inflow||0),fmtMoneySimple.format(t.outflow||0),fmtMoneySimple.format(t.balance||0)])
        }
        const liqRows=[]
        for(let i=0;i<labels.length;i++){
            const r=ratios[i]||{}
            liqRows.push([labels[i],(r.ratio||0).toFixed(2)])
        }
        const elOp=document.getElementById('pred-data-operativa'); 
        if(elOp){
            const meta=`<div class="pred-data-meta"><div class="pred-data-meta-title">Definición y fuente</div><div class="pred-data-meta-list"><div>Proyección: Ingresos/Gastos con crecimiento compuesto (CMGR)</div><div>Resultado = Ingresos − Gastos</div><div>Fuente: /api/financial/evolution/evolution (horizonte y escenario)</div></div></div>`
            elOp.innerHTML=meta+mkTable(['Mes','Ingresos','Gastos','Resultado'],operRows)
        }
        const elTes=document.getElementById('pred-data-tesoreria'); 
        if(elTes){
            const meta=`<div class="pred-data-meta"><div class="pred-data-meta-title">Definición y fuente</div><div class="pred-data-meta-list"><div>Definición: Cobros (inflow), Pagos (outflow), Caja (balance)</div><div>Fuente: /api/financial/treasury/forecast</div><div>Horizonte según selección</div></div></div>`
            elTes.innerHTML=meta+mkTable(['Mes','Cobros','Pagos','Balance'],tesRows)
        }
        const elLiq=document.getElementById('pred-data-liquidez'); 
        if(elLiq){
            const meta=`<div class="pred-data-meta"><div class="pred-data-meta-title">Definición y fuente</div><div class="pred-data-meta-list"><div>Fórmula: Liquidez Corriente = Activo Corriente / Pasivo Corriente</div><div>Ajuste UI: Activo Corriente + variación de caja proyectada</div><div>Fuente: Balance resumen y Tesorería (/api/financial/balance/summary, /api/financial/treasury/forecast)</div></div></div>`
            elLiq.innerHTML=meta+mkTable(['Mes','Liquidez'],liqRows)
        }
        const elComb=document.getElementById('pred-data-combinado'); 
        if(elComb){
            const meta=`<div class="pred-data-meta"><div class="pred-data-meta-title">Definición y fuente</div><div class="pred-data-meta-list"><div>Visualización combinada de Ingresos, Gastos y Resultado</div><div>Resultado = Ingresos − Gastos</div><div>Fuente: /api/financial/evolution/evolution</div></div></div>`
            elComb.innerHTML=meta+mkTable(['Mes','Ingresos','Gastos','Resultado'],operRows)
        }
        const elFluj=document.getElementById('pred-data-flujocaja');
        if(elFluj){
            const rows=[]
            for(let i=0;i<labels.length;i++){
                const t=cf[i]||{}
                const inflow=Number(t.inflow||0)
                const outflow=Number(t.outflow||0)
                const net=inflow-outflow
                const bal=Number(t.balance||0)
                rows.push([labels[i],fmtMoneySimple.format(inflow),fmtMoneySimple.format(outflow),fmtMoneySimple.format(net),fmtMoneySimple.format(bal)])
            }
            const meta=`<div class="pred-data-meta"><div class="pred-data-meta-title">Definición y fuente</div><div class="pred-data-meta-list"><div>Cobros (inflow) · Pagos (outflow) · Flujo Neto = Cobros − Pagos</div><div>Balance = Caja proyectada</div><div>Fuente: /api/financial/treasury/forecast</div></div></div>`
            elFluj.innerHTML=meta+mkTable(['Mes','Cobros','Pagos','Flujo Neto','Balance'],rows)
        }
    }
    function attachToggleHandlers(){
        const buttons=document.querySelectorAll('.pred-toggle')
        buttons.forEach(btn=>{
            const target=btn.getAttribute('data-target')
            const panel=document.getElementById(target)
            if(!panel)return
            btn.onclick=function(){
                const isOpen=panel.style.display!=='none'
                panel.style.display=isOpen?'none':'block'
                btn.setAttribute('aria-expanded', String(!isOpen))
                btn.textContent=isOpen?'Ver datos de origen':'Ocultar datos de origen'
            }
        })
    }
    window.initPrediccion=initPrediccion
})(); 
