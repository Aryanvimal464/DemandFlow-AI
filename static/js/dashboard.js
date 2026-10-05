const NODES=[['bar','Historical Data'],['trend','Demand Analysis'],['package','Inventory State'],['cpu','Q-Learning Agent'],['target','Action Selection'],['check','Business Outcome'],['shield','Reward / Penalty'],['zap','Learning Update']];
const STATUS=['LOADING HISTORICAL DATA...','ANALYZING DEMAND...','READING INVENTORY STATE...','EVALUATING ACTIONS...','SELECTING BEST ACTION...','CALCULATING BUSINESS IMPACT...','COMPUTING REWARD / PENALTY...','UPDATING LEARNING MODEL...'];
let D=null,demoRunning=false,pipeRun=0;

function renderPipe(caps){$('pipe').innerHTML=NODES.map((n,i)=>`<div class="node" id="n${i}"><div class="ic">${ico(n[0],22)}</div><b>${n[1]}</b><small>${esc((caps||[])[i]||'')}</small></div>`).join('')}
function setNodes(active,done){NODES.forEach((_,i)=>{const e=$('n'+i);if(!e)return;e.classList.toggle('active',active.includes(i));e.classList.toggle('done',done.includes(i)&&!active.includes(i))})}
async function playPipeline(){
  if(demoRunning)return;const id=++pipeRun;const done=[];
  for(let i=0;i<NODES.length;i++){if(id!==pipeRun)return;setNodes([i],done);$('pipeStatus').textContent=STATUS[i];await sleep(520);done.push(i)}
  if(id===pipeRun){setNodes([],done);$('pipeStatus').textContent='RECOMMENDATION READY'}
}

function kpiCard(c){return `<div class="card kpi"><div class="top"><div class="lbl" data-tip="${esc(c.tip)}">${c.label}</div><div class="ic ${c.color}">${ico(c.icon,18)}</div></div><div class="val">${c.value}</div><div class="desc">${c.desc}</div>${c.delta}</div>`}
const ptsDelta=(pts,basis,hide)=>pts==null?delta(null,{basis}):`<div class="delta ${pts>0.05?'up':pts<-0.05?'down':'flat'}">${pts>0?'↑':pts<0?'↓':'→'} ${Math.abs(pts).toFixed(1)} pts <span>${esc(basis)}</span></div>`;
function renderKpis(k){
  const sr=k.stockout_risk;const srPct=sr.no_action_flagged>0?100*(sr.ai_flagged-sr.no_action_flagged)/sr.no_action_flagged:null;
  const fa=k.forecast_accuracy;
  $('kpis').innerHTML=[
   {label:'Inventory Value',icon:'package',color:'blue',value:money(k.inventory_value.value),desc:'stock × unit price',delta:delta(k.inventory_value.change_pct,{basis:'vs ~4 weeks ago'}),tip:k.inventory_value.basis},
   {label:'Pending Orders',icon:'clipboard',color:'cyan',value:fmt(k.pending_orders.value),desc:'Pending + Confirmed',delta:delta(k.pending_orders.change_pct,{basis:'new orders vs prior 7 days'}),tip:k.pending_orders.basis},
   {label:'Stockout Risk',icon:'alert',color:sr.value?'red':'green',value:fmt(sr.value)+' Product'+(sr.value===1?'':'s'),desc:'high-risk right now',delta:delta(srPct,{basis:`AI vs no action (${sr.no_action_flagged}→${sr.ai_flagged}, simulated)`,invert:true}),tip:sr.basis},
   {label:'7-Day Forecast Demand',icon:'trend',color:'purple',value:fmt(k.forecast_demand.value)+' kg',desc:'statistical forecast',delta:delta(k.forecast_demand.change_pct,{basis:'vs last 7 days actual'}),tip:k.forecast_demand.basis},
   {label:'Forecast Accuracy',icon:'target',color:'blue',value:fa.value==null?'–':fa.value.toFixed(1)+'%',desc:'30-day backtest (synthetic)',delta:fa.value==null?delta(null,{}):ptsDelta(fa.value-fa.naive,'vs naive baseline'),tip:fa.basis},
   {label:'AI Estimated Savings',icon:'dollar',color:'green',value:money(k.ai_savings.value),desc:'simulated, '+(D.decision.impact.horizon_weeks)+'-week horizon',delta:delta(k.ai_savings.pct,{basis:'cost reduction vs no action'}),tip:k.ai_savings.basis},
   {label:'Service Level',icon:'shield',color:'green',value:k.service_level.value.toFixed(1)+'%',desc:'simulated fill rate with AI',delta:ptsDelta(k.service_level.delta_pts,'vs no action'),tip:k.service_level.basis},
   {label:'Active Alerts',icon:'bell',color:k.alerts.critical?'orange':'green',value:fmt(k.alerts.value),desc:k.alerts.critical+' critical',delta:'<div class="delta flat"><span>generated from live inventory data</span></div>',tip:'Alerts are derived from stock cover, demand trend, overstock and order deadlines.'}
  ].map(kpiCard).join('');
}

function renderDecision(r){
  const im=r.impact;
  const risk=im.stockout_risk_reduction_pct>0?`Stockout risk ↓ ${im.stockout_risk_reduction_pct}%`:`Stockout risk ${im.stockout_risk_before}% → ${im.stockout_risk_after}%`;
  $('decision').innerHTML=`<div class="card-h"><div class="name">AI DECISION CENTER</div><span class="tag">SIMULATION</span></div>
   <div class="name" style="color:#9db9f5">${esc(r.product_name.toUpperCase())}</div><div class="head">${esc(r.headline)}</div>
   <div class="dgrid"><div><span>Recommended Quantity</span><b>${fmt(r.reorder_qty)} kg</b></div><div><span>Confidence</span><b>${r.confidence}%</b></div>
    <div><span>Risk</span><b>${badge(r.risk)}</b></div>
    <div><span>Expected Impact (${im.horizon_weeks} wk sim)</span><b style="font-size:13px;line-height:1.5">${risk}<br>Service level ↑ ${im.service_delta_pts} pts</b></div></div>
   <ul class="reasons">${r.reasons.slice(0,4).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
   ${r.trained?'':`<p class="small" style="color:#fbbf24">The Q-learning agent is untrained, so this recommendation is exploratory. <a href="/training">Train it in the AI Training Lab</a>.</p>`}
   <div class="row"><button class="btn" onclick="showExplain()">View Explanation</button><a class="btn" href="/what-if?product=${r.product_id}">Run Simulation</a>
    <button class="btn primary" onclick="applyTop()">Apply Recommendation (simulation)</button></div>`;
}
function showExplain(){const r=D.decision;
  openModal(`<h3>Why ${esc(r.label)} for ${esc(r.product_name)}?</h3><div class="chips" style="margin-bottom:10px">${r.state_parts.map(s=>`<span class="chip">${s}</span>`).join('')}</div>
   <ol style="padding-left:18px;color:#cbd5ec">${r.reasons.map(x=>`<li style="margin-bottom:5px">${esc(x)}</li>`).join('')}</ol>
   <p class="small mut">Confidence ${r.confidence}% · Risk ${r.risk}. Impact figures come from a 300-run Monte-Carlo simulation with editable parameters.</p>
   <div class="acts"><a class="btn" href="/ai-agent">Open AI Supply Agent</a><button class="btn primary" onclick="closeModal()">Close</button></div>`)}
async function applyTop(){const r=D.decision;
  if(!await confirmDialog('Apply recommendation (simulation)?',`This runs a <b>simulated</b> week for ${esc(r.product_name)} (${esc(r.label)}${r.reorder_qty?' '+r.reorder_qty+' kg':''}), updates the demo database and gives the agent a reward or penalty.`,'Apply in simulation'))return;
  try{const x=await post(`/api/recommendation/${r.product_id}/apply`);toast(`Simulated outcome: ${x.outcome}. Reward ${x.reward>0?'+':''}${x.reward}`);await load()}catch(e){toast(e.message,1)}}

function renderAlerts(a){
  $('alertCount').textContent=D.kpis.alerts.value?`${D.kpis.alerts.value} active`:'';
  $('alerts').innerHTML=a.length?a.map(x=>`<div class="alert" onclick="showAlert(${x.id})"><span class="sev ${x.severity}">${x.severity}</span><div><div class="at">${esc(x.title)}</div><small>${esc(x.action)} · ${esc(x.timestamp)}</small></div></div>`).join(''):emptyState('No active alerts','Inventory looks healthy.');
}
function showAlert(id){const x=D.alerts.find(a=>a.id===id);if(!x)return;
  openModal(`<h3><span class="sev ${x.severity}">${x.severity}</span> ${esc(x.title)}</h3>
   <div class="m"><span class="mut">Product</span><b style="font-size:13px">${esc(x.product)}</b></div><div class="m"><span class="mut">Reason</span><span style="max-width:300px;text-align:right">${esc(x.reason)}</span></div>
   <div class="m"><span class="mut">Recommended action</span><b style="font-size:13px">${esc(x.action)}</b></div><div class="m"><span class="mut">Timestamp</span><span>${esc(x.timestamp)}</span></div>
   <div class="acts"><a class="btn" href="/inventory?open=${x.product_id}">Open product</a><a class="btn" href="/ai-agent">AI agent</a><button class="btn primary" onclick="closeModal()">Close</button></div>`)}

async function load(){
  try{
    D=await api('/api/command-center');
    renderPipe([`${D.kpis.pending_orders.value} open orders`,`${fmt(D.forecast_next)} kg / 7d`,`${D.kpis.stockout_risk.value} at risk`,`${D.q_states}/${D.q_states_total} states`,D.decision.label,'simulated','reward ±','Q-table update']);
    renderKpis(D.kpis);renderDecision(D.decision);renderAlerts(D.alerts);
    makeChart('cStock',{type:'bar',data:{labels:D.inventory.map(i=>i.name),datasets:[{label:'Current stock',data:D.inventory.map(i=>i.stock),backgroundColor:'#4f8cff',borderRadius:4},{label:'Predicted 7-day demand',data:D.inventory.map(i=>i.d7),backgroundColor:'#22d3ee',borderRadius:4},{label:'Safety stock',data:D.inventory.map(i=>i.safety),backgroundColor:'#f59e0b',borderRadius:4}]},options:{scales:{y:axisT('kg'),x:{ticks:{maxRotation:55}}}}});
    const wl=D.weekly_total.map((_,i)=>i===D.weekly_total.length-1?'This week':`W-${D.weekly_total.length-1-i}`).concat(['Next 7 days']);
    makeChart('cWeekly',{type:'line',data:{labels:wl,datasets:[{label:'Actual demand',data:D.weekly_total,borderColor:'#4f8cff',backgroundColor:'#4f8cff22',fill:true,tension:.3,pointRadius:3},{label:'Forecast',data:D.weekly_total.map((_,i)=>i===D.weekly_total.length-1?D.weekly_total[i]:null).concat([D.forecast_next]),borderColor:'#22d3ee',borderDash:[6,5],pointRadius:4}]},options:{scales:{y:axisT('kg / week')}}});
    makeChart('cOrders',{type:'doughnut',data:{labels:Object.keys(D.order_status),datasets:[{data:Object.values(D.order_status),backgroundColor:['#22c55e','#f59e0b','#4f8cff','#8b5cf6','#ef4444'],borderColor:'#121a2f'}]},options:{cutout:'62%',plugins:{legend:{position:'right'}}}});
    if(D.curve.length){makeChart('cLearn',{type:'line',data:{labels:D.curve.map((_,i)=>i+1),datasets:[{label:'Avg episode reward',data:D.curve,borderColor:'#22c55e',pointRadius:0,tension:.3,fill:true,backgroundColor:'#22c55e18'}]},options:{animation:false,scales:{x:axisT('training progress'),y:axisT('reward')},plugins:{legend:{display:false}}}});
      $('learnNote').textContent=`${fmt(D.episodes)} episodes · ${D.q_states}/${D.q_states_total} states learned`}
    else{if(charts.cLearn){charts.cLearn.destroy();delete charts.cLearn}$('learnNote').innerHTML='Agent untrained. <a href="/training">Start training</a> or run the full demo.'}
    $('recent').innerHTML=D.recent_decisions.length?D.recent_decisions.map(x=>`<div class="step"><div><b>${esc(x.product_name)}</b> · ${esc(x.label)} ${badge(x.status)} <span class="mono small">${x.reward>0?'+':''}${x.reward}</span><br><span class="small mut">${esc(x.outcome)}</span></div></div>`).join(''):emptyState('No decisions yet','Apply or reject a recommendation to see learning feedback.');
  }catch(e){errorState($('decision'),e.message,load);$('kpis').innerHTML='';}
}

const cmpRows=m=>`<div class="m"><span>Decision accuracy</span><b>${m.decision_accuracy}%</b></div><div class="m"><span>Stockout rate</span><b>${m.stockout_rate}%</b></div><div class="m"><span>Excess inventory</span><b>${m.excess_inventory}%</b></div><div class="m"><span>Average reward</span><b>${m.average_reward>0?'+':''}${m.average_reward}</b></div>`;
async function runDemo(){
  if(demoRunning)return;
  if(!await confirmDialog('Run the full demo?','The demo <b>resets the AI brain</b> (Q-table), runs one simulated decision loop, trains 1,500 simulated episodes and shows before/after metrics.','Run demo'))return;
  demoRunning=true;pipeRun++;const btn=$('demoBtn');btn.disabled=true;btn.textContent='Running demo…';
  const log=$('demoLog');log.innerHTML=`<div style="margin-top:12px">${skeleton(3)}</div>`;
  try{
    const r=await post('/api/demo');log.innerHTML='<div style="margin-top:12px"></div>';const box=log.firstChild;const done=[];
    for(const s of r.steps){
      setNodes(s.node,done);$('pipeStatus').textContent=STATUS[s.node[s.node.length-1]]||'';
      box.insertAdjacentHTML('beforeend',`<div class="step"><div class="no">${s.n}</div><div><b>${esc(s.title)}</b><div class="mut">${esc(s.text)}</div>${s.reasons?'<ul>'+s.reasons.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':''}</div></div>`);
      if(s.before)box.insertAdjacentHTML('beforeend',`<div class="cmp" style="margin-top:12px"><div class="card before"><h3>Before training <small>simulation metrics</small></h3>${cmpRows(s.before)}</div><div class="card after"><h3>After training <small>simulation metrics</small></h3>${cmpRows(s.after)}</div></div><p class="note"><a href="/training">Open the AI Training Lab for the learning curve and Q-table →</a></p>`);
      s.node.forEach(n=>done.push(n));await sleep(1100);
    }
    setNodes([],done);$('pipeStatus').textContent='RECOMMENDATION READY';toast('Demo complete: '+r.episodes+' episodes trained');await load();refreshMeta();
  }catch(e){toast(e.message,1);log.innerHTML=''}
  demoRunning=false;btn.disabled=false;btn.textContent='Run Full Demo';
}
window.onBrainChanged=load;
load().then(playPipeline);
