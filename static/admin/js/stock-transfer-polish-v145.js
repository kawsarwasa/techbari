(() => {
  const source = document.querySelector('#id_from_warehouse');
  const destination = document.querySelector('#id_to_warehouse');
  const message = document.querySelector('[data-transfer-route-message]');
  const submitButtons = [...document.querySelectorAll('[data-complete-transfer]')];
  if (!source || !destination) return;

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
      // The shared searchable-select clears the native <select> when the
      // visible search input is cleared. Refresh the cross-field filtering
      // immediately so previously-disabled warehouses come back without a
      // full page reload. Close the stale open menu; the next click rebuilds
      // it from the freshly-enabled native options.
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
})();