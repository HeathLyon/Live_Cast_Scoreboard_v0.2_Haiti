'use strict';
const params = new URLSearchParams(location.search);
const viewToken = params.get('view_token') || '';
const publicBackend = (params.get('backend') || '').trim().replace(/\/+$/, '');
if (publicBackend && !/^https:\/\/[a-zA-Z0-9.-]+(?::[0-9]+)?$/.test(publicBackend)) {
  throw new Error('The backend URL must be an HTTPS origin, without a path.');
}
const el=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function ranks(list){return list.length?list.map(m=>`<div class="rank-row"><span class="rank-num ${m.rank===1?'first':''}">${m.rank}</span><span class="rank-identity">${esc(m.name)}</span><span class="rank-points">${Number(m.points).toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2})} <small>PWEN</small></span></div>`).join(''):'<p class="muted">Pa gen patisipan.</p>'}
async function tick(){try{const res=await fetch(publicBackend ? publicBackend+'/public/state' : '/api/state', {cache:'no-store',headers:publicBackend?{}:(viewToken?{'X-View-Token':viewToken}:{})});if(!res.ok)throw new Error('Unreachable');const data=await res.json();el('p-gross').textContent = publicBackend ? '—' : '$'+Number(data.gross_usd).toLocaleString('en-US',{minimumFractionDigits:2});el('p-events').textContent=publicBackend?'—':data.event_count;el('p-pending').textContent=publicBackend?'—':data.pending_count;el('p-top3').innerHTML=ranks(data.top3);el('p-all').innerHTML=ranks(data.ranking);el('p-time').textContent='Mizajou '+new Date(data.updated_at).toLocaleTimeString('fr-FR');el('producer-status').textContent=`● Done tès yo disponib · Dènye mizajou: ${new Date(data.updated_at).toLocaleString('fr-FR')}`;el('producer-status').classList.remove('bad')}catch{el('producer-status').textContent='● Koneksyon pèdi — rezilta ki sou ekran an ka pa ajou';el('producer-status').classList.add('bad')}}
tick();setInterval(tick,1500);
