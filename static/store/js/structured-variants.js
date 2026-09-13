(() => {
  const storeNode = document.getElementById('store-data');
  const routesNode = document.getElementById('store-routes');
  if (!storeNode) return;

  const DATA = JSON.parse(storeNode.textContent || '{}');
  const ROUTES = routesNode ? JSON.parse(routesNode.textContent || '{}') : {};
  const currentId = DATA.current_product;
  if (!currentId) return;
  const product = (DATA.products || []).find((row) => String(row.id) === String(currentId));
  if (!product || !(product.options || []).length) return;

  const money = (value) => `৳ ${Math.max(0, Number(value) || 0).toLocaleString('en-BD')}`;
  const variants = product.variants || [];
  const options = product.options || [];
  const variantById = new Map(variants.map((variant) => [String(variant.id), variant]));
  const defaultVariant = variants.find((variant) => variant.is_default) || variants[0] || null;
  const selected = new Map();
  (defaultVariant?.values || []).forEach((row) => selected.set(String(row.attribute_id), String(row.value_id)));

  const host = document.querySelector('.swatches');
  const title = document.querySelector('.variant-title');
  const currentPrice = document.querySelector('.product-price .current');
  const regularPrice = document.querySelector('.product-price .old-price');
  const stockNode = document.querySelector('.product-price .stock');
  const mainImage = document.getElementById('mainProductImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');
  const qtyNode = document.getElementById('productQty');
  const oldAdd = document.getElementById('productAddToCart');
  const oldBuy = document.getElementById('productBuyNow');
  if (!host || !oldAdd || !oldBuy) return;

  oldAdd.id = 'structuredProductAddToCart';
  oldBuy.id = 'structuredProductBuyNow';
  oldAdd.classList.remove('add-cart');
  oldBuy.classList.remove('add-cart');
  host.classList.remove('swatches');
  host.classList.add('structured-variant-groups');
  host.innerHTML = '';

  let selectedVariant = null;
  const summary = document.createElement('div');
  summary.className = 'structured-variant-summary';
  host.insertAdjacentElement('afterend', summary);

  const valueMap = new Map();
  options.forEach((option) => (option.values || []).forEach((value) => valueMap.set(String(value.id), { option, value })));

  const variantValueMap = (variant) => {
    const map = new Map();
    (variant?.values || []).forEach((row) => map.set(String(row.attribute_id), String(row.value_id)));
    return map;
  };

  const matchesSelection = (variant, overrideAttributeId = null, overrideValueId = null) => {
    const map = variantValueMap(variant);
    for (const option of options) {
      const attrId = String(option.id);
      const wanted = attrId === String(overrideAttributeId) ? String(overrideValueId) : selected.get(attrId);
      if (wanted && map.get(attrId) !== wanted) return false;
    }
    return true;
  };

  const exactVariant = () => {
    if (selected.size !== options.length) return null;
    return variants.find((variant) => {
      const map = variantValueMap(variant);
      return options.every((option) => map.get(String(option.id)) === selected.get(String(option.id)));
    }) || null;
  };

  const writeCart = (variant, qty) => {
    let cart = [];
    try { cart = JSON.parse(localStorage.getItem('nu_cart') || '[]') || []; } catch (_) { cart = []; }
    const safeQty = Math.max(1, Math.min(Number(qty) || 1, Number(variant.stock) || 1));
    const existing = cart.find((item) => String(item.id) === String(product.id) && String(item.variant_id) === String(variant.id));
    if (existing) existing.qty = Math.min(Number(variant.stock) || existing.qty + safeQty, (Number(existing.qty) || 0) + safeQty);
    else cart.push({ id: product.id, qty: safeQty, variant: variant.name, variant_id: variant.id });
    localStorage.setItem('nu_cart', JSON.stringify(cart));
    const badge = document.getElementById('cartCount');
    if (badge) badge.textContent = String(cart.reduce((sum, item) => sum + (Number(item.qty) || 1), 0));
  };

  const imageUrlsForSelection = () => {
    const groups = product.image_groups || {};
    for (const option of options) {
      const valueId = selected.get(String(option.id));
      const urls = groups[String(valueId)] || [];
      if (urls.length) return urls;
    }
    return product.images || [product.image_url].filter(Boolean);
  };

  const renderImages = () => {
    const urls = imageUrlsForSelection();
    if (!urls.length) return;
    if (mainImage) mainImage.src = urls[0];
    if (!thumbHost) return;
    const existingThumbs = [...thumbHost.querySelectorAll('.thumb')];
    if (!existingThumbs.length) return;
    existingThumbs.forEach((thumb, index) => {
      if (index < urls.length) {
        thumb.hidden = false;
        const image = thumb.querySelector('img');
        if (image) image.src = urls[index];
        thumb.classList.toggle('active', index === 0);
        thumb.onclick = () => {
          existingThumbs.forEach((node) => node.classList.remove('active'));
          thumb.classList.add('active');
          if (mainImage) mainImage.src = urls[index];
        };
      } else {
        thumb.hidden = true;
      }
    });
  };

  const updateAvailability = () => {
    host.querySelectorAll('[data-structured-value]').forEach((control) => {
      const attrId = control.dataset.attributeId;
      const valueId = control.dataset.structuredValue;
      const current = selected.get(String(attrId)) === String(valueId);
      const possible = variants.some((variant) => Number(variant.stock) > 0 && matchesSelection(variant, attrId, valueId));
      control.disabled = !possible && !current;
      control.classList.toggle('active', current);
      control.setAttribute('aria-pressed', current ? 'true' : 'false');
    });
    host.querySelectorAll('select[data-structured-attribute]').forEach((select) => {
      const attrId = select.dataset.structuredAttribute;
      [...select.options].forEach((optionNode) => {
        if (!optionNode.value) return;
        const current = selected.get(String(attrId)) === String(optionNode.value);
        const possible = variants.some((variant) => Number(variant.stock) > 0 && matchesSelection(variant, attrId, optionNode.value));
        optionNode.disabled = !possible && !current;
      });
    });
  };

  const renderState = () => {
    selectedVariant = exactVariant();
    updateAvailability();
    const chosenLabels = options.map((option) => {
      const valueId = selected.get(String(option.id));
      const row = (option.values || []).find((value) => String(value.id) === String(valueId));
      return row ? `${option.name}: ${row.value}` : `${option.name}: —`;
    });
    summary.innerHTML = chosenLabels.map((label) => `<span>${label.replace(/</g, '&lt;')}</span>`).join('<span class="variant-summary-sep">•</span>');

    if (!selectedVariant) {
      summary.classList.remove('is-ready');
      summary.classList.add('is-invalid');
      summary.insertAdjacentHTML('beforeend', '<strong>Select a valid complete combination.</strong>');
      oldAdd.disabled = true;
      oldBuy.disabled = true;
      return;
    }

    summary.classList.remove('is-invalid');
    summary.classList.add('is-ready');
    summary.insertAdjacentHTML('beforeend', `<strong>SKU: ${String(selectedVariant.sku).replace(/</g, '&lt;')}</strong>`);
    if (title) title.textContent = selectedVariant.name;
    if (currentPrice) currentPrice.textContent = money(selectedVariant.price);
    if (regularPrice) {
      regularPrice.textContent = money(selectedVariant.regular_price);
      regularPrice.hidden = Number(selectedVariant.regular_price) <= Number(selectedVariant.price);
    }
    if (stockNode) {
      stockNode.textContent = Number(selectedVariant.stock) > 0 ? `● In Stock (${selectedVariant.stock})` : '● Out of Stock';
      stockNode.classList.toggle('out', Number(selectedVariant.stock) <= 0);
    }
    const unavailable = Number(selectedVariant.stock) <= 0;
    oldAdd.disabled = unavailable;
    oldBuy.disabled = unavailable;
    if (qtyNode) qtyNode.textContent = String(unavailable ? 1 : Math.min(Number(qtyNode.textContent) || 1, Number(selectedVariant.stock)));
    renderImages();
  };

  options.forEach((option) => {
    const group = document.createElement('div');
    group.className = 'structured-variant-group';
    const head = document.createElement('div');
    head.className = 'structured-variant-head';
    const label = document.createElement('strong');
    label.textContent = option.name;
    const currentLabel = document.createElement('span');
    head.append(label, currentLabel);
    group.appendChild(head);

    const values = option.values || [];
    const updateLabel = () => {
      const value = values.find((row) => String(row.id) === selected.get(String(option.id)));
      currentLabel.textContent = value ? value.value : 'Choose one';
    };

    if (option.display_type === 'dropdown') {
      const select = document.createElement('select');
      select.className = 'structured-variant-select';
      select.dataset.structuredAttribute = option.id;
      select.innerHTML = '<option value="">Choose one</option>';
      values.forEach((value) => {
        const row = document.createElement('option');
        row.value = value.id;
        row.textContent = value.value;
        row.selected = selected.get(String(option.id)) === String(value.id);
        select.appendChild(row);
      });
      select.addEventListener('change', () => {
        if (select.value) selected.set(String(option.id), String(select.value));
        else selected.delete(String(option.id));
        updateLabel();
        renderState();
      });
      group.appendChild(select);
    } else {
      const list = document.createElement('div');
      list.className = 'structured-variant-options';
      values.forEach((value) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'structured-variant-option';
        button.dataset.structuredValue = value.id;
        button.dataset.attributeId = option.id;
        if (option.display_type === 'swatch' && (value.color_hex || value.symbol)) {
          const swatch = document.createElement('i');
          swatch.className = 'structured-variant-swatch';
          if (value.color_hex) swatch.style.background = value.color_hex;
          else swatch.textContent = value.symbol;
          button.appendChild(swatch);
        }
        const text = document.createElement('span');
        text.textContent = value.value;
        button.appendChild(text);
        button.addEventListener('click', () => {
          selected.set(String(option.id), String(value.id));
          updateLabel();
          renderState();
        });
        list.appendChild(button);
      });
      group.appendChild(list);
    }
    updateLabel();
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
    if (plus) qtyNode.textContent = String(Math.min(Number(selectedVariant.stock) || 1, current + 1));
    if (minus) qtyNode.textContent = String(Math.max(1, current - 1));
  }, true);

  renderState();
})();
