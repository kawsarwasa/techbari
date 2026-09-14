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
    return values.filter((value) => {
      const normalized = absoluteUrl(value);
      if (!normalized || seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
  };

  // General/common product media should remain available beside a selected
  // Color gallery. detail_image_url is included because the presentation layer
  // historically kept Detail-role media outside product.images.
  const commonImageUrls = uniqueUrls([
    product?.image_url,
    ...(product?.images || []),
    product?.detail_image_url,
  ]);

  const resetZoom = () => {
    zoomStage?.classList.remove('is-zooming');
    mainImage.style.transform = 'scale(1)';
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

  let normalizingThumbs = false;
  const ensureCommonThumbnails = () => {
    if (!thumbHost || normalizingThumbs || !commonImageUrls.length) return;

    const existing = new Set(
      [...thumbHost.querySelectorAll('.thumb img')]
        .map((image) => absoluteUrl(image.src))
        .filter(Boolean),
    );
    const missing = commonImageUrls.filter((url) => !existing.has(absoluteUrl(url)));
    if (!missing.length) return;

    normalizingThumbs = true;
    const startIndex = thumbHost.querySelectorAll('.thumb').length;
    missing.forEach((url, offset) => thumbHost.appendChild(createThumb(url, startIndex + offset)));
    normalizingThumbs = false;
  };

  const firstThumbImage = () => {
    if (!thumbHost) return null;
    const active = thumbHost.querySelector('.thumb.active img');
    return active || thumbHost.querySelector('.thumb img');
  };

  ensureCommonThumbnails();

  // Keep the initial hero image synchronized with the visible gallery instead of
  // starting on a separate close-up asset. The image is always full-size/contain
  // before any desktop hover zoom begins.
  const initialThumb = firstThumbImage();
  if (initialThumb?.src && absoluteUrl(initialThumb.src) !== absoluteUrl(mainImage.src)) {
    mainImage.src = initialThumb.src;
  }
  syncGalleryState();

  // Dynamic variant galleries replace thumbnails after Color/attribute changes.
  // Re-append General/common images without leaking images mapped to other colors.
  if (thumbHost) {
    const thumbObserver = new MutationObserver((mutations) => {
      if (normalizingThumbs || !mutations.some((mutation) => mutation.type === 'childList')) return;
      requestAnimationFrame(() => {
        ensureCommonThumbnails();
        syncActiveThumbnail(mainImage.src);
      });
    });
    thumbObserver.observe(thumbHost, { childList: true });
  }

  // Any main-image src change must return to a full, unzoomed image first.
  const imageObserver = new MutationObserver((mutations) => {
    if (!mutations.some((mutation) => mutation.type === 'attributes' && mutation.attributeName === 'src')) return;
    syncGalleryState();
  });
  imageObserver.observe(mainImage, { attributes: true, attributeFilter: ['src'] });
  mainImage.addEventListener('load', syncGalleryState);

  if (thumbHost) {
    thumbHost.addEventListener('click', (event) => {
      const thumb = event.target.closest('.thumb');
      if (!thumb || !thumbHost.contains(thumb)) return;
      const image = thumb.querySelector('img');
      if (!image?.src) return;

      // Run after the existing/static or structured-variant gallery handler so
      // this becomes the final synchronized UI state.
      requestAnimationFrame(() => {
        if (absoluteUrl(mainImage.src) !== absoluteUrl(image.src)) mainImage.src = image.src;
        syncGalleryState();
      });
    });
  }
})();
