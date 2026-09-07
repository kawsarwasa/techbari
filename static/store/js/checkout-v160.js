(() => {
  const CART_KEY = 'nu_cart';
  const COUPON_KEY = 'nu_coupon';

  const successNode = document.getElementById('checkoutSuccessV160');
  if (successNode) {
    localStorage.setItem(CART_KEY, '[]');
    localStorage.removeItem(COUPON_KEY);
    const badge = document.getElementById('cartCount');
    if (badge) badge.textContent = '0';
    return;
  }

  const form = document.getElementById('checkoutForm');
  if (!form) return;

  const storeNode = document.getElementById('store-data');
  const storeData = storeNode ? JSON.parse(storeNode.textContent || '{}') : {};
  const products = storeData.products || [];
  const productMap = new Map(products.map((product) => [String(product.id), product]));
  const payloadNode = document.getElementById('checkoutCartPayload');
  const errorNode = document.getElementById('checkoutClientError');
  const submitButton = document.getElementById('placeOrder');

  function readCart() {
    try {
      const cart = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      return Array.isArray(cart) ? cart : [];
    } catch (_) {
      return [];
    }
  }

  function buildPayload() {
    const merged = new Map();
    for (const item of readCart()) {
      const product = productMap.get(String(item.id));
      if (!product) continue;
      const variants = product.variants || [];
      let variant = null;
      if (item.variant_id != null) {
        variant = variants.find((row) => String(row.id) === String(item.variant_id));
      }
      if (!variant && item.variant) {
        variant = variants.find((row) => row.name === item.variant);
      }
      if (!variant) {
        variant = variants.find((row) => row.is_default) || variants[0] || null;
      }
      if (!variant) continue;
      const qty = Math.max(1, Number(item.qty) || 1);
      const key = String(variant.id);
      merged.set(key, (merged.get(key) || 0) + qty);
    }
    return [...merged.entries()].map(([variantId, qty]) => ({ variant_id: Number(variantId), qty }));
  }

  function setClientError(message) {
    if (!errorNode) return;
    errorNode.textContent = message || '';
    errorNode.hidden = !message;
    if (message) errorNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function preparePayload() {
    const payload = buildPayload();
    if (payloadNode) payloadNode.value = JSON.stringify(payload);
    const couponInput = document.getElementById('checkoutCouponInput');
    if (couponInput && !couponInput.value.trim()) {
      couponInput.value = (localStorage.getItem(COUPON_KEY) || '').toUpperCase();
    }
    return payload;
  }

  // app.js used to show a fake "Order Placed" animation on this button.
  // Capture the click before that legacy target listener and submit the real form instead.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('#placeOrder');
    if (!button || button.disabled) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const payload = preparePayload();
    if (!payload.length) {
      setClientError('Your cart is empty. Add a product before placing an order.');
      return;
    }
    setClientError('');
    form.requestSubmit();
  }, true);

  form.addEventListener('submit', (event) => {
    const payload = preparePayload();
    if (!payload.length) {
      event.preventDefault();
      setClientError('Your cart is empty. Add a product before placing an order.');
      return;
    }
    setClientError('');
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = 'Placing Order…';
    }
  });
})();
