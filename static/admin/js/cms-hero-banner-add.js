(function () {
  'use strict';

  const root = document.querySelector('[data-hero-banner-add]');
  if (!root) return;

  const byId = (id) => document.getElementById(id);
  const titleInput = byId('id_title');
  const eyebrowInput = byId('id_eyebrow');
  const descriptionInput = byId('id_description');
  const ctaInput = byId('id_cta_label');
  const imageInput = byId('id_image');
  const fallbackInput = byId('id_fallback_static');
  const activeInput = byId('id_is_active');

  const previewTitle = root.querySelector('[data-preview-title]');
  const previewEyebrow = root.querySelector('[data-preview-eyebrow]');
  const previewDescription = root.querySelector('[data-preview-description]');
  const previewCta = root.querySelector('[data-preview-cta]');
  const liveImage = root.querySelector('[data-live-image]');
  const livePreview = root.querySelector('[data-live-preview]');
  const statusLabel = root.querySelector('[data-status-label]');
  const statusCopy = root.querySelector('[data-status-copy]');

  const imagePreview = root.querySelector('[data-image-preview]');
  const imageEmpty = root.querySelector('[data-image-empty]');
  const imageMeta = root.querySelector('[data-image-meta]');
  const imageName = root.querySelector('[data-image-name]');
  const imageSize = root.querySelector('[data-image-size]');
  const uploadZone = root.querySelector('.hba-upload-zone');

  const existingImageUrl = (root.dataset.existingImageUrl || '').trim();
  const existingImageName = (root.dataset.existingImageName || '').trim();

  let uploadedObjectUrl = null;

  function textOr(input, fallback) {
    if (!input) return fallback;
    const value = (input.value || '').trim();
    return value || fallback;
  }

  function updateCopyPreview() {
    if (previewTitle) previewTitle.textContent = textOr(titleInput, 'Your banner title');
    if (previewEyebrow) previewEyebrow.textContent = textOr(eyebrowInput, 'Eyebrow');
    if (previewDescription) previewDescription.textContent = textOr(descriptionInput, 'Add a short description to preview it here.');
    if (previewCta) previewCta.textContent = textOr(ctaInput, 'CTA');
  }

  function setLiveImage(src) {
    if (!liveImage) return;
    if (src) {
      liveImage.src = src;
      liveImage.hidden = false;
    } else {
      liveImage.removeAttribute('src');
      liveImage.hidden = true;
    }
  }

  function setImagePreview(src, name, sizeText) {
    if (!src) return false;
    if (imagePreview) {
      imagePreview.src = src;
      imagePreview.hidden = false;
    }
    if (imageEmpty) imageEmpty.hidden = true;
    if (imageMeta) imageMeta.hidden = false;
    if (imageName) imageName.textContent = name || 'Current image';
    if (imageSize) imageSize.textContent = sizeText || 'Current image';
    setLiveImage(src);
    return true;
  }

  function humanFileSize(bytes) {
    if (!Number.isFinite(bytes)) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  }

  function showSelectedImage(file) {
    if (!file || !file.type || !file.type.startsWith('image/')) return;

    if (uploadedObjectUrl) URL.revokeObjectURL(uploadedObjectUrl);
    uploadedObjectUrl = URL.createObjectURL(file);
    setImagePreview(uploadedObjectUrl, file.name || 'Selected image', humanFileSize(file.size));
  }

  function fallbackUrl() {
    const path = textOr(fallbackInput, '');
    if (!path) return '';
    if (/^https?:\/\//i.test(path) || path.startsWith('/')) return path;
    return '/static/' + path.replace(/^\/+/, '');
  }

  function updateFallbackPreview() {
    if (imageInput && imageInput.files && imageInput.files.length) return;

    if (existingImageUrl) {
      setImagePreview(existingImageUrl, existingImageName || 'Current image', 'Current image');
      return;
    }

    const src = fallbackUrl();
    if (src) {
      setLiveImage(src);
    } else {
      setLiveImage('');
    }
  }

  function updateStatus() {
    const active = !activeInput || activeInput.checked;
    if (statusLabel) statusLabel.textContent = active ? 'Active' : 'Inactive';
    if (statusCopy) {
      statusCopy.textContent = active
        ? 'Banner can be shown when its visibility window is valid.'
        : 'Banner is disabled and will not be shown on the storefront.';
    }
  }

  [titleInput, eyebrowInput, descriptionInput, ctaInput].forEach((input) => {
    if (input) input.addEventListener('input', updateCopyPreview);
  });

  if (imageInput) {
    imageInput.addEventListener('change', function () {
      const file = this.files && this.files[0];
      if (file) showSelectedImage(file);
      else updateFallbackPreview();
    });
  }

  if (fallbackInput) fallbackInput.addEventListener('input', function () {
    if (!existingImageUrl) updateFallbackPreview();
  });
  if (activeInput) activeInput.addEventListener('change', updateStatus);

  if (uploadZone && imageInput) {
    ['dragenter', 'dragover'].forEach((eventName) => {
      uploadZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        uploadZone.classList.add('is-dragging');
      });
    });
    ['dragleave', 'drop'].forEach((eventName) => {
      uploadZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        uploadZone.classList.remove('is-dragging');
      });
    });
    uploadZone.addEventListener('drop', function (event) {
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (!file || !file.type.startsWith('image/')) return;
      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        imageInput.files = transfer.files;
      } catch (error) {
        // Some browsers do not allow programmatic file assignment; preview still works.
      }
      showSelectedImage(file);
    });
  }

  root.querySelectorAll('[data-preview-mode]').forEach((button) => {
    button.addEventListener('click', function () {
      root.querySelectorAll('[data-preview-mode]').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      if (livePreview) livePreview.classList.toggle('mobile', button.dataset.previewMode === 'mobile');
    });
  });

  window.addEventListener('beforeunload', function () {
    if (uploadedObjectUrl) URL.revokeObjectURL(uploadedObjectUrl);
  });

  updateCopyPreview();
  updateStatus();
  if (existingImageUrl) {
    setImagePreview(existingImageUrl, existingImageName || 'Current image', 'Current image');
  } else {
    updateFallbackPreview();
  }
})();
