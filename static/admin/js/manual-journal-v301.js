(() => {
  const form = document.querySelector('[data-manual-journal-form]');
  if (!form) return;

  const rows = Array.from(form.querySelectorAll('[data-journal-line]'));
  const addButton = form.querySelector('[data-add-journal-line]');
  const debitTotal = form.querySelector('[data-total-debit]');
  const creditTotal = form.querySelector('[data-total-credit]');
  const difference = form.querySelector('[data-balance-difference]');
  const balanceBadge = form.querySelector('[data-balance-status]');
  const lineCount = form.querySelector('[data-visible-line-count]');
  const submitButton = form.querySelector('[data-post-journal]');

  const money = new Intl.NumberFormat('en-BD', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function numberValue(input) {
    if (!input) return 0;
    const parsed = Number.parseFloat(input.value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  }

  function visibleRows() {
    return rows.filter((row) => !row.classList.contains('is-hidden'));
  }

  function updateRemoveButtons() {
    const visible = visibleRows();
    rows.forEach((row) => {
      const button = row.querySelector('[data-remove-journal-line]');
      if (!button) return;
      button.disabled = row.classList.contains('is-hidden') || visible.length <= 2;
    });
    if (lineCount) lineCount.textContent = `${visible.length} lines`;
    if (addButton) addButton.disabled = visible.length >= rows.length;
  }

  function updateBalance() {
    let debit = 0;
    let credit = 0;
    visibleRows().forEach((row) => {
      debit += numberValue(row.querySelector('input[name="debit"]'));
      credit += numberValue(row.querySelector('input[name="credit"]'));
    });

    const diff = Math.abs(debit - credit);
    const hasAmounts = debit > 0 || credit > 0;
    const balanced = hasAmounts && diff < 0.005;

    if (debitTotal) debitTotal.textContent = `৳${money.format(debit)}`;
    if (creditTotal) creditTotal.textContent = `৳${money.format(credit)}`;
    if (difference) difference.textContent = `৳${money.format(diff)}`;

    if (balanceBadge) {
      balanceBadge.classList.remove('is-neutral', 'is-good', 'is-bad');
      if (!hasAmounts) {
        balanceBadge.classList.add('is-neutral');
        balanceBadge.textContent = 'Waiting for entries';
      } else if (balanced) {
        balanceBadge.classList.add('is-good');
        balanceBadge.textContent = 'Balanced';
      } else {
        balanceBadge.classList.add('is-bad');
        balanceBadge.textContent = 'Not balanced';
      }
    }

    if (submitButton) submitButton.disabled = !balanced;
  }

  function resetRow(row) {
    row.querySelectorAll('input').forEach((input) => {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    row.querySelectorAll('select').forEach((select) => {
      select.selectedIndex = 0;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  if (addButton) {
    addButton.addEventListener('click', () => {
      const next = rows.find((row) => row.classList.contains('is-hidden'));
      if (!next) return;
      next.classList.remove('is-hidden');
      next.setAttribute('aria-hidden', 'false');
      updateRemoveButtons();
      updateBalance();
      const firstControl = next.querySelector('select, input');
      if (firstControl) firstControl.focus({ preventScroll: true });
    });
  }

  rows.forEach((row) => {
    row.addEventListener('input', updateBalance);
    row.addEventListener('change', updateBalance);
    const removeButton = row.querySelector('[data-remove-journal-line]');
    if (removeButton) {
      removeButton.addEventListener('click', () => {
        if (visibleRows().length <= 2) return;
        resetRow(row);
        row.classList.add('is-hidden');
        row.setAttribute('aria-hidden', 'true');
        updateRemoveButtons();
        updateBalance();
      });
    }
  });

  updateRemoveButtons();
  updateBalance();
})();