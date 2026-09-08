(function(){
  if(!document.querySelector('meta[name="techbari-customer-account"]')) return;
  const cookie=(name)=>document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1)||'';
  document.addEventListener('click',function(event){
    const button=event.target.closest('[data-wish],[data-remove-wish]');
    if(!button) return;
    const productId=button.dataset.wish||button.dataset.removeWish;
    if(!productId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const body=new URLSearchParams();
    body.set('next',window.location.pathname+window.location.search);
    fetch('/wishlist/toggle/'+encodeURIComponent(productId)+'/',{
      method:'POST',
      credentials:'same-origin',
      headers:{'X-CSRFToken':decodeURIComponent(cookie('csrftoken')),'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},
      body:body.toString()
    }).then(function(response){if(response.ok||response.redirected) window.location.reload();});
  },true);
})();
