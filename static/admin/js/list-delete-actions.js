(function(){
  const TRASH_ICON='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M7 7l1 13h8l1-13"/><path d="M10 11v5M14 11v5"/></svg>';
  const CONTROL_SELECTOR='button,a';
  const LIST_CONTEXT='table,[role="table"],.table-scroll,.data-table,.row-actions,.crud-actions,.list-actions,.item-actions,.list-card,.card-list,[class*="list-card"],[class*="-list"],[class*="list-"]';

  function attributeText(element){
    return Array.from(element.attributes||[]).map(attribute=>`${attribute.name}=${attribute.value}`).join(' ').toLowerCase();
  }

  function formDeletes(element){
    const form=element.closest('form');
    if(!form)return false;
    return Array.from(form.querySelectorAll('input,button')).some(control=>{
      const name=(control.getAttribute('name')||'').toLowerCase();
      const value=(control.getAttribute('value')||'').toLowerCase();
      return (name==='action'||name.endsWith('_action'))&&value==='delete';
    });
  }

  function isDeleteControl(element){
    if(!element.matches(CONTROL_SELECTOR))return false;
    const text=(element.textContent||'').trim().toLowerCase();
    const metadata=[attributeText(element),element.getAttribute('title')||'',element.getAttribute('aria-label')||'',text].join(' ').toLowerCase();
    const explicit=/\bdelete\b/.test(metadata)||/(^|[-_:])delete($|[-_:])/.test(metadata)||formDeletes(element);
    if(!explicit)return false;
    const explicitData=Array.from(element.attributes||[]).some(attribute=>attribute.name.toLowerCase().includes('delete'));
    const actionParent=element.closest('.row-actions,.crud-actions,.list-actions,.item-actions,[class*="action"]');
    return Boolean(explicitData||actionParent||element.closest(LIST_CONTEXT));
  }

  function decorate(element){
    if(element.dataset.techbariDeleteIcon==='1'||!isDeleteControl(element))return;
    element.dataset.techbariDeleteIcon='1';
    element.classList.add('list-delete-action');
    element.setAttribute('title','Delete');
    element.setAttribute('aria-label','Delete');
    element.innerHTML=TRASH_ICON;
  }

  function scan(root=document){
    if(root.nodeType===1&&root.matches?.(CONTROL_SELECTOR))decorate(root);
    root.querySelectorAll?.(CONTROL_SELECTOR).forEach(decorate);
  }

  function init(){
    scan();
    new MutationObserver(mutations=>mutations.forEach(mutation=>mutation.addedNodes.forEach(node=>{
      if(node.nodeType===1)scan(node);
    }))).observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
