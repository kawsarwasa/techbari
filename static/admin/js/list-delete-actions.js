(function(){
  const TRASH_ICON='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M7 7l1 13h8l1-13"/><path d="M10 11v5M14 11v5"/></svg>';
  const CONTROL_SELECTOR='button,a,input[type="submit"]';
  const LIST_CONTEXT='table,[role="table"],.table-scroll,.data-table,.row-actions,.crud-actions,.list-actions,.item-actions,.list-card,.card-list,[class*="list-card"],[class*="-list"],[class*="list-"]';
  const DIALOG_CONTEXT='dialog,[role="dialog"],.modal,.product-delete-modal,.product-delete-overlay,.tb-delete-overlay';

  const overlay=document.getElementById('globalDeleteOverlay');
  const titleNode=document.getElementById('globalDeleteTitle');
  const questionNode=document.getElementById('globalDeleteQuestion');
  const previewNode=document.getElementById('globalDeletePreview');
  const warningNode=document.getElementById('globalDeleteWarning');
  const detailNode=document.getElementById('globalDeleteDetail');
  const confirmNode=document.getElementById('globalDeleteConfirm');
  let pendingResolve=null;

  function clean(value){return String(value||'').replace(/\s+/g,' ').trim();}
  function titleCase(value){return clean(value).replace(/[-_]+/g,' ').replace(/\b\w/g,m=>m.toUpperCase());}
  function attributeText(element){return Array.from(element?.attributes||[]).map(attribute=>`${attribute.name}=${attribute.value}`).join(' ').toLowerCase();}
  function actionValue(form,submitter){
    const direct=(submitter?.getAttribute('name')||'').toLowerCase()==='action' ? submitter?.value : '';
    if(direct)return String(direct).toLowerCase();
    return String(form?.querySelector('input[name="action"]')?.value||'').toLowerCase();
  }
  function isDeleteAction(value){return /^delete(?:$|[_-])/.test(String(value||'').toLowerCase());}
  function formLooksDelete(form,submitter){
    if(!form)return false;
    if(form.dataset.skipDeleteConfirm==='1'||form.closest(DIALOG_CONTEXT))return false;
    if(isDeleteAction(actionValue(form,submitter)))return true;
    const action=String(form.getAttribute('action')||'').toLowerCase();
    if(/\/delete\/?(?:[?#].*)?$/.test(action)||/\/delete\//.test(action))return true;
    const text=clean(submitter?.textContent||submitter?.value).toLowerCase();
    const meta=[attributeText(submitter),submitter?.getAttribute('title')||'',submitter?.getAttribute('aria-label')||'',text].join(' ').toLowerCase();
    return /\bdelete\b/.test(meta)&&((submitter?.getAttribute('type')||'submit').toLowerCase()==='submit');
  }
  function isDeleteControl(element){
    if(!element?.matches?.(CONTROL_SELECTOR)||element.closest(DIALOG_CONTEXT))return false;
    if(element.hasAttribute('data-close-product-delete')||element.hasAttribute('data-product-delete'))return false;
    const form=element.closest('form');
    if(formLooksDelete(form,element))return true;
    if(!element.closest(LIST_CONTEXT))return false;
    const text=clean(element.textContent||element.value).toLowerCase();
    const metadata=[attributeText(element),element.getAttribute('title')||'',element.getAttribute('aria-label')||'',text].join(' ').toLowerCase();
    return /\bdelete\b/.test(metadata)||/(^|[-_:])delete($|[-_:])/.test(metadata);
  }
  function decorate(element){
    if(element.dataset.techbariDeleteIcon==='1'||!isDeleteControl(element))return;
    if(!element.closest(LIST_CONTEXT))return;
    element.dataset.techbariDeleteIcon='1';
    element.classList.add('list-delete-action');
    element.setAttribute('title','Delete');
    element.setAttribute('aria-label','Delete');
    if(element.tagName!=='INPUT')element.innerHTML=TRASH_ICON;
  }
  function scan(root=document){
    if(root.nodeType===1&&root.matches?.(CONTROL_SELECTOR))decorate(root);
    root.querySelectorAll?.(CONTROL_SELECTOR).forEach(decorate);
  }
  function inferKind(form,submitter){
    const explicit=submitter?.dataset.deleteKind||form?.dataset.deleteKind;
    if(explicit)return clean(explicit);
    const action=actionValue(form,submitter);
    if(action==='delete_value')return 'Attribute Value';
    if(action==='delete_attribute')return 'Attribute';
    const hay=[submitter?.getAttribute('aria-label'),submitter?.getAttribute('title'),submitter?.textContent,form?.getAttribute('action')].map(clean).join(' ').toLowerCase();
    const pairs=[
      ['customer group','Customer Group'],['customer','Customer'],['supplier','Supplier'],['warehouse','Warehouse'],
      ['banner','Banner'],['specification','Specification'],['variant','Variant'],['image','Product Image'],
      ['purchase','Draft Purchase'],['order','Draft Order'],['category','Category'],['brand','Brand'],['coupon','Coupon']
    ];
    for(const [needle,label] of pairs)if(hay.includes(needle))return label;
    return 'Record';
  }
  function inferName(form,submitter,kind){
    const explicit=submitter?.dataset.deleteName||form?.dataset.deleteName;
    if(explicit)return clean(explicit);
    const aria=clean(submitter?.getAttribute('aria-label'));
    if(/^delete\s+/i.test(aria)&&!/^delete\s+(this|record|item)$/i.test(aria))return aria.replace(/^delete\s+/i,'');
    const scope=submitter?.closest('tr,[data-media-card],.attribute-row,.card,.list-card');
    const candidate=scope?.querySelector('strong,h3,.media-card-title,[data-name]');
    const value=clean(candidate?.dataset?.name||candidate?.textContent);
    return value||kind;
  }
  function inferImage(form,submitter){
    const explicit=submitter?.dataset.deleteImage||form?.dataset.deleteImage;
    if(explicit)return explicit;
    const scope=submitter?.closest('tr,[data-media-card],.card,.list-card');
    return scope?.querySelector('img')?.getAttribute('src')||'';
  }
  function addSubmitterValue(form,submitter){
    if(!form||!submitter?.name)return;
    let hidden=form.querySelector('input[data-tb-delete-submitter="1"]');
    if(!hidden){
      hidden=document.createElement('input');
      hidden.type='hidden';
      hidden.dataset.tbDeleteSubmitter='1';
      form.appendChild(hidden);
    }
    hidden.name=submitter.name;
    hidden.value=submitter.value||'';
  }
  function close(result){
    if(overlay)overlay.hidden=true;
    const resolve=pendingResolve;
    pendingResolve=null;
    if(resolve)resolve(Boolean(result));
  }
  function renderPreview({kind,name,image,detail}){
    if(!previewNode)return;
    previewNode.replaceChildren();
    if(!name&&!image&&!detail){previewNode.hidden=true;return;}
    previewNode.hidden=false;
    if(image){
      const img=document.createElement('img'); img.src=image; img.alt=name||kind; previewNode.appendChild(img);
    }else{
      const fallback=document.createElement('span'); fallback.className='tb-delete-preview-fallback'; fallback.textContent=(clean(name||kind).charAt(0)||'?').toUpperCase(); previewNode.appendChild(fallback);
    }
    const copy=document.createElement('div');
    const strong=document.createElement('strong'); strong.textContent=name||kind;
    const meta=document.createElement('span'); meta.textContent=detail||kind;
    copy.append(strong,meta); previewNode.appendChild(copy);
  }
  function ask(options={}){
    if(!overlay)return Promise.resolve(false);
    if(pendingResolve)close(false);
    const kind=clean(options.kind)||'Record';
    const name=clean(options.name)||kind;
    const count=Number(options.products||0);
    titleNode.textContent=options.title||`Delete ${kind}`;
    questionNode.textContent=options.question||`Are you sure you want to delete this ${kind.toLowerCase()}?`;
    confirmNode.textContent=options.confirmLabel||`Delete ${kind}`;
    warningNode.textContent=options.warning||(count>0
      ? `This ${kind.toLowerCase()} is used by ${count} product${count===1?'':'s'}. TechBari will keep protected dependencies safe and block deletion where required.`
      : 'Eligible records will be permanently removed. Protected business history and dependencies will not be bypassed.');
    detailNode.textContent=options.info||'Review the item carefully before confirming.';
    renderPreview({kind,name,image:options.image||'',detail:options.detail||''});
    overlay.hidden=false;
    confirmNode.focus();
    return new Promise(resolve=>{pendingResolve=resolve;});
  }
  window.TechBariDeleteConfirm={ask};

  document.addEventListener('click',async function(event){
    const submitter=event.target.closest('button,input[type="submit"]');
    if(!submitter)return;
    const form=submitter.closest('form');
    if(!formLooksDelete(form,submitter))return;
    if(form.dataset.tbDeleteConfirmed==='1')return;
    event.preventDefault();
    event.stopPropagation();
    if(event.stopImmediatePropagation)event.stopImmediatePropagation();

    const kind=inferKind(form,submitter);
    const name=inferName(form,submitter,kind);
    const image=inferImage(form,submitter);
    const products=Number(submitter.dataset.deleteProducts||form.dataset.deleteProducts||0);
    const ok=await ask({
      kind,name,image,products,
      detail:submitter.dataset.deleteDetail||form.dataset.deleteDetail||'',
      warning:submitter.dataset.deleteWarning||form.dataset.deleteWarning||''
    });
    if(!ok)return;
    addSubmitterValue(form,submitter);
    form.dataset.tbDeleteConfirmed='1';
    HTMLFormElement.prototype.submit.call(form);
  },true);

  document.addEventListener('submit',async function(event){
    const form=event.target;
    if(!(form instanceof HTMLFormElement)||form.dataset.tbDeleteConfirmed==='1')return;
    const submitter=event.submitter||null;
    if(!formLooksDelete(form,submitter))return;
    event.preventDefault();
    event.stopPropagation();
    if(event.stopImmediatePropagation)event.stopImmediatePropagation();

    const kind=inferKind(form,submitter);
    const name=inferName(form,submitter,kind);
    const image=inferImage(form,submitter);
    const ok=await ask({kind,name,image,detail:submitter?.dataset.deleteDetail||form.dataset.deleteDetail||''});
    if(!ok)return;
    addSubmitterValue(form,submitter);
    form.dataset.tbDeleteConfirmed='1';
    HTMLFormElement.prototype.submit.call(form);
  },true);

  function init(){
    scan();
    new MutationObserver(mutations=>mutations.forEach(mutation=>mutation.addedNodes.forEach(node=>{
      if(node.nodeType===1)scan(node);
    }))).observe(document.body,{childList:true,subtree:true});
    overlay?.querySelectorAll('[data-close-global-delete]').forEach(button=>button.addEventListener('click',()=>close(false)));
    overlay?.addEventListener('click',event=>{if(event.target===overlay)close(false);});
    confirmNode?.addEventListener('click',()=>close(true));
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&overlay&&!overlay.hidden)close(false);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();