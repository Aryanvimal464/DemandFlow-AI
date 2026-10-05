/* SupplyMind AI shared front-end helpers */
const ICONS={
 grid:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
 package:'<path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
 trend:'<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
 clipboard:'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
 users:'<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
 cpu:'<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
 sliders:'<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
 zap:'<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
 truck:'<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
 dollar:'<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
 activity:'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
 bell:'<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
 search:'<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
 menu:'<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>',
 alert:'<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
 check:'<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
 shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
 target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
 x:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
 inbox:'<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
 up:'<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
 down:'<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>',
 box:'<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>',
 clock:'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
 help:'<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
 bar:'<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'
};
const ico=(n,s)=>`<svg class="ico" viewBox="0 0 24 24"${s?` style="width:${s}px;height:${s}px"`:''}>${ICONS[n]||''}</svg>`;
function paintIcons(root){(root||document).querySelectorAll('svg[data-ico]').forEach(s=>{s.setAttribute('viewBox','0 0 24 24');s.innerHTML=ICONS[s.dataset.ico]||'';s.removeAttribute('data-ico')})}

/* networking */
async function api(url,opts){let r;try{r=await fetch(url,opts)}catch(e){throw new Error('Network error: could not reach the server')}
 let j={};try{j=await r.json()}catch(e){}if(!r.ok)throw new Error(j.error||j.message||('Request failed ('+r.status+')'));return j}
const post=(u,b={})=>api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});

/* formatting */
const fmt=(n,d=0)=>(n==null||isNaN(n))?'–':Number(n).toLocaleString('en-IN',{maximumFractionDigits:d});
const money=n=>{if(n==null||isNaN(n))return '–';const a=Math.abs(n),s=n<0?'-':'';
 if(a>=1e7)return s+'₹'+(a/1e7).toFixed(2)+'Cr';if(a>=1e5)return s+'₹'+(a/1e5).toFixed(2)+'L';return s+'₹'+Math.round(a).toLocaleString('en-IN')};
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const debounce=(f,ms=250)=>{let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),ms)}};
const BADGE={'Healthy':'green','Low Stock':'orange','Critical':'red','Out of Stock':'red','Overstock':'blue','Pending':'orange','Confirmed':'blue','Dispatched':'purple','Delivered':'green','Returned':'red','Low':'green','Medium':'orange','High':'red','Applied':'green','Rejected':'red','Operational':'green','Down':'red','OK':'green','On order':'blue','Reorder now':'orange'};
const badge=t=>`<span class="badge b-${BADGE[t]||'gray'}">${esc(t)}</span>`;
function delta(pct,opts){opts=opts||{};if(pct==null)return `<div class="delta flat">– <span>${esc(opts.basis||'no comparison available')}</span></div>`;
 const good=opts.invert?pct<0:pct>0;const cls=Math.abs(pct)<0.05?'flat':(good?'up':'down');const arrow=pct>0?'↑':pct<0?'↓':'→';
 return `<div class="delta ${cls}">${arrow} ${Math.abs(pct).toFixed(1)}% <span>${esc(opts.basis||'')}</span></div>`}

/* UI states */
const skeleton=(n=3,h=18)=>Array.from({length:n},()=>`<div class="skel" style="height:${h}px;margin-bottom:10px"></div>`).join('');
const emptyState=(msg,sub)=>`<div class="empty">${ico('inbox')}<div><b>${esc(msg)}</b></div>${sub?`<div class="small">${esc(sub)}</div>`:''}</div>`;
function errorState(el,msg,retry){el.innerHTML=`<div class="errbox">${ico('alert')}<div><b>Something went wrong</b></div><div class="small">${esc(msg)}</div>${retry?'<button class="btn sm" style="margin-top:10px" id="retryBtn">Retry</button>':''}</div>`;
 if(retry){const b=el.querySelector('#retryBtn');if(b)b.onclick=retry}}
function toast(m,err){const d=document.createElement('div');d.className='toast'+(err?' err':'');d.textContent=m;$('toasts').appendChild(d);setTimeout(()=>d.remove(),4200)}

/* dialogs */
function openModal(html){$('modal').innerHTML=html;$('overlay').classList.add('show')}
function closeModal(){$('overlay').classList.remove('show')}
function confirmDialog(title,body,okText='Confirm',danger=false){return new Promise(res=>{
 openModal(`<h3>${esc(title)}</h3><div class="mut">${body}</div><div class="acts"><button class="btn" id="cNo">Cancel</button><button class="btn ${danger?'danger':'primary'}" id="cYes">${esc(okText)}</button></div>`);
 $('cNo').onclick=()=>{closeModal();res(false)};$('cYes').onclick=()=>{closeModal();res(true)};$('cYes').focus()})}
function openDrawer(title,html){$('drawerTitle').textContent=title;$('drawerBody').innerHTML=html;$('drawer').classList.add('show')}
function closeDrawer(){$('drawer').classList.remove('show')}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();closeDrawer();document.querySelectorAll('.dropdown.show,.menu.show').forEach(x=>x.classList.remove('show'))}});
$('overlay').addEventListener('click',e=>{if(e.target.id==='overlay')closeModal()});

/* charts: consistent dark theme */
const charts={};
const PALETTE=['#4f8cff','#22d3ee','#8b5cf6','#22c55e','#f59e0b','#ef4444'];
function makeChart(id,cfg){const el=$(id);if(!el)return null;
 if(typeof Chart==='undefined'){el.parentElement.innerHTML='<div class="empty">Chart library could not load. Check your internet connection (Chart.js is loaded from a CDN).</div>';return null}
 if(charts[id])charts[id].destroy();
 Chart.defaults.color='#8f9bb8';Chart.defaults.borderColor='#222e48';Chart.defaults.font.family="'Plus Jakarta Sans',sans-serif";Chart.defaults.font.size=11;
 cfg.options=Object.assign({maintainAspectRatio:false,responsive:true,interaction:{mode:'index',intersect:false}},cfg.options||{});
 cfg.options.plugins=Object.assign({legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,usePointStyle:true}},tooltip:{backgroundColor:'#0a0f1d',borderColor:'#2c3a58',borderWidth:1,padding:10}},cfg.options.plugins||{});
 charts[id]=new Chart(el,cfg);return charts[id]}
const axisT=(t)=>({title:{display:true,text:t}});

/* shell behaviour */
async function refreshMeta(){try{const m=await api('/api/meta');$('simDate').textContent='Simulation date: '+m.as_of;window.META=m}catch(e){}}
async function saveBrain(){try{const r=await post('/api/brain/save');toast('AI brain saved ('+r.episodes+' episodes)')}catch(e){toast(e.message,1)}}
async function loadBrain(){try{const r=await post('/api/brain/load');toast('AI brain loaded: '+r.episodes+' episodes');refreshMeta();if(window.onBrainChanged)window.onBrainChanged()}catch(e){toast(e.message,1)}}
async function resetData(){if(!await confirmDialog('Reset demo data?','Reloads the original synthetic CSV data. Orders, stock and the decision log are reset. The AI brain is kept.','Reset data',true))return;
 try{await post('/api/reset-data');toast('Demo data reloaded');setTimeout(()=>location.reload(),600)}catch(e){toast(e.message,1)}}
async function pollHealth(){const p=$('aiStatus');try{const h=await api('/health');p.classList.toggle('off',h.status!=='ok');p.querySelector('span').textContent=h.status==='ok'?'AI SYSTEM ONLINE':'AI SYSTEM DEGRADED'}catch(e){p.classList.add('off');p.querySelector('span').textContent='AI SYSTEM OFFLINE'}}
async function loadBell(){try{const a=await api('/api/alerts');const c=$('bellCount');c.style.display=a.length?'grid':'none';c.textContent=a.length;
 $('bellDd').innerHTML=a.length?a.slice(0,8).map(x=>`<a class="dd-item" href="/inventory?open=${x.product_id}"><span class="sev ${x.severity}">${x.severity}</span> ${esc(x.title)}<small>${esc(x.action)}</small></a>`).join(''):emptyState('No active alerts')}catch(e){errorState($('bellDd'),e.message)}}
function initShell(){
 paintIcons();
 if(window.innerWidth>900&&localStorage.getItem('sm_collapsed')==='1')document.body.classList.add('collapsed');
 $('menuBtn').onclick=()=>{if(window.innerWidth<=900)document.body.classList.toggle('open');else{document.body.classList.toggle('collapsed');localStorage.setItem('sm_collapsed',document.body.classList.contains('collapsed')?'1':'0')}};
 document.addEventListener('click',e=>{if(window.innerWidth<=900&&document.body.classList.contains('open')&&!e.target.closest('#sidebar')&&!e.target.closest('#menuBtn'))document.body.classList.remove('open');
  if(!e.target.closest('.search'))$('searchDd').classList.remove('show');if(!e.target.closest('.menu-wrap')){$('bellDd').classList.remove('show');$('profileMenu').classList.remove('show')}});
 $('bellBtn').onclick=()=>$('bellDd').classList.toggle('show');$('avatarBtn').onclick=()=>$('profileMenu').classList.toggle('show');
 $('gsearch').addEventListener('input',debounce(async e=>{const v=e.target.value.trim(),dd=$('searchDd');if(!v){dd.classList.remove('show');return}
  try{const r=await api('/api/search?q='+encodeURIComponent(v));dd.innerHTML=r.length?r.map(x=>`<a class="dd-item" href="${x.url}"><span class="badge b-gray">${x.type}</span> ${esc(x.title)}<small>${esc(x.sub)}</small></a>`).join(''):'<div class="empty small">No results</div>';dd.classList.add('show')}catch(err){dd.innerHTML='<div class="errbox small">Search failed</div>';dd.classList.add('show')}}));
 refreshMeta();pollHealth();loadBell();setInterval(pollHealth,30000);
}
document.addEventListener('DOMContentLoaded',initShell);


/* contextual help: "?" button in the top bar explains the current page */
const PAGE_HELP={
 '/':{t:'Dashboard',what:'Business health in one screen.',use:['Read the 8 KPI cards (hover for the comparison basis).','Check the AI Decision Center for the top recommendation.','Click an alert to see details.','Press Run Full Demo to train the AI and see before vs after.'],ai:'The animated pipeline shows data → forecast → state → agent → action → reward → learning.'},
 '/inventory':{t:'Inventory Intelligence',what:'Stock status of every product.',use:['Search or use the filters.','Badges show Healthy, Low, Critical, Overstock.','Click a product for its forecast and cost impact.'],ai:'Reorder qty and risk come from the same AI recommendation used in the AI Supply Agent page.'},
 '/demand':{t:'Demand Intelligence',what:'Forecast of future demand.',use:['Compare 7-day and 30-day forecasts.','Read trend and seasonality.','Use the backtest chart to judge accuracy.'],ai:'Forecast = weighted average of 30/60/90 days × trend × seasonal index. It feeds the demand part of the AI state.'},
 '/orders':{t:'Orders',what:'Dealer orders and their lifecycle.',use:['Create a demo order.','Move it Pending → Confirmed → Dispatched → Delivered / Returned.'],ai:'Pending and Confirmed orders count as pending demand, which changes the AI state.'},
 '/dealers':{t:'Dealers',what:'Dealer performance and priority.',use:['Sort by revenue, pending orders or risk.','Open a dealer for the demand pattern and AI advice.'],ai:'Dealer priority is used by the Route Planner to sequence deliveries.'},
 '/ai-agent':{t:'AI Supply Agent',what:'The AI recommendation for one product.',use:['Choose a product.','Read state, Q-values, action, confidence and reasons.','Press Apply (simulated week) or Reject (penalty).'],ai:'The agent picks the action with the highest Q-value for the current state. Apply and Reject create reward feedback that updates learning.'},
 '/what-if':{t:'What-If Simulator',what:'Test scenarios without touching real data.',use:['Move the sliders (demand, stock, lead time, costs).','Compare current plan vs AI plan in the charts.'],ai:'A 300-run Monte-Carlo simulation estimates cost, stockout chance and service level.'},
 '/training':{t:'AI Training Lab',what:'Teach the agent in simulation.',use:['Set episodes and epsilon, then Train.','Watch reward and action charts, and the Q-table.','Save, load or reset the brain.'],ai:'Each episode = 12 simulated weeks. The Q-table is updated after every decision using the Q-learning formula.'},
 '/route-planner':{t:'Route Optimization',what:'Delivery order on a simulated map.',use:['Review the sequence, capacity and priority deliveries.','Compare transport cost.'],ai:'A heuristic sequences stops by priority, distance and deadline. It is not GPS routing.'},
 '/cost-optimization':{t:'Cost Optimization',what:'Cost of the current plan vs the AI plan.',use:['Compare holding, stockout, ordering and transport cost.'],ai:'Costs use the editable parameters in Settings; they are assumptions, not real costs.'},
 '/system-health':{t:'System Health',what:'Are all components working?',use:['Check live component status.','Press Run tests to run pytest. Results show only after a real run.'],ai:'Checks include the forecast, Q-learning agent, decision engine and cost model.'},
 '/settings':{t:'Settings',what:'Simulation parameters and data.',use:['Edit holding cost, stockout penalty, ordering and transport cost, etc.','Save or load the AI brain.','Reset demo data.'],ai:'Changing parameters changes cost, savings and what-if numbers (not the Q-table).'},
 '/help':{t:'Help & Guide',what:'This page explains the whole website and the AI workflow.',use:['Use the contents bar at the top.','Press Play walkthrough in the AI workflow.'],ai:'The live example shows the AI\'s real view of a product.'}
};
function openPageHelp(){
 let p=location.pathname;let h=PAGE_HELP[p];
 if(!h&&p.startsWith('/dealers/'))h={t:'Dealer detail',what:'One dealer in depth.',use:['See orders, revenue and demand pattern.','Read the AI recommendation for this dealer.'],ai:'Uses the same demand analysis as the rest of the system.'};
 if(!h)h={t:'Help',what:'See the full guide for details.',use:[],ai:''};
 openDrawer('Help: '+h.t,`<p><b>What this page shows</b></p><p class="mut">${esc(h.what)}</p>
  ${h.use.length?`<p><b>How to use it</b></p><ul class="mut" style="padding-left:18px">${h.use.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
  ${h.ai?`<p><b>Where the AI is involved</b></p><p class="mut">${esc(h.ai)}</p>`:''}
  <a class="btn primary" href="/help#ai-workflow">Full AI workflow →</a> <a class="btn" href="/help">Complete guide</a>`);
}
(function(){const b=document.getElementById('helpBtn');if(b)b.addEventListener('click',openPageHelp)})();
