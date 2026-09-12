(() => {
  const table = document.querySelector('[data-sales-items]');
  const addButton = document.querySelector('[data-sales-add-row]');
  if (!table || !addButton) return;

  let pickerSequence = 0;

  const closeOtherPickers = (current) => {
    document.querySelectorAll('.sales-sku-picker.open').forEach((picker) => {
      if (picker === current) return;
      picker.classList.remove('open');
      const menu = picker.querySelector('.sales-sku-picker-menu');
      const input = picker.querySelector('.sales-sku-picker-input');
      if (menu) menu.hidden = true;
      if (input) input.setAttribute('aria-expanded', 'false');
    });
  };

  const enhanceSkuSelect = (select) => {
    if (!select || select.dataset.searchableReady === '1') return;
    select.dataset.searchableReady = '1';
    select.classList.add('sales-native-select');

    const picker = document.createElement('div');
    picker.className = 'sales-sku-picker';

    const inputWrap = document.createElement('div');
    inputWrap.className = 'sales-sku-picker-input-wrap';

    const searchIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    searchIcon.setAttribute('viewBox', '0 0 24 24');
    searchIcon.setAttribute('aria-hidden', 'true');
    searchIcon.classList.add('sales-sku-picker-icon');
    searchIcon.innerHTML = '<circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path>';

    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'sales-sku-picker-input';
    input.placeholder = 'Search product / SKU...';
    input.autocomplete = 'off';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');

    const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevron.setAttribute('viewBox', '0 0 24 24');
    chevron.setAttribute('aria-hidden', 'true');
    chevron.classList.add('sales-sku-picker-chevron');
    chevron.innerHTML = '<path d="m7 10 5 5 5-5"></path>';

    const menu = document.createElement('div');
    menu.className = 'sales-sku-picker-menu';
    menu.hidden = true;
    menu.setAttribute('role', 'listbox');
    menu.id = `sales-sku-list-${++pickerSequence}`;
    input.setAttribute('aria-controls', menu.id);

    inputWrap.append(searchIcon, input, chevron);
    picker.append(inputWrap, menu);
    select.insertAdjacentElement('afterend', picker);

    const availableOptions = [...select.options].filter((option) => option.value);
    let filteredOptions = [];
    let activeIndex = -1;

    const selectedOption = () => select.options[select.selectedIndex];
    const selectedText = () => (select.value && selectedOption() ? selectedOption().text.trim() : '');

    const markActive = () => {
      const buttons = [...menu.querySelectorAll('.sales-sku-option')];
      buttons.forEach((button, index) => button.classList.toggle('active', index === activeIndex));
      if (activeIndex >= 0 && buttons[activeIndex]) buttons[activeIndex].scrollIntoView({ block: 'nearest' });
    };

    const chooseOption = (option) => {
      if (!option) return;
      select.value = option.value;
      input.value = option.text.trim();
      picker.classList.remove('invalid', 'open');
      menu.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      select.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const renderOptions = (query = '') => {
      const normalized = query.toLowerCase().trim();
      filteredOptions = availableOptions.filter((option) => !normalized || option.text.toLowerCase().includes(normalized));
      menu.replaceChildren();

      if (!filteredOptions.length) {
        const empty = document.createElement('div');
        empty.className = 'sales-sku-empty';
        empty.textContent = 'No matching product / SKU found';
        menu.appendChild(empty);
        activeIndex = -1;
        return;
      }

      filteredOptions.forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'sales-sku-option';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', option.value === select.value ? 'true' : 'false');
        if (option.value === select.value) button.classList.add('selected');

        const parts = option.text.trim().split(' — ');
        const title = document.createElement('strong');
        title.textContent = parts.shift() || option.text.trim();
        button.appendChild(title);
        if (parts.length) {
          const meta = document.createElement('span');
          meta.textContent = parts.join(' • ');
          button.appendChild(meta);
        }

        button.addEventListener('mousedown', (event) => event.preventDefault());
        button.addEventListener('click', () => chooseOption(option));
        button.addEventListener('mouseenter', () => {
          activeIndex = index;
          markActive();
        });
        menu.appendChild(button);
      });

      const selectedIndex = filteredOptions.findIndex((option) => option.value === select.value);
      activeIndex = selectedIndex >= 0 ? selectedIndex : -1;
      markActive();
    };

    const openPicker = () => {
      closeOtherPickers(picker);
      picker.classList.add('open');
      menu.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      const currentSelectedText = selectedText();
      renderOptions(input.value.trim() === currentSelectedText ? '' : input.value);
    };

    const closePicker = () => {
      picker.classList.remove('open');
      menu.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      if (!select.value) input.value = '';
      else input.value = selectedText();
    };

    if (select.value) input.value = selectedText();

    input.addEventListener('focus', () => {
      openPicker();
      if (select.value) input.select();
    });

    input.addEventListener('click', openPicker);

    input.addEventListener('input', () => {
      if (input.value.trim() !== selectedText()) select.value = '';
      picker.classList.remove('invalid');
      openPicker();
      renderOptions(input.value);
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!picker.classList.contains('open')) openPicker();
        if (filteredOptions.length) activeIndex = Math.min(activeIndex + 1, filteredOptions.length - 1);
        markActive();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!picker.classList.contains('open')) openPicker();
        if (filteredOptions.length) activeIndex = activeIndex <= 0 ? filteredOptions.length - 1 : activeIndex - 1;
        markActive();
      } else if (event.key === 'Enter' && picker.classList.contains('open') && activeIndex >= 0) {
        event.preventDefault();
        chooseOption(filteredOptions[activeIndex]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closePicker();
      }
    });

    select.addEventListener('change', () => {
      if (select.value) input.value = selectedText();
      picker.classList.remove('invalid');
    });

    select.addEventListener('invalid', () => {
      picker.classList.add('invalid');
      openPicker();
      setTimeout(() => input.focus(), 0);
    });

    picker._closeSkuPicker = closePicker;
  };

  const wireRow = (row) => {
    const select = row.querySelector('select[name="variant_id"]');
    const price = row.querySelector('input[name="unit_price"]');
    const remove = row.querySelector('[data-sales-remove-row]');

    if (select && price) {
      select.addEventListener('change', () => {
        const option = select.options[select.selectedIndex];
        if (option && option.dataset.price && !price.value) price.value = option.dataset.price;
      });
      enhanceSkuSelect(select);
    }

    if (remove) {
      remove.addEventListener('click', () => {
        const rows = table.querySelectorAll('[data-sales-row]');
        if (rows.length > 1) row.remove();
      });
    }
  };

  table.querySelectorAll('[data-sales-row]').forEach(wireRow);

  addButton.addEventListener('click', () => {
    const source = table.querySelector('[data-sales-row]');
    if (!source) return;
    const row = source.cloneNode(true);
    row.querySelectorAll('.sales-sku-picker').forEach((picker) => picker.remove());

    const select = row.querySelector('select[name="variant_id"]');
    const quantity = row.querySelector('input[name="quantity"]');
    const price = row.querySelector('input[name="unit_price"]');
    const discount = row.querySelector('input[name="line_discount"]');

    if (select) {
      select.value = '';
      select.classList.remove('sales-native-select');
      delete select.dataset.searchableReady;
    }
    if (quantity) quantity.value = '1';
    if (price) price.value = '';
    if (discount) discount.value = '0.00';

    table.appendChild(row);
    wireRow(row);
  });

  document.addEventListener('click', (event) => {
    document.querySelectorAll('.sales-sku-picker.open').forEach((picker) => {
      if (picker.contains(event.target)) return;
      if (typeof picker._closeSkuPicker === 'function') picker._closeSkuPicker();
    });
  });
})();
