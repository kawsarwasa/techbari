(() => {
  const stage = document.getElementById('productZoomStage');
  const mainImage = document.getElementById('mainProductImage');
  const lightboxImage = document.getElementById('productLightboxImage');
  const thumbHost = document.querySelector('.product-thumbs, .thumbs');
  if (!stage || !mainImage) return;

  const resetZoom = () => {
    stage.classList.remove('is-zooming');
    mainImage.style.transformOrigin = '50% 50%';
  };

  const dedupeThumbs = () => {
    if (!thumbHost) return;
    const seen = new Set();
    [...thumbHost.querySelectorAll('.thumb')].forEach((thumb) => {
      const image = thumb.querySelector('img');
      const url = image?.currentSrc || image?.src || '';
      if (!url) return;
      if (seen.has(url)) thumb.remove();
      else seen.add(url);
    });

    const thumbs = [...thumbHost.querySelectorAll('.thumb')];
    if (thumbs.length && !thumbs.some((thumb) => thumb.classList.contains('active'))) {
      thumbs[0].classList.add('active');
    }
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

  const syncImageState = () => {
    resetZoom();
    if (lightboxImage) lightboxImage.src = mainImage.src;
    dedupeThumbs();
  };

  mainImage.addEventListener('load', syncImageState);

  if (thumbHost) {
    new MutationObserver(() => {
      resetZoom();
      dedupeThumbs();
    }).observe(thumbHost, { childList: true, subtree: true });
  }

  dedupeThumbs();
})();
