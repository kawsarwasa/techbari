(() => {
  const storeNode = document.getElementById('store-data');
  if (!storeNode) return;

  let data;
  try {
    data = JSON.parse(storeNode.textContent || '{}');
  } catch (_) {
    return;
  }

  const currentId = data.current_product;
  if (!currentId) return;

  const product = (data.products || []).find(
    (row) => String(row.id) === String(currentId),
  );
  const options = product?.options || [];
  const variants = product?.variants || [];
  if (!product || options.length < 2 || variants.length < 2) return;

  const optionIds = options.map((option) => String(option.id));
  const isComplete = (variant) => {
    const present = new Set(
      (variant.values || []).map((row) => String(row.attribute_id)),
    );
    return optionIds.every((attributeId) => present.has(attributeId));
  };

  const completeVariants = variants.filter(isComplete);
  if (!completeVariants.length || completeVariants.length === variants.length) return;

  // Once a product uses multiple structured dimensions, storefront selection must
  // resolve to a complete exact SKU. Legacy one-dimensional rows remain in admin
  // history but are not offered as sellable combinations here.
  product.variants = completeVariants;
  storeNode.textContent = JSON.stringify(data);
})();
