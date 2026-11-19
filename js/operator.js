'use strict';
const el = id => document.getElementById(id);
const money = micros => '$' + (Number(micros) / 1_000_000).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const escaped = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let snapshot = null, graphics = [], currentPreset = 'top3', activeTab = 'overview', toastTimeout;
async function request(path, options={}) {
  const response = await fetch(path,{cache:'no-store',...options, headers:{'Content-Type':'application/json',...(options.headers||{})}});
  let body;try{body=await response.json()}catch{body={detail:await response.text()}}
  if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail||'Request failed'));
  return body;
}
const post = (url, obj) => request(url,{method:'POST',body:JSON.stringify(obj)});
const put = (url, obj) => request(url,{method:'PUT',body:JSON.stringify(obj)});
function toast(message,error=false){const node=el('toast');node.textContent=message;node.classList.toggle('error',error);node.classList.remove('hidden');clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>node.classList.add('hidden'),5500)}
function setTab(name){
  activeTab=name;
  const titles={overview:'Operator overview',simulator:'Donation simulator',review:'Assignment queue',graphics:'Graphics Studio',settings:'Scoring & cast'};
  el('section-title').textContent=titles[name]||name;
  document.querySelectorAll('.tab-view').forEach(node=>node.classList.toggle('hidden',node.id!==`tab-${name}`));
  document.querySelectorAll('[data-tab]').forEach(node=>node.classList.toggle('selected',node.classList.contains('nav-button')&&node.dataset.tab===name));
  if(name==='graphics') refreshGraphics().catch(e=>toast(e.message,true));
  if(name==='settings'&&snapshot) updateCastList();
}
function renderRankList(rank,container){
  container.innerHTML = rank.length ? rank.map(m=>`<div class="rank-row"><span class="rank-num ${m.rank===1?'first':''}">${m.rank}</span><span class="rank-identity">${escaped(m.name)}</span><span class="rank-points">${Number(m.points).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})} <small>PTS</small></span></div>`).join('') : '<p class="muted small">No cast yet.</p>';
}
function renderEvents(rows){
  el('recent-list').innerHTML=rows.length?rows.map(e=>`<div class="event-row"><div class="event-main"><b>${escaped(e.donor)} · ${money(e.amount_micros)} ${escaped(e.currency)}</b><div class="event-meta">${escaped(e.kind==='superStickerEvent'?'Super Sticker':e.message||'(No message)')}<br>${escaped(e.id)}</div></div><span class="status-pill ${escaped(e.status)}">${escaped(e.status)}</span>${e.status==='assigned'?`<button class="btn small ghost event-correct" data-correct="${escaped(e.id)}">Correct</button>`:''}</div>`).join(''):'<p class="muted small">No simulated donations yet.</p>';
  el('recent-list').querySelectorAll('[data-correct]').forEach(button=>button.addEventListener('click',async()=>{
    const row=rows.find(e=>e.id===button.dataset.correct),members=snapshot.cast.filter(c=>c.active);
    const newId=prompt('Assign to which cast ID? '+members.map(c=>`${c.id} (${c.name})`).join(', '),row.cast_id||'');
    if(!newId||newId===row.cast_id)return;
    const reason=prompt('Reason for correcting this cast assignment:','Producer correction');
    if(!reason||reason.trim().length<3)return;
    try{await post('/api/assign',{donation_id:row.id,cast_id:newId.trim(),reason});toast('Correction applied and recorded. Scores updated; no misleading second donation alert.');await refreshState()}
    catch(e){toast(e.message,true)}
  }));
}
function renderQueue(rows){
  const options=(snapshot?.cast||[]).filter(x=>x.active).map(c=>`<option value="${escaped(c.id)}">${escaped(c.name)}</option>`).join('');
  el('pending-label').textContent=`${rows.length} shown`;
  el('review-list').innerHTML=rows.length?rows.map(e=>`<div class="review-item" data-review="${escaped(e.id)}"><div class="review-body"><b>${escaped(e.donor)} · ${money(e.amount_micros)} ${escaped(e.currency)}</b><small>${escaped(e.kind==='superStickerEvent'?'Super Sticker':e.message||'No hashtag')} · ${escaped(e.status)}</small></div><div class="review-controls">${e.currency==='USD'?`<select aria-label="Assign cast member">${options}</select><input aria-label="Reason" value="Producer reviewed hashtag" placeholder="Reason"><button class="btn primary small" data-assign="${escaped(e.id)}">Assign</button>`:'<span class="status-pill review_currency">FX review required</span>'}</div></div>`).join(''):'<p class="muted small">No donations require review.</p>';
  el('review-list').querySelectorAll('[data-assign]').forEach(button=>button.addEventListener('click',async()=>{
    const row=button.closest('.review-item'), select=row.querySelector('select'), reason=row.querySelector('input');
    try{await post('/api/assign',{donation_id:row.dataset.review,cast_id:select.value,reason:reason.value||'Producer review'});toast('Donation assigned. Scores and overlays updated.');await refreshState()}
    catch(e){toast(e.message,true)}
  }));
}
function updateCastList(){
  if(!snapshot)return;
  el('cast-list').innerHTML=snapshot.cast.map(c=>`<div class="cast-item"><div><b>${escaped(c.name)}${c.active?'':' (inactive)'}</b><small>${c.hashtags.map(t=>'#'+escaped(t.replace(/^#/,''))).join(' · ')}</small></div><button data-editcast="${escaped(c.id)}">Edit</button></div>`).join('');
  el('cast-list').querySelectorAll('[data-editcast]').forEach(b=>b.addEventListener('click',()=>{
    const c=snapshot.cast.find(c=>c.id===b.dataset.editcast);if(!c)return;
    el('cast-id').value=c.id;el('cast-name').value=c.name;el('cast-tags').value=c.hashtags.join(', ');el('cast-active').checked=c.active;
    toast(`Editing ${c.name}. Save to apply your changes.`);
  }));
}
async function refreshState(){
  const s=await request('/api/state');snapshot=s;
  el('sync-indicator').textContent='● Simulation connected';el('sync-indicator').className='pill ok';
  el('stat-gross').textContent='$'+Number(s.gross_usd).toLocaleString('en-US',{minimumFractionDigits:2});
  el('stat-events').textContent=s.event_count;
  el('stat-pending').textContent=s.pending_count;
  el('stat-multiplier').textContent=s.points_per_usd+'×';
  el('system-status').textContent=`Demo ledger • Revision ${s.revision} • Last changed ${new Date(s.updated_at).toLocaleString()} • No actual YouTube API connected • Render demo data is temporary`;
  renderRankList(s.ranking,el('rank-list'));renderEvents(s.recent);if(activeTab==='review')renderQueue(s.pending);
  if(activeTab==='settings')updateCastList();
}
function hydrateGraphic(g){
  if(!g)return;currentPreset=g.id;const d=g.draft;
  el('editor-title').textContent=`Edit: ${d.name}`;
  el('g-name').value=d.name;el('g-title-en').value=d.title_en;el('g-title-ht').value=d.title_ht;
  el('g-color').value=d.accent;el('g-position').value=d.position;el('g-scale').value=d.scale;
  el('g-duration').value=d.duration;el('g-enabled').checked=d.enabled;
  el('preview-link').href=`/overlay/${g.id}?preview=1`;
  el('live-link').href=`/overlay/${g.id}`;
  document.querySelectorAll('.preset-item').forEach(n=>n.classList.toggle('active',n.dataset.preset===g.id));
}
async function refreshGraphics(){
  const g=await request('/api/graphics');graphics=g.graphics;
  const list=el('preset-list');list.innerHTML=graphics.map(g=>`<button class="preset-item ${g.id===currentPreset?'active':''}" data-preset="${escaped(g.id)}"><strong>${escaped(g.published.name)}</strong><span>${escaped(g.published.kind)} · /overlay/${escaped(g.id)}</span></button>`).join('');
  list.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>hydrateGraphic(graphics.find(x=>x.id===b.dataset.preset))));
  el('clone-source').innerHTML=graphics.map(x=>`<option value="${escaped(x.id)}">${escaped(x.published.name)}</option>`).join('');
  hydrateGraphic(graphics.find(x=>x.id===currentPreset)||graphics[0]);
}
function draftFromForm(){return{name:el('g-name').value,accent:el('g-color').value,position:el('g-position').value,scale:el('g-scale').value,title_en:el('g-title-en').value,title_ht:el('g-title-ht').value,duration:Number(el('g-duration').value),enabled:el('g-enabled').checked}}
function bind(){
  document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
  el('simulate-form').addEventListener('submit',async e=>{
    e.preventDefault();try{
      const data={kind:el('sim-kind').value,amount:el('sim-amount').value,currency:el('sim-currency').value,donor:el('sim-donor').value,message:el('sim-message').value,event_id:el('sim-id').value||null};
      const result=await post('/api/simulate',data);el('sim-result').textContent=JSON.stringify(result,null,2);
      toast(result.result==='duplicate'?'Duplicate ID ignored: no points added.':result.result==='ignored'?'Free chat ignored for scoring.':'Test event recorded.');await refreshState();
    }catch(error){toast(error.message,true)}
  });
  el('settings-form').addEventListener('submit',async e=>{e.preventDefault();try{await put('/api/settings',{points_per_usd:el('points-multiplier').value});toast('New multiplier saved for FUTURE events only.');await refreshState()}catch(err){toast(err.message,true)}});
  el('cast-form').addEventListener('submit',async e=>{e.preventDefault();try{
    await post('/api/cast',{id:el('cast-id').value,name:el('cast-name').value,hashtags:el('cast-tags').value.split(',').map(s=>s.trim()).filter(Boolean),active:el('cast-active').checked});
    toast('Cast roster saved.');await refreshState();
  }catch(err){toast(err.message,true)}});
  el('graphic-form').addEventListener('submit',async e=>{e.preventDefault();try{
    await put(`/api/graphics/${currentPreset}/draft`,draftFromForm());toast('Draft saved. Open the draft preview to inspect it.');await refreshGraphics();
  }catch(err){toast(err.message,true)}});
  el('publish-button').addEventListener('click',async()=>{try{
    await put(`/api/graphics/${currentPreset}/draft`,draftFromForm());await post(`/api/graphics/${currentPreset}/publish`,{});
    toast('Published. Existing graphic pages update automatically.');await refreshGraphics();
  }catch(err){toast(err.message,true)}});
  el('clone-form').addEventListener('submit',async e=>{e.preventDefault();try{
    const result=await post('/api/graphics',{source_id:el('clone-source').value,id:el('clone-id').value,name:el('clone-name').value});
    currentPreset=result.id;toast('New graphic created with a stable URL.');await refreshGraphics();
  }catch(err){toast(err.message,true)}});
  el('reset-button').addEventListener('click',async()=>{
    const confirmText=prompt('Type RESET DEMO to permanently erase simulated donations and alerts:');
    if(confirmText!=='RESET DEMO')return;
    try{await post('/api/reset',{confirm:confirmText});toast('All demo donations reset.');await refreshState()}catch(err){toast(err.message,true)}
  });
}
(async()=>{bind();try{await refreshState();el('points-multiplier').value=snapshot.points_per_usd;await refreshGraphics()}catch(e){el('sync-indicator').textContent='● Server not responding';el('sync-indicator').className='pill neutral';toast(e.message,true)}setInterval(()=>refreshState().catch(()=>{el('sync-indicator').textContent='● Connection lost';el('sync-indicator').className='pill neutral'}),1500)})();
