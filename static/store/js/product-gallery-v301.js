(() => {
  const stage = document.getElementById('productZoomStage');
  const mainImage = document.getElementById('mainProductImage');
  const lightboxImage = document.getElementById('productLightboxImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');
  const storeNode = document.getElementById('store-data');
  if (!stage || !mainImage) return;

  let product = null;
  if (storeNode) {
    try {
      const data = JSON.parse(storeNode.textContent || '{}');
      product = (data.products || []).find((row) => String(row.id) === String(data.current_product)) || null;
    } catch (_) {
      product = null;
    }
  }

  const absoluteUrl = (url) => {
    if (!url) return '';
    try {
      return new URL(url, window.location.href).href;
    } catch (_) {
      return url;
    }
  };

  const uniqueUrls = (urls) => {
    const seen = new Set();
    const result = [];
    urls.filter(Boolean).forEach((url) => {
      const key = absoluteUrl(url);
      if (!key || seen.has(key)) return;
      seen.add(key);
      result.push(url);
    });
    return result;
  };

  const groupedUrls = product?.image_groups
    ? Object.values(product.image_groups).flat().filter(Boolean)
    : [];
  const galleryUrls = uniqueUrls([
    ...(product?.images || []),
    ...groupedUrls,
    product?.image_url,
  ]);

  const resetZoom = () => {
    stage.classList.remove('is-zooming');
    mainImage.style.transformOrigin = '50% 50%';
  };

  const setActiveThumb = () => {
    if (!thumbHost) return;
    const current = absoluteUrl(mainImage.currentSrc || mainImage.src);
    [...thumbHost.querySelectorAll('.thumb')].forEach((thumb) => {
      const image = thumb.querySelector('img');
      const url = absoluteUrl(image?.currentSrc || image?.src || '');
      thumb.classList.toggle('active', Boolean(current && url && current === url));
    });
  };

  const setMainImage = (url) => {
    if (!url) return;
    resetZoom();
    mainImage.src = url;
    if (lightboxImage) lightboxImage.src = url;
    setActiveThumb();
  };

  const currentThumbUrls = () => {
    if (!thumbHost) return [];
    return [...thumbHost.querySelectorAll('.thumb img')]
      .map((image) => absoluteUrl(image.currentSrc || image.src || ''))
      .filter(Boolean);
  };

  const renderAllThumbs = () => {
    if (!thumbHost || !galleryUrls.length) return;
    const expected = galleryUrls.map(absoluteUrl);
    const current = currentThumbUrls();
    const same = current.length === expected.length && current.every((url, index) => url === expected[index]);

    if (!same) {
      const fragment = document.createDocumentFragment();
      galleryUrls.forEach((url, index) => {
        const thumb = document.createElement('button');
        thumb.type = 'button';
        thumb.className = 'thumb';
        thumb.setAttribute('aria-label', `View product image ${index + 1}`);

        const image = document.createElement('img');
        image.src = url;
        image.alt = `${product?.short_name || product?.name || 'Product'} thumbnail ${index + 1}`;
        thumb.appendChild(image);
        thumb.addEventListener('click', () => setMainImage(url));
        fragment.appendChild(thumb);
      });
      thumbHost.replaceChildren(fragment);
    }

    setActiveThumb();
  };

  stage.addEventListener('pointerenter', (event) => {
    if (event.pointerType === 'mouse') stage.classList.add('is-zooming');
  });

  stage.addEventListener('pointermove', (event) => {
    if (event.pointerType !== 'mouse' || !stage.classList.contains('is-zooming')) return;
    const rect = stage.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100));
    mainImage.style.transformOrigin = `${x}% ${y}%`;
  });

  stage.addEventListener('pointerleave', resetZoom);

  mainImage.addEventListener('load', () => {
    resetZoom();
    if (lightboxImage) lightboxImage.src = mainImage.src;
    renderAllThumbs();
  });

  if (thumbHost) {
    new MutationObserver(() => {
      resetZoom();
      renderAllThumbs();
    }).observe(thumbHost, { childList: true, subtree: true });
  }

  renderAllThumbs();
})();
