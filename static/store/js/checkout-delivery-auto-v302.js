(() => {
  const form = document.getElementById('checkoutForm');
  const districtSelect = document.getElementById('id_district');
  const divisionSelect = document.getElementById('id_division');
  const deliveryOptions = [...document.querySelectorAll('.option[data-delivery]')];

  if (!form || !districtSelect || !deliveryOptions.length) return;

  const deliveryModeForDistrict = () => {
    const district = String(districtSelect.value || '').trim().toLocaleLowerCase();
    if (!district) return '';
    return district === 'dhaka' ? 'inside' : 'outside';
  };

  const syncDeliveryFromDistrict = (flash = false) => {
    const mode = deliveryModeForDistrict();

    deliveryOptions.forEach((option) => {
      const input = option.querySelector('input[name="delivery_option"]');
      const selected = Boolean(mode) && option.dataset.delivery === mode;

      option.classList.add('delivery-auto-locked');
      option.classList.toggle('active', selected);
      option.setAttribute('aria-disabled', 'true');

      if (input) {
        input.checked = selected;
        input.tabIndex = -1;
        input.setAttribute('aria-disabled', 'true');
      }
    });

    if (mode && typeof window.recalcCheckout === 'function') {
      window.recalcCheckout(flash);
      return;
    }

    if (!mode) {
      const label = document.getElementById('shippingLabel');
      const charge = document.getElementById('shippingCharge');
      if (label) label.textContent = 'Shipping Charge (select district)';
      if (charge) charge.textContent = '—';
    }
  };

  // Stop the legacy checkout handler from allowing a manual delivery-zone change.
  document.addEventListener('click', (event) => {
    const option = event.target.closest('.option[data-delivery]');
    if (!option || !form.contains(option)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    syncDeliveryFromDistrict(false);
  }, true);

  districtSelect.addEventListener('change', () => {
    window.setTimeout(() => syncDeliveryFromDistrict(true), 0);
  });

  divisionSelect?.addEventListener('change', () => {
    // checkout-v160.js rebuilds the district options first; run after it.
    window.setTimeout(() => syncDeliveryFromDistrict(true), 0);
  });

  syncDeliveryFromDistrict(false);

  // app.js initializes legacy checkout listeners on DOMContentLoaded. Re-sync once
  // afterwards so the district remains authoritative regardless of script order.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => syncDeliveryFromDistrict(false), { once: true });
  } else {
    window.setTimeout(() => syncDeliveryFromDistrict(false), 0);
  }
})();
