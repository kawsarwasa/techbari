(() => {
  const form = document.getElementById('checkoutForm');
  const currentButton = document.getElementById('placeOrder');
  const errorNode = document.getElementById('checkoutClientError');
  if (!form || !currentButton) return;

  // app.js still binds a legacy demo click handler directly to #placeOrder.
  // Replacing the node removes that stale listener before the real checkout
  // controller is initialized, while preserving the button markup/attributes.
  const submitButton = currentButton.cloneNode(true);
  currentButton.replaceWith(submitButton);

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
