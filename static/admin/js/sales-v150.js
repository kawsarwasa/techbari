(() => {
  const table = document.querySelector('[data-sales-items]');
  const addButton = document.querySelector('[data-sales-add-row]');
  if (!table || !addButton) return;

  const wireRow = (row) => {
    const select = row.querySelector('select[name="variant_id"]');
    const price = row.querySelector('input[name="unit_price"]');
    const remove = row.querySelector('[data-sales-remove-row]');

    if (select && price) {
      select.addEventListener('change', () => {
        const option = select.options[select.selectedIndex];
        if (option && option.dataset.price && !price.value) price.value = option.dataset.price;
      });
    }
    if (remove) {
      remove.addEventListener('click', () => {
        const rows = table.querySelectorAll('[data-sales-row]');
        if (rows.length > 1) row.remove();
      });
    }
  };

  table.querySelectorAll('[data-sales-row]').forEach(wireRow);

  addButton.addEventListener('click', () => {
    const source = table.querySelector('[data-sales-row]');
    if (!source) return;
    const row = source.cloneNode(true);
    const select = row.querySelector('select[name="variant_id"]');
    const quantity = row.querySelector('input[name="quantity"]');
    const price = row.querySelector('input[name="unit_price"]');
    const discount = row.querySelector('input[name="line_discount"]');
    if (select) select.value = '';
    if (quantity) quantity.value = '1';
    if (price) price.value = '';
    if (discount) discount.value = '0.00';
    table.appendChild(row);
    wireRow(row);
  });
})();
