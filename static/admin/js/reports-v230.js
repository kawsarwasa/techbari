(() => {
  const select = document.querySelector('[data-report-type-select]');
  if (!select) return;

  select.addEventListener('change', () => {
    const target = select.value;
    if (target) window.location.assign(target);
  });
})();
