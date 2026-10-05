let rewards=[],running=false,stopFlag=false,QT=[];
const ACT=['ORDER_MORE','SUPPLY_NORMAL','SUPPLY_HIGH','WAIT','REDUCE_STOCK'];
function binned(arr,maxPts=300){const step=Math.max(1,Math.ceil(arr.length/maxPts)),out=[],lab=[];for(let i=0;i<arr.length;i+=step){const ch=arr.slice(i,i+step);out.push(ch.reduce((a,b)=>a+b,0)/ch.length);lab.push(i+ch.length)}return{lab,out}}
const movAvg=(arr,w=50)=>arr.map((_,i)=>{const s=arr.slice(Math.max(0,i-w+1),i+1);return s.reduce((a,b)=>a+b,0)/s.length});
function drawCharts(s){
  const b=binned(rewards),m=binned(movAvg(rewards).map(x=>x/12));
  makeChart('cReward',{type:'line',data:{labels:b.lab,datasets:[{label:'Episode reward (binned)',data:b.out,borderColor:'#4f8cff',backgroundColor:'#4f8cff18',fill:true,pointRadius:0,borderWidth:1.5,tension:.2}]},options:{animation:false,scales:{x:axisT('Training episode'),y:axisT('Total reward per episode')}}});
  makeChart('cAvg',{type:'line',data:{labels:m.lab,datasets:[{label:'Average reward per decision',data:m.out,borderColor:'#22c55e',pointRadius:0,borderWidth:2.5,tension:.3}]},options:{animation:false,scales:{x:axisT('Training episode'),y:axisT('Reward per decision')},plugins:{legend:{display:false}}}});
  const ac=s.action_counts||[0,0,0,0,0];
  makeChart('cAct',{type:'bar',data:{labels:ACT,datasets:[{label:'Times chosen',data:ac,backgroundColor:['#4f8cff','#22d3ee','#8b5cf6','#f59e0b','#ef4444'],borderRadius:4}]},options:{animation:false,scales:{y:axisT('count')},plugins:{legend:{display:false}}}});
}
const card=(l,v,s,c)=>`<div class="card kpi"><div class="top"><div class="lbl">${l}</div></div><div class="val" style="color:${c||'inherit'}">${v}</div><div class="desc">${s||''}</div></div>`;
function renderLive(s,cur,eps,pct){
  $('live').innerHTML=[card('Training Episodes',fmt(s.episodes),'total in this brain'),card('States',s.q_states+' / '+s.q_states_total,'visited by the agent'),card('Actions','5','ORDER_MORE … REDUCE_STOCK'),
   card('Total Reward',fmt(s.total_reward),'cumulative, all episodes'),card('Average Reward',(s.avg_reward_per_decision>0?'+':'')+s.avg_reward_per_decision,'per decision, last 100 episodes','#4ade80'),
   card('Exploration Rate',(eps==null?s.last_epsilon:eps).toFixed(3),'probability of a random action'),card('Q-table Size',s.q_pairs+' / '+s.q_pairs_total,'state-action pairs tried'),
   card('Training Progress',Math.round(pct==null?(s.episodes?100:0):pct)+'%',`stockout ${(100*s.stockout_rate).toFixed(1)}% · success ${(100*s.success_rate).toFixed(1)}%`)].join('');
}
function qtable(rows){QT=rows;$('qt').innerHTML=rows.map(r=>{const mx=Math.max(...r.q.map(Math.abs),0.01),best=r.best?r.q.indexOf(Math.max(...r.q)):-1;
  return `<tr><td style="text-align:left;white-space:nowrap">${r.state}</td>${r.q.map((v,i)=>{const a=(Math.min(1,Math.abs(v)/mx)*0.5).toFixed(2);return `<td class="${i===best?'best':''}" style="background:${r.visits?(v>=0?`rgba(79,140,255,${a})`:`rgba(239,68,68,${a})`):'#0e1527'}">${r.visits?v.toFixed(2):'–'}</td>`}).join('')}<td>${r.visits}</td></tr>`}).join('')}
function showQ(){$('qCard').style.display='block';$('qCard').scrollIntoView({behavior:'smooth'})}
const metrics=m=>[['Decision accuracy',m.decision_accuracy+'%'],['Stockout rate',m.stockout_rate+'%'],['Excess inventory',m.excess_inventory+'%'],['Average reward',(m.average_reward>0?'+':'')+m.average_reward]].map(x=>`<div class="m"><span class="mut">${x[0]}</span><b>${x[1]}</b></div>`).join('');
async function evaluate(){
  try{const r=await post('/api/evaluate',{episodes:300});$('before').innerHTML=metrics(r.before);
    if(r.episodes_trained>0){$('after').innerHTML=metrics(r.after);$('afterNote').textContent='learned policy, '+fmt(r.episodes_trained)+' episodes'}
    else{$('after').innerHTML=emptyState('Not trained yet','Click Start Training');$('afterNote').textContent=''}}catch(e){toast(e.message,1)}
}
async function refresh(){
  try{const s=await api('/api/training/state');rewards=s.episode_rewards;drawCharts(s);renderLive(s,rewards.length?rewards[rewards.length-1]:null);qtable(s.qtable);refreshMeta();
    if(!rewards.length){$('progTxt').textContent='Agent untrained. Set the parameters and click Start Training.'}
  }catch(e){errorState($('live'),e.message,refresh)}
}
async function startTraining(){
  if(running)return;
  const alpha=+$('alpha').value,gamma=+$('gamma').value,eps=+$('eps').value,total=Math.round(+$('episodes').value);
  if(!(alpha>0&&alpha<=1)||!(gamma>=0&&gamma<1)||!(eps>=0&&eps<=1)||!(total>=50)){toast('Check inputs: 0<α≤1, 0≤γ<1, 0≤ε≤1, episodes ≥ 50',1);return}
  running=true;stopFlag=false;$('startBtn').disabled=true;$('stopBtn').disabled=false;await evaluate();
  const batch=Math.max(10,Math.ceil(total/80));let done=0;
  try{
    while(done<total&&!stopFlag){
      const n=Math.min(batch,total-done);
      const r=await post('/api/train',{episodes:n,offset:done,total,alpha,gamma,epsilon:eps});
      done+=n;rewards=rewards.concat(r.batch_rewards);const pct=100*done/total;
      renderLive(r,r.current_reward,r.epsilon,pct);drawCharts(r);$('prog').style.width=pct+'%';$('progTxt').textContent=`Training… ${done} / ${total} episodes (ε = ${r.epsilon.toFixed(3)})`;
      await sleep(60);
    }
    await post('/api/training/finish');
  }catch(e){toast(e.message,1)}
  $('progTxt').textContent=stopFlag?`Stopped after ${done} episodes.`:`Finished ${done} episodes. Log saved to data/training_results.csv.`;
  running=false;$('startBtn').disabled=false;$('stopBtn').disabled=true;await refresh();await evaluate();refreshMeta();
}
const stopTraining=()=>{stopFlag=true};
async function resetAgent(){
  if(running)return;
  if(!await confirmDialog('Reset the agent?','All learned Q-values and training history are deleted. A saved brain file is not touched.','Reset agent',true))return;
  try{await post('/api/training/reset');rewards=[];$('prog').style.width='0%';await refresh();await evaluate();toast('Agent reset')}catch(e){toast(e.message,1)}
}
window.onBrainChanged=async()=>{await refresh();await evaluate()};
refresh().then(evaluate);
