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

  const availableValues = (select) => [...select.options]
    .filter((option) => option.value && !option.disabled)
    .map((option) => option.value);

  const selectOnlyRemainingWarehouse = (select) => {
    if (select.value) return false;
    const values = availableValues(select);
    if (values.length !== 1) return false;
    select.value = values[0];
    syncSearchable(select);
    return true;
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

    let autoSelected = false;
    if (sourceValue && !destinationValue) {
      autoSelected = selectOnlyRemainingWarehouse(destination);
      destinationValue = destination.value;
    } else if (destinationValue && !sourceValue) {
      autoSelected = selectOnlyRemainingWarehouse(source);
      sourceValue = source.value;
    }

    if (autoSelected) {
      resetDisabled(source);
      resetDisabled(destination);
      sourceValue = source.value;
      destinationValue = destination.value;
      disableValue(destination, sourceValue);
      disableValue(source, destinationValue);
    }

    syncSearchable(source);
    syncSearchable(destination);

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

  source.addEventListener('change', () => renderState(source));
  destination.addEventListener('change', () => renderState(destination));
  renderState();
})();