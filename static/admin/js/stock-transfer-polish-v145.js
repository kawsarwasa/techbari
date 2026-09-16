(() => {
  const source = document.querySelector('#id_from_warehouse');
  const destination = document.querySelector('#id_to_warehouse');
  const message = document.querySelector('[data-transfer-route-message]');
  const submitButtons = [...document.querySelectorAll('[data-complete-transfer]')];
  if (!source || !destination) return;

  const syncSearchable = (select) => select._tbSearchable?.syncInput?.();
  const resetDisabled = (select) => {
    [...select.options].forEach((option) => { option.disabled = false; });
  };
  const disableValue = (select, value) => {
    if (!value) return;
    const option = [...select.options].find((row) => row.value === value);
    if (option) option.disabled = true;
  };

  const renderState = () => {
    resetDisabled(source);
    resetDisabled(destination);

    const sourceValue = source.value;
    let destinationValue = destination.value;

    if (sourceValue && destinationValue && sourceValue === destinationValue) {
      destination.value = '';
      destinationValue = '';
      syncSearchable(destination);
    }

    disableValue(destination, sourceValue);
    disableValue(source, destinationValue);

    const ready = Boolean(sourceValue && destinationValue && sourceValue !== destinationValue);
    submitButtons.forEach((button) => {
      button.disabled = !ready;
      button.setAttribute('aria-disabled', ready ? 'false' : 'true');
      button.title = ready ? '' : 'Choose two different warehouses first.';
    });

    if (!message) return;
    message.classList.toggle('is-ready', ready);
    const copy = message.querySelector('[data-transfer-route-copy]');
    if (!copy) return;
    if (ready) {
      copy.textContent = 'Source and destination are different. Add the SKU quantities to complete the transfer.';
    } else if (sourceValue) {
      copy.textContent = 'Choose a destination warehouse different from the source.';
    } else {
      copy.textContent = 'Choose the source and destination warehouses. They must be different.';
    }
  };

  source.addEventListener('change', renderState);
  destination.addEventListener('change', renderState);
  renderState();
})();