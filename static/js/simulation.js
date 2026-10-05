/* What-If Simulator */
let base=null,runs=[],defaults={};
const IDS=['stock','pending','lead','tc','sp'];
function fillInputs(d){$('w_stock').value=d.stock;$('w_pending').value=d.pending;$('w_lead').value=d.lead;$('w_chg').value=0;$('dcv').textContent='0';$('w_tc').value=defaults.transport_cost_per_km;$('w_sp').value=defaults.stockout_penalty_pct}
async function loadBase(){
  try{base=await api('/api/recommendation/'+$('prod').value);fillInputs(base.default_whatif);
    $('baseNote').textContent=`Baseline: ${fmt(base.default_whatif.demand)} kg predicted 7-day demand`}catch(e){toast(e.message,1)}
}
function preset(k){
  if(k==='reset'){fillInputs(base.default_whatif);return}
  const p={ok:{stock:500,pending:80,lead:5,chg:0},crisis:{stock:100,pending:80,lead:7,chg:40}}[k];
  $('w_stock').value=p.stock;$('w_pending').value=p.pending;$('w_lead').value=p.lead;$('w_chg').value=p.chg;$('dcv').textContent=p.chg;
}
const col=(a,b,lowerBetter)=>{const better=lowerBetter?b<a:b>a;return b===a?'':`style="color:${better?'#4ade80':'#f87171'}"`};
function metricRow(l,a,b,f,lowerBetter){return `<tr><td>${l}</td><td class="n">${f(a)}</td><td class="n" ${col(a,b,lowerBetter)}><b>${f(b)}</b></td></tr>`}
async function run(){
  const body={product_id:$('prod').value,demand_change_pct:$('w_chg').value,stock:$('w_stock').value,pending:$('w_pending').value,lead:$('w_lead').value,transport_cost:$('w_tc').value,stockout_penalty:$('w_sp').value};
  $('runBtn').disabled=true;$('runBtn').textContent='Simulating…';
  $('result').innerHTML=`<div class="card">${skeleton(4,40)}</div>`;
  try{
    const r=await post('/api/whatif/compare',body),c=r.current,a=r.ai,rec=r.recommendation,H=r.horizon_weeks;
    runs.unshift({name:$('prod').selectedOptions[0].text,body,h:rec.headline,sav:r.savings,so:[c.stockout_prob,a.stockout_prob]});runs=runs.slice(0,6);
    $('log').innerHTML=runs.map((x,i)=>`<div class="step"><div class="no">${runs.length-i}</div><div><b>${esc(x.name)}</b> <span class="small mut">stock ${x.body.stock} · demand ${x.body.demand_change_pct>=0?'+':''}${x.body.demand_change_pct}% · lead ${x.body.lead}d</span><br>AI → <b>${esc(x.h)}</b> <span class="small mut">stockout ${x.so[0]}% → ${x.so[1]}% · saving ${money(x.sav)}</span></div></div>`).join('');
    $('result').innerHTML=`<div class="grid g4">${[['Stockout risk',c.stockout_prob+'%',a.stockout_prob+'%','alert','red'],['Inventory cost',money(c.holding),money(a.holding),'package','blue'],['Service level',c.service_level+'%',a.service_level+'%','shield','green'],['Expected profit',money(c.expected_profit),money(a.expected_profit),'dollar','purple']]
      .map(x=>`<div class="card kpi"><div class="top"><div class="lbl">${x[0]}</div><div class="ic ${x[4]}">${ico(x[3],18)}</div></div><div class="small mut" style="margin-top:8px">Current</div><b>${x[1]}</b><div class="small mut" style="margin-top:4px">AI recommended</div><div class="val" style="font-size:21px;margin:0">${x[2]}</div></div>`).join('')}</div>
     <div class="grid g-main"><div class="card decision"><div class="card-h"><div class="name">AI DECISION</div><span class="tag">SIMULATION</span></div><div class="head">AI → ${esc(rec.headline)}</div>
       <div class="dgrid"><div><span>Reorder</span><b>${fmt(rec.reorder_qty)} kg</b></div><div><span>Supply</span><b>${fmt(rec.supply_qty)} kg</b></div><div><span>Risk</span><b>${badge(rec.risk)}</b></div><div><span>Estimated savings (${H} wk)</span><b style="color:${r.savings>=0?'#4ade80':'#f87171'}">${money(r.savings)}</b></div></div>
       <ul class="reasons">${rec.reasons.slice(0,5).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${rec.trained?'':'<p class="small" style="color:#fbbf24">Agent untrained: decision is exploratory. <a href="/training">Train the agent</a>.</p>'}</div>
      <div class="card"><div class="card-h"><h3>Comparison table</h3></div><div class="tbl"><table><thead><tr><th>Metric (${H}-week sim)</th><th class="n">Current</th><th class="n">AI</th></tr></thead><tbody>
       ${metricRow('Stockout risk (%)',c.stockout_prob,a.stockout_prob,v=>v+'%',true)}${metricRow('Service level (%)',c.service_level,a.service_level,v=>v+'%',false)}${metricRow('Holding cost',c.holding,a.holding,money,true)}${metricRow('Stockout cost',c.stockout,a.stockout,money,true)}${metricRow('Ordering cost',c.ordering,a.ordering,money,true)}${metricRow('Transport cost',c.transport,a.transport,money,false)}${metricRow('Total cost',c.total_cost,a.total_cost,money,true)}${metricRow('Expected profit',c.expected_profit,a.expected_profit,money,false)}</tbody></table></div>
       <p class="note">${esc(r.label)}. Transport cost rises with sales volume, so a higher value can simply mean more demand was served.</p></div></div>
     <div class="grid g-eq"><div class="card"><div class="card-h"><h3>Risk and service level</h3></div><div class="chartbox sm"><canvas id="cA"></canvas></div></div>
      <div class="card"><div class="card-h"><h3>Cost breakdown <small>₹, ${H} weeks</small></h3></div><div class="chartbox sm"><canvas id="cB"></canvas></div></div></div>
     <div class="card"><div class="card-h"><h3>Projected stock level <small>mean of 300 simulated runs, kg</small></h3></div><div class="chartbox"><canvas id="cC"></canvas></div></div>`;
    makeChart('cA',{type:'bar',data:{labels:['Stockout risk (%)','Service level (%)'],datasets:[{label:'Current scenario',data:[c.stockout_prob,c.service_level],backgroundColor:'#5f6c8b',borderRadius:4},{label:'AI recommended',data:[a.stockout_prob,a.service_level],backgroundColor:'#4f8cff',borderRadius:4}]},options:{scales:{y:{max:100,...axisT('%')}}}});
    const comp=['holding','stockout','transport','ordering'],names=['Holding','Stockout','Transport','Ordering'];
    makeChart('cB',{type:'bar',data:{labels:['Current scenario','AI recommended'],datasets:comp.map((k,i)=>({label:names[i],data:[c[k],a[k]],backgroundColor:['#4f8cff','#ef4444','#22d3ee','#8b5cf6'][i]}))},options:{scales:{x:{stacked:true},y:{stacked:true,...axisT('₹')}}}});
    makeChart('cC',{type:'line',data:{labels:c.traj.map((_,i)=>i===0?'Now':'Week '+i),datasets:[{label:'Current scenario',data:c.traj,borderColor:'#8f9bb8',tension:.25,pointRadius:3},{label:'AI recommended',data:a.traj,borderColor:'#22d3ee',tension:.25,pointRadius:3}]},options:{scales:{y:axisT('kg in stock')}}});
  }catch(e){errorState($('result'),e.message,run)}
  $('runBtn').disabled=false;$('runBtn').textContent='Run Simulation';
}
async function init(){
  try{const s=await api('/api/settings');defaults=s.settings;
    const recs=await api('/api/recommendations');$('prod').innerHTML=recs.map(r=>`<option value="${r.product_id}">${esc(r.product_name)}</option>`).join('');
    const p=new URLSearchParams(location.search).get('product');if(p)$('prod').value=p;await loadBase();
  }catch(e){toast(e.message,1)}
}
$('prod').onchange=loadBase;$('w_chg').oninput=e=>$('dcv').textContent=e.target.value;
window.onBrainChanged=()=>{};
init();
