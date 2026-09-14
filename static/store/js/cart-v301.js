(() => {
  const tbody = document.getElementById('cartItemsBody');
  if (!tbody) return;

  const bindVariantSelect = (select) => {
    if (!select || select.dataset.cartVariantGuard === '1') return;
    select.dataset.cartVariantGuard = '1';

    // The legacy cart handler also listens on the cart tbody and redraws rows
    // on every click. Stop the select click at the control so the native menu
    // can stay open while catalog-v110.js remains the authoritative cart engine.
    select.addEventListener('click', (event) => {
      event.stopPropagation();
    });
  };

  const bindVariantSelects = () => {
    tbody.querySelectorAll('.variant-select').forEach(bindVariantSelect);
  };

  bindVariantSelects();

  new MutationObserver(bindVariantSelects).observe(tbody, {
    childList: true,
    subtree: true,
  });
})();
