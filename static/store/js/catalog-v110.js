(() => {
  const storeNode = document.getElementById('store-data');
  const routesNode = document.getElementById('store-routes');
  if (!storeNode) return;

  const DATA = JSON.parse(storeNode.textContent || '{}');
  const ROUTES = routesNode ? JSON.parse(routesNode.textContent || '{}') : {};
  const PRODUCTS = DATA.products || [];
  const LISTING_PRODUCTS = DATA.listing_products || PRODUCTS;
  const PRODUCT_BY_ID = new Map(PRODUCTS.map((product) => [String(product.id), product]));
  const CART_KEY = 'nu_cart';
  const COUPON_KEY = 'nu_coupon';

  const money = (value) => `৳ ${Math.max(0, Number(value) || 0).toLocaleString('en-BD')}`;
  const escapeHTML = (value) => {
    const node = document.createElement('div');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  };

  function readCart() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY) || '[]') || [];
    } catch (_) {
      return [];
    }
  }

  function writeCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartCount(cart);
  }

  function updateCartCount(cart = readCart()) {
    const count = cart.reduce((sum, item) => sum + (Number(item.qty) || 1), 0);
    const badge = document.getElementById('cartCount');
    if (badge) badge.textContent = String(count);
  }

  function defaultVariant(product) {
    if (!product) return null;
    return (product.variants || []).find((variant) => variant.is_default) || (product.variants || [])[0] || null;
  }

  function variantFor(product, itemOrName = null) {
    if (!product) return null;
    const variants = product.variants || [];
    if (itemOrName && typeof itemOrName === 'object') {
      if (itemOrName.variant_id != null) {
        const byId = variants.find((variant) => String(variant.id) === String(itemOrName.variant_id));
        if (byId) return byId;
      }
      if (itemOrName.variant) {
        const byName = variants.find((variant) => variant.name === itemOrName.variant);
        if (byName) return byName;
      }
    } else if (itemOrName) {
      const byName = variants.find((variant) => variant.name === itemOrName);
      if (byName) return byName;
    }
    return defaultVariant(product);
  }

  function normalizedCart() {
    let changed = false;
    const rows = [];
    for (const original of readCart()) {
      const product = PRODUCT_BY_ID.get(String(original.id));
      if (!product) {
        changed = true;
        continue;
      }
      const variant = variantFor(product, original);
      const item = { ...original, id: product.id, qty: Math.max(1, Number(original.qty) || 1) };
      if (variant) {
        if (item.variant !== variant.name || String(item.variant_id || '') !== String(variant.id)) changed = true;
        item.variant = variant.name;
        item.variant_id = variant.id;
        if (variant.stock > 0 && item.qty > variant.stock) {
          item.qty = variant.stock;
          changed = true;
        }
      }
      rows.push(item);
    }
    if (changed) writeCart(rows);
    return rows;
  }

  function unitPrice(product, item) {
    const variant = variantFor(product, item);
    return Number(variant ? variant.price : product?.price) || 0;
  }

  function couponDiscount(subtotal) {
    const code = (localStorage.getItem(COUPON_KEY) || '').toUpperCase();
    const coupon = (DATA.coupons || {})[code];
    if (!coupon) return 0;
    const raw = coupon.type === 'fixed' ? Number(coupon.value) : Math.round(subtotal * Number(coupon.value) / 100);
    return Math.min(subtotal, Math.max(0, raw || 0));
  }

  function addVariantToCart(product, variant, qty) {
    if (!product || !variant || variant.stock <= 0) return false;
    qty = Math.max(1, Math.min(Number(qty) || 1, variant.stock));
    const cart = normalizedCart();
    const existing = cart.find((item) => String(item.id) === String(product.id) && String(item.variant_id) === String(variant.id));
    if (existing) existing.qty = Math.min(variant.stock, existing.qty + qty);
    else cart.push({ id: product.id, qty, variant: variant.name, variant_id: variant.id });
    writeCart(cart);
    return true;
  }

  function initProductDetail() {
    const productId = DATA.current_product;
    if (!productId) return;
    const product = PRODUCT_BY_ID.get(String(productId));
    if (!product) return;

    const swatches = [...document.querySelectorAll('.swatch[data-variant]')];
    let selected = defaultVariant(product);

    const title = document.querySelector('.variant-title');
    const currentPrice = document.querySelector('.product-price .current');
    const regularPrice = document.querySelector('.product-price .old-price');
    const stockNode = document.querySelector('.product-price .stock');
    const qtyNode = document.getElementById('productQty');
    const addButton = document.getElementById('productAddToCart');
    const buyButton = document.getElementById('productBuyNow');

    let meta = document.querySelector('.variant-meta-v110');
    if (!meta && title) {
      meta = document.createElement('div');
      meta.className = 'variant-meta-v110';
      title.insertAdjacentElement('afterend', meta);
    }

    const updateVariant = (variant) => {
      if (!variant) return;
      selected = variant;
      swatches.forEach((button) => {
        const active = button.dataset.variant === variant.name;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      if (title) title.textContent = `Variant: ${variant.name}`;
      if (meta) meta.textContent = `SKU: ${variant.sku}${variant.barcode ? ` · Barcode: ${variant.barcode}` : ''}`;
      if (currentPrice) currentPrice.textContent = money(variant.price);
      if (regularPrice) {
        regularPrice.textContent = money(variant.regular_price);
        regularPrice.hidden = Number(variant.regular_price) <= Number(variant.price);
      }
      if (stockNode) {
        stockNode.textContent = variant.stock > 0 ? `● In Stock (${variant.stock})` : '● Out of Stock';
        stockNode.classList.toggle('out', variant.stock <= 0);
      }
      const unavailable = variant.stock <= 0;
      if (addButton) addButton.disabled = unavailable;
      if (buyButton) buyButton.disabled = unavailable;
      if (qtyNode) qtyNode.textContent = String(unavailable ? 1 : Math.min(Number(qtyNode.textContent) || 1, variant.stock));
    };

    swatches.forEach((button) => {
      button.addEventListener('click', () => {
        const variant = variantFor(product, button.dataset.variant);
        if (variant) updateVariant(variant);
      });
    });

    const defaultButton = selected && swatches.find((button) => button.dataset.variant === selected.name);
    if (defaultButton) defaultButton.classList.add('active');
    updateVariant(selected);

    const summary = document.querySelector('.product-info > p.muted');
    if (summary) summary.textContent = product.short_description || product.description || '';

    const descriptionPanel = document.querySelector('[data-product-panel="description"] .product-description-panel');
    if (descriptionPanel) {
      const descriptionHTML = product.description_html || `<p>${escapeHTML(product.description || '')}</p>`;
      const boxItems = (product.box_contents || []).length
        ? product.box_contents.map((item) => `<li>${escapeHTML(item)}</li>`).join('')
        : '<li>Product package contents may vary.</li>';
      descriptionPanel.innerHTML = `<h3>Product Description</h3><div class="product-rich-description-v110">${descriptionHTML}</div><h3>What's in the Box</h3><ul>${boxItems}</ul>`;
    }

    document.addEventListener('click', (event) => {
      const target = event.target.closest('#productAddToCart, #productBuyNow');
      if (!target) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!selected || selected.stock <= 0) return;
      const qty = Number(qtyNode?.textContent || 1);
      if (!addVariantToCart(product, selected, qty)) return;
      if (target.id === 'productBuyNow') {
        if (ROUTES.checkout) window.location.href = ROUTES.checkout;
        return;
      }
      const previous = target.innerHTML;
      target.textContent = `✓ Added${qty > 1 ? ` × ${qty}` : ''}`;
      setTimeout(() => { target.innerHTML = previous; }, 900);
    }, true);
  }

  function initListing() {
    const grid = document.getElementById('allProductsGrid');
    if (!grid) return;

    const cards = new Map();
    grid.querySelectorAll('.product-card').forEach((card) => {
      const id = card.querySelector('[data-product]')?.dataset.product;
      if (id) cards.set(String(id), card);
    });

    const search = document.getElementById('productSearch');
    const sort = document.getElementById('catalogSort');
    const priceSlider = document.getElementById('catalogPriceRange');
    const priceValue = document.getElementById('catalogPriceValue');
    const showing = document.getElementById('catalogShowing');
    const categoryChecks = [...document.querySelectorAll('[data-catalog-category]')];
    const brandChecks = [...document.querySelectorAll('[data-catalog-brand]')];
    const availabilityChecks = [...document.querySelectorAll('[data-catalog-availability]')];
    const presets = [...document.querySelectorAll('[data-catalog-price-preset]')];
    let presetRange = null;

    const params = new URLSearchParams(window.location.search);
    const query = (params.get('q') || '').trim();
    if (search && query) search.value = query;
    const categoryParam = params.get('category');
    const brandParam = params.get('brand');
    if (categoryParam) categoryChecks.forEach((box) => { box.checked = box.value === categoryParam; });
    if (brandParam) brandChecks.forEach((box) => { box.checked = box.value === brandParam; });

    const apply = () => {
      const q = (search?.value || '').trim().toLowerCase();
      const categories = new Set(categoryChecks.filter((box) => box.checked).map((box) => box.value));
      const brands = new Set(brandChecks.filter((box) => box.checked).map((box) => box.value));
      const availability = new Set(availabilityChecks.filter((box) => box.checked).map((box) => box.value));
      const sliderMax = Number(priceSlider?.value || 50000);

      let list = LISTING_PRODUCTS.filter((product) => {
        const text = `${product.name} ${product.brand} ${product.category} ${product.sku || ''}`.toLowerCase();
        if (q && !text.includes(q)) return false;
        if (categories.size && !categories.has(product.category)) return false;
        if (brands.size && !brands.has(product.brand)) return false;
        if (availability.size === 1) {
          if (availability.has('in') && Number(product.stock) <= 0) return false;
          if (availability.has('out') && Number(product.stock) > 0) return false;
        } else if (availability.size === 0) {
          return false;
        }
        const price = Number(product.price) || 0;
        if (presetRange) {
          if (price < presetRange.min) return false;
          if (presetRange.max != null && price > presetRange.max) return false;
        } else if (price > sliderMax) {
          return false;
        }
        return true;
      });

      const mode = sort?.value || 'featured';
      const compare = {
        newest: (a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')),
        'price-asc': (a, b) => Number(a.price) - Number(b.price),
        'price-desc': (a, b) => Number(b.price) - Number(a.price),
        featured: (a, b) => Number(Boolean(b.is_featured)) - Number(Boolean(a.is_featured)),
      }[mode];
      if (compare) list = [...list].sort(compare);

      const fragment = document.createDocumentFragment();
      list.forEach((product) => {
        const card = cards.get(String(product.id));
        if (card) fragment.appendChild(card);
      });
      grid.replaceChildren(fragment);
      if (!list.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = 'No products match the selected filters.';
        grid.appendChild(empty);
      }
      if (showing) showing.textContent = `Showing ${list.length} product${list.length === 1 ? '' : 's'}`;
      if (priceValue && priceSlider && !presetRange) priceValue.textContent = `Up to ${money(priceSlider.value)}`;
    };

    [search, sort, priceSlider, ...categoryChecks, ...brandChecks, ...availabilityChecks].forEach((control) => {
      if (!control) return;
      control.addEventListener(control === search || control === priceSlider ? 'input' : 'change', () => {
        if (control === priceSlider) {
          presetRange = null;
          presets.forEach((button) => button.classList.remove('active'));
        }
        apply();
      });
    });

    presets.forEach((button) => {
      button.addEventListener('click', () => {
        const min = Number(button.dataset.min || 0);
        const rawMax = button.dataset.max;
        presetRange = { min, max: rawMax === '' || rawMax == null ? null : Number(rawMax) };
        presets.forEach((item) => item.classList.toggle('active', item === button));
        if (priceValue) priceValue.textContent = button.textContent.trim();
        apply();
      });
    });

    document.querySelector('[data-catalog-clear]')?.addEventListener('click', () => {
      if (search) search.value = '';
      categoryChecks.forEach((box) => { box.checked = false; });
      brandChecks.forEach((box) => { box.checked = false; });
      availabilityChecks.forEach((box) => { box.checked = true; });
      if (priceSlider) priceSlider.value = priceSlider.max || '50000';
      if (sort) sort.value = 'featured';
      presetRange = null;
      presets.forEach((button) => button.classList.remove('active'));
      apply();
    });

    apply();
  }

  function renderCart() {
    const tbody = document.getElementById('cartItemsBody');
    if (!tbody) return;
    const cart = normalizedCart();

    tbody.innerHTML = cart.map((item) => {
      const product = PRODUCT_BY_ID.get(String(item.id));
      if (!product) return '';
      const variant = variantFor(product, item);
      const price = unitPrice(product, item);
      const variants = (product.variants || []).map((option) => {
        const selected = variant && String(option.id) === String(variant.id) ? ' selected' : '';
        const disabled = option.stock <= 0 && !selected ? ' disabled' : '';
        return `<option value="${escapeHTML(option.id)}"${selected}${disabled}>${escapeHTML(option.name)}${option.stock <= 0 ? ' — Out of stock' : ''}</option>`;
      }).join('');
      return `<tr data-cart-id="${escapeHTML(product.id)}" data-variant-id="${escapeHTML(variant?.id || '')}"><td><div class="cart-product"><img src="${escapeHTML(product.img || product.image_url)}" alt="${escapeHTML(product.name)}"><div><strong>${escapeHTML(product.name)}</strong><span class="muted">${escapeHTML(product.brand)}</span></div></div></td><td data-label="Variant"><select class="variant-select">${variants}</select></td><td data-label="Unit Price"><strong>${money(price)}</strong></td><td data-label="Quantity"><div class="qty"><button type="button" data-v110-qty-minus aria-label="Decrease">−</button><span data-v110-qty>${item.qty}</span><button type="button" data-v110-qty-plus aria-label="Increase">+</button></div></td><td data-label="Subtotal"><strong>${money(price * item.qty)}</strong></td><td data-label="Action"><button type="button" class="remove-item" data-v110-remove aria-label="Remove ${escapeHTML(product.name)}">×</button></td></tr>`;
    }).join('');

    const empty = document.getElementById('cartEmpty');
    const actions = document.getElementById('cartActions');
    const table = tbody.closest('table');
    if (empty) empty.hidden = cart.length > 0;
    if (actions) actions.style.display = cart.length ? 'flex' : 'none';
    if (table) table.style.display = cart.length ? 'table' : 'none';
    const checkout = document.getElementById('checkoutButton');
    if (checkout) {
      checkout.style.pointerEvents = cart.length ? '' : 'none';
      checkout.style.opacity = cart.length ? '1' : '.45';
    }
    updateCartTotals(cart);
  }

  function updateCartTotals(cart = normalizedCart()) {
    const subtotal = cart.reduce((sum, item) => {
      const product = PRODUCT_BY_ID.get(String(item.id));
      return sum + (product ? unitPrice(product, item) * item.qty : 0);
    }, 0);
    const discount = couponDiscount(subtotal);
    const qty = cart.reduce((sum, item) => sum + item.qty, 0);
    const subtotalNode = document.querySelector('[data-cart-subtotal]');
    const grandNode = document.querySelector('[data-cart-grand]');
    if (subtotalNode) subtotalNode.textContent = money(subtotal);
    if (grandNode) grandNode.textContent = money(subtotal - discount);
    const summaryCount = document.getElementById('summaryItemCount');
    if (summaryCount) summaryCount.textContent = String(qty);
    const itemText = document.getElementById('cartItemText');
    if (itemText) itemText.textContent = `${qty} item${qty === 1 ? '' : 's'}`;
    const row = document.getElementById('cartDiscountRow');
    if (row) row.hidden = !discount;
    const amount = document.getElementById('cartDiscountAmount');
    if (amount) amount.textContent = `- ${money(discount)}`;
    updateCartCount(cart);
  }

  function initCart() {
    const tbody = document.getElementById('cartItemsBody');
    if (!tbody) return;
    renderCart();

    tbody.addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-cart-id]');
      if (!row) return;
      const plus = event.target.closest('[data-v110-qty-plus]');
      const minus = event.target.closest('[data-v110-qty-minus]');
      const remove = event.target.closest('[data-v110-remove]');
      if (!plus && !minus && !remove) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const cart = normalizedCart();
      const item = cart.find((entry) => String(entry.id) === row.dataset.cartId && String(entry.variant_id || '') === row.dataset.variantId);
      if (!item) return;
      const product = PRODUCT_BY_ID.get(String(item.id));
      const variant = variantFor(product, item);
      if (remove) {
        writeCart(cart.filter((entry) => entry !== item));
      } else if (plus) {
        item.qty = Math.min(variant?.stock || item.qty + 1, item.qty + 1);
        writeCart(cart);
      } else if (minus) {
        item.qty = Math.max(1, item.qty - 1);
        writeCart(cart);
      }
      renderCart();
    }, true);

    tbody.addEventListener('change', (event) => {
      if (!event.target.matches('.variant-select')) return;
      event.stopImmediatePropagation();
      const row = event.target.closest('tr[data-cart-id]');
      const cart = normalizedCart();
      const item = cart.find((entry) => String(entry.id) === row.dataset.cartId && String(entry.variant_id || '') === row.dataset.variantId);
      const product = item && PRODUCT_BY_ID.get(String(item.id));
      const variant = product?.variants?.find((entry) => String(entry.id) === String(event.target.value));
      if (!item || !variant || variant.stock <= 0) return renderCart();
      const duplicate = cart.find((entry) => entry !== item && String(entry.id) === String(item.id) && String(entry.variant_id) === String(variant.id));
      if (duplicate) {
        duplicate.qty = Math.min(variant.stock, duplicate.qty + item.qty);
        cart.splice(cart.indexOf(item), 1);
      } else {
        item.variant = variant.name;
        item.variant_id = variant.id;
        item.qty = Math.min(item.qty, variant.stock);
      }
      writeCart(cart);
      renderCart();
    }, true);

    document.getElementById('clearCart')?.addEventListener('click', () => setTimeout(renderCart, 0));
    document.getElementById('cartCouponApply')?.addEventListener('click', () => setTimeout(() => updateCartTotals(), 0));
    document.getElementById('cartCouponInput')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') setTimeout(() => updateCartTotals(), 0);
    });
  }

  function renderCheckout() {
    const wrap = document.getElementById('checkoutItems');
    if (!wrap) return;
    const cart = normalizedCart();
    wrap.innerHTML = cart.map((item) => {
      const product = PRODUCT_BY_ID.get(String(item.id));
      if (!product) return '';
      const variant = variantFor(product, item);
      const price = unitPrice(product, item);
      return `<div class="order-item"><img src="${escapeHTML(product.img || product.image_url)}" alt="${escapeHTML(product.name)}"><div><strong>${escapeHTML(product.name)}</strong><br><span class="muted">${escapeHTML(variant?.name || '')} · Qty: ${item.qty}</span></div><span class="price">${money(price * item.qty)}</span></div>`;
    }).join('');
    const count = cart.reduce((sum, item) => sum + item.qty, 0);
    ['checkoutItemCount', 'checkoutSummaryCount'].forEach((id) => {
      const node = document.getElementById(id);
      if (node) node.textContent = String(count);
    });
    updateCheckoutTotals(cart);

    const unavailable = cart.some((item) => {
      const product = PRODUCT_BY_ID.get(String(item.id));
      const variant = variantFor(product, item);
      return !variant || variant.stock < item.qty;
    });
    const placeOrder = document.getElementById('placeOrder');
    if (placeOrder) {
      placeOrder.disabled = unavailable || !cart.length;
      placeOrder.title = unavailable ? 'One or more selected variants are out of stock.' : '';
    }
  }

  function updateCheckoutTotals(cart = normalizedCart()) {
    if (!document.getElementById('checkoutSubtotal')) return;
    const subtotal = cart.reduce((sum, item) => {
      const product = PRODUCT_BY_ID.get(String(item.id));
      return sum + (product ? unitPrice(product, item) * item.qty : 0);
    }, 0);
    const selected = document.querySelector('.option[data-delivery] input:checked')?.closest('.option') || document.querySelector('.option[data-delivery].active');
    const shipping = Number(selected?.dataset.charge || 60);
    const outside = selected?.dataset.delivery === 'outside';
    const discount = couponDiscount(subtotal);
    const subtotalNode = document.getElementById('checkoutSubtotal');
    const shippingNode = document.getElementById('shippingCharge');
    const shippingLabel = document.getElementById('shippingLabel');
    const grandNode = document.getElementById('checkoutGrand');
    if (subtotalNode) subtotalNode.textContent = money(subtotal);
    if (shippingNode) shippingNode.textContent = money(shipping);
    if (shippingLabel) shippingLabel.textContent = `Shipping Charge (${outside ? 'Outside Dhaka' : 'Inside Dhaka'})`;
    if (grandNode) grandNode.textContent = money(subtotal - discount + shipping);
    const discountRow = document.getElementById('checkoutDiscountRow');
    if (discountRow) discountRow.hidden = !discount;
    const discountNode = document.getElementById('checkoutDiscount');
    if (discountNode) discountNode.textContent = `- ${money(discount)}`;
  }

  function initCheckout() {
    if (!document.getElementById('checkoutItems')) return;
    renderCheckout();
    document.querySelectorAll('.option[data-delivery]').forEach((option) => option.addEventListener('click', () => setTimeout(() => updateCheckoutTotals(), 0)));
    document.getElementById('checkoutCouponApply')?.addEventListener('click', () => setTimeout(() => updateCheckoutTotals(), 0));
    document.getElementById('checkoutCouponInput')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') setTimeout(() => updateCheckoutTotals(), 0);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initProductDetail();
    initListing();
    initCart();
    initCheckout();
    updateCartCount(normalizedCart());
  });
})();
