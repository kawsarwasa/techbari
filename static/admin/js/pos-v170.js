(() => {
  const root = document.querySelector('[data-pos-real="1"]');
  const dataNode = document.getElementById('pos-real-data');
  if (!root || !dataNode) return;

  const DATA = JSON.parse(dataNode.textContent || '{}');
  const products = DATA.products || [];
  let held = DATA.held || [];
  let cart = [];
  let selectedCategory = 'All';
  let paymentMethod = 'cash';
  let activeHoldId = null;

  const $ = (s) => root.querySelector(s);
  const $$ = (s) => [...root.querySelectorAll(s)];
  const money = (n) => `৳ ${Number(n || 0).toLocaleString('en-BD', {maximumFractionDigits: 2})}`;
  const csrf = root.querySelector('input[name=csrfmiddlewaretoken]')?.value || '';

  function productByVariant(id) {
    return products.find((p) => String(p.variant_id) === String(id));
  }

  function subtotal() {
    return cart.reduce((sum, item) => sum + Number(item.price) * Number(item.qty), 0);
  }

  function discountAmount() {
    const raw = Math.max(0, Number($('[data-real-pos-discount]')?.value || 0));
    const sub = subtotal();
    return $('[data-real-pos-discount-type]')?.value === 'percent'
      ? Math.min(sub, sub * Math.min(raw, 100) / 100)
      : Math.min(sub, raw);
  }

  function totals() {
    const sub = subtotal();
    const discount = discountAmount();
    return {subtotal: sub, discount, total: Math.max(0, sub - discount)};
  }

  function renderProducts() {
    const q = ($('[data-real-pos-search]')?.value || '').trim().toLowerCase();
    const sort = $('[data-real-pos-sort]')?.value || 'name';
    let rows = products.filter((p) => {
      if (selectedCategory !== 'All' && p.category !== selectedCategory) return false;
      if (!q) return true;
      return `${p.name} ${p.variant} ${p.sku} ${p.barcode} ${p.brand} ${p.category}`.toLowerCase().includes(q);
    });
    const sorters = {
      name: (a, b) => `${a.name} ${a.variant}`.localeCompare(`${b.name} ${b.variant}`),
      'price-low': (a, b) => Number(a.price) - Number(b.price),
      'price-high': (a, b) => Number(b.price) - Number(a.price),
      stock: (a, b) => Number(b.stock) - Number(a.stock),
    };
    rows = [...rows].sort(sorters[sort] || sorters.name);
    $('[data-real-pos-grid]').innerHTML = rows.map((p) => `
      <article class="pos-ref-product">
        <div class="pos-img-wrap"><img src="${p.image}" alt=""></div>
        <div><h3>${p.name}</h3><div class="pos-cat">${p.variant} · ${p.sku}</div><div class="pos-stock">Available: <strong>${p.stock}</strong>${p.barcode ? ` · ${p.barcode}` : ''}</div><div class="pos-price">${money(p.price)}</div></div>
        <button class="pos-add-btn" type="button" data-real-pos-add="${p.variant_id}" ${Number(p.stock) <= 0 ? 'disabled' : ''}>Add to Cart</button>
      </article>`).join('') || '<div class="empty-state">No matching stock found in this warehouse.</div>';
  }

  function renderCart() {
    $('[data-real-pos-cart]').innerHTML = cart.length ? cart.map((item) => `
      <div class="pos-ref-cart-row">
        <img src="${item.image}" alt=""><div class="pos-cart-info"><div class="pos-cart-line1"><strong>${item.name}</strong><strong>${money(Number(item.price) * item.qty)}</strong></div>
        <div class="pos-cart-unit">${item.variant} · ${item.sku} · ${money(item.price)}</div>
        <div class="pos-qty"><button type="button" data-real-pos-minus="${item.variant_id}">−</button><span>${item.qty}</span><button type="button" data-real-pos-plus="${item.variant_id}">+</button></div></div>
        <button class="pos-remove" type="button" data-real-pos-remove="${item.variant_id}">×</button>
      </div>`).join('') : '<div class="empty-state">No products in current order.</div>';
    const t = totals();
    $('[data-real-pos-subtotal]').textContent = money(t.subtotal);
    $('[data-real-pos-discount-value]').textContent = `- ${money(t.discount)}`;
    $('[data-real-pos-total]').textContent = money(t.total);
    $('[data-real-pos-complete-total]').textContent = money(t.total);
    $('[data-real-pos-discount-unit]').textContent = $('[data-real-pos-discount-type]').value === 'percent' ? '%' : '৳';
    const tendered = $('[data-real-pos-tendered]');
    if (tendered && (!tendered.value || paymentMethod !== 'cash')) tendered.value = t.total.toFixed(2);
  }

  function feedback(text, ok = false) {
    const box = $('[data-real-pos-feedback]');
    if (!box) return;
    box.className = `coupon-feedback ${ok ? 'success' : 'error'}`;
    box.textContent = text || '';
  }

  function renderHeld() {
    const body = $('[data-real-pos-held-body]');
    if (!body) return;
    body.innerHTML = held.map((order) => `<tr><td><strong>${order.order_number}</strong></td><td>${order.customer_name}</td><td>${order.items.reduce((s, i) => s + i.qty, 0)}</td><td>${money(order.total)}</td><td>${new Date(order.created_at).toLocaleString()}</td><td><button class="btn" type="button" data-real-pos-resume="${order.id}">Resume</button> <button class="btn" type="button" data-real-pos-discard="${order.id}">Discard</button></td></tr>`).join('') || '<tr><td colspan="6"><div class="empty-state">No held POS orders.</div></td></tr>';
  }

  function payload(action) {
    const t = totals();
    return {
      action,
      order_id: activeHoldId,
      warehouse_id: Number(DATA.warehouse_id),
      customer_id: $('[data-real-pos-customer]').value || null,
      items: cart.map((i) => ({variant_id: i.variant_id, qty: i.qty})),
      discount_amount: t.discount.toFixed(2),
      note: $('[data-real-pos-note]').value || '',
      payment_method: paymentMethod,
      payment_reference: $('[data-real-pos-reference]').value || '',
      tendered_amount: $('[data-real-pos-tendered]').value || t.total.toFixed(2),
    };
  }

  async function action(body) {
    const response = await fetch('/dashboard/pos/action/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({ok: false, error: 'Invalid server response.'}));
    if (!response.ok || !data.ok) throw new Error(data.error || 'POS request failed.');
    return data;
  }

  function clearOrder() {
    cart = [];
    activeHoldId = null;
    $('[data-real-pos-customer]').value = '';
    $('[data-real-pos-discount]').value = '0';
    $('[data-real-pos-note]').value = '';
    $('[data-real-pos-reference]').value = '';
    renderCart();
  }

  $('[data-real-pos-search]')?.addEventListener('input', renderProducts);
  $('[data-real-pos-sort]')?.addEventListener('change', renderProducts);
  $('[data-real-pos-barcode]')?.addEventListener('click', () => $('[data-real-pos-search]')?.focus());
  $('[data-real-pos-discount]')?.addEventListener('input', renderCart);
  $('[data-real-pos-discount-type]')?.addEventListener('change', renderCart);
  $('[data-real-pos-clear]')?.addEventListener('click', clearOrder);
  $('[data-real-pos-held-toggle]')?.addEventListener('click', () => {
    const panel = $('[data-real-pos-held-panel]');
    panel.hidden = !panel.hidden;
  });

  root.addEventListener('click', async (event) => {
    const category = event.target.closest('[data-real-pos-category]');
    if (category) {
      selectedCategory = category.dataset.realPosCategory;
      $$('[data-real-pos-category]').forEach((node) => node.classList.toggle('active', node === category));
      renderProducts();
      return;
    }
    const add = event.target.closest('[data-real-pos-add]');
    if (add) {
      const p = productByVariant(add.dataset.realPosAdd);
      if (!p || Number(p.stock) <= 0) return;
      const existing = cart.find((i) => String(i.variant_id) === String(p.variant_id));
      if (existing) {
        if (existing.qty >= Number(p.stock)) return feedback(`Only ${p.stock} unit(s) available for ${p.sku}.`);
        existing.qty += 1;
      } else cart.push({...p, qty: 1});
      renderCart(); feedback(''); return;
    }
    const plus = event.target.closest('[data-real-pos-plus]');
    if (plus) {
      const item = cart.find((i) => String(i.variant_id) === plus.dataset.realPosPlus);
      if (item && item.qty < Number(item.stock)) item.qty += 1;
      renderCart(); return;
    }
    const minus = event.target.closest('[data-real-pos-minus]');
    if (minus) {
      const item = cart.find((i) => String(i.variant_id) === minus.dataset.realPosMinus);
      if (item) { item.qty -= 1; if (item.qty <= 0) cart = cart.filter((i) => i !== item); }
      renderCart(); return;
    }
    const remove = event.target.closest('[data-real-pos-remove]');
    if (remove) { cart = cart.filter((i) => String(i.variant_id) !== remove.dataset.realPosRemove); renderCart(); return; }
    const pay = event.target.closest('[data-real-pos-payment]');
    if (pay) {
      paymentMethod = pay.dataset.realPosPayment;
      $$('[data-real-pos-payment]').forEach((node) => node.classList.toggle('active', node === pay));
      $('[data-real-pos-reference]').required = paymentMethod !== 'cash';
      renderCart(); return;
    }
    const resume = event.target.closest('[data-real-pos-resume]');
    if (resume) {
      const order = held.find((row) => String(row.id) === resume.dataset.realPosResume);
      if (!order) return;
      activeHoldId = order.id;
      cart = order.items.map((row) => ({...productByVariant(row.variant_id), ...row, qty: row.qty})).filter((row) => row.variant_id);
      $('[data-real-pos-customer]').value = order.customer_id || '';
      $('[data-real-pos-discount-type]').value = 'fixed';
      $('[data-real-pos-discount]').value = order.discount_amount || 0;
      $('[data-real-pos-note]').value = order.notes || '';
      renderCart(); feedback(`Resumed ${order.order_number}.`, true); return;
    }
    const discard = event.target.closest('[data-real-pos-discard]');
    if (discard) {
      if (!confirm('Discard this held POS order?')) return;
      try {
        await action({action: 'discard', order_id: Number(discard.dataset.realPosDiscard)});
        held = held.filter((row) => String(row.id) !== discard.dataset.realPosDiscard);
        if (String(activeHoldId) === discard.dataset.realPosDiscard) clearOrder();
        renderHeld(); feedback('Held order discarded.', true);
      } catch (error) { feedback(error.message); }
    }
  });

  $('[data-real-pos-hold]')?.addEventListener('click', async () => {
    if (!cart.length) return feedback('Add products before holding the order.');
    try {
      const result = await action(payload('hold'));
      const order = result.order;
      held = [order, ...held.filter((row) => row.id !== order.id)];
      renderHeld(); clearOrder(); feedback(`${order.order_number} held successfully.`, true);
    } catch (error) { feedback(error.message); }
  });

  $('[data-real-pos-complete]')?.addEventListener('click', async () => {
    if (!cart.length) return feedback('Add products before completing the sale.');
    const button = $('[data-real-pos-complete]');
    button.disabled = true;
    try {
      const result = await action(payload('complete'));
      held = held.filter((row) => row.id !== activeHoldId);
      renderHeld();
      const change = Number(result.change_amount || 0);
      feedback(`Sale ${result.order_number} completed.${change > 0 ? ` Change: ${money(change)}.` : ''}`, true);
      clearOrder();
      window.open(result.receipt_url, '_blank', 'noopener');
      setTimeout(() => location.reload(), 500);
    } catch (error) { feedback(error.message); }
    finally { button.disabled = false; }
  });

  renderProducts(); renderCart(); renderHeld();
})();
