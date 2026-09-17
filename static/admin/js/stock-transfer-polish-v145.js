(() => {
  const source = document.querySelector('#id_from_warehouse');
  const destination = document.querySelector('#id_to_warehouse');
  const message = document.querySelector('[data-transfer-route-message]');
  const submitButtons = [...document.querySelectorAll('[data-complete-transfer]')];

  if (source && destination) {
    let syncing = false;

    const syncSearchable = (select) => select._tbSearchable?.syncInput?.();
    const resetDisabled = (select) => {
      [...select.options].forEach((option) => { option.disabled = false; });
    };
    const disableValue = (select, value) => {
      if (!value) return;
      const option = [...select.options].find((row) => row.value === value);
      if (option) option.disabled = true;
    };

    const renderState = (changedField = null) => {
      if (syncing) return;
      syncing = true;

      resetDisabled(source);
      resetDisabled(destination);

      let sourceValue = source.value;
      let destinationValue = destination.value;

      if (sourceValue && destinationValue && sourceValue === destinationValue) {
        if (changedField === destination) {
          source.value = '';
          sourceValue = '';
          syncSearchable(source);
        } else {
          destination.value = '';
          destinationValue = '';
          syncSearchable(destination);
        }
      }

      disableValue(destination, sourceValue);
      disableValue(source, destinationValue);

      const ready = Boolean(sourceValue && destinationValue && sourceValue !== destinationValue);
      submitButtons.forEach((button) => {
        button.disabled = !ready;
        button.setAttribute('aria-disabled', ready ? 'false' : 'true');
        button.title = ready ? '' : 'Choose two different warehouses first.';
      });

      if (message) {
        message.classList.toggle('is-ready', ready);
        const copy = message.querySelector('[data-transfer-route-copy]');
        if (copy) {
          if (ready) {
            copy.textContent = 'Source and destination are different. Add the SKU quantities to complete the transfer.';
          } else if (sourceValue) {
            copy.textContent = 'Choose a destination warehouse different from the source.';
          } else if (destinationValue) {
            copy.textContent = 'Choose a source warehouse different from the destination.';
          } else {
            copy.textContent = 'Choose the source and destination warehouses. They must be different.';
          }
        }
      }

      syncing = false;
    };

    const bindSearchableClear = (select) => {
      const searchable = select._tbSearchable;
      const input = searchable?.input;
      if (!input) return;

      input.addEventListener('input', () => {
        if (input.value.trim() || select.value) return;
        renderState(select);
        searchable.close?.();
      });
    };

    source.addEventListener('change', () => renderState(source));
    destination.addEventListener('change', () => renderState(destination));
    bindSearchableClear(source);
    bindSearchableClear(destination);
    renderState();
  }

  const transferForm = document.querySelector('#transferForm');
  const itemsContainer = transferForm?.querySelector('[data-transfer-items]');
  const addItemButton = transferForm?.querySelector('[data-add-transfer-item]');
  const itemCount = transferForm?.querySelector('[data-transfer-item-count]');
  const emptyRowTemplate = document.querySelector('#stockTransferEmptyRow');
  const totalFormsInput = transferForm?.querySelector('input[name$="-TOTAL_FORMS"]');
  const maxFormsInput = transferForm?.querySelector('input[name$="-MAX_NUM_FORMS"]');

  if (!transferForm || !itemsContainer || !addItemButton || !emptyRowTemplate || !totalFormsInput) return;

  const prefix = totalFormsInput.name.replace(/-TOTAL_FORMS$/, '');
  const escapedPrefix = prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const indexedFieldPattern = new RegExp(`(${escapedPrefix}-)\\d+(-)`, 'g');
  const maxForms = Math.max(1, Number.parseInt(maxFormsInput?.value || '50', 10) || 50);

  const rows = () => [...itemsContainer.querySelectorAll('[data-transfer-item-row]')];

  const replaceIndex = (value, index) => value.replace(indexedFieldPattern, `$1${index}$2`);

  const reindexRows = () => {
    rows().forEach((row, index) => {
      row.dataset.formIndex = String(index);
      const number = row.querySelector('[data-transfer-row-number]');
      if (number) number.textContent = String(index + 1);

      row.querySelectorAll('[name], [id], [for]').forEach((element) => {
        ['name', 'id', 'for'].forEach((attribute) => {
          const value = element.getAttribute(attribute);
          if (!value || !indexedFieldPattern.test(value)) {
            indexedFieldPattern.lastIndex = 0;
            return;
          }
          indexedFieldPattern.lastIndex = 0;
          element.setAttribute(attribute, replaceIndex(value, index));
        });
      });
    });
    totalFormsInput.value = String(rows().length);
  };

  const refreshRowActions = () => {
    const currentRows = rows();
    const canRemove = currentRows.length > 1;
    currentRows.forEach((row) => {
      const removeButton = row.querySelector('[data-remove-transfer-item]');
      if (removeButton) removeButton.hidden = !canRemove;
    });

    addItemButton.disabled = currentRows.length >= maxForms;
    addItemButton.title = addItemButton.disabled ? `Maximum ${maxForms} items per transfer.` : '';
    if (itemCount) {
      itemCount.textContent = `${currentRows.length} item${currentRows.length === 1 ? '' : 's'}`;
    }
  };

  const addRow = () => {
    const currentRows = rows();
    if (currentRows.length >= maxForms) return;

    const index = currentRows.length;
    const holder = document.createElement('template');
    holder.innerHTML = emptyRowTemplate.innerHTML.replaceAll('__prefix__', String(index)).trim();
    const row = holder.content.firstElementChild;
    if (!row) return;

    itemsContainer.appendChild(row);
    reindexRows();
    refreshRowActions();
    window.TechBariSearchableSelect?.enhanceAll?.(row);

    window.setTimeout(() => {
      row.querySelector('.tb-searchable-input, select, input')?.focus();
    }, 0);
  };

  const removeRow = (row) => {
    if (!row || rows().length <= 1) return;
    row.querySelectorAll('select').forEach((select) => select._tbSearchable?.destroy?.());
    row.remove();
    reindexRows();
    refreshRowActions();
  };

  addItemButton.addEventListener('click', addRow);
  itemsContainer.addEventListener('click', (event) => {
    const removeButton = event.target.closest('[data-remove-transfer-item]');
    if (!removeButton) return;
    removeRow(removeButton.closest('[data-transfer-item-row]'));
  });

  reindexRows();
  refreshRowActions();
})();