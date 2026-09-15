(() => {
  const menu = document.querySelector('[data-category-menu]');
  if (!menu) return;

  const trigger = menu.querySelector('[data-category-menu-trigger]');
  const panel = menu.querySelector('[data-category-menu-panel]');
  if (!trigger || !panel) return;

  const setOpen = (open, focusFirst = false) => {
    menu.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.hidden = !open;
    if (open && focusFirst) {
      requestAnimationFrame(() => panel.querySelector('a')?.focus());
    }
  };

  trigger.addEventListener('click', () => {
    setOpen(!menu.classList.contains('is-open'));
  });

  trigger.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true, true);
    }
  });

  panel.addEventListener('click', (event) => {
    if (event.target.closest('a')) setOpen(false);
  });

  document.addEventListener('pointerdown', (event) => {
    if (!menu.contains(event.target)) setOpen(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !menu.classList.contains('is-open')) return;
    setOpen(false);
    trigger.focus();
  });
})();
