(() => {
  const grid = document.querySelector('[data-home-featured-grid]');
  const dataNode = document.getElementById('home-featured-collections');
  const tabs = [...document.querySelectorAll('[data-home-featured-tab]')];
  const viewAll = document.querySelector('[data-home-featured-view-all]');
  if (!grid || !dataNode || !tabs.length || !viewAll) return;

  let collections = {};
  try {
    collections = JSON.parse(dataNode.textContent || '{}');
  } catch (_) {
    collections = {};
  }

  const renderCollection = (key) => {
    const ids = Array.isArray(collections[key]) ? collections[key] : [];
    const fragment = document.createDocumentFragment();

    ids.forEach((id) => {
      const template = document.getElementById(`product-card-${id}`);
      if (template?.content) fragment.appendChild(template.content.cloneNode(true));
    });

    grid.replaceChildren(fragment);
    if (!grid.children.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No products in this collection yet.';
      grid.appendChild(empty);
    }

    if (typeof renderIcons === 'function') renderIcons(grid);
    if (typeof syncWishlistButtons === 'function') syncWishlistButtons(grid);

    tabs.forEach((tab) => {
      const active = tab.dataset.homeFeaturedTab === key;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    const productsUrl = viewAll.dataset.productsUrl || '/products/';
    viewAll.href = `${productsUrl}?collection=${encodeURIComponent(key)}`;
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => renderCollection(tab.dataset.homeFeaturedTab));
  });
})();
