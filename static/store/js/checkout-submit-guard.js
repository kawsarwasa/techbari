(() => {
  const form = document.getElementById('checkoutForm');
  const errorNode = document.getElementById('checkoutClientError');
  if (!form) return;

  // app.js registers its legacy demo Place Order handler from its
  // DOMContentLoaded callback. Because app.js is loaded before this file, its
  // callback runs first. Clone the button immediately afterwards so the demo
  // listener is genuinely removed, while checkout-v160's delegated document
  // handler continues to work with the replacement button.
  function removeLegacyPlaceOrderHandler() {
    const currentButton = document.getElementById('placeOrder');
    if (!currentButton || currentButton.dataset.checkoutSubmitGuarded === '1') return;
    const cleanButton = currentButton.cloneNode(true);
    cleanButton.dataset.checkoutSubmitGuarded = '1';
    currentButton.replaceWith(cleanButton);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', removeLegacyPlaceOrderHandler, { once: true });
  } else {
    removeLegacyPlaceOrderHandler();
  }

  function showError(message, target = null) {
    if (errorNode) {
      errorNode.textContent = message;
      errorNode.hidden = false;
      errorNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    if (target) {
      const searchableInput = document.getElementById(`${target.id}_search`);
      window.setTimeout(() => (searchableInput || target).focus(), 0);
    }
  }

  function clearError() {
    if (!errorNode) return;
    errorNode.textContent = '';
    errorNode.hidden = true;
  }

  function checked(name) {
    return form.querySelector(`input[name="${name}"]:checked`);
  }

  // checkout-v160 creates the searchable controls later in the same page load.
  // Typing a label that is not the currently selected option clears the native
  // value so a user cannot submit text that was never actually selected.
  window.setTimeout(() => {
    ['id_division', 'id_district', 'id_upazila'].forEach((selectId) => {
      const select = document.getElementById(selectId);
      const input = document.getElementById(`${selectId}_search`);
      if (!select || !input) return;
      input.addEventListener('input', () => {
        const selected = select.options[select.selectedIndex];
        const selectedLabel = selected && selected.value ? selected.textContent.trim() : '';
        if (input.value.trim() !== selectedLabel) select.value = '';
      });
    });
  }, 0);

  form.addEventListener('submit', (event) => {
    clearError();

    const requiredFields = [
      ['id_full_name', 'Enter your full name.'],
      ['id_phone', 'Enter your phone number.'],
      ['id_division', 'Select a Division from the list.'],
      ['id_district', 'Select a District from the list.'],
      ['id_upazila', 'Select an Upazila / Thana from the list.'],
      ['id_address', 'Enter your delivery address.'],
    ];

    for (const [id, message] of requiredFields) {
      const field = document.getElementById(id);
      if (!field || !String(field.value || '').trim()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        showError(message, field);
        return;
      }
    }

    if (!checked('delivery_option')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      showError('Select a delivery option.');
      return;
    }

    if (!checked('payment_method')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      showError('Select an available payment method.');
      return;
    }

    const cartPayload = document.getElementById('checkoutCartPayload');
    let cart = [];
    try {
      cart = JSON.parse(cartPayload?.value || '[]');
    } catch (_) {
      cart = [];
    }
    if (!Array.isArray(cart) || !cart.length) {
      event.preventDefault();
      event.stopImmediatePropagation();
      showError('Your cart is empty. Add a product before placing an order.');
    }
  }, true);
})();
