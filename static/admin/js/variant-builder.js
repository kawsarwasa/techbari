(() => {
  const page = document.querySelector('.variant-builder-page');
  if (!page) return;

  const form = document.querySelector('[data-variant-generator]');
  const summary = document.querySelector('[data-combination-summary]');
  const countNode = document.querySelector('[data-combination-count]');
  const generateLabel = document.querySelector('[data-generate-label]');

  const updateCount = () => {
    if (!form) return;
    const groups = [...form.querySelectorAll('[data-builder-attribute]')];
    let total = groups.length ? 1 : 0;
    let ready = groups.length > 0;
    groups.forEach(group => {
      const selected = group.querySelectorAll('input[name="value_ids"]:checked').length;
      if (!selected) ready = false;
      total *= selected || 1;
    });
    if (!ready) total = 0;
    if (countNode) countNode.textContent = String(total);
    if (summary) summary.dataset.ready = ready ? '1' : '0';
    if (generateLabel) generateLabel.textContent = ready ? `Generate ${total} Variant${total === 1 ? '' : 's'}` : 'Select values to generate';
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = !ready || total > 250;
  };

  form?.querySelectorAll('input[name="value_ids"]').forEach(input => input.addEventListener('change', updateCount));
  updateCount();

  const productSelect = document.querySelector('[data-builder-product]');
  const presetSelect = document.querySelector('[data-builder-preset]');
  const navigate = () => {
    const url = new URL(window.location.href);
    if (productSelect?.value) url.searchParams.set('product', productSelect.value); else url.searchParams.delete('product');
    if (presetSelect?.value) url.searchParams.set('preset', presetSelect.value); else url.searchParams.delete('preset');
    url.searchParams.delete('notice');
    url.searchParams.delete('created');
    url.searchParams.delete('reused');
    url.searchParams.delete('skipped');
    window.location.assign(url.toString());
  };
  productSelect?.addEventListener('change', navigate);
  presetSelect?.addEventListener('change', navigate);
})();
