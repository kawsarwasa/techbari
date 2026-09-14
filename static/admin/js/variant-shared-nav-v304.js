(() => {
  const path = window.location.pathname;
  if (!path.includes('/variants/')) return;

  const routes = document.getElementById('variantNavRoutes');
  if (!routes) return;

  const pageHead = document.querySelector('.page-head');
  if (!pageHead) return;

  let nav = pageHead.querySelector('.variant-nav') || pageHead.querySelector('.head-actions');
  if (!nav) {
    nav = document.createElement('nav');
    pageHead.appendChild(nav);
  }

  const params = new URLSearchParams(window.location.search);
  const product = params.get('product');
  const withProduct = (url) => product ? `${url}?product=${encodeURIComponent(product)}` : url;

  const items = [
    { key: 'products', label: 'Products', href: routes.dataset.productsUrl },
    { key: 'options', label: 'Variant Options', href: routes.dataset.optionsUrl },
    { key: 'builder', label: 'Build Variants', href: withProduct(routes.dataset.builderUrl) },
    { key: 'skus', label: 'SKU & Stock', href: withProduct(routes.dataset.skusUrl) },
  ];

  const activeKey = path.includes('/variants/attributes/') || path.includes('/variants/options/')
    ? 'options'
    : path.includes('/variants/builder/')
      ? 'builder'
      : path.includes('/variants/form/') || /\/variants\/?$/.test(path)
        ? 'skus'
        : '';

  nav.className = 'variant-nav variant-nav-shared';
  nav.setAttribute('aria-label', 'Variant management navigation');
  nav.replaceChildren();

  items.forEach((item) => {
    const link = document.createElement('a');
    link.className = `btn${item.key === activeKey ? ' is-active' : ''}`;
    link.href = item.href;
    link.textContent = item.label;
    if (item.key === activeKey) link.setAttribute('aria-current', 'page');
    nav.appendChild(link);
  });

  const heading = pageHead.querySelector('h1');
  if (heading) {
    const titles = {
      options: 'Variant Options',
      builder: 'Build Variants',
      skus: 'SKU & Stock',
    };
    if (titles[activeKey]) heading.textContent = titles[activeKey];
  }

  if (activeKey === 'options') document.title = 'Variant Options | TechBari Admin';
  if (activeKey === 'builder') document.title = 'Build Variants | TechBari Admin';
  if (activeKey === 'skus') document.title = 'SKU & Stock | TechBari Admin';
})();
