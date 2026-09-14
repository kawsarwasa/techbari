(() => {
  const mainImage = document.getElementById('mainProductImage');
  if (!mainImage) return;

  const zoomStage = document.getElementById('productZoomStage');
  const lightboxImage = document.getElementById('productLightboxImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');

  const absoluteUrl = (value) => {
    if (!value) return '';
    try {
      return new URL(value, document.baseURI).href;
    } catch (_) {
      return value;
    }
  };

  const resetZoom = () => {
    zoomStage?.classList.remove('is-zooming');
    mainImage.style.removeProperty('transform');
    mainImage.style.transformOrigin = '50% 50%';
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

  const firstThumbImage = () => {
    if (!thumbHost) return null;
    const active = thumbHost.querySelector('.thumb.active img');
    return active || thumbHost.querySelector('.thumb img');
  };

  // Keep the initial hero image synchronized with the visible gallery instead of
  // starting on a separate detail/close-up asset.
  const initialThumb = firstThumbImage();
  if (initialThumb?.src && absoluteUrl(initialThumb.src) !== absoluteUrl(mainImage.src)) {
    mainImage.src = initialThumb.src;
  }
  syncGalleryState();

  // Dynamic variant galleries replace thumbnails after Color/attribute changes.
  // Any main-image src change must return to a full, unzoomed image first.
  const imageObserver = new MutationObserver((mutations) => {
    if (!mutations.some((mutation) => mutation.type === 'attributes' && mutation.attributeName === 'src')) return;
    syncGalleryState();
  });
  imageObserver.observe(mainImage, { attributes: true, attributeFilter: ['src'] });

  if (thumbHost) {
    thumbHost.addEventListener('click', (event) => {
      const thumb = event.target.closest('.thumb');
      if (!thumb || !thumbHost.contains(thumb)) return;
      const image = thumb.querySelector('img');
      if (!image?.src) return;
      // Run after the existing gallery handler so this becomes the final UI state.
      requestAnimationFrame(() => {
        if (absoluteUrl(mainImage.src) !== absoluteUrl(image.src)) mainImage.src = image.src;
        syncGalleryState();
      });
    });
  }
})();
