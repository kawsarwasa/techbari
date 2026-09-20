(() => {
  const root = document.querySelector('[data-ie-entry-form]');
  if (!root) return;
  const category = root.querySelector('select[name="category"]');
  const amount = root.querySelector('input[name="amount"]');
  const initial = root.querySelector('input[name="initial_amount"]');
  const accountWrap = root.querySelector('[data-ie-account]');
  const referenceWrap = root.querySelector('[data-ie-reference]');
  const partialWrap = root.querySelector('[data-ie-partial]');
  const dueWrap = root.querySelector('[data-ie-due]');
  const accountLabel = root.querySelector('[data-ie-account-label]');
  const initialLabel = root.querySelector('[data-ie-initial-label]');
  const checked = (name) => root.querySelector(`input[name="${name}"]:checked`)?.value || '';

  const syncCategories = () => {
    if (!category) return;
    const type = checked('entry_type');
    [...category.options].forEach((option) => {
      if (!option.value) return;
      const matches = option.dataset.entryType === type;
      option.hidden = !matches;
      option.disabled = !matches;
    });
    if (category.selectedOptions[0]?.disabled) category.value = '';
  };

  const syncPayment = () => {
    const type = checked('entry_type');
    const status = checked('settlement_status');
    const due = status === 'due';
    const partial = status === 'partial';
    if (accountWrap) accountWrap.hidden = due;
    if (referenceWrap) referenceWrap.hidden = due;
    if (partialWrap) partialWrap.hidden = !partial;
    if (dueWrap) dueWrap.hidden = status === 'paid';
    if (accountLabel) accountLabel.textContent = type === 'income' ? 'Received In' : 'Paid From';
    if (initialLabel) initialLabel.textContent = type === 'income' ? 'Received Now' : 'Paid Now';
    if (initial) {
      if (status === 'paid' && amount?.value) initial.value = amount.value;
      if (due) initial.value = '';
    }
  };

  root.querySelectorAll('input[name="entry_type"]').forEach(radio => radio.addEventListener('change', () => { syncCategories(); syncPayment(); }));
  root.querySelectorAll('input[name="settlement_status"]').forEach(radio => radio.addEventListener('change', syncPayment));
  amount?.addEventListener('input', () => {
    if (checked('settlement_status') === 'paid' && initial) initial.value = amount.value;
  });
  syncCategories();
  syncPayment();
})();
