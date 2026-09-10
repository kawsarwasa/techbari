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

  // Bangladesh dependent location selectors.
  // The same hierarchy is also enforced by CheckoutForm on the server.
  const locationsNode = document.getElementById('checkoutBdLocations');
  const divisionSelect = document.getElementById('id_division');
  const districtSelect = document.getElementById('id_district');
  const upazilaSelect = document.getElementById('id_upazila');
  const searchableSelects = new Map();
  let bdLocations = {};

  if (locationsNode) {
    try {
      bdLocations = JSON.parse(locationsNode.textContent || '{}');
    } catch (_) {
      bdLocations = {};
    }
  }

  function normalizeSearch(value) {
    return String(value || '').trim().toLocaleLowerCase();
  }

  function selectedLabel(select) {
    const selected = select && select.options ? select.options[select.selectedIndex] : null;
    return selected && selected.value ? selected.textContent.trim() : '';
  }

  function enhanceSearchableSelect(select) {
    if (!select || searchableSelects.has(select)) return searchableSelects.get(select);

    const wrapper = document.createElement('div');
    wrapper.className = 'tb-searchable-select';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'tb-searchable-select__input';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');

    const menu = document.createElement('div');
    menu.className = 'tb-searchable-select__menu';
    menu.setAttribute('role', 'listbox');
    menu.id = `${select.id}-search-listbox`;
    input.setAttribute('aria-controls', menu.id);

    const chevron = document.createElement('span');
    chevron.className = 'tb-searchable-select__chevron';
    chevron.setAttribute('aria-hidden', 'true');

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(input);
    wrapper.appendChild(chevron);
    wrapper.appendChild(menu);

    select.classList.add('tb-searchable-select__native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    input.id = `${select.id}_search`;
    const label = document.querySelector(`label[for="${select.id}"]`);
    if (label) label.htmlFor = input.id;

    let activeIndex = -1;

    function optionRows(query = '') {
      const needle = normalizeSearch(query);
      return [...select.options].filter((option) => {
        if (!option.value || option.disabled) return false;
        return !needle || normalizeSearch(option.textContent).includes(needle);
      });
    }

    function setActive(index) {
      const rows = [...menu.querySelectorAll('.tb-searchable-select__option')];
      if (!rows.length) {
        activeIndex = -1;
        return;
      }
      activeIndex = Math.max(0, Math.min(index, rows.length - 1));
      rows.forEach((row, rowIndex) => row.classList.toggle('is-active', rowIndex === activeIndex));
      rows[activeIndex].scrollIntoView({ block: 'nearest' });
    }

    function choose(value) {
      const option = [...select.options].find((row) => row.value === value);
      if (!option) return;
      select.value = value;
      input.value = option.textContent.trim();
      select.dispatchEvent(new Event('change', { bubbles: true }));
      close(false);
    }

    function render(query = '') {
      menu.replaceChildren();
      const rows = optionRows(query);
      const currentValue = select.value;

      if (!rows.length) {
        const empty = document.createElement('div');
        empty.className = 'tb-searchable-select__empty';
        empty.textContent = 'No matching option found';
        menu.appendChild(empty);
        activeIndex = -1;
        return;
      }

      rows.forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'tb-searchable-select__option';
        button.setAttribute('role', 'option');
        button.dataset.value = option.value;
        button.textContent = option.textContent.trim();
        if (option.value === currentValue) {
          button.classList.add('is-selected');
          button.setAttribute('aria-selected', 'true');
        } else {
          button.setAttribute('aria-selected', 'false');
        }
        button.addEventListener('mousedown', (event) => {
          event.preventDefault();
          choose(option.value);
        });
        menu.appendChild(button);
        if (option.value === currentValue) activeIndex = index;
      });
    }

    function open() {
      if (select.disabled) return;
      wrapper.classList.add('is-open');
      input.setAttribute('aria-expanded', 'true');
      const currentLabel = selectedLabel(select);
      const query = input.value && input.value !== currentLabel ? input.value : '';
      render(query);
    }

    function close(restore = true) {
      wrapper.classList.remove('is-open');
      input.setAttribute('aria-expanded', 'false');
      activeIndex = -1;
      if (restore) input.value = selectedLabel(select);
    }

    function refresh() {
      input.disabled = select.disabled;
      const placeholder = select.options.length ? select.options[0].textContent.trim() : 'Select option';
      input.placeholder = placeholder;
      input.value = selectedLabel(select);
      if (wrapper.classList.contains('is-open')) render('');
    }

    input.addEventListener('focus', () => {
      open();
      window.setTimeout(() => input.select(), 0);
    });

    input.addEventListener('click', () => {
      open();
    });

    input.addEventListener('input', () => {
      if (!wrapper.classList.contains('is-open')) open();
      render(input.value);
      setActive(0);
    });

    input.addEventListener('keydown', (event) => {
      const rows = [...menu.querySelectorAll('.tb-searchable-select__option')];
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!wrapper.classList.contains('is-open')) open();
        setActive(activeIndex < 0 ? 0 : activeIndex + 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!wrapper.classList.contains('is-open')) open();
        setActive(activeIndex < 0 ? Math.max(0, rows.length - 1) : activeIndex - 1);
      } else if (event.key === 'Enter' && wrapper.classList.contains('is-open')) {
        const active = rows[activeIndex];
        if (active) {
          event.preventDefault();
          choose(active.dataset.value);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        close(true);
        input.blur();
      }
    });

    input.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (!wrapper.contains(document.activeElement)) close(true);
      }, 0);
    });

    select.addEventListener('change', refresh);

    const api = { refresh, close };
    searchableSelects.set(select, api);
    refresh();
    return api;
  }

  document.addEventListener('mousedown', (event) => {
    for (const [select, widget] of searchableSelects.entries()) {
      const wrapper = select.closest('.tb-searchable-select');
      if (wrapper && !wrapper.contains(event.target)) widget.close(true);
    }
  });

  function replaceOptions(select, values, placeholder, selectedValue = '') {
    if (!select) return;
    const fragment = document.createDocumentFragment();
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = placeholder;
    fragment.appendChild(placeholderOption);

    for (const value of values) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      if (value === selectedValue) option.selected = true;
      fragment.appendChild(option);
    }

    select.replaceChildren(fragment);
    select.disabled = values.length === 0;
    const widget = searchableSelects.get(select);
    if (widget) widget.refresh();
  }

  function syncUpazilas(preserveSelection = true) {
    if (!divisionSelect || !districtSelect || !upazilaSelect) return;
    const division = divisionSelect.value;
    const district = districtSelect.value;
    const selected = preserveSelection ? upazilaSelect.value : '';
    const values = (bdLocations[division] && bdLocations[division][district]) || [];
    replaceOptions(upazilaSelect, values, 'Select Upazila / Thana', selected);
  }

  function syncDistricts(preserveSelection = true) {
    if (!divisionSelect || !districtSelect || !upazilaSelect) return;
    const division = divisionSelect.value;
    const selected = preserveSelection ? districtSelect.value : '';
    const districts = Object.keys(bdLocations[division] || {});
    replaceOptions(districtSelect, districts, 'Select District', selected);
    syncUpazilas(preserveSelection && districtSelect.value === selected);
  }

  if (divisionSelect && districtSelect && upazilaSelect && Object.keys(bdLocations).length) {
    // Server-rendered choices preserve an older saved address if necessary.
    // Only rebuild when the user changes a parent selection.
    districtSelect.disabled = !divisionSelect.value;
    upazilaSelect.disabled = !divisionSelect.value || !districtSelect.value;
    divisionSelect.addEventListener('change', () => syncDistricts(false));
    districtSelect.addEventListener('change', () => syncUpazilas(false));

    enhanceSearchableSelect(divisionSelect);
    enhanceSearchableSelect(districtSelect);
    enhanceSearchableSelect(upazilaSelect);
  }

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
