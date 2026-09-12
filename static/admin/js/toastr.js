(function(){
  const defaults={timeOut:4200,errorTimeOut:6000,warningTimeOut:5200,positionClass:'toast-top-right'};
  const state={lastLegacyText:'',lastLegacyAt:0};

  function escapeText(value){return String(value==null?'':value)}
  function normalise(value){return escapeText(value).replace(/^\s*[✓✔!⚠]+\s*/,'').replace(/\s+/g,' ').trim().toLowerCase()}

  function classify(message,requestedType){
    const type=(requestedType||'info').toLowerCase();
    const text=escapeText(message).toLowerCase();
    if(type==='error')return{type:'error',title:'Error'};
    if(/\b(deleted|removed|purged)\b/.test(text))return{type:'error',title:'Deleted'};
    if(/\b(archived|deactivated|cancelled|canceled|disabled)\b/.test(text))return{type:'warning',title:/archive/.test(text)?'Archived':'Updated'};
    if(/\b(updated|edited|changed|adjusted|transferred)\b/.test(text))return{type:'info',title:'Updated'};
    if(/\b(created|added|saved|completed|posted|recorded|received|activated|sent|successfully)\b/.test(text))return{type:'success',title:'Success'};
    if(type==='warning')return{type:'warning',title:'Warning'};
    if(type==='success')return{type:'success',title:'Success'};
    return{type:'info',title:'Information'};
  }

  function iconSvg(type){
    if(type==='success')return'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
    if(type==='error')return'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></svg>';
    if(type==='warning')return'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4M12 16.5v.5"/></svg>';
    return'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>';
  }

  function region(){
    let node=document.getElementById('techbari-toast-region');
    if(!node){node=document.createElement('div');node.id='techbari-toast-region';node.className='techbari-toast-region';node.setAttribute('aria-live','polite');node.setAttribute('aria-atomic','false');document.body.appendChild(node)}
    return node;
  }

  function hideInlineDuplicate(message){
    const needle=normalise(message);if(!needle)return;
    document.querySelectorAll('.soft-note,.inline-info').forEach(node=>{
      const hay=normalise(node.textContent);
      if(hay===needle||hay.endsWith(needle)||hay.includes(needle))node.hidden=true;
    });
  }

  function removeToast(node){
    if(!node||node.dataset.leaving==='1')return;
    node.dataset.leaving='1';node.classList.remove('is-visible');node.classList.add('is-leaving');
    setTimeout(()=>node.remove(),330);
  }

  function show(message,requestedType,title){
    message=escapeText(message).trim();if(!message)return null;
    const meta=classify(message,requestedType);const type=meta.type;const heading=title||meta.title;
    const duration=type==='error'?defaults.errorTimeOut:type==='warning'?defaults.warningTimeOut:defaults.timeOut;
    const node=document.createElement('div');
    node.className=`techbari-toast techbari-toast-${type}`;
    node.setAttribute('role',type==='error'?'alert':'status');
    node.style.setProperty('--toast-duration',duration+'ms');
    node.innerHTML=`<div class="techbari-toast-icon">${iconSvg(type)}</div><div class="techbari-toast-copy"><strong class="techbari-toast-title"></strong><p class="techbari-toast-message"></p></div><button class="techbari-toast-close" type="button" aria-label="Close notification">×</button><div class="techbari-toast-progress" aria-hidden="true"></div>`;
    node.querySelector('.techbari-toast-title').textContent=heading;
    node.querySelector('.techbari-toast-message').textContent=message;
    node.querySelector('.techbari-toast-close').addEventListener('click',()=>removeToast(node));
    region().appendChild(node);
    requestAnimationFrame(()=>requestAnimationFrame(()=>node.classList.add('is-visible')));
    setTimeout(()=>removeToast(node),duration);
    node.addEventListener('click',e=>{if(!e.target.closest('.techbari-toast-close'))removeToast(node)});
    hideInlineDuplicate(message);
    return node;
  }

  function clear(){document.querySelectorAll('.techbari-toast').forEach(removeToast)}

  window.toastr={
    options:defaults,
    show,
    success:(message,title)=>show(message,'success',title),
    error:(message,title)=>show(message,'error',title),
    warning:(message,title)=>show(message,'warning',title),
    info:(message,title)=>show(message,'info',title),
    clear
  };
  window.TechBariToast=window.toastr;

  function loadServerMessages(){
    const node=document.getElementById('techbari-toast-data');if(!node)return;
    let items=[];try{items=JSON.parse(node.textContent)||[]}catch(_error){items=[]}
    items.forEach((item,index)=>setTimeout(()=>show(item.message,item.level),index*120));
  }

  function bridgeLegacyToast(){
    const legacy=document.getElementById('toast');if(!legacy)return;
    const relay=()=>{
      const text=legacy.textContent.trim();if(!text||!legacy.classList.contains('show'))return;
      const now=Date.now();if(text===state.lastLegacyText&&now-state.lastLegacyAt<350)return;
      state.lastLegacyText=text;state.lastLegacyAt=now;show(text,'info');
    };
    new MutationObserver(relay).observe(legacy,{attributes:true,childList:true,characterData:true,subtree:true});
  }

  function init(){loadServerMessages();bridgeLegacyToast()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
