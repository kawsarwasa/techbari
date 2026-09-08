(function(){
  function deliveryConfig(){return (typeof STORE_DATA!=='undefined'&&STORE_DATA.delivery)||{};}
  function configuredShipping(subtotal,selected){
    const cfg=deliveryConfig();
    const threshold=Number(cfg.free_threshold||0);
    if(threshold>0&&subtotal>=threshold)return 0;
    const outside=selected?.dataset.delivery==='outside';
    return Number(outside?cfg.outside_charge:cfg.inside_charge)||0;
  }
  function applyDeliveryLabels(){
    const cfg=deliveryConfig();
    document.querySelectorAll('.option[data-delivery]').forEach(opt=>{
      const outside=opt.dataset.delivery==='outside';
      const charge=Number(outside?cfg.outside_charge:cfg.inside_charge)||0;
      const days=outside?cfg.outside_days:cfg.inside_days;
      opt.dataset.charge=String(charge);
      const muted=opt.querySelector('.muted');if(muted&&days)muted.textContent=`Delivery in ${days}`;
      const price=opt.querySelector('b');if(price)price.textContent=money(charge);
    });
    const cod=document.querySelector('.payment input[value="cod"]')?.closest('.payment');
    if(cod&&cfg.cod_enabled===false){
      cod.classList.remove('active');cod.setAttribute('aria-disabled','true');
      const input=cod.querySelector('input');if(input){input.disabled=true;input.checked=false;}
      const muted=cod.querySelector('.muted');if(muted)muted.textContent='Currently unavailable';
      const btn=document.getElementById('placeOrder');if(btn){btn.disabled=true;btn.title='Cash on Delivery is currently disabled';}
    }
  }
  const original=typeof recalcCheckout==='function'?recalcCheckout:null;
  if(original){
    recalcCheckout=function(flash=false){
      if(!document.getElementById('checkoutSubtotal'))return;
      const cart=getCart();
      const subtotal=cart.reduce((sum,it)=>{const p=PRODUCTS.find(x=>x.id===it.id);return sum+(p?p.price*(it.qty||1):0)},0);
      const selected=document.querySelector('.option[data-delivery] input:checked')?.closest('.option')||document.querySelector('.option[data-delivery].active');
      const outside=selected?.dataset.delivery==='outside';
      const shipping=configuredShipping(subtotal,selected);
      const discount=calcDiscount(subtotal),grand=subtotal-discount+shipping;
      document.getElementById('checkoutSubtotal').textContent=money(subtotal);
      document.getElementById('shippingCharge').textContent=shipping===0?'Free':money(shipping);
      document.getElementById('shippingLabel').textContent=`Shipping Charge (${outside?'Outside Dhaka':'Inside Dhaka'})`;
      document.getElementById('checkoutGrand').textContent=money(grand);
      const drow=document.getElementById('checkoutDiscountRow');if(drow)drow.hidden=!discount;
      document.getElementById('checkoutDiscount').textContent='- '+money(discount);
      if(flash){['shippingCharge','checkoutGrand'].forEach(id=>{const e=document.getElementById(id);if(!e)return;e.classList.remove('flash');void e.offsetWidth;e.classList.add('flash')})}
    };
  }
  document.addEventListener('DOMContentLoaded',()=>{applyDeliveryLabels();if(typeof recalcCheckout==='function')recalcCheckout();});
})();
