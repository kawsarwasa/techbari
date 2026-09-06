(function(){
  const DEMO=JSON.parse(document.getElementById("admin-data").textContent);
  const routes=JSON.parse(document.getElementById("admin-routes").textContent);
  const $=(s,c=document)=>c.querySelector(s), $$=(s,c=document)=>[...c.querySelectorAll(s)];
  const key='techbari_admin_products';
  const fallback=DEMO.seeds.products;
  const get=()=>{try{const v=JSON.parse(localStorage.getItem(key)||'null');if(Array.isArray(v))return v;}catch{} localStorage.setItem(key,JSON.stringify(fallback));return [...fallback]};
  const set=v=>localStorage.setItem(key,JSON.stringify(v));
  const money=n=>'৳ '+Number(n||0).toLocaleString('en-US',{maximumFractionDigits:0});
  const toast=m=>{const t=document.getElementById('toast');if(!t)return;t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1700)};
  let rows=get();
  const body=$('#productRows');
  if(body){
    let deleteId=null;
    const selected=new Set();
    const render=()=>{
      const q=($('#productSearch')?.value||'').trim().toLowerCase(), cat=$('#productCategoryFilter')?.value||'', stock=$('#productStockFilter')?.value||'', sort=$('#productSort')?.value||'newest';
      let list=rows.filter(p=>{const matches=!q||`${p.name} ${p.sku} ${p.brand} ${p.category}`.toLowerCase().includes(q);const cm=!cat||p.category===cat;const sm=!stock||(stock==='out'?Number(p.stock)<=0:stock==='low'?Number(p.stock)>0&&Number(p.stock)<=10:Number(p.stock)>0);return matches&&cm&&sm});
      if(sort==='name')list.sort((a,b)=>a.name.localeCompare(b.name));if(sort==='price-low')list.sort((a,b)=>a.price-b.price);if(sort==='price-high')list.sort((a,b)=>b.price-a.price);if(sort==='stock')list.sort((a,b)=>b.stock-a.stock);
      body.innerHTML=list.slice(0,10).map((p,i)=>`<tr><td><label class="check-wrap"><input type="checkbox" data-product-select="${p.id}" ${selected.has(p.id)?'checked':''}><span></span></label></td><td>${i+1}</td><td><div class="product-cell"><img src="${p.image||DEMO.default_image}" alt="${p.name}"><div><strong>${p.name}</strong><span>${p.category}</span></div></div></td><td>${p.sku}</td><td>${p.category}</td><td>${p.brand}</td><td><strong>${money(p.price)}</strong></td><td><span class="stock-num ${p.stock<=0?'out':p.stock<=15?'low':'ok'}">${p.stock}</span></td><td><span class="status ${p.status==='Active'?'green':p.status==='Draft'?'yellow':p.status==='Archived'?'gray':'red'}">${p.status}</span></td><td><div class="row-actions"><a class="edit-product" href="${routes.product_edit}?id=${p.id}" title="Edit">✎</a><button class="more-product" type="button" data-product-delete="${p.id}" title="More actions">⋮</button></div></td></tr>`).join('')||'<tr><td colspan="10"><div class="empty-state">No products found.</div></td></tr>';
      $('#selectedProductCount').textContent=selected.size;$('#productTotal').textContent=list.length;$('#productRange').textContent=list.length?`1–${Math.min(10,list.length)}`:'0–0';
      const active=rows.filter(p=>p.status==='Active').length,out=rows.filter(p=>Number(p.stock)<=0).length,draft=rows.filter(p=>p.status==='Draft').length;const kt=$('[data-product-kpi="total"]'),ka=$('[data-product-kpi="active"]'),ko=$('[data-product-kpi="out"]'),kd=$('[data-product-kpi="draft"]');if(kt)kt.textContent=rows.length;if(ka)ka.textContent=active;if(ko)ko.textContent=out;if(kd)kd.textContent=draft;
    };
    render();
    ['productSearch','productCategoryFilter','productStockFilter','productSort'].forEach(id=>document.getElementById(id)?.addEventListener(id==='productSearch'?'input':'change',render));
    document.addEventListener('change',e=>{if(e.target.matches('[data-product-select]')){const id=Number(e.target.dataset.productSelect);e.target.checked?selected.add(id):selected.delete(id);render()}});
    const setAll=checked=>{selected.clear();if(checked)rows.slice(0,10).forEach(p=>selected.add(p.id));render();};$('#selectAllProducts')?.addEventListener('change',e=>setAll(e.target.checked));$('#selectAllProductsHead')?.addEventListener('change',e=>setAll(e.target.checked));
    document.addEventListener('click',e=>{const b=e.target.closest('[data-product-delete]');if(!b)return;deleteId=Number(b.dataset.productDelete);const p=rows.find(x=>x.id===deleteId);if(!p)return;$('#deleteProductPreview').innerHTML=`<img src="${p.image||DEMO.default_image}"><div><strong>${p.name}</strong><p>SKU: ${p.sku}<br>${p.category}</p></div><span class="brand-mini">${p.brand||''}</span>`;$('#productDeleteOverlay').hidden=false;});
    $$('[data-close-product-delete]').forEach(b=>b.addEventListener('click',()=>{$('#productDeleteOverlay').hidden=true;deleteId=null}));
    $('#confirmProductDelete')?.addEventListener('click',()=>{if(deleteId==null)return;rows=rows.filter(x=>x.id!==deleteId);set(rows);selected.delete(deleteId);$('#productDeleteOverlay').hidden=true;toast('Product deleted');render()});
    $('#archiveProductBtn')?.addEventListener('click',()=>{if(deleteId==null)return;rows=rows.map(x=>x.id===deleteId?{...x,status:'Archived'}:x);set(rows);$('#productDeleteOverlay').hidden=true;toast('Product archived');render()});
    $('#productBulkAction')?.addEventListener('change',e=>{const action=e.target.value;if(!action||action==='Bulk Actions'||!selected.size)return;if(action==='delete')rows=rows.filter(x=>!selected.has(x.id));if(action==='archive')rows=rows.map(x=>selected.has(x.id)?{...x,status:'Archived'}:x);if(action==='activate')rows=rows.map(x=>selected.has(x.id)?{...x,status:'Active'}:x);if(action==='draft')rows=rows.map(x=>selected.has(x.id)?{...x,status:'Draft'}:x);selected.clear();set(rows);toast('Bulk action applied');e.target.value='Bulk Actions';render()});
  }

  const addForm=$('[data-product-custom-form="add"]');
  if(addForm){
    const save=(asDraft=false)=>{const fd=new FormData(addForm),obj=Object.fromEntries(fd.entries());obj.id=Math.max(0,...rows.map(x=>x.id||0))+1;obj.price=Number(obj.price||0);obj.stock=Number(obj.stock||0);obj.status=asDraft?'Draft':(obj.status||'Active');obj.image=DEMO.upload_image;rows.push(obj);set(rows);toast(asDraft?'Draft saved':'Product published');setTimeout(()=>location.href=routes.products,450)};
    addForm.addEventListener('submit',e=>{e.preventDefault();save(false)});$('[data-product-save-draft]')?.addEventListener('click',()=>save(true));
    $('#addSpecificationBtn')?.addEventListener('click',()=>{const div=document.createElement('div');div.innerHTML='<input placeholder="Specification"><input placeholder="Value">';$('#specEditor')?.appendChild(div)});
    $('#productImageInput')?.addEventListener('change',e=>{[...e.target.files].slice(0,5).forEach(file=>{const url=URL.createObjectURL(file),d=document.createElement('div');d.className='image-tile';d.innerHTML=`<img src="${url}"><button type="button">×</button>`;d.querySelector('button').onclick=()=>d.remove();$('#productImageStrip')?.appendChild(d)})});
  }

  const editForm=$('[data-product-custom-form="edit"]');
  if(editForm){
    const id=Number(new URLSearchParams(location.search).get('id')||1);let p=rows.find(x=>x.id===id)||rows[0];if(p){['name','sku','category','brand','price','stock','status'].forEach(n=>{const f=editForm.elements[n];if(f&&p[n]!=null)f.value=p[n]});const img=$('#editMainProductImage');if(img)img.src=p.image||img.src}
    editForm.addEventListener('submit',e=>{e.preventDefault();const fd=new FormData(editForm),obj=Object.fromEntries(fd.entries());obj.id=id;obj.price=Number(obj.price||0);obj.stock=Number(obj.stock||0);obj.image=$('#editMainProductImage')?.getAttribute('src')||p.image;rows=rows.map(x=>x.id===id?{...x,...obj}:x);set(rows);toast('Product updated');setTimeout(()=>location.href=routes.products,450)});
    $$('[data-edit-image]').forEach(b=>b.addEventListener('click',()=>{$('#editMainProductImage').src=b.dataset.editImage}));
    $('[data-duplicate-product]')?.addEventListener('click',()=>{const copy={...p,id:Math.max(0,...rows.map(x=>x.id||0))+1,name:p.name+' Copy',sku:p.sku+'-COPY',status:'Draft'};rows.push(copy);set(rows);toast('Product duplicated as draft')});
    $('#editAddSpecBtn')?.addEventListener('click',()=>{const d=document.createElement('div');d.innerHTML='<span>New Spec</span><input placeholder="Value"><button type="button">♙</button>';$('#editSpecList')?.appendChild(d)});
  }
})();
