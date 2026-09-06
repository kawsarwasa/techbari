(function () {
  const $ = (selector, context = document) => context.querySelector(selector);
  const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];
  const toast = (message) => { const node = $('#toast'); if (!node) return; node.textContent = message; node.classList.add('show'); setTimeout(() => node.classList.remove('show'), 1800); };

  const body = $('#productRows[data-server-rendered]');
  if (body) {
    const selected = new Set();
    let actionProductId = '';
    const dataRows = () => $$('[data-product-row]', body);
    const visibleRows = () => dataRows().filter((row) => row.style.display !== 'none');
    const applyFilters = () => {
      const query = ($('#productSearch')?.value || '').trim().toLowerCase();
      const category = $('#productCategoryFilter')?.value || '';
      const stock = $('#productStockFilter')?.value || '';
      const sort = $('#productSort')?.value || 'newest';
      dataRows().forEach((row) => {
        const searchable = `${row.dataset.name} ${row.dataset.sku} ${row.dataset.brand} ${row.dataset.category}`.toLowerCase();
        const quantity = Number(row.dataset.stock || 0);
        const matches = (!query || searchable.includes(query)) && (!category || row.dataset.category === category) && (!stock || (stock === 'out' ? quantity <= 0 : stock === 'low' ? quantity > 0 && quantity <= 10 : quantity > 0));
        row.style.display = matches ? '' : 'none';
      });
      const sortable = visibleRows();
      const compare = { name: (a,b)=>a.dataset.name.localeCompare(b.dataset.name), 'price-low': (a,b)=>Number(a.dataset.price)-Number(b.dataset.price), 'price-high': (a,b)=>Number(b.dataset.price)-Number(a.dataset.price), stock: (a,b)=>Number(b.dataset.stock)-Number(a.dataset.stock), newest: (a,b)=>String(b.dataset.created||'').localeCompare(String(a.dataset.created||'')) }[sort];
      if (compare) sortable.sort(compare).forEach((row) => body.appendChild(row));
      const visible = visibleRows().length;
      if ($('#productTotal')) $('#productTotal').textContent = String(visible);
      if ($('#productRange')) $('#productRange').textContent = visible ? `1–${visible}` : '0–0';
      if ($('#selectedProductCount')) $('#selectedProductCount').textContent = String(selected.size);
    };
    ['productSearch','productCategoryFilter','productStockFilter','productSort'].forEach((id) => document.getElementById(id)?.addEventListener(id === 'productSearch' ? 'input' : 'change', applyFilters));
    document.addEventListener('change', (event) => { if (!event.target.matches('[data-product-select]')) return; const id=String(event.target.dataset.productSelect); event.target.checked ? selected.add(id) : selected.delete(id); applyFilters(); });
    const setAll=(checked)=>{ visibleRows().forEach((row)=>{ const id=String(row.dataset.id); const box=row.querySelector('[data-product-select]'); if(box) box.checked=checked; checked ? selected.add(id) : selected.delete(id); }); applyFilters(); };
    $('#selectAllProducts')?.addEventListener('change',(e)=>setAll(e.target.checked)); $('#selectAllProductsHead')?.addEventListener('change',(e)=>setAll(e.target.checked));
    document.addEventListener('click',(event)=>{ const button=event.target.closest('[data-product-delete]'); if(!button)return; const row=button.closest('[data-product-row]'); if(!row)return; actionProductId=row.dataset.id; const preview=$('#deleteProductPreview'); if(preview) preview.innerHTML=`<img src="${row.dataset.image}" alt=""><div><strong>${row.dataset.name}</strong><p>SKU: ${row.dataset.sku}<br>${row.dataset.category}</p></div><span class="brand-mini">${row.dataset.brand}</span>`; const overlay=$('#productDeleteOverlay'); if(overlay) overlay.hidden=false; });
    $$('[data-close-product-delete]').forEach((button)=>button.addEventListener('click',()=>{ const overlay=$('#productDeleteOverlay'); if(overlay) overlay.hidden=true; actionProductId=''; }));
    const submitAction=(action,productId='')=>{ const form=$('#productActionForm'); if(!form)return; $('#productAction').value=action; $('#productActionId').value=productId; $('#bulkProductIds').replaceChildren(); if(action.startsWith('bulk_')) selected.forEach((id)=>{ const input=document.createElement('input'); input.type='hidden'; input.name='product_ids'; input.value=id; $('#bulkProductIds').appendChild(input); }); form.submit(); };
    $('#confirmProductDelete')?.addEventListener('click',()=>actionProductId&&submitAction('delete',actionProductId));
    $('#archiveProductBtn')?.addEventListener('click',()=>actionProductId&&submitAction('archive',actionProductId));
    $('#productBulkAction')?.addEventListener('change',(event)=>{ const action=event.target.value; if(!action)return; if(!selected.size){toast('Select at least one product first');event.target.value='';return;} if(action==='bulk_delete'&&!window.confirm(`Delete ${selected.size} selected product(s)?`)){event.target.value='';return;} submitAction(action); });
    applyFilters();
  }

  const form = $('[data-catalog-product-form]');
  if (form) {
    $('[data-product-save-draft]')?.addEventListener('click',()=>{ const status=form.elements.status; if(status) status.value='draft'; form.requestSubmit(); });
    const addSpecRow=(container)=>{ if(!container)return; const row=document.createElement('div'); row.innerHTML='<input name="spec_name" placeholder="Specification"><input name="spec_value" placeholder="Value"><button type="button" data-remove-spec>×</button>'; container.appendChild(row); row.querySelector('input')?.focus(); };
    $('#addSpecificationBtn')?.addEventListener('click',()=>addSpecRow($('#specEditor'))); $('#editAddSpecBtn')?.addEventListener('click',()=>addSpecRow($('#editSpecList')));
    document.addEventListener('click',(event)=>event.target.closest('[data-remove-spec]')?.parentElement?.remove());
    $('#productImageInput')?.addEventListener('change',(event)=>{ const strip=$('#productImageStrip'); if(!strip)return; strip.replaceChildren(); const files=[...event.target.files]; const oversized=files.find((file)=>file.size>2*1024*1024); if(oversized) toast(`${oversized.name} is larger than 2MB and will be rejected.`); files.slice(0,8).forEach((file)=>{ const tile=document.createElement('div'); tile.className='image-tile'; const image=document.createElement('img'); image.src=URL.createObjectURL(file); image.alt=file.name; image.onload=()=>URL.revokeObjectURL(image.src); tile.appendChild(image); strip.appendChild(tile); }); });
    $$('[data-edit-image]').forEach((button)=>button.addEventListener('click',()=>{ const main=$('#editMainProductImage'); if(main) main.src=button.dataset.editImage; }));
  }
})();
