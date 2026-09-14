(() => {
  const tbody = document.getElementById('cartItemsBody');
  if (!tbody) return;

  const trashIcon = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M3 6h18"></path>
      <path d="M8 6V4h8v2"></path>
      <path d="M19 6l-1 15H6L5 6"></path>
      <path d="M10 11v6"></path>
      <path d="M14 11v6"></path>
    </svg>`;

  const bindVariantSelect = (select) => {
    if (!select || select.dataset.cartVariantGuard === '1') return;
    select.dataset.cartVariantGuard = '1';
    select.addEventListener('click', (event) => {
      event.stopPropagation();
    });
  };

  const decorateRemoveButton = (button) => {
    if (!button || button.dataset.cartDeleteDecorated === '1') return;
    button.dataset.cartDeleteDecorated = '1';
    button.classList.add('cart-delete-icon');
    button.innerHTML = trashIcon;
    button.setAttribute('aria-label', 'Remove item');
    button.setAttribute('title', 'Remove item');
  };

  const mobileToolbar = document.getElementById('cartMobileToolbar');
  const mobileCountText = document.getElementById('mobileCartCountText');
  const summaryCount = document.getElementById('summaryItemCount');
  const desktopClear = document.getElementById('clearCart');
  const mobileClear = document.getElementById('mobileClearCart');

  const syncMobileToolbar = () => {
    const rowCount = tbody.querySelectorAll('tr[data-cart-id]').length;
    const parsed = Number(summaryCount?.textContent || 0);
    const count = Number.isFinite(parsed) ? parsed : rowCount;
    if (mobileCountText) mobileCountText.textContent = `${count} ${count === 1 ? 'Item' : 'Items'} in Cart`;
    if (mobileToolbar) mobileToolbar.hidden = rowCount === 0;
  };

  const refreshCartControls = () => {
    tbody.querySelectorAll('.variant-select').forEach(bindVariantSelect);
    tbody.querySelectorAll('[data-v110-remove], [data-remove-cart]').forEach(decorateRemoveButton);
    syncMobileToolbar();
  };

  mobileClear?.addEventListener('click', () => desktopClear?.click());

  refreshCartControls();

  new MutationObserver(refreshCartControls).observe(tbody, {
    childList: true,
    subtree: true,
  });

  if (summaryCount) {
    new MutationObserver(syncMobileToolbar).observe(summaryCount, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }
})();
