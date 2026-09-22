(function(){
  const overlay=document.getElementById('catalogDeleteOverlay');
  if(!overlay)return;

  let activeForm=null;
  const title=document.getElementById('catalogDeleteTitle');
  const question=document.getElementById('catalogDeleteQuestion');
  const preview=document.getElementById('catalogDeletePreview');
  const warning=document.getElementById('catalogDeleteWarning');
  const confirmButton=document.getElementById('confirmCatalogDelete');

  function closeModal(){
    overlay.hidden=true;
    activeForm=null;
  }

  document.addEventListener('click',function(event){
    const trigger=event.target.closest('[data-catalog-delete]');
    if(!trigger)return;

    activeForm=trigger.closest('form');
    const kind=trigger.dataset.deleteKind||'Item';
    const name=trigger.dataset.deleteName||kind;
    const image=trigger.dataset.deleteImage||'';
    const products=Number(trigger.dataset.deleteProducts||0);

    title.textContent='Delete '+kind;
    question.textContent='Are you sure you want to delete this '+kind.toLowerCase()+'?';
    confirmButton.textContent='Delete '+kind;
    warning.textContent=products>0
      ? 'This '+kind.toLowerCase()+' is used by '+products+' product'+(products===1?'':'s')+'. The server will block deletion while it is in use.'
      : 'The '+kind.toLowerCase()+' will be permanently removed from the catalog.';

    preview.replaceChildren();
    if(image){
      const img=document.createElement('img');
      img.src=image;
      img.alt=name;
      preview.appendChild(img);
    }else{
      const fallback=document.createElement('span');
      fallback.className='catalog-delete-preview-fallback';
      fallback.textContent=(name.trim().charAt(0)||'?').toUpperCase();
      preview.appendChild(fallback);
    }

    const copy=document.createElement('div');
    const strong=document.createElement('strong');
    strong.textContent=name;
    const meta=document.createElement('span');
    meta.textContent=products+' product'+(products===1?'':'s');
    copy.append(strong,meta);
    preview.appendChild(copy);

    overlay.hidden=false;
  });

  overlay.querySelectorAll('[data-close-catalog-delete]').forEach(function(button){
    button.addEventListener('click',closeModal);
  });

  overlay.addEventListener('click',function(event){
    if(event.target===overlay)closeModal();
  });

  document.addEventListener('keydown',function(event){
    if(event.key==='Escape'&&!overlay.hidden)closeModal();
  });

  confirmButton.addEventListener('click',function(){
    if(activeForm)activeForm.submit();
  });
})();