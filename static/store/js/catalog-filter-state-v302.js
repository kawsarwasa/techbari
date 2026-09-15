(() => {
  const grid = document.getElementById('allProductsGrid');
  if (!grid) return;

  const allCategories = document.querySelector('[data-catalog-category-all]');
  const allBrands = document.querySelector('[data-catalog-brand-all]');
  const categoryChecks = [...document.querySelectorAll('[data-catalog-category]')];
  const brandChecks = [...document.querySelectorAll('[data-catalog-brand]')];
  const availabilityChecks = [...document.querySelectorAll('[data-catalog-availability]')];
  const search = document.getElementById('productSearch');
  const sort = document.getElementById('catalogSort');
  const clearButton = document.querySelector('[data-catalog-clear]');
  const initialParams = new URLSearchParams(window.location.search);
  const activeSearchQuery = (initialParams.get('q') || '').trim();

  const availabilityByValue = new Map(availabilityChecks.map((box) => [box.value, box]));
  const inStock = availabilityByValue.get('in');
  const outOfStock = availabilityByValue.get('out');

  const triggerApply = (controls) => {
    const control = controls.find(Boolean);
    if (control) control.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const syncAllControl = (allControl, itemControls) => {
    if (!allControl) return;
    allControl.checked = !itemControls.some((box) => box.checked);
  };

  const setAll = (allControl, itemControls) => {
    itemControls.forEach((box) => { box.checked = false; });
    if (allControl) allControl.checked = true;
    triggerApply(itemControls);
  };

  const selectedParams = (params, key) => {
    const values = params.getAll(key).flatMap((value) => value.split(',')).map((value) => value.trim()).filter(Boolean);
    return new Set(values);
  };

  const syncUrl = () => {
    const params = new URLSearchParams();
    const q = (search?.value || activeSearchQuery).trim();
    if (q) params.set('q', q);

    categoryChecks.filter((box) => box.checked).forEach((box) => params.append('category', box.value));
    brandChecks.filter((box) => box.checked).forEach((box) => params.append('brand', box.value));

    const selectedAvailability = availabilityChecks.filter((box) => box.checked).map((box) => box.value);
    const isDefaultAvailability = selectedAvailability.length === 1 && selectedAvailability[0] === 'in';
    if (!isDefaultAvailability) {
      selectedAvailability.forEach((value) => params.append('availability', value));
      if (!selectedAvailability.length) params.set('availability', 'none');
    }

    if (sort?.value && sort.value !== 'featured') params.set('sort', sort.value);

    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash || ''}`;
    window.history.replaceState({}, '', nextUrl);
  };

  const params = initialParams;
  const categoriesFromUrl = selectedParams(params, 'category');
  const brandsFromUrl = selectedParams(params, 'brand');

  if (categoriesFromUrl.size) {
    categoryChecks.forEach((box) => { box.checked = categoriesFromUrl.has(box.value); });
  }
  if (brandsFromUrl.size) {
    brandChecks.forEach((box) => { box.checked = brandsFromUrl.has(box.value); });
  }

  if (params.has('availability')) {
    const availabilityFromUrl = selectedParams(params, 'availability');
    availabilityChecks.forEach((box) => { box.checked = availabilityFromUrl.has(box.value); });
  } else {
    if (inStock) inStock.checked = true;
    if (outOfStock) outOfStock.checked = false;
  }

  const sortFromUrl = params.get('sort');
  if (sort && sortFromUrl && [...sort.options].some((option) => option.value === sortFromUrl)) {
    sort.value = sortFromUrl;
  }

  syncAllControl(allCategories, categoryChecks);
  syncAllControl(allBrands, brandChecks);

  allCategories?.addEventListener('change', () => {
    if (!allCategories.checked) {
      if (!categoryChecks.some((box) => box.checked)) allCategories.checked = true;
      return;
    }
    setAll(allCategories, categoryChecks);
    syncUrl();
  });

  allBrands?.addEventListener('change', () => {
    if (!allBrands.checked) {
      if (!brandChecks.some((box) => box.checked)) allBrands.checked = true;
      return;
    }
    setAll(allBrands, brandChecks);
    syncUrl();
  });

  categoryChecks.forEach((box) => {
    box.addEventListener('change', () => {
      syncAllControl(allCategories, categoryChecks);
      syncUrl();
    });
  });

  brandChecks.forEach((box) => {
    box.addEventListener('change', () => {
      syncAllControl(allBrands, brandChecks);
      syncUrl();
    });
  });

  availabilityChecks.forEach((box) => box.addEventListener('change', syncUrl));
  search?.addEventListener('input', syncUrl);
  sort?.addEventListener('change', syncUrl);

  clearButton?.addEventListener('click', () => {
    // catalog-v110.js clears first; restore the desired storefront defaults afterwards.
    categoryChecks.forEach((box) => { box.checked = false; });
    brandChecks.forEach((box) => { box.checked = false; });
    if (allCategories) allCategories.checked = true;
    if (allBrands) allBrands.checked = true;
    if (inStock) inStock.checked = true;
    if (outOfStock) outOfStock.checked = false;
    triggerApply(availabilityChecks);
    syncUrl();
  });

  // Re-apply once after restoring URL/default state because catalog-v110.js initializes first.
  triggerApply([...categoryChecks, ...brandChecks, ...availabilityChecks]);
  syncUrl();
})();
