(() => {
  const root = document.querySelector('[data-purchase-items]');
  const template = document.querySelector('#purchase-item-template');
  const addButton = document.querySelector('[data-add-purchase-row]');
  if (!root || !template || !addButton) return;

  const wireRow = (row) => {
    const remove = row.querySelector('[data-remove-purchase-row]');
    if (!remove) return;
    remove.addEventListener('click', () => {
      const rows = root.querySelectorAll('[data-purchase-row]');
      if (rows.length <= 1) {
        row.querySelectorAll('input').forEach((input) => {
          if (input.name === 'ordered_quantity') input.value = '1';
          else if (input.name === 'unit_cost') input.value = '0.00';
          else input.value = '';
        });
        const select = row.querySelector('select');
        if (select) select.value = '';
        return;
      }
      row.remove();
    });
  };

  root.querySelectorAll('[data-purchase-row]').forEach(wireRow);
  addButton.addEventListener('click', () => {
    const fragment = template.content.cloneNode(true);
    const row = fragment.querySelector('[data-purchase-row]');
    root.appendChild(fragment);
    wireRow(row);
  });
})();