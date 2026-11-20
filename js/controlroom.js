'use strict';
// Operator-only transaction explorer and isolated debug controls. Never deployed on GitHub Pages.
(() => {
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd=v=>'$'+(Number(v)/1_000_000).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const call=async(url,init)=>{const r=await fetch(url,{cache:'no-store',...init});if(!r.ok){let message='HTTP '+r.status;try{message=(await r.json()).detail||message}catch{}throw Error(message)}return r.json()};
  const put=(url,payload)=>call(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const post=(url,payload)=>call(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const notice=(message,error=false)=>{if(typeof toast==='function')toast(message,error);else alert(message)};
  const opt=(value,label)=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o};
  const limit=50;
  let offset=0,total=0,activeId='',testItems=[];
  const lookup=new Map();

  async function refreshRoster(){
    const data=await call('/api/data/summary');
    const current=$('data-cast').value;
    $('data-cast').replaceChildren(opt('all','All cast members'),opt('unassigned','Unassigned'),...data.cast.map(c=>opt(c.id,c.name)));
    if([...$('data-cast').options].some(o=>o.value===current))$('data-cast').value=current;
    $('data-cast-summary').replaceChildren(...data.cast.map(c=>{
      const card=document.createElement('button');card.type='button';card.className='cast-data-card';
      card.innerHTML=`<strong>${esc(c.name)}</strong><b>${esc(c.points)} points</b><small>${Number(c.donations)} assigned donations</small>`;
      card.addEventListener('click',()=>{$('data-cast').value=c.id;offset=0;loadRows()});return card;
    }));
    lookup.clear();data.cast.forEach(c=>lookup.set(c.id,c.name));
  }
  const filters=()=>new URLSearchParams({cast_id:$('data-cast').value,source:$('data-source').value,status:$('data-status').value,
    q:$('data-search').value.trim(),limit:String(limit),offset:String(offset)});
  async function loadRows(){
    try{
      const data=await call('/api/data/history?'+filters());
      total=data.total;
      const rows=data.items;
      $('data-summary').textContent=`${total.toLocaleString()} matching records. Real donations are never deleted. Select View / Correct for details and the audit trail.`;
      $('data-table').innerHTML=rows.map(row=>{
        const effective=row.adjusted_amount_micros??row.amount_micros;
        return `<tr><td>${esc(row.received_at.slice(0,19).replace('T',' '))}</td><td><strong>${esc(row.donor)}</strong><small class="ledger-id">${esc(row.id)}</small></td>
          <td>${usd(effective)}${row.adjusted_amount_micros!==null?'<small class="ledger-id">Corrected</small>':''}</td>
          <td>${esc(lookup.get(row.cast_id)||'Unassigned')}</td><td>${row.source==='youtube'?'YouTube':'TEST'}</td><td>${esc(row.status)}</td>
          <td><button type="button" class="btn ghost small" data-transaction="${esc(row.id)}">View / Correct</button></td></tr>`;
      }).join('') || '<tr><td colspan="7">No transactions match these filters.</td></tr>';
      $('data-page').textContent=total?`${offset+1}–${offset+rows.length} of ${total}`:'0 results';
      $('data-prev').disabled=offset<=0;$('data-next').disabled=offset+rows.length>=total;
      $('data-table').querySelectorAll('[data-transaction]').forEach(b=>b.addEventListener('click',()=>openTransaction(b.dataset.transaction)));
    }catch(e){$('data-summary').textContent='History unavailable: '+e.message}
  }
  async function loadDataPage(){await refreshRoster();await loadRows()}
  window.loadDataPage=()=>loadDataPage().catch(e=>notice(e.message,true));
  async function openTransaction(id){
    try{
      const {item,audit}=await call('/api/data/transaction/'+encodeURIComponent(id));
      activeId=id;
      const original=`${usd(item.amount_micros)} ${esc(item.currency)}`;
      $('transaction-original').innerHTML=`<p><strong>Event ID:</strong> <code>${esc(item.id)}</code></p>
        <p><strong>Source:</strong> ${item.source==='youtube'?'Real YouTube':'Simulated / TEST'} · <strong>Donor:</strong> ${esc(item.donor)}</p>
        <p><strong>Original paid amount:</strong> ${original} · <strong>Time:</strong> ${esc(item.published_at)}</p>
        <p><strong>Original comment:</strong> ${esc(item.message||'(none)')}</p>
        <p><strong>Recorded status:</strong> ${esc(item.status)} · <strong>Awarded points:</strong> ${(Number(item.points_milli)/1000).toFixed(2)}</p>`;
      $('transaction-cast').replaceChildren(opt('','Unassigned / Needs review'),...[...lookup].map(([cid,name])=>opt(cid,name)));
      $('transaction-cast').value=item.cast_id||'';
      $('transaction-amount').value=(Number(item.effective_amount_micros)/1_000_000).toFixed(2);
      $('transaction-amount').disabled=item.currency!=='USD';
      $('transaction-form').querySelector('button[type=submit]').disabled=item.currency!=='USD';
      $('transaction-reason').value='';
      $('transaction-audit').innerHTML=audit.length?audit.map(a=>`<div class="event-row"><div><b>${esc(a.action)} · ${esc(a.at)}</b><div class="event-meta">${esc(a.details)}</div></div></div>`).join(''):'<p class="muted small">No previous corrections recorded.</p>';
      $('transaction-dialog').showModal();
    }catch(e){notice(e.message,true)}
  }
  $('transaction-form').addEventListener('submit',async e=>{
    e.preventDefault();const amount=$('transaction-amount').value,cast_id=$('transaction-cast').value||null,reason=$('transaction-reason').value;
    if(!confirm('Apply this audited correction to the official ledger?\nCast: '+(cast_id||'Unassigned')+'\nAmount: $'+amount+'\nReason: '+reason))return;
    try{const result=await put('/api/data/transaction/'+encodeURIComponent(activeId),{amount,cast_id,reason});
      notice(result.result==='unchanged'?'No values changed.':'Correction saved. Scores and goals recalculated.');
      $('transaction-dialog').close();await loadDataPage();if(typeof refreshState==='function')await refreshState();
    }catch(err){notice(err.message,true)}
  });
  $('transaction-close').addEventListener('click',()=>$('transaction-dialog').close());
  $('data-filters').addEventListener('submit',e=>{e.preventDefault();offset=0;loadRows()});
  $('data-reset').addEventListener('click',()=>{$('data-filters').reset();offset=0;loadRows()});
  $('data-refresh').addEventListener('click',()=>loadDataPage());
  $('data-prev').addEventListener('click',()=>{offset=Math.max(0,offset-limit);loadRows()});
  $('data-next').addEventListener('click',()=>{if(offset+limit<total){offset+=limit;loadRows()}});

  async function loadDebugEvents(){
    try{
      const data=await call('/api/debug/events?limit=100&offset=0');testItems=data.items;
      $('debug-count').textContent=`${data.total} simulated records total · latest ${testItems.length} shown. Remove selected or clear all.`;
      $('debug-list').innerHTML=testItems.length?testItems.map(row=>`<div class="review-item">
        <label class="check-row"><input type="checkbox" class="debug-checkbox" data-test-id="${esc(row.id)}"><span><strong>${esc(row.donor)} · ${usd(row.amount_micros)}</strong><small>${esc(row.id)} · ${esc(row.status)} · ${esc(row.message)}</small></span></label></div>`).join(''):'<p class="muted small">No test events saved.</p>';
      $('debug-select-all').checked=false;
    }catch(err){$('debug-count').textContent='Test records unavailable: '+err.message}
  }
  window.loadDebugEvents=()=>loadDebugEvents();
  $('debug-refresh').addEventListener('click',loadDebugEvents);
  $('debug-select-all').addEventListener('change',e=>document.querySelectorAll('.debug-checkbox').forEach(box=>box.checked=e.target.checked));
  $('debug-remove').addEventListener('click',async()=>{
    const ids=[...document.querySelectorAll('.debug-checkbox:checked')].map(c=>c.dataset.testId);
    if(!ids.length){notice('Select at least one test event.');return}
    const reason=prompt('Reason for removing '+ids.length+' test event(s):','Cleanup after graphics test');
    if(!reason)return;if(!confirm('Remove '+ids.length+' selected TEST event(s)? Real YouTube events will remain untouched.'))return;
    try{const result=await post('/api/debug/remove',{ids,reason});notice(result.removed+' synthetic events removed.');await loadDebugEvents();if(typeof refreshState==='function')await refreshState()}catch(e){notice(e.message,true)}
  });
  $('debug-clear').addEventListener('click',async()=>{
    const confirmText=prompt('Type CLEAR TEST EVENTS to remove all synthetic donations. Real YouTube records will not be deleted.');
    if(confirmText!=='CLEAR TEST EVENTS')return;
    const reason=prompt('Reason for clearing test history:','Completed production readiness test');
    if(!reason)return;
    try{const result=await post('/api/debug/clear',{confirm:confirmText,reason});notice(result.removed+' test events removed.');await loadDebugEvents();if(typeof refreshState==='function')await refreshState()}catch(e){notice(e.message,true)}
  });
  $('debug-burst').addEventListener('click',async()=>{
    const count=Number($('debug-burst-size').value);
    if(!Number.isInteger(count)||count<1||count>100){notice('Choose a count from 1 to 100.',true);return}
    try{const response=await post('/api/debug/burst',{count,cast_id:'marcus'});notice('Saved '+response.created+' isolated test donations.');await loadDebugEvents();if(typeof refreshState==='function')await refreshState()}catch(e){notice(e.message,true)}
  });
})();
