(() => {
  if (typeof PRODUCTS === 'undefined' || typeof routes === 'undefined') return;

  const COUPON_KEY = 'nu_coupon';
  let validated = { code: '', discount: 0, signature: '' };
  let pendingSignature = '';

  function cartPayload(cart = getCart()) {
    const merged = new Map();
    for (const item of cart) {
      const product = PRODUCTS.find((row) => String(row.id) === String(item.id));
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
    return [...merged.entries()].map(([variantId, qty]) => ({
      variant_id: Number(variantId),
      qty,
    }));
  }

  function cartSignature(payload = cartPayload()) {
    return payload
      .map((row) => `${row.variant_id}:${row.qty}`)
      .sort()
      .join('|');
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  async function serverPreview(code) {
    const cart = cartPayload();
    if (!cart.length) {
      return { valid: false, discount: 0, reason: 'Your cart is empty.' };
    }
    const response = await fetch(routes.coupon_preview, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ code, cart }),
    });
    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }
    if (!response.ok && !data.reason) {
      throw new Error('Coupon validation is temporarily unavailable.');
    }
    return data;
  }

  function resetValidated() {
    validated = { code: '', discount: 0, signature: '' };
  }

  getCoupon = function () {
    return (localStorage.getItem(COUPON_KEY) || '').trim().toUpperCase();
  };

  calcDiscount = function () {
    const code = getCoupon();
    const signature = cartSignature();
    if (!code || validated.code !== code || validated.signature !== signature) return 0;
    return Math.max(0, Number(validated.discount) || 0);
  };

  async function validateAndRender(code, context, { clearOnInvalid = true } = {}) {
    const signature = cartSignature();
    pendingSignature = signature;
    try {
      const preview = await serverPreview(code);
      if (pendingSignature !== signature) return false;
      pendingSignature = '';

      if (!preview.valid) {
        resetValidated();
        if (clearOnInvalid) setCoupon('');
        const input = document.getElementById(context === 'cart' ? 'cartCouponInput' : 'checkoutCouponInput');
        if (clearOnInvalid && input) input.value = '';
        couponFeedback(context, 'error', preview.reason || 'This coupon code is not valid.');
        context === 'cart' ? baseRecalcCart() : baseRecalcCheckout();
        return false;
      }

      validated = {
        code,
        discount: Number(preview.discount) || 0,
        signature,
      };
      setCoupon(code);
      couponFeedback(context, 'success', `Coupon applied: ${code}`);
      context === 'cart' ? baseRecalcCart() : baseRecalcCheckout();
      return true;
    } catch (_) {
      pendingSignature = '';
      resetValidated();
      couponFeedback(context, 'error', 'Coupon validation is temporarily unavailable. Please try again.');
      context === 'cart' ? baseRecalcCart() : baseRecalcCheckout();
      return false;
    }
  }

  const baseRecalcCart = recalcCart;
  const baseRecalcCheckout = recalcCheckout;

  function scheduleRevalidation(context) {
    const code = getCoupon();
    if (!code) return;
    const signature = cartSignature();
    if (!signature || (validated.code === code && validated.signature === signature) || pendingSignature === signature) return;
    validateAndRender(code, context, { clearOnInvalid: true });
  }

  recalcCart = function () {
    baseRecalcCart();
    scheduleRevalidation('cart');
  };

  recalcCheckout = function (flash = false) {
    baseRecalcCheckout(flash);
    scheduleRevalidation('checkout');
  };

  applyCouponFromInput = async function (context) {
    const input = document.getElementById(context === 'cart' ? 'cartCouponInput' : 'checkoutCouponInput');
    if (!input) return;
    const code = input.value.trim().toUpperCase();

    if (!code) {
      setCoupon('');
      resetValidated();
      couponFeedback(context, '', '');
      context === 'cart' ? baseRecalcCart() : baseRecalcCheckout();
      return;
    }

    couponFeedback(context, '', 'Checking coupon…');
    await validateAndRender(code, context, { clearOnInvalid: true });
  };

  renderCouponUI = function (context) {
    const code = getCoupon();
    const input = document.getElementById(context === 'cart' ? 'cartCouponInput' : 'checkoutCouponInput');
    if (input) input.value = code;
    if (!code) {
      resetValidated();
      couponFeedback(context, '', '');
      context === 'cart' ? baseRecalcCart() : baseRecalcCheckout();
      return;
    }
    couponFeedback(context, '', 'Checking coupon…');
    validateAndRender(code, context, { clearOnInvalid: true });
  };
})();
