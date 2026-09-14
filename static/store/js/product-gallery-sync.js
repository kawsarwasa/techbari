(() => {
  const mainImage = document.getElementById('mainProductImage');
  if (!mainImage) return;

  const zoomStage = document.getElementById('productZoomStage');
  const lightboxImage = document.getElementById('productLightboxImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');
  const storeNode = document.getElementById('store-data');

  let product = null;
  try {
    const data = JSON.parse(storeNode?.textContent || '{}');
    product = (data.products || []).find(
      (row) => String(row.id) === String(data.current_product),
    ) || null;
  } catch (_) {
    product = null;
  }

  const absoluteUrl = (value) => {
    if (!value) return '';
    try {
      return new URL(value, document.baseURI).href;
    } catch (_) {
      return value;
    }
  };

  const uniqueUrls = (values) => {
    const seen = new Set();
    const urls = [];
    (values || []).forEach((value) => {
      const normalized = absoluteUrl(value);
      if (!normalized || seen.has(normalized)) return;
      seen.add(normalized);
      urls.push(value);
    });
    return urls;
  };

  const groups = product?.image_groups || {};
  const hasMappedGroups = Object.values(groups).some((urls) => Array.isArray(urls) && urls.length);
  const commonImageUrls = uniqueUrls(
    product?.general_images?.length
      ? product.general_images
      : (!hasMappedGroups
        ? [product?.image_url, ...(product?.images || []), product?.detail_image_url]
        : []),
  );

  const selectedMappedUrls = () => {
    const activeValues = [
      ...document.querySelectorAll('.structured-variant-option.active[data-structured-value]'),
    ].map((control) => control.dataset.structuredValue).filter(Boolean);

    const selectedValues = [
      ...document.querySelectorAll('select[data-structured-attribute]'),
    ].map((select) => select.value).filter(Boolean);

    for (const valueId of [...activeValues, ...selectedValues]) {
      const urls = groups[String(valueId)] || [];
      if (urls.length) return urls;
    }
    return [];
  };

  const desiredUrls = () => {
    const mapped = selectedMappedUrls();
    const combined = uniqueUrls([...mapped, ...commonImageUrls]);
    if (combined.length) return combined;
    return uniqueUrls([
      ...(product?.images || []),
      product?.image_url,
      product?.detail_image_url,
    ]);
  };

  const resetZoom = () => {
    zoomStage?.classList.remove('is-zooming');
    // Never pin transform inline: the stylesheet must be free to apply
    // .is-zooming { transform: scale(...) } on mouse hover.
    mainImage.style.removeProperty('transform');
    mainImage.style.transformOrigin = '50% 50%';
    mainImage.style.objectFit = 'contain';
    mainImage.style.objectPosition = '50% 50%';
  };

  const syncActiveThumbnail = (src) => {
    if (!thumbHost) return;
    const current = absoluteUrl(src);
    [...thumbHost.querySelectorAll('.thumb')].forEach((thumb) => {
      const image = thumb.querySelector('img');
      thumb.classList.toggle('active', absoluteUrl(image?.src) === current);
    });
  };

  const syncGalleryState = () => {
    resetZoom();
    if (lightboxImage) lightboxImage.src = mainImage.src;
    syncActiveThumbnail(mainImage.src);
  };

  const createThumb = (url, index) => {
    const thumb = document.createElement('button');
    thumb.type = 'button';
    thumb.className = 'thumb';
    thumb.setAttribute('aria-label', `View product image ${index + 1}`);

    const image = document.createElement('img');
    image.src = url;
    image.alt = `${product?.short_name || product?.name || 'Product'} thumbnail ${index + 1}`;
    thumb.appendChild(image);
    return thumb;
  };

  const sameUrlList = (left, right) => (
    left.length === right.length
    && left.every((value, index) => absoluteUrl(value) === absoluteUrl(right[index]))
  );

  let normalizingThumbs = false;
  const normalizeGallery = ({ preferFirst = false } = {}) => {
    const urls = desiredUrls();
    if (!urls.length) {
      syncGalleryState();
      return;
    }

    if (thumbHost) {
      const currentUrls = [...thumbHost.querySelectorAll('.thumb img')].map((image) => image.src);
      if (!sameUrlList(currentUrls, urls)) {
        normalizingThumbs = true;
        thumbHost.replaceChildren(...urls.map((url, index) => createThumb(url, index)));
        normalizingThumbs = false;
      }
    }

    const allowed = new Set(urls.map(absoluteUrl));
    if (preferFirst || !allowed.has(absoluteUrl(mainImage.src))) {
      mainImage.src = urls[0];
    }
    syncGalleryState();
  };

  // Initial product image should match the first gallery item and be fully visible.
  normalizeGallery({ preferFirst: true });

  if (thumbHost) {
    const thumbObserver = new MutationObserver((mutations) => {
      if (normalizingThumbs || !mutations.some((mutation) => mutation.type === 'childList')) return;
      // Structured variant rendering rebuilds the thumbnail list. Normalize after it finishes.
      requestAnimationFrame(() => normalizeGallery());
    });
    thumbObserver.observe(thumbHost, { childList: true });

    thumbHost.addEventListener('click', (event) => {
      const thumb = event.target.closest('.thumb');
      if (!thumb || !thumbHost.contains(thumb)) return;
      const image = thumb.querySelector('img');
      if (!image?.src) return;

      requestAnimationFrame(() => {
        if (absoluteUrl(mainImage.src) !== absoluteUrl(image.src)) mainImage.src = image.src;
        syncGalleryState();
      });
    });
  }

  // Color/attribute controls can change before the structured gallery finishes rebuilding.
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-structured-value]')) return;
    requestAnimationFrame(() => requestAnimationFrame(() => normalizeGallery()));
  });
  document.addEventListener('change', (event) => {
    if (!event.target.matches('select[data-structured-attribute]')) return;
    requestAnimationFrame(() => normalizeGallery());
  });

  const imageObserver = new MutationObserver((mutations) => {
    if (!mutations.some((mutation) => mutation.type === 'attributes' && mutation.attributeName === 'src')) return;
    syncGalleryState();
  });
  imageObserver.observe(mainImage, { attributes: true, attributeFilter: ['src'] });
  mainImage.addEventListener('load', syncGalleryState);
})();
