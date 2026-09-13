(() => {
  const page = document.querySelector('.variant-editor-page');
  if (!page) return;

  const form = document.getElementById('variantForm');
  const product = document.getElementById('id_product');
  const source = document.getElementById('id_option_values');
  const nameInput = document.getElementById('id_name');
  const skuInput = document.getElementById('id_sku');
  const symbolInput = document.getElementById('id_symbol');
  const groupHost = document.querySelector('[data-option-groups]');
  const preview = document.querySelector('[data-variant-preview]');
  const previewBadge = document.querySelector('[data-variant-preview-status]');
  const legacyNameField = document.querySelector('[data-legacy-name-field]');
  const generateSkuButton = document.querySelector('[data-generate-sku]');

  const parseOption = (text) => {
    const parts = String(text || '').split(/\s+—\s+/);
    const group = (parts.shift() || 'Variant').trim();
    const rawValue = parts.join(' — ').trim();
    return { group, rawValue: rawValue || String(text || '').trim() };
  };

  const stripSymbol = (value) => {
    const text = String(value || '').trim();
    const match = text.match(/^([^\p{L}\p{N}]+)\s*(.+)$/u);
    return match ? { symbol: match[1].trim(), label: match[2].trim() } : { symbol: '', label: text };
  };

  const selectedOptions = () => source ? Array.from(source.options).filter(option => option.selected) : [];

  const optionGroups = () => {
    const groups = new Map();
    if (!source) return groups;
    Array.from(source.options).forEach(option => {
      const parsed = parseOption(option.textContent);
      if (!groups.has(parsed.group)) groups.set(parsed.group, []);
      groups.get(parsed.group).push({ option, ...parsed, ...stripSymbol(parsed.rawValue) });
    });
    return groups;
  };

  const updatePreview = () => {
    if (!source || !preview) return;
    const groups = optionGroups();
    const chosen = selectedOptions().map(option => {
      const parsed = parseOption(option.textContent);
      return stripSymbol(parsed.rawValue).label;
    });
    const complete = groups.size > 0 && chosen.length === groups.size;
    const value = chosen.join(' / ');

    preview.textContent = value || 'Select one value from each option';
    if (previewBadge) {
      previewBadge.textContent = complete ? 'Ready' : `${chosen.length}/${groups.size || 0} selected`;
    }
    if (nameInput && groups.size > 0) {
      nameInput.value = value;
      nameInput.readOnly = true;
    }
    if (legacyNameField) legacyNameField.classList.toggle('is-structured', groups.size > 0);

    if (symbolInput && !symbolInput.value) {
      const first = selectedOptions()[0];
      if (first) {
        const parsed = parseOption(first.textContent);
        const symbol = stripSymbol(parsed.rawValue).symbol;
        if (symbol) symbolInput.placeholder = symbol;
      }
    }
  };

  const renderGroups = () => {
    if (!source || !groupHost) return;
    const groups = optionGroups();
    groupHost.innerHTML = '';

    if (!groups.size) {
      groupHost.innerHTML = '<div class="empty-options">No structured options are configured for this product. Use <a href="' + (groupHost.dataset.optionSetupUrl || '#') + '">Option Setup</a> to add Color, Storage, Size or other values.</div>';
      if (legacyNameField) legacyNameField.classList.remove('is-structured');
      if (nameInput) nameInput.readOnly = false;
      return;
    }

    source.classList.add('structured-option-source');
    groups.forEach((values, groupName) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'option-group';

      const head = document.createElement('div');
      head.className = 'option-group-head';
      const name = document.createElement('div');
      name.className = 'option-group-name';
      name.textContent = groupName;
      const selectedLabel = document.createElement('div');
      selectedLabel.className = 'option-group-value';
      const current = values.find(value => value.option.selected);
      selectedLabel.textContent = current ? current.label : 'Choose one';
      head.append(name, selectedLabel);

      const list = document.createElement('div');
      list.className = 'option-choice-list';
      values.forEach(value => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'option-choice' + (value.option.selected ? ' is-selected' : '');
        button.dataset.optionValue = value.option.value;
        if (value.symbol) {
          const symbol = document.createElement('span');
          symbol.className = 'option-symbol';
          symbol.textContent = value.symbol;
          button.appendChild(symbol);
        }
        const label = document.createElement('span');
        label.textContent = value.label;
        button.appendChild(label);

        button.addEventListener('click', () => {
          values.forEach(item => { item.option.selected = false; });
          value.option.selected = true;
          list.querySelectorAll('.option-choice').forEach(node => node.classList.remove('is-selected'));
          button.classList.add('is-selected');
          selectedLabel.textContent = value.label;
          source.dispatchEvent(new Event('change', { bubbles: true }));
          updatePreview();
        });
        list.appendChild(button);
      });

      wrapper.append(head, list);
      groupHost.appendChild(wrapper);
    });
    updatePreview();
  };

  const slugToken = (value, max = 8) => String(value || '')
    .normalize('NFKD')
    .replace(/[^A-Za-z0-9]+/g, '')
    .toUpperCase()
    .slice(0, max);

  const generatedSku = () => {
    const selectedProductText = product && product.selectedOptions.length ? product.selectedOptions[0].textContent : '';
    const productTokens = String(selectedProductText || '').trim().split(/\s+/).filter(Boolean);
    const prefix = productTokens.map(token => slugToken(token, 3)).filter(Boolean).slice(0, 3).join('-') || 'SKU';
    const optionTokens = selectedOptions().map(option => {
      const parsed = parseOption(option.textContent);
      return slugToken(stripSymbol(parsed.rawValue).label, 6);
    }).filter(Boolean);
    return [prefix, ...optionTokens].join('-').slice(0, 64);
  };

  if (generateSkuButton) {
    generateSkuButton.addEventListener('click', () => {
      const value = generatedSku();
      if (skuInput && value) {
        skuInput.value = value;
        skuInput.focus();
      }
    });
  }

  if (product && !product.disabled) {
    product.addEventListener('change', () => {
      const value = product.value;
      if (!value) return;
      const url = new URL(window.location.href);
      url.searchParams.set('product', value);
      url.searchParams.delete('id');
      window.location.assign(url.toString());
    });
  }

  if (form) {
    form.addEventListener('submit', () => {
      updatePreview();
    });
  }

  renderGroups();
})();