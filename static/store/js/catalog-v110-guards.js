(() => {
  const node = document.getElementById('store-data');
  if (!node) return;
  const data = JSON.parse(node.textContent || '{}');

  document.addEventListener('DOMContentLoaded', () => {
    const products = data.products || [];
    const current = products.find((product) => String(product.id) === String(data.current_product));

    if (current) {
      document.addEventListener('click', (event) => {
        const button = event.target.closest('#productQtyPlus, #productQtyMinus');
        if (!button) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const qty = document.getElementById('productQty');
        if (!qty) return;
        const selectedName = document.querySelector('.swatch.active')?.dataset.variant;
        const variant = (current.variants || []).find((item) => item.name === selectedName)
          || (current.variants || []).find((item) => item.is_default)
          || (current.variants || [])[0];
        const max = Math.max(1, Number(variant?.stock) || 0);
        const value = Number(qty.textContent) || 1;
        qty.textContent = String(button.id === 'productQtyPlus' ? Math.min(max, value + 1) : Math.max(1, value - 1));
      }, true);
    }

    const slider = document.getElementById('catalogPriceRange');
    if (slider) {
      const listing = data.listing_products || products;
      const highest = Math.max(0, ...listing.map((product) => Number(product.price) || 0));
      const max = Math.max(10000, Math.ceil(highest / 1000) * 1000);
      slider.max = String(max);
      slider.value = String(max);
      const label = document.getElementById('catalogPriceValue');
      if (label) label.textContent = `Up to ৳ ${max.toLocaleString('en-BD')}`;
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
})();
