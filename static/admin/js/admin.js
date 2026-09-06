
(function(){
  const DEMO=JSON.parse(document.getElementById("admin-data").textContent);
  const routes=JSON.parse(document.getElementById("admin-routes").textContent);
  const body=document.body;
  document.addEventListener('click',e=>{const row=e.target.closest('[data-row-link]');if(row&&!e.target.closest('a,input'))location.href=row.dataset.rowLink});
  const $=(s,c=document)=>c.querySelector(s), $$=(s,c=document)=>[...c.querySelectorAll(s)];
  const money=n=>'৳ '+Number(n||0).toLocaleString('en-US',{maximumFractionDigits:0});
  const toast=(m)=>{const t=$('#toast');if(!t)return; t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1800)};
  $$('[data-menu-toggle]').forEach(btn=>btn.addEventListener('click',()=>body.classList.toggle('sidebar-open')));
  $$('[data-sidebar-overlay]').forEach(el=>el.addEventListener('click',()=>body.classList.remove('sidebar-open')));
  $$('[data-demo-alert]').forEach(btn=>btn.addEventListener('click',e=>{e.preventDefault();toast(btn.getAttribute('data-demo-alert'))}));
  $$('[data-table-search]').forEach(input=>{const table=$(input.getAttribute('data-table-search'));if(!table)return;input.addEventListener('input',()=>{const q=input.value.toLowerCase().trim();$$('tbody tr',table).forEach(r=>r.style.display=!q||r.innerText.toLowerCase().includes(q)?'':'none')})});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('.global-search input')?.focus()}});

  const seeds=DEMO.seeds;
  const key=e=>'techbari_admin_'+e;
  const get=e=>{let v=localStorage.getItem(key(e));if(!v){localStorage.setItem(key(e),JSON.stringify(seeds[e]||[]));v=localStorage.getItem(key(e))}try{return JSON.parse(v)||[]}catch{return[]}};
  const set=(e,v)=>localStorage.setItem(key(e),JSON.stringify(v));
  const statusClass=s=>{s=String(s||'').toLowerCase();if(/active|delivered|paid|received|success|posted|approved|in stock/.test(s))return'green';if(/processing|shipped|in transit|partial/.test(s))return'blue';if(/pending|low stock|inspection/.test(s))return'orange';if(/out of stock|cancel|reject|failed/.test(s))return'red';return'gray'};
  if(DEMO.detail){
    const entity=DEMO.detail.entity, row=get(entity).find(record=>Number(record.id)===DEMO.detail.id);
    if(row){
      const person=entity==='orders'?get('customers').find(customer=>customer.name===row.customer):row;
      const detail={...row,order_no:row.orderId||row.order_no,email:row.email||person?.email||'',phone:row.phone||person?.phone||'',customer_no:'CUST'+String(row.id).padStart(3,'0'),initials:(row.name||row.customer||'').split(' ').map(word=>word[0]).join('')};
      if(row.date)detail.date_label=new Date(row.date+'T00:00:00').toLocaleDateString('en-US',{month:'short',day:'2-digit',year:'numeric'});
      $$('[data-detail-key]').forEach(element=>{const value=detail[element.dataset.detailKey];if(value==null)return;element.textContent=(element.dataset.detailPrefix||'')+(element.hasAttribute('data-detail-money')?money(value):value)+(element.dataset.detailSuffix||'');if(element.dataset.detailKey==='status')element.className='status '+statusClass(value)});
      $$('a[href*="?id="]').forEach(link=>{const url=new URL(link.href);url.searchParams.set('id',row.id);link.href=url.href});
      const history=$('[data-customer-history]');
      if(entity==='customers'&&history){
        history.replaceChildren();
        get('orders').filter(order=>order.customer===row.name).forEach(order=>{
          const tr=document.createElement('tr');
          [order.orderId||order.order_no,order.date,money(order.amount),order.payment,order.status].forEach((value,index)=>{
            const td=document.createElement('td');
            if(index===0){const link=document.createElement('a');link.href=routes.order_detail+'?id='+order.id+'&local=1';link.textContent=value||'';td.appendChild(link)}
            else if(index===4){const badge=document.createElement('span');badge.className='status '+statusClass(value);badge.textContent=value||'';td.appendChild(badge)}
            else td.textContent=value||'';
            tr.appendChild(td);
          });
          history.appendChild(tr);
        });
      }
    }else{
      const page=$('main .page');if(page){page.replaceChildren();const empty=document.createElement('div');empty.className='empty-state';empty.textContent='This record is no longer available in this browser.';page.appendChild(empty)}
    }
  }
  const editMap=DEMO.edit_urls;
  const colMap=DEMO.columns;
  const moneyKeys=new Set(['price','amount','spent','total','purchases','outstanding','value','minimum','refund','cod']);
  function renderTable(table){const e=table.dataset.crudTable, rows=get(e), cols=colMap[e]||[];const tb=$('tbody',table);if(!tb)return;tb.innerHTML=rows.map((r,i)=>{let cells=cols.map(([k])=>{let v=r[k]??'';if(moneyKeys.has(k))v=money(v);if(k==='name'&&e==='products')v=`<div class="product-cell"><img class="thumb" src="${r.image||DEMO.default_image}"><div><strong>${r.name}</strong><br><span style="color:#7890ad">${r.category||''}</span></div></div>`;if(k==='status'||k==='payment'||k==='receipt'||k==='result')v=`<span class="status ${statusClass(v)}">${v}</span>`;return `<td>${v}</td>`}).join('');const form=editMap[e];const view=(e==='orders'?'<a class="icon-btn" href="'+routes.order_detail+'?id='+r.id+'&local=1'+ '" title="View">'+`<svg viewBox="0 0 24 24" class="svg"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/></svg>`+'</a>':e==='customers'?'<a class="icon-btn" href="'+routes.customer_detail+'?id='+r.id+'&local=1'+ '" title="View">👁</a>':'');const edit=form?`<a class="icon-btn" href="${form}?id=${r.id}" title="Edit">✎</a>`:'';const del=e==='audit'?'':`<button class="icon-btn danger" data-delete-row="${e}" data-id="${r.id}" title="Delete">×</button>`;return `<tr><td>${i+1}</td>${cells}<td><div class="crud-actions">${view}${edit}${del}</div></td></tr>`}).join('')||'<tr><td colspan="20"><div class="empty-state">No records found.</div></td></tr>';const c=table.closest('.card')?.querySelector('[data-table-count]');if(c)c.textContent=`${rows.length} records`;}
  $$('table[data-crud-table]').forEach(renderTable);
  document.addEventListener('click',e=>{const b=e.target.closest('[data-delete-row]');if(!b)return;const ent=b.dataset.deleteRow,id=Number(b.dataset.id);if(confirm('Delete this record from the static demo?')){set(ent,get(ent).filter(x=>x.id!==id));const table=$(`table[data-crud-table="${ent}"]`);if(table)renderTable(table);toast('Record deleted')}});
  const form=$('[data-crud-form]');if(form){const ent=form.dataset.crudForm, list=form.dataset.listUrl;const params=new URLSearchParams(location.search),id=Number(params.get('id'));let rows=get(ent);if(id){const row=rows.find(x=>x.id===id);if(row){$$('[name]',form).forEach(f=>{if(row[f.name]!=null&&f.type!=='file')f.value=row[f.name]});$('[data-form-mode]')?.replaceChildren(document.createTextNode('Edit'))}}form.addEventListener('submit',e=>{e.preventDefault();const fd=new FormData(form), obj=Object.fromEntries(fd.entries());$$('input[type=number]',form).forEach(f=>{if(f.name)obj[f.name]=Number(f.value||0)});obj.status=form.elements.status?.value||obj.status||'Active';if(ent==='products')obj.image=rows.find(x=>x.id===id)?.image||DEMO.default_image;if(id){obj.id=id;rows=rows.map(x=>x.id===id?{...x,...obj}:x)}else{obj.id=Math.max(0,...rows.map(x=>x.id||0))+1;rows.push(obj)}set(ent,rows);toast(id?'Record updated':'Record created');setTimeout(()=>location.href=list,500)})}
  $$('[data-export-table]').forEach(b=>b.addEventListener('click',()=>{const t=$(b.dataset.exportTable);if(!t)return;const rows=$$('tr',t).map(r=>$$('th,td',r).slice(0,-1).map(c=>'"'+c.innerText.replaceAll('"','""').replace(/\n/g,' ')+'"').join(','));const blob=new Blob([rows.join('\n')],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='techbari-export.csv';a.click();URL.revokeObjectURL(a.href)}));

  // POS reference-match demo
  const posGrid=$('[data-pos-grid]');
  if(posGrid){
    const posProducts=DEMO.pos_products;
    let selectedCategory='All', searchQuery='', viewMode='grid', paymentMethod='Cash';
    let cart=[{...posProducts[0],qty:1},{...posProducts[6],qty:1},{...posProducts[3],qty:1}];
    const discountInput=$('[data-pos-discount]'), discountType=$('[data-pos-discount-type]');
    const getFiltered=()=>{
      let rows=posProducts.filter(p=>(selectedCategory==='All'||p.category===selectedCategory)&&(!searchQuery||`${p.name} ${p.sku} ${p.category}`.toLowerCase().includes(searchQuery.toLowerCase())));
      const sort=$('[data-pos-sort]')?.value||'featured';
      if(sort==='price-low')rows=[...rows].sort((a,b)=>a.price-b.price);if(sort==='price-high')rows=[...rows].sort((a,b)=>b.price-a.price);if(sort==='stock')rows=[...rows].sort((a,b)=>b.stock-a.stock);
      return rows;
    };
    const cartTotals=()=>{
      const subtotal=cart.reduce((sum,i)=>sum+i.price*i.qty,0);
      const raw=Math.max(0,Number(discountInput?.value||0));
      const type=discountType?.value||'percent';
      const discount=type==='percent'?subtotal*Math.min(raw,100)/100:Math.min(raw,subtotal);
      const taxable=Math.max(0,subtotal-discount), vat=taxable*.05, total=taxable+vat;
      return{subtotal,raw,type,discount,vat,total};
    };
    const renderProducts=()=>{
      const rows=getFiltered();
      posGrid.classList.toggle('list-view',viewMode==='list');
      posGrid.innerHTML=rows.map(p=>`<article class="pos-ref-product"><div class="pos-img-wrap"><img src="${p.image}" alt="${p.name}"></div><div><h3>${p.name}</h3><div class="pos-cat">${p.category}</div><div class="pos-stock">In stock: <strong>${p.stock}</strong></div><div class="pos-price">${money(p.price)}</div></div><button class="pos-add-btn" type="button" data-pos-add="${p.id}"><svg viewBox="0 0 24 24" class="svg"><path d="M3 4h2l2 11h10l2-8H6"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/></svg>Add to Cart</button></article>`).join('')||'<div class="empty-state">No products found.</div>';
    };
    const renderCart=()=>{
      const box=$('[data-pos-cart]');
      box.innerHTML=cart.length?cart.map(i=>`<div class="pos-ref-cart-row"><img src="${i.image}" alt="${i.name}"><div class="pos-cart-info"><div class="pos-cart-line1"><strong>${i.name}</strong><strong class="line-total">${money(i.price*i.qty)}</strong></div><div class="pos-cart-unit">${money(i.price)}</div><div class="pos-qty"><button type="button" data-pos-minus="${i.id}">−</button><span>${i.qty}</span><button type="button" data-pos-plus="${i.id}">+</button></div></div><button class="pos-remove" type="button" data-pos-remove="${i.id}" aria-label="Remove">×</button></div>`).join(''):'<div class="empty-state">No products in current order.</div>';
      const t=cartTotals();
      $('[data-pos-subtotal]').textContent=money(t.subtotal);
      $('[data-pos-discount-label]').textContent=t.type==='percent'?`Discount (${t.raw}%)`:'Discount';
      $('[data-pos-discount-value]').textContent='- '+money(t.discount);
      $('[data-pos-vat]').textContent=money(t.vat);
      $('[data-pos-total]').textContent=money(t.total);
      $('[data-pos-complete-total]').textContent=money(t.total);
      $('[data-pos-discount-unit]').textContent=t.type==='percent'?'%':'৳';
    };
    renderProducts();renderCart();
    $('[data-pos-search]')?.addEventListener('input',e=>{searchQuery=e.target.value;renderProducts()});
    $('[data-pos-sort]')?.addEventListener('change',renderProducts);
    $('[data-pos-barcode]')?.addEventListener('click',()=>{const input=$('[data-pos-search]');input?.focus();toast('Barcode scanner ready — type or scan a barcode')});
    discountInput?.addEventListener('input',renderCart);discountType?.addEventListener('change',renderCart);
    document.addEventListener('click',e=>{
      const cat=e.target.closest('[data-pos-category]');if(cat){selectedCategory=cat.dataset.posCategory;$$('[data-pos-category]').forEach(x=>x.classList.toggle('active',x===cat));renderProducts();return;}
      const view=e.target.closest('[data-pos-view]');if(view){viewMode=view.dataset.posView;$$('[data-pos-view]').forEach(x=>x.classList.toggle('active',x===view));renderProducts();return;}
      const add=e.target.closest('[data-pos-add]');if(add){const p=posProducts.find(x=>x.id===Number(add.dataset.posAdd));if(!p)return;const c=cart.find(x=>x.id===p.id);c?c.qty++:cart.push({...p,qty:1});renderCart();toast(`${p.name} added`);return;}
      const plus=e.target.closest('[data-pos-plus]');if(plus){const c=cart.find(x=>x.id===Number(plus.dataset.posPlus));if(c&&c.qty<c.stock)c.qty++;renderCart();return;}
      const minus=e.target.closest('[data-pos-minus]');if(minus){const c=cart.find(x=>x.id===Number(minus.dataset.posMinus));if(c){c.qty--;if(c.qty<=0)cart=cart.filter(x=>x.id!==c.id)}renderCart();return;}
      const rem=e.target.closest('[data-pos-remove]');if(rem){cart=cart.filter(x=>x.id!==Number(rem.dataset.posRemove));renderCart();return;}
      const pay=e.target.closest('[data-pos-payment]');if(pay){paymentMethod=pay.dataset.posPayment;$$('[data-pos-payment]').forEach(x=>x.classList.toggle('active',x===pay));return;}
    });
    $('[data-pos-clear]')?.addEventListener('click',()=>{cart=[];renderCart()});
    $('[data-pos-complete]')?.addEventListener('click',()=>{if(!cart.length)return toast('Add products first');const t=cartTotals();toast(`Sale completed: ${money(t.total)} via ${paymentMethod}`);cart=[];if(discountInput)discountInput.value=0;renderCart()});
  }
})();
