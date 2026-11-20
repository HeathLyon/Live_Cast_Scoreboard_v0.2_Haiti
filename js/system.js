"use strict";
// Operator-only status and canonical vMix URLs. Never expose credentials in links.
const sysEl=id=>document.getElementById(id);
const sysText=v=>String(v??'');
const prettyUptime=seconds=>{
  const x=Math.max(0,Number(seconds)||0);return Math.floor(x/3600)+'h '+Math.floor(x%3600/60)+'m';
};
const escapeSys=v=>sysText(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const isHttps=url=>{try{const u=new URL(url);return u.protocol==='https:'}catch{return false}};
function linkNode(title,url,compact=false){
  const wrap=document.createElement('div');wrap.className='status-url-item';
  const label=document.createElement('strong');label.textContent=title;
  const actions=document.createElement('div');actions.className='button-row';
  const link=document.createElement('a');link.href=isHttps(url)?url:'#';link.target='_blank';link.rel='noopener noreferrer';link.className='btn ghost small';link.textContent=compact?'Open':'Open graphic';
  const button=document.createElement('button');button.type='button';button.className='btn ghost small';button.textContent='Copy URL';
  button.addEventListener('click',()=>navigator.clipboard.writeText(url).then(()=>{button.textContent='Copied';setTimeout(()=>button.textContent='Copy URL',2000)}).catch(()=>{button.textContent='Copy failed'}));
  actions.append(link,button);wrap.append(label,actions);
  if(!compact){const value=document.createElement('code');value.textContent=url;wrap.append(value)}
  return wrap;
}
async function refreshSystemStatus(){
  try{
    const r=await fetch('/api/system/status',{cache:'no-store'});
    if(!r.ok)throw Error('System status HTTP '+r.status);
    const status=await r.json();
    const isProd=status.environment==='production';
    const identity=status.operator||{};
    if(identity.role && identity.role!=='admin'){
      const debugNav=document.querySelector('.nav-button[data-tab=simulator]');
      if(debugNav)debugNav.classList.add('hidden');
      const settingsNav=document.querySelector('.nav-button[data-tab=settings]');
      if(settingsNav && identity.role==='viewer')settingsNav.classList.add('hidden');
    }
    sysEl('profile-name').textContent=isProd?'PRODUCTION PROFILE':'STAGING PROFILE';
    sysEl('profile-detail').textContent=isProd?'Only real YouTube purchases count.':'Test and real data may mix. Not for official scoring.';
    const notice=sysEl('deployment-notice');
    notice.innerHTML=isProd?'<strong>PRODUCTION PROFILE</strong> — Real YouTube events only. Check YouTube listener, persistent database, broadcast queue, backup storage and operator access before going live.':'<strong>STAGING PROFILE</strong> — Test and real events may mix here. Switch to production only after adding a paid persistent disk and checking all connections.';
    const c=status.connections,y=status.youtube,q=status.broadcast;
    const statuses=[
      ['Backend',true,status.version+' · '+prettyUptime(status.uptime_seconds)],
      ['Database',c.database,status.storage.kind+' · '+Math.ceil(status.storage.database_size_bytes/1024)+' KB'],
      ['YouTube API key',c.youtube_api_key,c.youtube_api_key?'Configured':'Missing'],
      ['Live YouTube chat',c.youtube_listening,y.status+(y.error?' · '+y.error:'')],
      ['Public graphics',c.public_overlays,c.public_overlays?'Enabled':'Disabled'],
      ['Broadcast queue',q.enabled,q.paused?'Paused':q.active?'On air':'Ready']
    ];
    sysEl('system-tiles').replaceChildren(...statuses.map(([name,ok,detail])=>{
      const el=document.createElement('div');el.className='system-tile';
      const head=document.createElement('strong');head.textContent=(ok?'● ':'○ ')+name;
      const sub=document.createElement('small');sub.textContent=detail;el.append(head,sub);return el;
    }));
    sysEl('system-details').textContent=[
      'Environment: '+status.environment.toUpperCase()+' | Uptime: '+prettyUptime(status.uptime_seconds),
      'Signed in as: '+(identity.username||'operator')+' ('+(identity.role||'legacy')+')',
      'Backend: '+status.backend_url,
      'GitHub Pages: '+status.pages_url,
      'DB integrity: '+(status.storage.integrity||status.storage.error||'unknown'),
      'Real events: '+status.storage.real_events+' | Test events: '+status.storage.test_events,
      'YouTube video ID: '+(y.video_id||'not selected'),
      'YouTube last check: '+(y.last_checked||'none'),
      'Last YouTube error: '+(y.error||'none'),
      'Public API enabled: '+c.public_overlays,
      'Server queue: '+(q.enabled?'Enabled':'Off')+' | Waiting: '+q.pending,
    ].join('\n');
    sysEl('queue-status').textContent='Pending: '+q.pending+' | Playing: '+(q.active?q.active.cast_name+' +'+q.active.delta_points:'none')+' | Completed: '+q.completed+' | Skipped: '+q.skipped+' | Grouped: '+q.grouped+' | Grouping: '+(q.grouping?'ON':'OFF')+' | '+(q.paused?'PAUSED':'RUNNING');
    const urls=[['Combined Top 3 + Alert','combined'],['Goals & countdown','goals'],['Permanent Top 3','top3'],['Donation-only Top 3','top3_on_donation'],['Donation alert','alert'],['Full standings','full'],['Haitian producer','producer'],['Link setup','setup']];
    sysEl('system-urls').replaceChildren(...urls.map(([title,key])=>linkNode(title,status.graphics[key])));
    sysEl('system-graphic-health').replaceChildren(...Object.entries(status.graphic_readiness||{}).map(([id,config])=>{
      const item=document.createElement('div');item.className='system-tile';
      const head=document.createElement('strong');head.textContent=(config.enabled && c.public_overlays?'● ':'○ ')+id;
      const sub=document.createElement('small');sub.textContent=!c.public_overlays?'Public overlay API disabled':config.enabled?'Published / enabled — open link to verify rendering':'Not enabled / not configured on air';
      item.append(head,sub);return item;
    }));
    sysEl('quick-graphic-links').replaceChildren(linkNode('Combined donation graphic',status.graphics.combined,true),linkNode('Goals graphic',status.graphics.goals,true));
    sysEl('quick-system-summary').textContent=status.environment.toUpperCase()+' · DB '+(c.database?'OK':'ERROR')+' · YouTube '+(c.youtube_listening?'LISTENING':y.status)+' · Queue '+q.pending+' waiting';
  }catch(err){
    sysEl('system-details').textContent='Unable to read status: '+err.message;
    sysEl('quick-system-summary').textContent='System monitor unavailable: '+err.message;
  }
}
window.refreshSystemStatus=refreshSystemStatus;
for(const action of ['pause','resume','skip','group_on','group_off']){
  sysEl('queue-'+action).addEventListener('click',async()=>{
    try{
      const r=await fetch('/api/system/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
      if(!r.ok)throw Error('Server rejected '+action+' ('+r.status+')');
      await refreshSystemStatus();
    }catch(err){sysEl('queue-status').textContent=err.message}
  });
}
sysEl('system-refresh').addEventListener('click',refreshSystemStatus);
refreshSystemStatus();
