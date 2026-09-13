(() => {
  const page = document.querySelector('.variant-builder-page');
  if (!page) return;

  const parseExisting = () => {
    const node = document.getElementById('variant-builder-existing');
    if (!node) return [];
    try {
      return JSON.parse(node.textContent || '[]');
    } catch (error) {
      return [];
    }
  };

  const existingMap = new Map(parseExisting().map(row => [String(row.signature), row]));
  const productSelect = page.querySelector('[data-builder-product]');
  const presetSelect = page.querySelector('[data-builder-preset]');

  const navigate = () => {
    const url = new URL(window.location.href);
    if (productSelect?.value) url.searchParams.set('product', productSelect.value);
    else url.searchParams.delete('product');
    if (presetSelect?.value) url.searchParams.set('preset', presetSelect.value);
    else url.searchParams.delete('preset');
    ['notice', 'created', 'reused', 'skipped'].forEach(key => url.searchParams.delete(key));
    window.location.assign(url.toString());
  };

  productSelect?.addEventListener('change', navigate);
  presetSelect?.addEventListener('change', navigate);

  const form = page.querySelector('[data-variant-generator]');
  if (form) {
    const toggleCards = [...form.querySelectorAll('[data-attribute-toggle-card]')];
    const toggles = [...form.querySelectorAll('[data-attribute-toggle]')];
    const groups = [...form.querySelectorAll('[data-builder-attribute]')];
    const countNode = form.querySelector('[data-combination-count]');
    const summaryCopy = form.querySelector('[data-summary-copy]');
    const previewButton = form.querySelector('[data-preview-button]');
    const previewPanel = form.querySelector('[data-preview-panel]');
    const previewBody = form.querySelector('[data-preview-body]');
    const previewTotal = form.querySelector('[data-preview-total]');
    const previewNew = form.querySelector('[data-preview-new]');
    const previewExisting = form.querySelector('[data-preview-existing]');
    const previewSelected = form.querySelector('[data-preview-selected]');
    const previewMessage = form.querySelector('[data-preview-message]');
    const generateButton = form.querySelector('[data-generate-selected]');
    const signatureContainer = form.querySelector('[data-selected-signatures]');
    const selectAllNew = form.querySelector('[data-preview-select-all]');
    const clearNew = form.querySelector('[data-preview-clear]');
    const MAX_PREVIEW = 1000;
    const MAX_GENERATE = 250;

    const groupById = new Map(groups.map(group => [String(group.dataset.attributeId), group]));

    const syncAttributeCard = toggle => {
      const card = toggle.closest('[data-attribute-toggle-card]');
      const group = groupById.get(String(toggle.value));
      card?.classList.toggle('is-selected', toggle.checked);
      if (!group) return;
      group.classList.toggle('is-hidden', !toggle.checked);
      group.querySelectorAll('input[name="value_ids"]').forEach(input => {
        input.disabled = !toggle.checked;
      });
    };

    const activeGroups = () => toggles
      .filter(toggle => toggle.checked)
      .map(toggle => groupById.get(String(toggle.value)))
      .filter(Boolean);

    const selectionState = () => {
      const selectedGroups = activeGroups();
      if (!selectedGroups.length) {
        return { ready: false, total: 0, groups: [], reason: 'Choose at least one attribute.' };
      }

      const valueGroups = [];
      for (const group of selectedGroups) {
        const selected = [...group.querySelectorAll('input[name="value_ids"]:checked:not(:disabled)')];
        if (!selected.length) {
          const name = group.querySelector('.builder-attribute-head strong')?.textContent?.trim() || 'each attribute';
          return { ready: false, total: 0, groups: [], reason: `Select at least one value for ${name}.` };
        }
        valueGroups.push(selected);
      }
      const total = valueGroups.reduce((result, selected) => result * selected.length, 1);
      return { ready: true, total, groups: valueGroups, reason: '' };
    };

    const resetPreview = () => {
      if (previewPanel) previewPanel.hidden = true;
      if (previewBody) previewBody.replaceChildren();
      if (signatureContainer) signatureContainer.replaceChildren();
      if (generateButton) generateButton.disabled = true;
    };

    const updateSummary = () => {
      const state = selectionState();
      if (countNode) countNode.textContent = String(state.total);
      if (previewButton) previewButton.disabled = !state.ready || state.total > MAX_PREVIEW;
      if (summaryCopy) {
        if (!state.ready) summaryCopy.textContent = state.reason;
        else if (state.total > MAX_PREVIEW) summaryCopy.textContent = `${state.total} combinations is too large to preview at once. Reduce the selected values below ${MAX_PREVIEW + 1}.`;
        else if (state.total > MAX_GENERATE) summaryCopy.textContent = `${state.total} combinations can be previewed. Select no more than ${MAX_GENERATE} new rows to generate in one batch.`;
        else summaryCopy.textContent = `${state.total} possible combination${state.total === 1 ? '' : 's'}. Preview them before anything is created.`;
      }
    };

    const combinationsFromGroups = valueGroups => {
      let rows = [[]];
      valueGroups.forEach(group => {
        const next = [];
        rows.forEach(prefix => group.forEach(input => next.push([...prefix, input])));
        rows = next;
      });
      return rows;
    };

    const signatureFor = inputs => inputs
      .map(input => Number(input.value))
      .sort((a, b) => a - b)
      .join(',');

    const refreshPreviewSelection = () => {
      const selectable = previewBody ? [...previewBody.querySelectorAll('input[data-preview-choice]')] : [];
      const selected = selectable.filter(input => input.checked);
      if (previewSelected) previewSelected.textContent = String(selected.length);
      if (signatureContainer) {
        signatureContainer.replaceChildren();
        selected.forEach(input => {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'selected_signatures';
          hidden.value = input.value;
          signatureContainer.appendChild(hidden);
        });
      }
      if (generateButton) {
        generateButton.disabled = selected.length === 0 || selected.length > MAX_GENERATE;
        generateButton.textContent = selected.length
          ? `Generate ${selected.length} Selected Variant${selected.length === 1 ? '' : 's'}`
          : 'Generate selected variants';
      }
      if (previewMessage) {
        if (selected.length > MAX_GENERATE) previewMessage.textContent = `Select no more than ${MAX_GENERATE} new combinations in one batch.`;
        else if (selected.length) previewMessage.textContent = `${selected.length} new combination${selected.length === 1 ? '' : 's'} will be created. Existing SKUs remain unchanged.`;
        else previewMessage.textContent = 'Select at least one new combination to continue.';
      }
      previewBody?.querySelectorAll('.preview-row').forEach(row => {
        const choice = row.querySelector('input[data-preview-choice]');
        if (choice) row.classList.toggle('is-unselected', !choice.checked);
      });
    };

    const buildPreviewRow = inputs => {
      const signature = signatureFor(inputs);
      const existing = existingMap.get(signature);
      const row = document.createElement('tr');
      row.className = `preview-row${existing ? ' is-existing' : ''}`;

      const checkCell = document.createElement('td');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = signature;
      checkbox.setAttribute('aria-label', existing ? 'Existing combination' : 'Create combination');
      if (existing) {
        checkbox.disabled = true;
        checkbox.checked = false;
      } else {
        checkbox.checked = true;
        checkbox.dataset.previewChoice = '1';
        checkbox.addEventListener('change', refreshPreviewSelection);
      }
      checkCell.appendChild(checkbox);

      const comboCell = document.createElement('td');
      const title = document.createElement('span');
      title.className = 'preview-combo-title';
      title.textContent = inputs.map(input => input.dataset.valueLabel || input.value).join(' / ');
      const detail = document.createElement('span');
      detail.className = 'preview-combo-sub';
      detail.textContent = inputs.map(input => `${input.dataset.attributeName}: ${input.dataset.valueLabel}`).join(' · ');
      comboCell.append(title, detail);

      const statusCell = document.createElement('td');
      const status = document.createElement('span');
      status.className = `preview-status ${existing ? 'existing' : 'new'}`;
      status.textContent = existing ? 'Existing' : 'New';
      statusCell.appendChild(status);

      const skuCell = document.createElement('td');
      skuCell.textContent = existing?.sku || 'Auto-generated after confirmation';
      if (!existing) skuCell.className = 'muted';

      row.append(checkCell, comboCell, statusCell, skuCell);
      return { row, existing: Boolean(existing) };
    };

    const renderPreview = () => {
      const state = selectionState();
      if (!state.ready || state.total > MAX_PREVIEW || !previewBody) return;
      previewBody.replaceChildren();
      const combinations = combinationsFromGroups(state.groups);
      let existingCount = 0;
      combinations.forEach(inputs => {
        const result = buildPreviewRow(inputs);
        if (result.existing) existingCount += 1;
        previewBody.appendChild(result.row);
      });
      const newCount = combinations.length - existingCount;
      if (previewTotal) previewTotal.textContent = String(combinations.length);
      if (previewNew) previewNew.textContent = String(newCount);
      if (previewExisting) previewExisting.textContent = String(existingCount);
      if (previewPanel) previewPanel.hidden = false;
      refreshPreviewSelection();
      previewPanel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    toggles.forEach(toggle => {
      syncAttributeCard(toggle);
      toggle.addEventListener('change', () => {
        syncAttributeCard(toggle);
        resetPreview();
        updateSummary();
      });
    });

    form.querySelectorAll('input[name="value_ids"]').forEach(input => {
      input.addEventListener('change', () => {
        input.closest('[data-builder-value-card]')?.classList.toggle('is-selected', input.checked);
        resetPreview();
        updateSummary();
      });
    });

    previewButton?.addEventListener('click', renderPreview);
    selectAllNew?.addEventListener('click', () => {
      previewBody?.querySelectorAll('input[data-preview-choice]').forEach(input => { input.checked = true; });
      refreshPreviewSelection();
    });
    clearNew?.addEventListener('click', () => {
      previewBody?.querySelectorAll('input[data-preview-choice]').forEach(input => { input.checked = false; });
      refreshPreviewSelection();
    });

    toggleCards.forEach(card => {
      const checkbox = card.querySelector('[data-attribute-toggle]');
      card.classList.toggle('is-selected', Boolean(checkbox?.checked));
    });
    updateSummary();
  }

  const bulkForm = page.querySelector('[data-bulk-form]');
  if (bulkForm) {
    const rows = [...bulkForm.querySelectorAll('[data-bulk-row]')];
    const selectAll = bulkForm.querySelector('[data-bulk-select-all]');
    const search = bulkForm.querySelector('[data-bulk-search]');
    const actionSelect = bulkForm.querySelector('[data-bulk-action]');
    const actionValue = bulkForm.querySelector('[data-bulk-value]');
    const applyButton = bulkForm.querySelector('[data-bulk-apply]');
    const selectedCount = bulkForm.querySelector('[data-bulk-selected-count]');
    const feedback = bulkForm.querySelector('[data-bulk-feedback]');

    const rowSelection = row => row.querySelector('[data-bulk-row-select]');
    const visibleRows = () => rows.filter(row => !row.classList.contains('is-filtered'));
    const selectedRows = () => rows.filter(row => rowSelection(row)?.checked);

    const updateBulkSelection = () => {
      rows.forEach(row => row.classList.toggle('is-selected', Boolean(rowSelection(row)?.checked)));
      const selected = selectedRows().length;
      if (selectedCount) selectedCount.textContent = String(selected);
      if (selectAll) {
        const visible = visibleRows();
        const checkedVisible = visible.filter(row => rowSelection(row)?.checked).length;
        selectAll.checked = visible.length > 0 && checkedVisible === visible.length;
        selectAll.indeterminate = checkedVisible > 0 && checkedVisible < visible.length;
      }
    };

    rows.forEach(row => rowSelection(row)?.addEventListener('change', updateBulkSelection));

    selectAll?.addEventListener('change', () => {
      visibleRows().forEach(row => {
        const checkbox = rowSelection(row);
        if (checkbox) checkbox.checked = selectAll.checked;
      });
      updateBulkSelection();
    });

    search?.addEventListener('input', () => {
      const term = search.value.trim().toLowerCase();
      rows.forEach(row => {
        const text = row.dataset.searchText || '';
        row.classList.toggle('is-filtered', Boolean(term) && !text.includes(term));
      });
      updateBulkSelection();
    });

    const updateBulkValueState = () => {
      if (!actionValue || !actionSelect) return;
      const needsValue = ['regular', 'price', 'stock', 'low'].includes(actionSelect.value);
      actionValue.hidden = !needsValue;
      actionValue.disabled = !needsValue;
      actionValue.step = ['stock', 'low'].includes(actionSelect.value) ? '1' : '0.01';
    };
    actionSelect?.addEventListener('change', updateBulkValueState);
    updateBulkValueState();

    const showBulkFeedback = (message, error = false) => {
      if (!feedback) return;
      feedback.hidden = false;
      feedback.textContent = message;
      feedback.classList.toggle('error', error);
    };

    applyButton?.addEventListener('click', () => {
      const selected = selectedRows();
      const action = actionSelect?.value || '';
      if (!selected.length) {
        showBulkFeedback('Select at least one variant row first.', true);
        return;
      }
      if (!action) {
        showBulkFeedback('Choose a bulk action first.', true);
        return;
      }

      const needsValue = ['regular', 'price', 'stock', 'low'].includes(action);
      const rawValue = actionValue?.value?.trim() || '';
      if (needsValue && (rawValue === '' || Number(rawValue) < 0 || Number.isNaN(Number(rawValue)))) {
        showBulkFeedback('Enter a valid non-negative value for this bulk action.', true);
        return;
      }

      selected.forEach(row => {
        if (action === 'activate' || action === 'deactivate') {
          const active = row.querySelector('input[name^="active_"]');
          if (active) active.checked = action === 'activate';
          return;
        }
        const field = row.querySelector(`input[name^="${action}_"]`);
        if (field) field.value = rawValue;
      });
      showBulkFeedback(`Applied to ${selected.length} selected variant${selected.length === 1 ? '' : 's'}. Save Bulk Changes to commit these edits.`);
    });

    updateBulkSelection();
  }
})();
