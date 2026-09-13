(() => {
  const storeNode = document.getElementById('store-data');
  const routesNode = document.getElementById('store-routes');
  if (!storeNode) return;

  const DATA = JSON.parse(storeNode.textContent || '{}');
  const ROUTES = routesNode ? JSON.parse(routesNode.textContent || '{}') : {};
  const currentId = DATA.current_product;
  if (!currentId) return;

  const product = (DATA.products || []).find((row) => String(row.id) === String(currentId));
  const variants = product?.variants || [];
  const options = product?.options || [];
  if (!product || !options.length || !variants.length) return;

  const host = document.querySelector('.swatches');
  const title = document.querySelector('.variant-title');
  const currentPrice = document.querySelector('.product-price .current');
  const regularPrice = document.querySelector('.product-price .old-price');
  const stockNode = document.querySelector('.product-price .stock');
  const mainImage = document.getElementById('mainProductImage');
  const lightboxImage = document.getElementById('productLightboxImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');
  const qtyNode = document.getElementById('productQty');
  const oldAdd = document.getElementById('productAddToCart');
  const oldBuy = document.getElementById('productBuyNow');
  if (!host || !oldAdd || !oldBuy) return;

  const money = (value) => `৳ ${Math.max(0, Number(value) || 0).toLocaleString('en-BD')}`;
  const optionIndex = new Map(options.map((option, index) => [String(option.id), index]));
  const variantMaps = new Map();
  const selected = new Map();
  const groupViews = [];

  const mapFor = (variant) => {
    const key = String(variant.id);
    if (!variantMaps.has(key)) {
      const map = new Map();
      (variant.values || []).forEach((row) => map.set(String(row.attribute_id), String(row.value_id)));
      variantMaps.set(key, map);
    }
    return variantMaps.get(key);
  };

  const firstPreferredVariant = () => {
    const defaultVariant = variants.find((variant) => variant.is_default);
    if (defaultVariant && Number(defaultVariant.stock) > 0) return defaultVariant;
    return variants.find((variant) => Number(variant.stock) > 0) || defaultVariant || variants[0] || null;
  };

  const initialVariant = firstPreferredVariant();
  (initialVariant?.values || []).forEach((row) => selected.set(String(row.attribute_id), String(row.value_id)));

  oldAdd.id = 'structuredProductAddToCart';
  oldBuy.id = 'structuredProductBuyNow';
  oldAdd.classList.remove('add-cart');
  oldBuy.classList.remove('add-cart');
  host.classList.remove('swatches');
  host.classList.add('structured-variant-groups');
  host.setAttribute('aria-label', 'Product options');
  host.innerHTML = '';

  let selectedVariant = null;
  const summary = document.createElement('div');
  summary.className = 'structured-variant-summary';
  summary.setAttribute('aria-live', 'polite');
  host.insertAdjacentElement('afterend', summary);

  const priceRow = currentPrice?.parentElement || null;
  let discountBadge = priceRow?.querySelector('.structured-variant-discount') || null;
  if (!discountBadge && priceRow) {
    discountBadge = document.createElement('span');
    discountBadge.className = 'structured-variant-discount';
    discountBadge.hidden = true;
    if (regularPrice) regularPrice.insertAdjacentElement('afterend', discountBadge);
    else currentPrice?.insertAdjacentElement('afterend', discountBadge);
  }

  const matchesConstraints = (variant, constraints) => {
    const map = mapFor(variant);
    for (const [attributeId, valueId] of constraints.entries()) {
      if (map.get(String(attributeId)) !== String(valueId)) return false;
    }
    return true;
  };

  const prefixConstraints = (index, currentValueId = null) => {
    const constraints = new Map();
    options.forEach((option, optionPosition) => {
      if (optionPosition >= index) return;
      const valueId = selected.get(String(option.id));
      if (valueId) constraints.set(String(option.id), String(valueId));
    });
    if (currentValueId != null) {
      constraints.set(String(options[index].id), String(currentValueId));
    }
    return constraints;
  };

  const stateForValue = (index, valueId) => {
    const constraints = prefixConstraints(index, valueId);
    const compatible = variants.filter((variant) => matchesConstraints(variant, constraints));
    return {
      exists: compatible.length > 0,
      available: compatible.some((variant) => Number(variant.stock) > 0),
    };
  };

  const exactVariant = () => {
    if (options.some((option) => !selected.get(String(option.id)))) return null;
    return variants.find((variant) => {
      const map = mapFor(variant);
      return options.every((option) => map.get(String(option.id)) === selected.get(String(option.id)));
    }) || null;
  };

  const bestCandidateFor = (index, valueId) => {
    const constraints = prefixConstraints(index, valueId);
    let candidates = variants.filter(
      (variant) => Number(variant.stock) > 0 && matchesConstraints(variant, constraints),
    );
    if (!candidates.length) {
      candidates = variants.filter((variant) => matchesConstraints(variant, constraints));
    }
    if (!candidates.length) return null;

    const downstream = options.slice(index + 1);
    return [...candidates].sort((a, b) => {
      const aMap = mapFor(a);
      const bMap = mapFor(b);
      const score = (variant, map) => {
        let value = variant.is_default ? 0.25 : 0;
        downstream.forEach((option) => {
          const current = selected.get(String(option.id));
          if (current && map.get(String(option.id)) === current) value += 1;
        });
        if (Number(variant.stock) > 0) value += 10;
        return value;
      };
      const difference = score(b, bMap) - score(a, aMap);
      if (difference) return difference;
      return Number(a.id) - Number(b.id);
    })[0];
  };

  const applyCandidateDownstream = (index, candidate) => {
    const map = candidate ? mapFor(candidate) : null;
    options.forEach((option, optionPosition) => {
      if (optionPosition <= index) return;
      const attributeId = String(option.id);
      const valueId = map?.get(attributeId);
      if (valueId) selected.set(attributeId, String(valueId));
      else selected.delete(attributeId);
    });
  };

  const chooseValue = (index, valueId) => {
    const option = options[index];
    if (!option) return;
    const state = stateForValue(index, valueId);
    if (!state.available && variants.some((variant) => Number(variant.stock) > 0)) return;

    selected.set(String(option.id), String(valueId));
    applyCandidateDownstream(index, bestCandidateFor(index, valueId));
    renderState();
  };

  const writeCart = (variant, qty) => {
    let cart = [];
    try {
      cart = JSON.parse(localStorage.getItem('nu_cart') || '[]') || [];
    } catch (_) {
      cart = [];
    }

    const stock = Math.max(0, Number(variant.stock) || 0);
    const safeQty = Math.max(1, Math.min(Number(qty) || 1, stock || 1));
    const existing = cart.find(
      (item) => String(item.id) === String(product.id) && String(item.variant_id) === String(variant.id),
    );
    if (existing) existing.qty = Math.min(stock || safeQty, (Number(existing.qty) || 0) + safeQty);
    else cart.push({ id: product.id, qty: safeQty, variant: variant.name, variant_id: variant.id });

    localStorage.setItem('nu_cart', JSON.stringify(cart));
    const badge = document.getElementById('cartCount');
    if (badge) badge.textContent = String(cart.reduce((sum, item) => sum + (Number(item.qty) || 1), 0));
  };

  const imageUrlsForSelection = () => {
    const groups = product.image_groups || {};
    const preferred = [
      ...options.filter((option) => option.display_type === 'swatch'),
      ...options.filter((option) => option.display_type !== 'swatch'),
    ];
    for (const option of preferred) {
      const valueId = selected.get(String(option.id));
      const urls = groups[String(valueId)] || [];
      if (urls.length) return urls;
    }
    return (product.images || [product.image_url]).filter(Boolean);
  };

  const setMainImage = (url, index = 0) => {
    if (!url) return;
    if (mainImage) mainImage.src = url;
    if (lightboxImage) lightboxImage.src = url;
    if (thumbHost) {
      [...thumbHost.querySelectorAll('.thumb')].forEach((thumb, thumbIndex) => {
        thumb.classList.toggle('active', thumbIndex === index);
      });
    }
  };

  const renderImages = () => {
    const urls = imageUrlsForSelection();
    if (!urls.length) return;
    setMainImage(urls[0], 0);
    if (!thumbHost) return;

    thumbHost.replaceChildren();
    urls.forEach((url, index) => {
      const thumb = document.createElement('button');
      thumb.type = 'button';
      thumb.className = `thumb${index === 0 ? ' active' : ''}`;
      thumb.setAttribute('aria-label', `View product image ${index + 1}`);

      const image = document.createElement('img');
      image.src = url;
      image.alt = `${product.short_name || product.name} thumbnail ${index + 1}`;
      thumb.appendChild(image);
      thumb.addEventListener('click', () => setMainImage(url, index));
      thumbHost.appendChild(thumb);
    });
  };

  const updateGroupLabels = () => {
    groupViews.forEach(({ option, currentLabel, select }) => {
      const valueId = selected.get(String(option.id));
      const value = (option.values || []).find((row) => String(row.id) === String(valueId));
      currentLabel.textContent = value ? value.value : 'Choose one';
      if (select) select.value = value ? String(value.id) : '';
    });
  };

  const updateAvailability = () => {
    host.querySelectorAll('[data-structured-value]').forEach((control) => {
      const index = Number(control.dataset.optionIndex);
      const valueId = control.dataset.structuredValue;
      const attributeId = String(options[index]?.id || '');
      const current = selected.get(attributeId) === String(valueId);
      const state = stateForValue(index, valueId);

      control.disabled = !state.available;
      control.classList.toggle('active', current);
      control.classList.toggle('is-unavailable', !state.exists);
      control.classList.toggle('is-out-of-stock', state.exists && !state.available);
      control.setAttribute('aria-pressed', current ? 'true' : 'false');
      control.title = !state.exists
        ? 'Not available with the selected options'
        : (!state.available ? 'Out of stock' : '');
    });

    host.querySelectorAll('select[data-structured-attribute]').forEach((select) => {
      const index = Number(select.dataset.optionIndex);
      let hasAvailable = false;
      [...select.options].forEach((optionNode) => {
        if (!optionNode.value) return;
        const state = stateForValue(index, optionNode.value);
        optionNode.disabled = !state.available;
        optionNode.textContent = `${optionNode.dataset.label || optionNode.textContent}${
          !state.exists ? ' — Not available' : (!state.available ? ' — Out of stock' : '')
        }`;
        if (state.available) hasAvailable = true;
      });
      select.disabled = !hasAvailable && variants.some((variant) => Number(variant.stock) > 0);
    });
  };

  const renderSummary = () => {
    summary.replaceChildren();
    const selectionText = options.map((option) => {
      const valueId = selected.get(String(option.id));
      const value = (option.values || []).find((row) => String(row.id) === String(valueId));
      return value?.value || '—';
    }).join(' / ');

    const selectedText = document.createElement('span');
    selectedText.className = 'structured-variant-picked';
    selectedText.textContent = `Selected: ${selectionText}`;
    summary.appendChild(selectedText);

    if (!selectedVariant) {
      const message = document.createElement('strong');
      message.textContent = 'Select an available combination.';
      summary.appendChild(message);
      summary.classList.remove('is-ready');
      summary.classList.add('is-invalid');
      return;
    }

    const sku = document.createElement('strong');
    sku.textContent = `SKU: ${selectedVariant.sku}`;
    summary.appendChild(sku);
    summary.classList.remove('is-invalid');
    summary.classList.add('is-ready');
  };

  const renderPriceAndStock = () => {
    if (!selectedVariant) {
      oldAdd.disabled = true;
      oldBuy.disabled = true;
      return;
    }

    const price = Number(selectedVariant.price) || 0;
    const regular = Number(selectedVariant.regular_price) || 0;
    const stock = Math.max(0, Number(selectedVariant.stock) || 0);

    if (title) title.textContent = `Selected Variant: ${selectedVariant.name}`;
    if (currentPrice) currentPrice.textContent = money(price);
    if (regularPrice) {
      regularPrice.textContent = money(regular);
      regularPrice.hidden = regular <= price;
    }
    if (discountBadge) {
      const discount = regular > price && regular > 0 ? Math.round(((regular - price) / regular) * 100) : 0;
      discountBadge.textContent = discount > 0 ? `${discount}% OFF` : '';
      discountBadge.hidden = discount <= 0;
    }
    if (stockNode) {
      stockNode.textContent = stock > 0 ? `● In Stock (${stock})` : '● Out of Stock';
      stockNode.classList.toggle('out', stock <= 0);
    }

    const unavailable = stock <= 0;
    oldAdd.disabled = unavailable;
    oldBuy.disabled = unavailable;
    if (qtyNode) {
      const current = Math.max(1, Number(qtyNode.textContent) || 1);
      qtyNode.textContent = String(unavailable ? 1 : Math.min(current, stock));
    }
  };

  const renderState = () => {
    selectedVariant = exactVariant();
    updateGroupLabels();
    updateAvailability();
    renderSummary();
    renderPriceAndStock();
    renderImages();
  };

  options.forEach((option, index) => {
    const group = document.createElement('div');
    group.className = 'structured-variant-group';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', option.name);

    const head = document.createElement('div');
    head.className = 'structured-variant-head';
    const label = document.createElement('strong');
    label.textContent = option.name;
    const currentLabel = document.createElement('span');
    currentLabel.className = 'structured-variant-current';
    head.append(label, currentLabel);
    group.appendChild(head);

    const values = option.values || [];
    let select = null;

    if (option.display_type === 'dropdown') {
      select = document.createElement('select');
      select.className = 'structured-variant-select';
      select.dataset.structuredAttribute = option.id;
      select.dataset.optionIndex = String(index);

      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Choose one';
      select.appendChild(placeholder);

      values.forEach((value) => {
        const row = document.createElement('option');
        row.value = String(value.id);
        row.dataset.label = value.value;
        row.textContent = value.value;
        select.appendChild(row);
      });

      select.addEventListener('change', () => {
        if (!select.value) return;
        chooseValue(index, select.value);
      });
      group.appendChild(select);
    } else {
      const list = document.createElement('div');
      list.className = 'structured-variant-options';
      values.forEach((value) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'structured-variant-option';
        button.dataset.structuredValue = String(value.id);
        button.dataset.attributeId = String(option.id);
        button.dataset.optionIndex = String(index);

        if (option.display_type === 'swatch') {
          const swatch = document.createElement('i');
          swatch.className = 'structured-variant-swatch';
          if (value.color_hex) swatch.style.background = value.color_hex;
          else if (value.symbol) swatch.textContent = value.symbol;
          button.appendChild(swatch);
        }

        const text = document.createElement('span');
        text.textContent = value.value;
        button.appendChild(text);
        button.addEventListener('click', () => chooseValue(index, value.id));
        list.appendChild(button);
      });
      group.appendChild(list);
    }

    groupViews.push({ option, currentLabel, select });
    host.appendChild(group);
  });

  document.addEventListener('click', (event) => {
    const target = event.target.closest('#structuredProductAddToCart, #structuredProductBuyNow');
    if (!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!selectedVariant || Number(selectedVariant.stock) <= 0) return;

    const qty = Number(qtyNode?.textContent || 1);
    writeCart(selectedVariant, qty);
    if (target.id === 'structuredProductBuyNow') {
      if (ROUTES.checkout) window.location.href = ROUTES.checkout;
      return;
    }

    const previous = target.innerHTML;
    target.textContent = `✓ Added${qty > 1 ? ` × ${qty}` : ''}`;
    setTimeout(() => { target.innerHTML = previous; }, 900);
  }, true);

  document.addEventListener('click', (event) => {
    const plus = event.target.closest('#productQtyPlus');
    const minus = event.target.closest('#productQtyMinus');
    if (!plus && !minus) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!qtyNode || !selectedVariant) return;

    const current = Number(qtyNode.textContent) || 1;
    const stock = Math.max(0, Number(selectedVariant.stock) || 0);
    if (plus && stock > 0) qtyNode.textContent = String(Math.min(stock, current + 1));
    if (minus) qtyNode.textContent = String(Math.max(1, current - 1));
  }, true);

  renderState();
})();
