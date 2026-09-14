(() => {
  const menus = [...document.querySelectorAll('.product-action-menu')];
  if (!menus.length) return;

  const closeAll = (except = null) => {
    menus.forEach((menu) => {
      if (menu !== except) menu.removeAttribute('open');
    });
  };

  menus.forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (menu.open) closeAll(menu);
    });
  });

  document.addEventListener('pointerdown', (event) => {
    if (menus.some((menu) => menu.contains(event.target))) return;
    closeAll();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAll();
  });

  document.querySelectorAll('.product-action-dropdown a').forEach((link) => {
    link.addEventListener('click', () => closeAll());
  });
})();
