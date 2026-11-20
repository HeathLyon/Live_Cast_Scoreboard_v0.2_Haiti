'use strict';
const el = id => document.getElementById(id);
const money = micros => '$' + (Number(micros) / 1_000_000).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const escaped = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Operator goal editor and searchable historical review queue.
let goalEditId = null, goalSnapshot = null, donationOffset = 0, donationTotal = 0;
const searchLimit=50;
const dateFromUTC = v => {
  if(!v)return '';
  const d=new Date(v), local=new Date(d.getTime()-d.getTimezoneOffset()*60000);
  return local.toISOString().slice(0,16);
};
function clearGoal(){
  goalEditId=null;
  el('goal-form').reset();
  el('goal-id').readOnly=false;el('goal-id').value='';
  el('goal-target').value='4000';el('goal-manual').value='0';el('goal-adjustment').value='0';
  el('goal-enabled').checked=true;el('goal-start-fresh').checked=true;
  el('goal-editor-title').textContent='Create a goal';el('goal-save').textContent='Create goal';
  el('goal-delete').classList.add('hidden');el('goal-reset-row').classList.add('hidden');
}
function editGoal(id){
  const g=goalSnapshot?.goals.find(x=>x.id===id);if(!g)return;
  goalEditId=g.id;
  el('goal-id').value=g.id;el('goal-id').readOnly=true;
  el('goal-title').value=g.title;el('goal-metric').value=g.metric;
  el('goal-target').value=g.target;el('goal-cast').value=g.cast_id||'';
  el('goal-manual').value=g.manual_value;el('goal-adjustment').value=g.adjustment;
  el('goal-ends').value=dateFromUTC(g.ends_at);
  el('goal-ticker').value=g.ticker;el('goal-order').value=g.sort_order;
  el('goal-enabled').checked=g.enabled;
  el('goal-editor-title').textContent='Editing: '+g.title;
  el('goal-save').textContent='Save changes';
  el('goal-reset').checked=false;
  el('goal-delete').classList.remove('hidden');el('goal-reset-row').classList.remove('hidden');
}
async function refreshGoals(){
  const data=await request('/api/goals');goalSnapshot=data;
  el('goals-visible').checked=data.visible;
  const list=el('goals-list');
  list.innerHTML=data.goals.length?data.goals.map(g=>`<div class="goal-admin-row">
    <div class="goal-admin-content"><strong>${escaped(g.title)}</strong><div class="muted small">${escaped(g.metric.replaceAll('_',' '))} · ${escaped(g.current)} / ${escaped(g.target)} · ${g.percent}%</div>
    <div class="goal-progress-mini"><div style="width:${g.percent}%"></div></div></div>
    <label class="check-row"><input type="checkbox" data-goal-toggle="${escaped(g.id)}" ${g.enabled?'checked':''}><span>On</span></label>
    <button type="button" class="btn ghost small" data-goal-edit="${escaped(g.id)}">Edit</button></div>`).join(''):
    '<p class="muted small">No goals yet. Create one below to show a countdown and progress bar in vMix.</p>';
  list.querySelectorAll('[data-goal-edit]').forEach(b=>b.addEventListener('click',()=>editGoal(b.dataset.goalEdit)));
  list.querySelectorAll('[data-goal-toggle]').forEach(b=>b.addEventListener('change',async()=>{
    const g=data.goals.find(x=>x.id===b.dataset.goalToggle);
    if(!g)return;
    try{await put('/api/goals/'+encodeURIComponent(g.id),goalPayload(g,{enabled:b.checked}));await refreshGoals();toast('Goal visibility updated live.');}
    catch(err){toast(err.message,true);await refreshGoals()}
  }));
  if(snapshot){
    const selected=el('goal-cast').value;
    el('goal-cast').innerHTML='<option value="">Choose a cast member</option>'+snapshot.cast.map(c=>`<option value="${escaped(c.id)}">${escaped(c.name)}</option>`).join('');
    el('goal-cast').value=selected;
  }
}
function goalPayload(g,overrides={}){
  return {id:g.id,title:g.title,metric:g.metric,target:g.target,cast_id:g.cast_id||null,
    manual_value:g.manual_value, adjustment:g.adjustment,ends_at:g.ends_at,
    ticker:g.ticker,sort_order:g.sort_order,enabled:g.enabled,start_fresh:false,...overrides};
}
function readGoalForm(){
  return {id:el('goal-id').value.trim().toLowerCase(),title:el('goal-title').value.trim(),
    metric:el('goal-metric').value,target:el('goal-target').value,
    cast_id:el('goal-cast').value||null,manual_value:el('goal-manual').value||'0',
    adjustment:el('goal-adjustment').value||'0',
    ends_at:el('goal-ends').value?new Date(el('goal-ends').value).toISOString():null,
    ticker:el('goal-ticker').value,sort_order:Number(el('goal-order').value||0),
    enabled:el('goal-enabled').checked,start_fresh:el('goal-start-fresh').checked,
    reset_baseline:el('goal-reset').checked};
}
function historyRow(e){
  const options=(snapshot?.cast||[]).filter(c=>c.active).map(c=>`<option value="${escaped(c.id)}" ${c.id===e.cast_id?'selected':''}>${escaped(c.name)}</option>`).join('');
  return `<div class="review-item" data-history="${escaped(e.id)}">
    <div class="review-body"><b>${escaped(e.donor)} · ${money(e.amount_micros)} ${escaped(e.currency)}</b>
    <small>${escaped(e.message||'(Super Sticker)')} · ${escaped(e.status)} · ${e.source==='youtube'?'REAL YOUTUBE':'SIMULATED'} · ${escaped(e.received_at)}</small>
    <small>Event: ${escaped(e.id)}</small></div>
    <div class="review-controls">${e.currency==='USD'?`<select aria-label="Select cast member">${options}</select><input aria-label="Assignment reason" value="Producer review" maxlength="250"><button type="button" class="btn primary small" data-hist-assign="${escaped(e.id)}">${e.status==='assigned'?'Correct':'Assign'}</button>`:'<span class="status-pill review_currency">FX policy required</span>'}</div>
  </div>`;
}
async function refreshHistory(){
  const params=new URLSearchParams({status:el('donation-filter').value,q:el('donation-search').value,limit:String(searchLimit),offset:String(donationOffset)});
  const result=await request('/api/donations?'+params);
  donationTotal=result.total;
  const div=el('donation-results');div.innerHTML=result.items.map(historyRow).join('')||'<p class="muted small">No matching donations.</p>';
  el('donation-page').textContent=result.total?`${donationOffset+1}–${donationOffset+result.items.length} of ${result.total}`:'No matches';
  el('donation-prev').disabled=donationOffset===0;
  el('donation-next').disabled=donationOffset+searchLimit>=donationTotal;
  div.querySelectorAll('[data-hist-assign]').forEach(b=>b.addEventListener('click',async()=>{
    const row=b.closest('[data-history]'), cast=row.querySelector('select').value,reason=row.querySelector('input').value;
    if(!reason.trim() || reason.trim().length<3){toast('Include an assignment reason.',true);return;}
    try{const ans=await post('/api/assign',{donation_id:row.dataset.history,cast_id:cast,reason});
      toast(ans.result==='unchanged'?'Donation already assigned to this cast.':'Assignment audited and rankings recalculated.');
      await refreshState();await refreshHistory();}
    catch(err){toast(err.message,true)}
  }));
}
function bindGoals(){
  clearGoal();
  el('goal-new').addEventListener('click',clearGoal);
  el('goals-visible').addEventListener('change',async e=>{
    try{await put('/api/goals/visibility',{visible:e.target.checked});toast(e.target.checked?'Goal graphic enabled on air.':'Goal graphic hidden on air.');await refreshGoals();}
    catch(err){toast(err.message,true);await refreshGoals()}
  });
  el('goal-form').addEventListener('submit',async e=>{e.preventDefault();
    try{const goal=readGoalForm();if(goalEditId)await put('/api/goals/'+encodeURIComponent(goalEditId),goal);
      else await post('/api/goals',goal);
      toast('Goal saved. vMix graphics refresh automatically.');await refreshGoals();editGoal(goal.id);
    }catch(err){toast(err.message,true)}
  });
  el('goal-delete').addEventListener('click',async()=>{
    if(!goalEditId||!confirm('Delete this goal? This cannot be undone.'))return;
    try{await request('/api/goals/'+encodeURIComponent(goalEditId),{method:'DELETE'});
      clearGoal();await refreshGoals();toast('Goal deleted.');}
    catch(err){toast(err.message,true)}
  });
  el('donation-search-form').addEventListener('submit',async e=>{e.preventDefault();donationOffset=0;await refreshHistory().catch(err=>toast(err.message,true))});
  el('donation-prev').addEventListener('click',()=>{donationOffset=Math.max(0,donationOffset-searchLimit);refreshHistory().catch(err=>toast(err.message,true))});
  el('donation-next').addEventListener('click',()=>{donationOffset+=searchLimit;refreshHistory().catch(err=>toast(err.message,true))});
}

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
  const titles={system:'Stats & health',overview:'Operator overview',data:'Donation data',simulator:'Debug & test events',review:'Assignment queue',graphics:'Graphics Studio',youtube:'YouTube live',goals:'Goals & ticker',settings:'Scoring & cast'};
  el('section-title').textContent=titles[name]||name;
  document.querySelectorAll('.tab-view').forEach(node=>node.classList.toggle('hidden',node.id!==`tab-${name}`));
  document.querySelectorAll('[data-tab]').forEach(node=>node.classList.toggle('selected',node.classList.contains('nav-button')&&node.dataset.tab===name));
  if(name==='goals') refreshGoals().catch(e=>toast(e.message,true));
  if(name==='review') refreshHistory().catch(e=>toast(e.message,true));
  if(name==='system' && window.refreshSystemStatus)window.refreshSystemStatus();
  if(name==='graphics') refreshGraphics().catch(e=>toast(e.message,true));
  if(name==='data' && window.loadDataPage)window.loadDataPage();
  if(name==='simulator' && window.loadDebugEvents)window.loadDebugEvents();
  if(name==='youtube') refreshYouTube().catch(e=>toast(e.message,true));
  if(name==='settings'&&snapshot) updateCastList();
}
function renderRankList(rank,container){
  container.innerHTML = rank.length ? rank.map(m=>`<div class="rank-row"><span class="rank-num ${m.rank===1?'first':''}">${m.rank}</span><span class="rank-identity">${escaped(m.name)}</span><span class="rank-points">${Number(m.points).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})} <small>PTS</small></span></div>`).join('') : '<p class="muted small">No cast yet.</p>';
}
function renderEvents(rows){
  el('recent-list').innerHTML=rows.length?rows.map(e=>`<div class="event-row"><div class="event-main"><b>${escaped(e.donor)} · ${money(e.amount_micros)} ${escaped(e.currency)} <span class="status-pill">${e.source==='youtube'?'REAL YOUTUBE':'SIMULATED'}</span></b><div class="event-meta">${escaped(e.kind==='superStickerEvent'?'Super Sticker':e.message||'(No message)')}<br>${escaped(e.id)}</div></div><span class="status-pill ${escaped(e.status)}">${escaped(e.status)}</span>${e.status==='assigned'?`<button class="btn small ghost event-correct" data-correct="${escaped(e.id)}">Correct</button>`:''}</div>`).join(''):'<p class="muted small">No donations recorded yet.</p>';
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
  el('review-list').innerHTML=rows.length?rows.map(e=>`<div class="review-item" data-review="${escaped(e.id)}"><div class="review-body"><b>${escaped(e.donor)} · ${money(e.amount_micros)} ${escaped(e.currency)} <span class="status-pill">${e.source==='youtube'?'REAL YOUTUBE':'SIMULATED'}</span></b><small>${escaped(e.kind==='superStickerEvent'?'Super Sticker':e.message||'No hashtag')} · ${escaped(e.status)}</small></div><div class="review-controls">${e.currency==='USD'?`<select aria-label="Assign cast member">${options}</select><input aria-label="Reason" value="Producer reviewed hashtag" placeholder="Reason"><button class="btn primary small" data-assign="${escaped(e.id)}">Assign</button>`:'<span class="status-pill review_currency">FX review required</span>'}</div></div>`).join(''):'<p class="muted small">No donations require review.</p>';
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
  el('sync-indicator').textContent=s.live_mode?'● Live backend connected':'● Staging backend connected';el('sync-indicator').className='pill ok';
  el('stat-gross').textContent='$'+Number(s.gross_usd).toLocaleString('en-US',{minimumFractionDigits:2});
  el('stat-events').textContent=s.event_count;
  el('stat-pending').textContent=s.pending_count;
  el('stat-multiplier').textContent=s.points_per_usd+'×';
  el('system-status').textContent=`${s.mode} • Revision ${s.revision} • YouTube paid events: ${s.youtube_event_count} ($${s.youtube_gross_usd} USD) • Test events: ${s.simulated_event_count} ($${s.simulated_gross_usd} USD)`;
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
  const publicUrl=g.public_url || `/overlay/${g.id}`;
  el('live-link').href=publicUrl;el('graphic-url').value=publicUrl;
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

let youtubeFieldsInitialized = false;
async function refreshYouTube(){
  const s = await request('/api/youtube/status');
  if (!youtubeFieldsInitialized) {
    el('youtube-video').value=s.video_id||'';
    el('youtube-enabled').checked=Boolean(s.enabled);
    youtubeFieldsInitialized=true;
  }
  const status = s.connected?'● Listening to live chat':s.enabled?'● '+s.status:'○ Disabled';
  el('youtube-status').textContent=status;
  el('youtube-details').textContent=[
    'API key configured: '+(s.api_key_configured?'Yes':'NO — add YOUTUBE_API_KEY in Render Environment'),
    'Video ID: '+(s.video_id||'none'),
    'Listener state: '+s.status,
    'Paid events recorded in this process: '+s.events_recorded,
    'Duplicates ignored: '+s.duplicates_skipped,
    'Last poll: '+(s.last_checked||'not connected'),
    'Minimum polling interval: '+s.poll_interval_seconds+' s',
    s.error?'Error: '+s.error:''
  ].filter(Boolean).join('\n');
}
function bind(){
  bindGoals();
  document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
  el('youtube-form').addEventListener('submit',async e=>{
    e.preventDefault();
    try {
      const result=await put('/api/youtube/config',{video:el('youtube-video').value,enabled:el('youtube-enabled').checked});
      toast(result.enabled?'YouTube connection requested. Wait for LISTENING before testing a purchase.':'YouTube listener disabled.');
      await refreshYouTube();
    } catch(error) {toast(error.message,true)}
  });
  el('simulate-form').addEventListener('submit',async e=>{
    e.preventDefault();try{
      const data={kind:el('sim-kind').value,amount:el('sim-amount').value,currency:el('sim-currency').value,donor:el('sim-donor').value,message:el('sim-message').value,event_id:el('sim-id').value||null};
      const result=await post('/api/simulate',data);el('sim-result').textContent=JSON.stringify(result,null,2);
      toast(result.result==='duplicate'?'Duplicate ID ignored: no points added.':result.result==='ignored'?'Free chat ignored for scoring.':'Test event recorded.');
      await refreshState();
      if(window.loadDebugEvents)await window.loadDebugEvents();
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
  el('copy-graphic-url').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(el('graphic-url').value);toast('vMix URL copied.')}catch(e){toast('Select and copy the URL field.',true)}});
  el('clone-form').addEventListener('submit',async e=>{e.preventDefault();try{
    const result=await post('/api/graphics',{source_id:el('clone-source').value,id:el('clone-id').value,name:el('clone-name').value});
    currentPreset=result.id;toast('New graphic created. Publish it when you are ready.');await refreshGraphics();
    el('graphic-url').select();
  }catch(err){toast(err.message,true)}});
  el('reset-button').addEventListener('click',async()=>{
    const confirmText=prompt('Type RESET DEMO to permanently erase simulated donations and alerts:');
    if(confirmText!=='RESET DEMO')return;
    try{await post('/api/reset',{confirm:confirmText});toast('All demo donations reset.');await refreshState()}catch(err){toast(err.message,true)}
  });
}
(async()=>{bind();try{await refreshState();el('points-multiplier').value=snapshot.points_per_usd;await refreshGraphics()}catch(e){el('sync-indicator').textContent='● Server not responding';el('sync-indicator').className='pill neutral';toast(e.message,true)}setInterval(()=>{if(activeTab==='youtube') refreshYouTube().catch(()=>{});if(activeTab==='goals')refreshGoals().catch(()=>{});if(activeTab==='system' && window.refreshSystemStatus)window.refreshSystemStatus();},3500);setInterval(()=>refreshState().catch(()=>{el('sync-indicator').textContent='● Connection lost';el('sync-indicator').className='pill neutral'}),1500)})();
