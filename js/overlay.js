'use strict';
// The overlay never displays raw viewer comments. Only configured cast names and points go on air.
const overlayRoot = document.getElementById('overlay-root');
const overlayParams = new URLSearchParams(location.search);
// A static GitHub Pages graphic selects its template by ?graphic=top3 or ?graphic=alert.
const graphicId = overlayParams.get('graphic') || decodeURIComponent(location.pathname.split('/').pop());
// Donation-triggered version of Top 3 (the default without this switch stays persistent).
const donationOnlyTop3 = graphicId === 'top3' && overlayParams.get('show') === 'on-donation';
const combined = graphicId === 'top3-alert';
let goalAlertCursor = null, goalUntil = 0;
// ?backend=https://your-service.onrender.com chooses the public, read-only feed.
const publicBackend = (overlayParams.get('backend') || '').trim().replace(/\/+$/, '');
const staticMode = Boolean(publicBackend);
if (staticMode && !/^https:\/\/[a-zA-Z0-9.-]+(?::[0-9]+)?$/.test(publicBackend)) {
  throw new Error('The backend URL must be an HTTPS origin, without a path.');
}
const preview = overlayParams.get('preview') === '1';
const viewToken = overlayParams.get('view_token') || '';
const escapeHTML = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let graphic = null, alertGraphic = null, state = null, lastRevision = -1, alertCursor = null;
// Keep the DEMO watermark visible while a card is on air, never during idle.
const demoWatermark = document.getElementById('overlay-watermark');
if (demoWatermark) {
  const syncWatermark = () => {demoWatermark.style.display=overlayRoot.querySelector('.graphic-card, .goal-panel')?'':'none'};
  new MutationObserver(syncWatermark).observe(overlayRoot,{childList:true});
  syncWatermark();
}

let lastGoalSignature = '', lastGoalChoice = '';
const fmtGoal = n => {
  const num = Number(n);
  return Number.isInteger(num) ? num.toLocaleString('en-US') : num.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
};
function countdownUntil(value){
  if(!value)return '';
  const seconds=Math.max(0,Math.ceil((new Date(value).getTime()-Date.now())/1000));
  if(!Number.isFinite(seconds))return '';
  const days=Math.floor(seconds/86400), h=String(Math.floor((seconds%86400)/3600)).padStart(2,'0'),
        m=String(Math.floor((seconds%3600)/60)).padStart(2,'0'), s=String(seconds%60).padStart(2,'0');
  return (days ? days+'d ' : '')+h+':'+m+':'+s;
}
function renderGoal(g){
  const label = g.metric==='manual'?'MANUAL GOAL':g.metric==='youtube_usd'?'REAL YOUTUBE GOAL':
    g.metric==='donations_usd'?'DONATION GOAL':g.metric==='cast_points'?'CAST SCORE GOAL':'CAST POINTS GOAL';
  const unit=(g.metric==='youtube_usd'||g.metric==='donations_usd')?'$':'';
  overlayRoot.innerHTML=`<section class="goal-panel">
    <div class="goal-top"><div><div class="goal-subtitle">${label}</div><div class="goal-title">${escapeHTML(g.title)}</div></div>
    <div class="goal-count">${unit}${fmtGoal(g.current)} <small>/ ${unit}${fmtGoal(g.target)}</small></div></div>
    <div class="goal-track"><div class="goal-bar" style="width:${Math.min(100,Math.max(0,Number(g.percent)))}%"></div></div>
    <div class="goal-footer"><span class="goal-ticker">${escapeHTML(g.ticker||'MÈSI POU SIPÒ NOU • LIVE CAST')}</span>
      <span class="goal-clock" id="goal-clock"></span><span>${Math.round(Number(g.percent))}%</span></div>
  </section>`;
}
async function tickGoals(){
  try{
    const data = await json('/api/overlay/goals');
    const eligible=data.visible?data.goals.filter(g=>g.enabled):[];
    const desired=overlayParams.get('goal');
    const target=desired ? eligible.find(g=>g.id===desired): eligible.length ? eligible[Math.floor(Date.now()/8000)%eligible.length]:null;
    // Optional: show the goal only alongside donation alerts (permanent is default).
    if(overlayParams.get('show')==='on-donation'){
      const [current, config] = await Promise.all([json('/api/state'),json('/api/graphics/alert')]);
      if(goalAlertCursor!==null && current.last_alert_id>goalAlertCursor && config.enabled){
        goalUntil=Date.now()+durationMs(config);
      }
      goalAlertCursor=current.last_alert_id;
      if(Date.now()>=goalUntil){overlayRoot.innerHTML='';lastGoalSignature='';return;}
    }
    if(!target){overlayRoot.innerHTML='';lastGoalSignature='';lastGoalChoice='';return;}
    const signature=JSON.stringify(target);
    if(signature!==lastGoalSignature || lastGoalChoice!==target.id){
      renderGoal(target);lastGoalSignature=signature;lastGoalChoice=target.id;
    }
    const clock=document.getElementById('goal-clock');
    if(clock)clock.textContent=target.ends_at?'RETE: '+countdownUntil(target.ends_at):'';
  }catch(err){
    // Do not air potentially incorrect goal totals when backend goes offline.
    overlayRoot.innerHTML='';lastGoalSignature='';lastGoalChoice='';
  }
}

let alertQueue = [], alertTimer = null, graphicSignature = '';
const fmt = v => Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const durationMs = config => Math.max(2000,Number(config.duration||6)*1000);
async function json(path){
  // Render's private endpoints still work as before; Pages never uses the operator API.
  const target = staticMode ? publicBackend + path.replace(/^\/api\/(overlay\/)?/, '/public/') : path;
  const headers = staticMode ? {} : (viewToken ? {'X-View-Token':viewToken} : {});
  const res = await fetch(target,{cache:'no-store',headers});
  if(!res.ok) throw Error('Scoreboard API returned '+res.status);
  return res.json();
}
function card(config,content,kind){
  const pos=config.position||'left',scale=config.scale||'normal';
  return `<section class="graphic-card ${kind} pos-${pos} size-${scale}" style="--accent:${escapeHTML(config.accent)}">${content}</section>`;
}
function rankLine(m){return `<div class="graphic-row"><span class="grank">${Number(m.rank)}</span><span class="gname">${escapeHTML(m.name).toUpperCase()}</span><span class="gscore">${fmt(m.points)} <small>PWEN</small></span></div>`}
function rankingMarkup(){
  if(!graphic || !state || !graphic.enabled)return '';
  const selected = graphic.kind === 'full'?state.ranking:state.top3;
  const title=escapeHTML(graphic.title_ht || (graphic.kind === 'full'?'KLASMAN AN DIRÈK':'3 PREMYE YO'));
  return card(graphic,`<p class="overlay-kicker">KLASMAN AN DIRÈK</p><h2><em>${title}</em></h2>${selected.map(rankLine).join('')||'<p>Pa gen done</p>'}`,graphic.kind);
}
function alertMarkup(config,a){
  if(!config.enabled)return '';
  const title=escapeHTML(config.title_ht||'NOUVO SUPER CHAT');
  const content=`<p class="overlay-kicker">${title}</p><div class="donor-plus">+${fmt(a.delta_points)} PWEN</div><h2>${escapeHTML(a.cast_name).toUpperCase()}</h2><div class="alert-stats"><div><div class="alert-stat-label">NOUVO TOTAL</div><div class="alert-stat-value">${fmt(a.new_total)}</div></div><div><div class="alert-stat-label">POZISYON AKTYÈL</div><div class="alert-stat-value rank">#${Number(a.rank)}</div></div></div>`;
  return card(config,content,'alert alert-entry');
}
function clearDonationGraphic(){
  clearTimeout(alertTimer);
  alertTimer=null;
  overlayRoot.innerHTML='';
}
function playQueue(){
  if(alertTimer!==null || !alertQueue.length || !alertGraphic?.enabled)return;
  const alert=alertQueue.shift();
  const ranking=(combined || donationOnlyTop3) ? rankingMarkup() : '';
  const donation=donationOnlyTop3 ? '' : alertMarkup(alertGraphic,alert);
  overlayRoot.innerHTML=ranking+donation;
  alertTimer=setTimeout(()=>{
    clearDonationGraphic();
    playQueue();
  },durationMs(alertGraphic));
}
async function fetchAlerts(lastKnownId){
  const batchSize = 200;
  const next = await json('/api/alerts?after='+alertCursor+'&limit='+batchSize);
  for(const item of next.alerts){
    if(item.seq > alertCursor){alertCursor=item.seq;alertQueue.push(item)}
  }
  // The sequence can include alerts removed by a simulation reset.
  if(next.alerts.length<batchSize)alertCursor=Math.max(alertCursor,lastKnownId);
  playQueue();
}
async function tick(){
  if(graphicId==='goals'){await tickGoals();return;}
  try{
    const id=combined ? 'top3' : graphicId;
    const [current, config, sharedAlert] = await Promise.all([
      json('/api/state'),
      json('/api/graphics/'+encodeURIComponent(id)+(preview?'?preview=true':'')),
      (combined || donationOnlyTop3) && !preview ? json('/api/graphics/alert') : null
    ]);
    state=current;graphic=config;
    if(preview){document.getElementById('overlay-watermark').textContent='TÈS / DEMO · DRAFT PREVIEW'}
    const sig=JSON.stringify(graphic);
    if(preview && graphic.kind==='alert'){
      if(sig!==graphicSignature){
        overlayRoot.innerHTML=alertMarkup(graphic,{cast_name:'EXAMPLE CAST',delta_points:'25.00',new_total:'1250.00',rank:4});
      }
    }else if(!preview && (combined || donationOnlyTop3 || graphic.kind==='alert')){
      alertGraphic=sharedAlert || graphic;
      if(!alertGraphic.enabled || (donationOnlyTop3 && !graphic.enabled) ||
         (alertCursor!==null && current.last_alert_id<alertCursor)){
        alertQueue=[];
        clearDonationGraphic();
        alertCursor=current.last_alert_id;
      }else if(alertCursor===null){
        alertCursor=current.last_alert_id;
      }else if(current.last_alert_id>alertCursor){
        await fetchAlerts(current.last_alert_id);
      }
    }else if(sig!==graphicSignature || current.revision!==lastRevision){
      overlayRoot.innerHTML=rankingMarkup();
    }
    graphicSignature=sig;lastRevision=current.revision;
  }catch(error){
    // If API is unavailable, never pretend an alert is still live.
    if(graphic && graphic.kind!=='alert' && !combined && !donationOnlyTop3){
      const previous=overlayRoot.innerHTML;
      if(previous && !previous.includes('DEKONEKTE'))overlayRoot.innerHTML=previous+'<div class="draft-watermark">DEKONEKTE — DONE YO KA PA AJOU</div>';
    }
  }
}
async function pollOverlay(){
  await tick();
  setTimeout(pollOverlay,1200);
}
pollOverlay();
