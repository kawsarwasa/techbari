(() => {
  if (typeof COUPONS === 'undefined' || typeof PRODUCTS === 'undefined') return;

  function lineSubtotal(item) {
    const product = PRODUCTS.find((row) => String(row.id) === String(item.id));
    if (!product) return 0;
    return Math.max(0, Number(product.price) || 0) * Math.max(1, Number(item.qty) || 1);
  }

  function couponPreview(code, cart = getCart()) {
    const coupon = COUPONS[String(code || '').toUpperCase()];
    if (!coupon) {
      return { valid: false, discount: 0, reason: 'This coupon code is not valid.' };
    }

    const subtotal = cart.reduce((sum, item) => sum + lineSubtotal(item), 0);
    const minimum = Math.max(0, Number(coupon.minimum) || 0);
    if (subtotal < minimum) {
      return {
        valid: false,
        discount: 0,
        reason: `Minimum order for this coupon is ${money(minimum)}.`,
      };
    }

    let eligibleSubtotal = subtotal;
    if (coupon.scope !== 'all') {
      const allowed = new Set((coupon.product_ids || []).map(String));
      eligibleSubtotal = cart.reduce(
        (sum, item) => allowed.has(String(item.id)) ? sum + lineSubtotal(item) : sum,
        0,
      );
    }

    if (eligibleSubtotal <= 0) {
      return {
        valid: false,
        discount: 0,
        reason: 'This coupon does not apply to the products in your cart.',
      };
    }

    const rawDiscount = coupon.type === 'fixed'
      ? Math.max(0, Number(coupon.value) || 0)
      : Math.round(eligibleSubtotal * Math.max(0, Number(coupon.value) || 0) / 100);

    return {
      valid: true,
      discount: Math.min(eligibleSubtotal, rawDiscount),
      eligibleSubtotal,
      subtotal,
      reason: '',
    };
  }

  calcDiscount = function (_subtotal, code = getCoupon()) {
    if (!code) return 0;
    return couponPreview(code).discount;
  };

  applyCouponFromInput = function (context) {
    const input = document.getElementById(context === 'cart' ? 'cartCouponInput' : 'checkoutCouponInput');
    if (!input) return;
    const code = input.value.trim().toUpperCase();

    if (!code) {
      setCoupon('');
      couponFeedback(context, '', '');
      context === 'cart' ? recalcCart() : recalcCheckout();
      return;
    }

    const preview = couponPreview(code);
    if (!preview.valid) {
      setCoupon('');
      couponFeedback(context, 'error', preview.reason);
      context === 'cart' ? recalcCart() : recalcCheckout();
      return;
    }

    setCoupon(code);
    couponFeedback(context, 'success', `Coupon applied: ${code}`);
    context === 'cart' ? recalcCart() : recalcCheckout();
  };

  renderCouponUI = function (context) {
    const code = getCoupon();
    const input = document.getElementById(context === 'cart' ? 'cartCouponInput' : 'checkoutCouponInput');
    if (input) input.value = code;

    if (code) {
      const preview = couponPreview(code);
      if (preview.valid) {
        couponFeedback(context, 'success', `Coupon applied: ${code}`);
      } else {
        setCoupon('');
        if (input) input.value = '';
        couponFeedback(context, 'error', preview.reason);
      }
    } else {
      couponFeedback(context, '', '');
    }

    context === 'cart' ? recalcCart() : recalcCheckout();
  };
})();
