(() => {
  const ENTITY_FIELDS = new Set([
    'variant','variant_id','product','product_id','customer','customer_id','supplier','supplier_id',
    'warehouse','warehouse_id','from_warehouse','to_warehouse','source_warehouse','destination_warehouse',
    'unit','unit_id','serial_unit','serial_unit_id','replacement_unit',
    'order','order_id','sales_order','purchase','purchase_id','purchase_order','purchase_order_id',
    'category','category_id','expense_category','parent','brand','brand_id','courier','courier_id',
    'account','account_id','payment_account','group','customer_group','role',
    'shipment','shipment_id','return_id','warranty_claim','warranty_claim_id'
  ]);

  const PLACEHOLDERS = {
    variant:'Search product / SKU...', variant_id:'Search product / SKU...', product:'Search product...', product_id:'Search product...',
    customer:'Search customer...', customer_id:'Search customer...', supplier:'Search supplier...', supplier_id:'Search supplier...',
    warehouse:'Search warehouse...', warehouse_id:'Search warehouse...', from_warehouse:'Search warehouse...', to_warehouse:'Search warehouse...',
    source_warehouse:'Search warehouse...', destination_warehouse:'Search warehouse...', unit:'Search Serial / IMEI...', unit_id:'Search Serial / IMEI...',
    serial_unit:'Search Serial / IMEI...', serial_unit_id:'Search Serial / IMEI...', replacement_unit:'Search replacement Serial / IMEI...',
    order:'Search order...', order_id:'Search order...', sales_order:'Search sales order...', purchase:'Search purchase...', purchase_id:'Search purchase...',
    purchase_order:'Search purchase...', purchase_order_id:'Search purchase...', category:'Search category...', category_id:'Search category...',
    expense_category:'Search expense category...', parent:'Search parent category...', brand:'Search brand...', brand_id:'Search brand...',
    courier:'Search courier...', courier_id:'Search courier...', account:'Search account...', account_id:'Search account...', payment_account:'Search payment account...',
    group:'Search customer group...', customer_group:'Search customer group...', role:'Search role...', shipment:'Search shipment...', shipment_id:'Search shipment...',
    return_id:'Search return...', warranty_claim:'Search warranty claim...', warranty_claim_id:'Search warranty claim...'
  };

  const states = new Set();
  let sequence = 0;

  const fieldKey = (select) => {
    if (select.hasAttribute('data-real-pos-customer')) return 'customer';
    const name = (select.getAttribute('name') || '').toLowerCase().trim();
    if (ENTITY_FIELDS.has(name)) return name;
    const last = name.split('-').pop();
    return ENTITY_FIELDS.has(last) ? last : name;
  };

  const shouldEnhance = (select) => {
    if (!(select instanceof HTMLSelectElement) || select.multiple || select.disabled) return false;
    if (select.dataset.searchableSelect === 'false') return false;
    if (select.hasAttribute('data-searchable-select') || select.hasAttribute('data-real-pos-customer')) return true;
    return ENTITY_FIELDS.has(fieldKey(select));
  };

  const cleanBlankText = (text) => /^\s*-+\s*$/.test(text || '') ? '' : (text || '').trim();

  const closeState = (state, restore = true) => {
    if (!state || state.destroyed) return;
    state.wrapper.classList.remove('open');
    state.menu.hidden = true;
    state.input.setAttribute('aria-expanded', 'false');
    if (restore) state.syncInput();
  };

  const closeOthers = (current) => {
    states.forEach((state) => {
      if (state !== current) closeState(state);
    });
  };

  const enhance = (select) => {
    if (!shouldEnhance(select)) return null;
    if (select._tbSearchable && !select._tbSearchable.destroyed) return select._tbSearchable;

    if (select.dataset.tbSearchableReady === '1') {
      select.removeAttribute('data-tb-searchable-ready');
      select.classList.remove('tb-native-select-hidden');
      const clonedUi = select.nextElementSibling;
      if (clonedUi?.classList.contains('tb-searchable-select')) clonedUi.remove();
    }

    const key = fieldKey(select);
    const wrapper = document.createElement('div');
    wrapper.className = 'tb-searchable-select';

    const inputWrap = document.createElement('div');
    inputWrap.className = 'tb-searchable-input-wrap';

    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    icon.classList.add('tb-searchable-icon');
    icon.innerHTML = '<circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path>';

    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'tb-searchable-input';
    input.placeholder = select.dataset.searchPlaceholder || PLACEHOLDERS[key] || 'Search...';
    input.autocomplete = 'off';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');

    const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevron.setAttribute('viewBox', '0 0 24 24');
    chevron.setAttribute('aria-hidden', 'true');
    chevron.classList.add('tb-searchable-chevron');
    chevron.innerHTML = '<path d="m7 10 5 5 5-5"></path>';

    const menu = document.createElement('div');
    menu.className = 'tb-searchable-menu';
    menu.hidden = true;
    menu.setAttribute('role', 'listbox');
    menu.id = `tb-searchable-list-${++sequence}`;
    input.setAttribute('aria-controls', menu.id);

    inputWrap.append(icon, input, chevron);
    wrapper.appendChild(inputWrap);
    select.insertAdjacentElement('afterend', wrapper);
    document.body.appendChild(menu);
    select.classList.add('tb-native-select-hidden');
    select.dataset.tbSearchableReady = '1';

    let filtered = [];
    let activeIndex = -1;

    const selectedOption = () => select.options[select.selectedIndex] || null;
    const selectedText = () => {
      const option = selectedOption();
      if (!option || !select.value) return '';
      return option.text.trim();
    };
    const syncInput = () => { input.value = selectedText(); };

    const positionMenu = () => {
      if (menu.hidden || !wrapper.isConnected) return;
      const rect = inputWrap.getBoundingClientRect();
      const gap = 6;
      const pad = 10;
      const desired = Math.min(280, menu.scrollHeight || 280);
      const below = window.innerHeight - rect.bottom - pad;
      const above = rect.top - pad;
      const openAbove = below < Math.min(220, desired) && above > below;
      menu.style.left = `${Math.max(pad, Math.min(rect.left, window.innerWidth - pad - rect.width))}px`;
      menu.style.width = `${Math.max(180, Math.min(rect.width, window.innerWidth - pad * 2))}px`;
      menu.style.maxHeight = `${Math.max(120, Math.min(280, (openAbove ? above : below) - gap))}px`;
      if (openAbove) {
        menu.style.top = 'auto';
        menu.style.bottom = `${Math.max(pad, window.innerHeight - rect.top + gap)}px`;
      } else {
        menu.style.bottom = 'auto';
        menu.style.top = `${rect.bottom + gap}px`;
      }
    };

    const markActive = () => {
      const buttons = [...menu.querySelectorAll('.tb-searchable-option')];
      buttons.forEach((button, index) => button.classList.toggle('active', index === activeIndex));
      if (activeIndex >= 0 && buttons[activeIndex]) buttons[activeIndex].scrollIntoView({ block: 'nearest' });
    };

    const optionRows = () => [...select.options].filter((option) => {
      if (option.disabled) return false;
      if (option.value) return true;
      return !select.required;
    });

    const choose = (option) => {
      if (!option) return;
      select.value = option.value;
      wrapper.classList.remove('invalid', 'open');
      menu.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      syncInput();
      select.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const render = (query = '') => {
      const normalized = query.toLowerCase().trim();
      filtered = optionRows().filter((option) => {
        const display = option.value ? option.text.trim() : (cleanBlankText(option.text) || 'Clear selection');
        return !normalized || display.toLowerCase().includes(normalized);
      });
      menu.replaceChildren();

      if (!filtered.length) {
        const empty = document.createElement('div');
        empty.className = 'tb-searchable-empty';
        empty.textContent = 'No matching option found';
        menu.appendChild(empty);
        activeIndex = -1;
        positionMenu();
        return;
      }

      filtered.forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'tb-searchable-option';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', option.value === select.value ? 'true' : 'false');
        if (option.value === select.value) button.classList.add('selected');

        const display = option.value ? option.text.trim() : (cleanBlankText(option.text) || 'Clear selection');
        const parts = display.split(' — ');
        const title = document.createElement('strong');
        title.textContent = parts.shift() || display;
        button.appendChild(title);
        if (parts.length) {
          const meta = document.createElement('span');
          meta.textContent = parts.join(' • ');
          button.appendChild(meta);
        }

        button.addEventListener('mousedown', (event) => event.preventDefault());
        button.addEventListener('click', () => choose(option));
        button.addEventListener('mouseenter', () => { activeIndex = index; markActive(); });
        menu.appendChild(button);
      });

      const current = filtered.findIndex((option) => option.value === select.value);
      activeIndex = current >= 0 ? current : -1;
      markActive();
      positionMenu();
    };

    const state = {
      select, wrapper, input, menu, destroyed: false, syncInput,
      close: () => closeState(state),
      destroy: () => {
        if (state.destroyed) return;
        state.destroyed = true;
        window.removeEventListener('resize', keepAligned);
        document.removeEventListener('scroll', keepAligned, true);
        menu.remove();
        wrapper.remove();
        select.classList.remove('tb-native-select-hidden');
        select.removeAttribute('data-tb-searchable-ready');
        delete select._tbSearchable;
        states.delete(state);
      }
    };

    const open = () => {
      closeOthers(state);
      wrapper.classList.add('open');
      menu.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      const currentText = selectedText();
      render(input.value.trim() === currentText ? '' : input.value);
      positionMenu();
    };
    const keepAligned = () => { if (wrapper.classList.contains('open')) positionMenu(); };

    inputWrap.addEventListener('click', () => { input.focus(); open(); });
    input.addEventListener('focus', () => { open(); if (select.value) input.select(); });
    input.addEventListener('input', () => {
      if (input.value.trim() !== selectedText()) select.value = '';
      wrapper.classList.remove('invalid');
      open();
      render(input.value);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!wrapper.classList.contains('open')) open();
        if (filtered.length) activeIndex = Math.min(activeIndex + 1, filtered.length - 1);
        markActive();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!wrapper.classList.contains('open')) open();
        if (filtered.length) activeIndex = activeIndex <= 0 ? filtered.length - 1 : activeIndex - 1;
        markActive();
      } else if (event.key === 'Enter' && wrapper.classList.contains('open') && activeIndex >= 0) {
        event.preventDefault();
        choose(filtered[activeIndex]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeState(state);
      }
    });

    select.addEventListener('change', () => { syncInput(); wrapper.classList.remove('invalid'); });
    select.addEventListener('invalid', () => {
      wrapper.classList.add('invalid');
      open();
      setTimeout(() => input.focus(), 0);
    });

    window.addEventListener('resize', keepAligned);
    document.addEventListener('scroll', keepAligned, true);
    select._tbSearchable = state;
    states.add(state);
    syncInput();
    return state;
  };

  const enhanceAll = (root = document) => {
    if (root instanceof HTMLSelectElement) enhance(root);
    root.querySelectorAll?.('select').forEach(enhance);
  };

  document.addEventListener('click', (event) => {
    states.forEach((state) => {
      if (state.wrapper.contains(event.target) || state.menu.contains(event.target)) return;
      closeState(state);
    });
  });

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.removedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        const removedSelects = node.matches('select') ? [node] : [...node.querySelectorAll('select')];
        removedSelects.forEach((select) => select._tbSearchable?.destroy());
      });
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        enhanceAll(node);
      });
    });
  });

  window.TechBariSearchableSelect = { enhance, enhanceAll };
  enhanceAll(document);
  observer.observe(document.body, { childList: true, subtree: true });
})();
