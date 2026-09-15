(() => {
  const menu = document.querySelector('[data-category-menu]');
  if (!menu) return;

  const trigger = menu.querySelector('[data-category-menu-trigger]');
  const panel = menu.querySelector('[data-category-menu-panel]');
  if (!trigger || !panel) return;

  const submenuItems = [...panel.querySelectorAll('[data-category-menu-item]')];

  const setSubmenuOpen = (item, open) => {
    const toggle = item.querySelector('[data-category-submenu-toggle]');
    const submenu = item.querySelector('[data-category-submenu]');
    if (!toggle || !submenu) return;
    item.classList.toggle('is-submenu-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    submenu.hidden = !open;
  };

  const closeSubmenus = (except = null) => {
    submenuItems.forEach((item) => {
      if (item !== except) setSubmenuOpen(item, false);
    });
  };

  const setOpen = (open, focusFirst = false) => {
    menu.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.hidden = !open;
    if (!open) closeSubmenus();
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
    const submenuToggle = event.target.closest('[data-category-submenu-toggle]');
    if (submenuToggle) {
      const item = submenuToggle.closest('[data-category-menu-item]');
      if (!item) return;
      const willOpen = !item.classList.contains('is-submenu-open');
      closeSubmenus(item);
      setSubmenuOpen(item, willOpen);
      return;
    }
    if (event.target.closest('a')) setOpen(false);
  });

  document.addEventListener('pointerdown', (event) => {
    if (!menu.contains(event.target)) setOpen(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !menu.classList.contains('is-open')) return;
    const openSubmenu = submenuItems.find((item) => item.classList.contains('is-submenu-open'));
    if (openSubmenu) {
      setSubmenuOpen(openSubmenu, false);
      openSubmenu.querySelector('[data-category-submenu-toggle]')?.focus();
      return;
    }
    setOpen(false);
    trigger.focus();
  });
})();
