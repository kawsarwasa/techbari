(()=>{
  const node=document.getElementById('tracking-integrations');
  if(!node)return;
  let cfg={};try{cfg=JSON.parse(node.textContent||'{}')}catch(_){return}
  const storeNode=document.getElementById('store-data');
  let store={};try{store=JSON.parse(storeNode?.textContent||'{}')}catch(_){store={}}
  const productById=id=>(store.products||[]).find(p=>String(p.id)===String(id));

  if(cfg.meta_pixel_enabled&&cfg.meta_pixel_id){
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init',cfg.meta_pixel_id);fbq('track','PageView');
  }
  if(cfg.ga4_enabled&&cfg.ga4_measurement_id){
    const s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(cfg.ga4_measurement_id);document.head.appendChild(s);
    window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments)};gtag('js',new Date());gtag('config',cfg.ga4_measurement_id);
  }

  function item(p,qty=1){if(!p)return null;return {item_id:p.sku||p.id,item_name:p.name,item_brand:p.brand,item_category:p.category,price:Number(p.price||p.current_price||0),quantity:Number(qty||1)}}
  function track(metaName,gaName,payload={},eventID=''){
    if(cfg.meta_pixel_enabled&&window.fbq&&metaName){const options=eventID?{eventID}:undefined;fbq('track',metaName,payload,options)}
    if(cfg.ga4_enabled&&window.gtag&&gaName)gtag('event',gaName,payload);
  }
  window.tbTrack=track;

  const current=store.current_product?productById(store.current_product):null;
  if(current){const i=item(current);track('ViewContent','view_item',{content_ids:[i.item_id],content_name:i.item_name,content_type:'product',currency:'BDT',value:i.price,items:[i]})}

  document.addEventListener('click',e=>{
    const add=e.target.closest('.add-cart');if(!add)return;
    const p=productById(add.dataset.product);if(!p)return;
    const qty=add.id==='productAddToCart'?Number(document.getElementById('productQty')?.textContent||1):1;
    const i=item(p,qty);track('AddToCart','add_to_cart',{content_ids:[i.item_id],content_name:i.item_name,content_type:'product',currency:'BDT',value:i.price*qty,contents:[{id:i.item_id,quantity:qty,item_price:i.price}],items:[i]});
  },true);

  const routesNode=document.getElementById('store-routes');let routes={};try{routes=JSON.parse(routesNode?.textContent||'{}')}catch(_){routes={}}
  if(routes.checkout&&location.pathname===routes.checkout){
    const cart=(()=>{try{return JSON.parse(localStorage.getItem('nu_cart')||'[]')}catch(_){return []}})();
    const items=cart.map(row=>item(productById(row.id),row.qty)).filter(Boolean);const value=items.reduce((n,row)=>n+row.price*row.quantity,0);
    track('InitiateCheckout','begin_checkout',{currency:'BDT',value,items});
  }

  const purchaseNode=document.getElementById('purchase-tracking-data');
  if(purchaseNode){let p={};try{p=JSON.parse(purchaseNode.textContent||'{}')}catch(_){p={}}
    if(p.order_number){
      const meta={currency:'BDT',value:Number(p.value||0),content_type:'product',contents:p.contents||[]};
      const ga={transaction_id:p.order_number,currency:'BDT',value:Number(p.value||0),shipping:Number(p.shipping||0),items:p.items||[]};
      track('Purchase','purchase',meta,p.event_id||('tb-purchase-'+p.order_number));
    }
  }
})();
