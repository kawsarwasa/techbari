(() => {
  const path = window.location.pathname;
  const marker = '/dashboard/';
  const markerIndex = path.indexOf(marker);
  if (markerIndex < 0) return;

  const dashboardBase = `${path.slice(0, markerIndex)}${marker}`;
  const relativePath = path
    .slice(markerIndex + marker.length)
    .replace(/^\/+|\/+$/g, '');

  if (!relativePath) return;

  const firstSegment = relativePath.split('/')[0];
  const rules = [
    { label: 'Inventory', home: 'inventory', segments: ['inventory', 'warehouses', 'stock-transfer', 'stock-adjustment'] },
    { label: 'Purchases', home: 'purchases', segments: ['purchases', 'suppliers'] },
    { label: 'Customers', home: 'customers', segments: ['customers'] },
    { label: 'Orders', home: 'orders', segments: ['orders'] },
    { label: 'Shipping', home: 'shipping', segments: ['shipping'] },
    { label: 'Returns', home: 'returns', segments: ['returns', 'warranty'] },
    { label: 'Payments', home: 'payments', segments: ['payments'] },
    { label: 'Accounts', home: 'accounts', segments: ['accounts'] },
    { label: 'Expenses', home: 'expenses', segments: ['expenses'] },
    { label: 'Marketing', home: 'marketing', segments: ['marketing', 'coupons'] },
    { label: 'Users', home: 'users', segments: ['users', 'audit-log'] },
    { label: 'Settings', home: 'settings', segments: ['settings'] },
    { label: 'Products', home: 'products', segments: ['products', 'brands', 'categories', 'variants', 'product-media', 'specifications', 'serials'] },
    { label: 'POS', home: 'pos', segments: ['pos'] },
  ];

  const rule = rules.find((item) => item.segments.includes(firstSegment));
  if (!rule) return;

  const normalizePath = (value) => {
    try {
      return new URL(value, window.location.origin).pathname.replace(/\/+$/, '') || '/';
    } catch (error) {
      return String(value || '').replace(/\/+$/, '') || '/';
    }
  };

  const parentHref = `${dashboardBase}${rule.home}/`;
  const normalizedParent = normalizePath(parentHref);
  const normalizedCurrent = normalizePath(path);

  // The module landing page itself does not need a back-to-self button.
  if (normalizedCurrent === normalizedParent) return;

  const header = document.querySelector('.page-head, .detail-head');
  if (!header) return;

  let actions = header.querySelector('.head-actions');
  if (!actions) {
    actions = document.createElement('div');
    actions.className = 'head-actions';
    header.appendChild(actions);
  }

  const links = [...actions.querySelectorAll('a[href]')];
  let parentLink = links.find((link) => normalizePath(link.getAttribute('href')) === normalizedParent);

  if (parentLink) {
    parentLink.textContent = `← ${rule.label}`;
    parentLink.setAttribute('aria-label', `Back to ${rule.label}`);
    parentLink.dataset.moduleParentNavigation = 'true';
    return;
  }

  parentLink = document.createElement('a');
  parentLink.className = 'btn';
  parentLink.href = parentHref;
  parentLink.textContent = `← ${rule.label}`;
  parentLink.setAttribute('aria-label', `Back to ${rule.label}`);
  parentLink.dataset.moduleParentNavigation = 'true';
  actions.prepend(parentLink);
})();
