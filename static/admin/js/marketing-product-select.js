(() => {
  const select = document.querySelector('.marketing-form select[multiple][name="products"]');
  if (!(select instanceof HTMLSelectElement) || select.dataset.marketingProductsReady === '1') return;

  select.dataset.marketingProductsReady = '1';
  select.classList.add('tb-native-select-hidden');

  const wrapper = document.createElement('div');
  wrapper.className = 'tb-searchable-select marketing-product-select';

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
  input.placeholder = 'Search products...';
  input.autocomplete = 'off';
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');

  const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  chevron.setAttribute('viewBox', '0 0 24 24');
  chevron.setAttribute('aria-hidden', 'true');
  chevron.classList.add('tb-searchable-chevron');
  chevron.innerHTML = '<path d="m7 10 5 5 5-5"></path>';

  const chips = document.createElement('div');
  chips.className = 'marketing-product-chips';
  chips.setAttribute('aria-live', 'polite');

  const menu = document.createElement('div');
  menu.className = 'tb-searchable-menu marketing-product-menu';
  menu.hidden = true;
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-multiselectable', 'true');
  menu.id = 'marketing-product-search-options';
  input.setAttribute('aria-controls', menu.id);

  inputWrap.append(icon, input, chevron);
  wrapper.append(inputWrap, chips);
  select.insertAdjacentElement('afterend', wrapper);
  document.body.appendChild(menu);

  const options = () => [...select.options].filter((option) => option.value && !option.disabled);
  const selectedOptions = () => options().filter((option) => option.selected);

  const positionMenu = () => {
    if (menu.hidden || !wrapper.isConnected) return;
    const rect = inputWrap.getBoundingClientRect();
    const gap = 6;
    const pad = 10;
    const below = window.innerHeight - rect.bottom - pad;
    const above = rect.top - pad;
    const openAbove = below < 220 && above > below;
    menu.style.left = `${Math.max(pad, Math.min(rect.left, window.innerWidth - pad - rect.width))}px`;
    menu.style.width = `${Math.max(220, Math.min(rect.width, window.innerWidth - pad * 2))}px`;
    menu.style.maxHeight = `${Math.max(140, Math.min(300, (openAbove ? above : below) - gap))}px`;
    if (openAbove) {
      menu.style.top = 'auto';
      menu.style.bottom = `${Math.max(pad, window.innerHeight - rect.top + gap)}px`;
    } else {
      menu.style.bottom = 'auto';
      menu.style.top = `${rect.bottom + gap}px`;
    }
  };

  const syncChips = () => {
    chips.replaceChildren();
    selectedOptions().forEach((option) => {
      const chip = document.createElement('span');
      chip.className = 'marketing-product-chip';

      const text = document.createElement('span');
      text.textContent = option.text.trim();

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'marketing-product-chip-remove';
      remove.setAttribute('aria-label', `Remove ${option.text.trim()}`);
      remove.textContent = '×';
      remove.addEventListener('click', () => {
        option.selected = false;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        syncChips();
        render(input.value);
      });

      chip.append(text, remove);
      chips.appendChild(chip);
    });

    chips.hidden = selectedOptions().length === 0;
  };

  const toggleOption = (option) => {
    option.selected = !option.selected;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    input.value = '';
    syncChips();
    render('');
    input.focus();
  };

  const render = (query = '') => {
    const normalized = query.toLowerCase().trim();
    const filtered = options().filter((option) => !normalized || option.text.toLowerCase().includes(normalized));
    menu.replaceChildren();

    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'tb-searchable-empty';
      empty.textContent = 'No matching product found';
      menu.appendChild(empty);
      positionMenu();
      return;
    }

    filtered.forEach((option) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tb-searchable-option marketing-product-option';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', option.selected ? 'true' : 'false');
      if (option.selected) button.classList.add('selected');

      const check = document.createElement('span');
      check.className = 'marketing-product-check';
      check.textContent = option.selected ? '✓' : '';

      const title = document.createElement('strong');
      title.textContent = option.text.trim();

      button.append(check, title);
      button.addEventListener('mousedown', (event) => event.preventDefault());
      button.addEventListener('click', () => toggleOption(option));
      menu.appendChild(button);
    });

    positionMenu();
  };

  const open = () => {
    wrapper.classList.add('open');
    menu.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    render(input.value);
    positionMenu();
  };

  const close = () => {
    wrapper.classList.remove('open');
    menu.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.value = '';
  };

  inputWrap.addEventListener('click', () => {
    input.focus();
    open();
  });
  input.addEventListener('focus', open);
  input.addEventListener('input', () => {
    open();
    render(input.value);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      input.blur();
    }
  });

  document.addEventListener('click', (event) => {
    if (wrapper.contains(event.target) || menu.contains(event.target)) return;
    close();
  });
  window.addEventListener('resize', positionMenu);
  document.addEventListener('scroll', positionMenu, true);
  select.addEventListener('change', syncChips);
  select.form?.addEventListener('reset', () => setTimeout(() => {
    syncChips();
    render('');
  }, 0));

  syncChips();
})();
