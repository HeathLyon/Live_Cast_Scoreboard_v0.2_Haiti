'use strict';
// The overlay never displays raw viewer comments. Only configured cast names and points go on air.
const overlayRoot = document.getElementById('overlay-root');
const graphicId = decodeURIComponent(location.pathname.split('/').pop());
const overlayParams = new URLSearchParams(location.search);
const preview = overlayParams.get('preview') === '1';
const viewToken = overlayParams.get('view_token') || '';
const escapeHTML = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let graphic = null, state = null, lastRevision = -1, alertCursor = null;
let alertQueue = [], alertActive = false, activeAlertSeq = null, graphicSignature = '';
const fmt = v => Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
async function json(path){const res=await fetch(path,{cache:'no-store',headers:viewToken?{'X-View-Token':viewToken}:{}});if(!res.ok)throw Error('Network response '+res.status);return res.json()}
function card(content,kind){
  const pos=graphic.position||'left',scale=graphic.scale||'normal';
  return `<section class="graphic-card ${kind} pos-${pos} size-${scale}" style="--accent:${escapeHTML(graphic.accent)}">${content}</section>`;
}
function rankLine(m){return `<div class="graphic-row"><span class="grank">${Number(m.rank)}</span><span class="gname">${escapeHTML(m.name).toUpperCase()}</span><span class="gscore">${fmt(m.points)} <small>PWEN</small></span></div>`}
function displayRanking(){
  if(!graphic || !state || !graphic.enabled){overlayRoot.innerHTML='';return}
  const selected = graphic.kind === 'full'?state.ranking:state.top3;
  const title=escapeHTML(graphic.title_ht || (graphic.kind === 'full'?'KLASMAN AN DIRÈK':'3 PREMYE YO'));
  overlayRoot.innerHTML=card(`<p class="overlay-kicker">KLASMAN AN DIRÈK</p><h2><em>${title}</em></h2>${selected.map(rankLine).join('')||'<p>Pa gen done</p>'}`,graphic.kind);
}
function displayAlert(a){
  if(!graphic || !graphic.enabled)return;
  const title=escapeHTML(graphic.title_ht||'NOUVO SUPER CHAT');
  const content=`<p class="overlay-kicker">${title}</p><div class="donor-plus">+${fmt(a.delta_points)} PWEN</div><h2>${escapeHTML(a.cast_name).toUpperCase()}</h2><div class="alert-stats"><div><div class="alert-stat-label">NOUVO TOTAL</div><div class="alert-stat-value">${fmt(a.new_total)}</div></div><div><div class="alert-stat-label">POZISYON AKTYÈL</div><div class="alert-stat-value rank">#${Number(a.rank)}</div></div></div>`;
  overlayRoot.innerHTML=card(content,'alert alert-entry');
  activeAlertSeq=a.seq;
}
function clearAlert(done){const cardNode=overlayRoot.querySelector('.graphic-card');if(cardNode)cardNode.classList.add('alert-exit');setTimeout(()=>{overlayRoot.innerHTML='';alertActive=false;activeAlertSeq=null;done()},290)}
function playQueue(){
  if(alertActive || !alertQueue.length || !graphic || !graphic.enabled)return;
  alertActive=true;
  const alert=alertQueue.shift();displayAlert(alert);
  setTimeout(()=>clearAlert(playQueue),Math.max(2000,Number(graphic.duration||6)*1000));
}
async function fetchAlerts(){
  if(alertCursor === null)return;
  const next = await json('/api/alerts?after='+alertCursor+'&limit=200');
  for(const item of next.alerts){
    if(item.seq > alertCursor){alertCursor=item.seq;alertQueue.push(item)}
  }
  playQueue();
}
async function tick(){
  try{
    const [current, config] = await Promise.all([json('/api/state'),json('/api/graphics/'+graphicId+(preview?'?preview=true':''))]);
    state=current;graphic=config;
    if(preview){document.getElementById('overlay-watermark').textContent='TÈS / DEMO · DRAFT PREVIEW'}
    const sig=JSON.stringify(graphic);
    if(graphic.kind!=='alert'){
      if(sig!==graphicSignature || current.revision!==lastRevision)displayRanking();
    }else{
      if(preview){
        if(sig!==graphicSignature){displayAlert({seq:0,cast_name:'EXAMPLE CAST',delta_points:'25.00',new_total:'1250.00',rank:4})}
        graphicSignature=sig;lastRevision=current.revision;return;
      }
      if(!graphic.enabled){alertQueue=[];overlayRoot.innerHTML=''}
      if(alertCursor===null)alertCursor=current.last_alert_id; // Never replay old alerts on a newly opened browser.
      else await fetchAlerts();
    }
    graphicSignature=sig;lastRevision=current.revision;
  }catch(error){
    if(graphic && graphic.kind!=='alert'){
      const previous=overlayRoot.innerHTML;
      if(previous && !previous.includes('DEKONEKTE'))overlayRoot.innerHTML=previous+'<div class="draft-watermark">DEKONEKTE — DONE YO KA PA AJOU</div>';
    }
  }
}
tick();setInterval(tick,1200);
