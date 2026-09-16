(() => {
  const wrappers = Array.from(document.querySelectorAll('.coupon-multi-field'));
  if (!wrappers.length) return;

  let openRoot = null;

  const closeRoot = (root) => {
    if (!root) return;
    root.classList.remove('is-open');
    const trigger = root.querySelector('.coupon-multi-trigger');
    const panel = root.querySelector('.coupon-multi-panel');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (panel) panel.hidden = true;
    if (openRoot === root) openRoot = null;
  };

  const closeOpen = () => closeRoot(openRoot);

  const makeIcon = () => {
    const icon = document.createElement('span');
    icon.className = 'coupon-multi-check';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '✓';
    return icon;
  };

  wrappers.forEach((wrapper) => {
    const select = wrapper.querySelector('select[multiple]');
    if (!select || select.dataset.couponEnhanced === '1') return;
    select.dataset.couponEnhanced = '1';

    const fieldName = wrapper.dataset.couponMulti || select.name || 'items';
    const plural = fieldName === 'categories' ? 'categories' : 'products';

    const root = document.createElement('div');
    root.className = 'coupon-multi';

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'coupon-multi-trigger';
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-haspopup', 'listbox');

    const triggerText = document.createElement('span');
    triggerText.className = 'coupon-multi-trigger-text';

    const triggerCount = document.createElement('span');
    triggerCount.className = 'coupon-multi-count';
    triggerCount.hidden = true;

    const chevron = document.createElement('span');
    chevron.className = 'coupon-multi-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '⌄';

    trigger.append(triggerText, triggerCount, chevron);

    const panel = document.createElement('div');
    panel.className = 'coupon-multi-panel';
    panel.hidden = true;

    const searchWrap = document.createElement('div');
    searchWrap.className = 'coupon-multi-search-wrap';

    const searchIcon = document.createElement('span');
    searchIcon.className = 'coupon-multi-search-icon';
    searchIcon.setAttribute('aria-hidden', 'true');
    searchIcon.textContent = '⌕';

    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'coupon-multi-search';
    search.placeholder = `Search ${plural}...`;
    search.autocomplete = 'off';
    search.setAttribute('aria-label', `Search ${plural}`);
    searchWrap.append(searchIcon, search);

    const list = document.createElement('div');
    list.className = 'coupon-multi-options';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-multiselectable', 'true');

    const empty = document.createElement('div');
    empty.className = 'coupon-multi-empty';
    empty.textContent = `No ${plural} found.`;
    empty.hidden = true;

    panel.append(searchWrap, list, empty);
    root.append(trigger, panel);
    select.insertAdjacentElement('afterend', root);
    wrapper.classList.add('is-enhanced');

    const rows = Array.from(select.options).map((option) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'coupon-multi-option';
      row.dataset.value = option.value;
      row.dataset.search = option.text.toLowerCase();
      row.setAttribute('role', 'option');

      const check = makeIcon();
      const label = document.createElement('span');
      label.className = 'coupon-multi-option-label';
      label.textContent = option.text;
      row.append(check, label);
      list.append(row);

      const syncRow = () => {
        row.classList.toggle('is-selected', option.selected);
        row.setAttribute('aria-selected', option.selected ? 'true' : 'false');
      };

      row.addEventListener('click', () => {
        option.selected = !option.selected;
        syncRow();
        syncSummary();
        select.dispatchEvent(new Event('change', { bubbles: true }));
      });

      syncRow();
      return { row, option, syncRow };
    });

    const syncSummary = () => {
      const selected = rows.filter(({ option }) => option.selected).map(({ option }) => option.text);
      if (!selected.length) {
        triggerText.textContent = `Select ${plural}...`;
        trigger.classList.add('is-placeholder');
        triggerCount.hidden = true;
        trigger.removeAttribute('title');
        return;
      }

      trigger.classList.remove('is-placeholder');
      triggerText.textContent = selected.length <= 2
        ? selected.join(', ')
        : `${selected[0]}, ${selected[1]}`;
      if (selected.length > 2) {
        triggerCount.textContent = `+${selected.length - 2}`;
        triggerCount.hidden = false;
      } else {
        triggerCount.hidden = true;
      }
      trigger.title = selected.join(', ');
    };

    const filterRows = () => {
      const term = search.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(({ row }) => {
        const show = !term || row.dataset.search.includes(term);
        row.hidden = !show;
        if (show) visible += 1;
      });
      empty.hidden = visible !== 0;
    };

    const open = () => {
      if (openRoot && openRoot !== root) closeRoot(openRoot);
      root.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
      panel.hidden = false;
      openRoot = root;
      window.requestAnimationFrame(() => search.focus());
    };

    trigger.addEventListener('click', () => {
      if (root.classList.contains('is-open')) closeRoot(root);
      else open();
    });

    search.addEventListener('input', filterRows);
    search.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRoot(root);
        trigger.focus();
      }
    });

    select.addEventListener('change', () => {
      rows.forEach(({ syncRow }) => syncRow());
      syncSummary();
    });

    syncSummary();
  });

  const scopeSelect = document.querySelector('#id_scope');
  const productsWrapper = document.querySelector('[data-coupon-multi="products"]');
  const categoriesWrapper = document.querySelector('[data-coupon-multi="categories"]');

  const clearSelection = (wrapper) => {
    if (!wrapper) return;
    const select = wrapper.querySelector('select[multiple]');
    if (!select) return;
    let changed = false;
    Array.from(select.options).forEach((option) => {
      if (option.selected) {
        option.selected = false;
        changed = true;
      }
    });
    if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const setFieldVisible = (wrapper, visible, clearWhenHidden = true) => {
    if (!wrapper) return;
    const root = wrapper.querySelector('.coupon-multi');
    if (!visible && root && root === openRoot) closeRoot(root);
    wrapper.hidden = !visible;
    wrapper.setAttribute('aria-hidden', visible ? 'false' : 'true');
    if (!visible && clearWhenHidden) clearSelection(wrapper);
  };

  const syncScopeFields = () => {
    if (!scopeSelect) return;
    const scope = scopeSelect.value;
    setFieldVisible(productsWrapper, scope === 'products');
    setFieldVisible(categoriesWrapper, scope === 'categories');
  };

  if (scopeSelect) {
    scopeSelect.addEventListener('change', syncScopeFields);
    syncScopeFields();
  }

  document.addEventListener('click', (event) => {
    if (openRoot && !openRoot.contains(event.target)) closeOpen();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && openRoot) closeOpen();
  });
})();
