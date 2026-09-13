(() => {
  const root = document.querySelector('[data-product-media-manager]');
  if (!root) return;

  const csrf = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  const productId = root.dataset.productId || '';
  const productName = root.dataset.productName || 'Product image';
  const mediaUrl = root.dataset.mediaUrl || window.location.pathname;
  const uploadUrl = root.dataset.uploadUrl || '';
  const maxImages = Number(root.dataset.maxImages || 24);
  const currentCount = Number(root.dataset.currentCount || 0);
  const maxBytes = 2 * 1024 * 1024;
  const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);

  const input = root.querySelector('[data-media-file-input]');
  const dropzone = root.querySelector('[data-media-dropzone]');
  const previewGrid = root.querySelector('[data-media-upload-previews]');
  const uploadButton = root.querySelector('[data-media-upload-button]');
  const uploadFeedback = root.querySelector('[data-media-upload-feedback]');
  let selectedFiles = [];
  let previewUrls = [];

  const formatBytes = bytes => `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  const setFeedback = (message, error = false) => {
    if (!uploadFeedback) return;
    uploadFeedback.textContent = message;
    uploadFeedback.classList.toggle('error', error);
  };

  const clearPreviewUrls = () => {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
  };

  const validateFile = file => {
    if (!allowedTypes.has(file.type)) return 'Only JPG, PNG and WebP are allowed.';
    if (file.size > maxBytes) return 'Image must be 2MB or smaller.';
    return '';
  };

  const renderPreviews = () => {
    if (!previewGrid) return;
    clearPreviewUrls();
    previewGrid.replaceChildren();
    previewGrid.hidden = selectedFiles.length === 0;
    selectedFiles.forEach((file, index) => {
      const error = validateFile(file);
      const url = URL.createObjectURL(file);
      previewUrls.push(url);
      const card = document.createElement('div');
      card.className = `media-upload-preview${error ? ' is-error' : ''}`;
      const image = document.createElement('img');
      image.src = url;
      image.alt = '';
      const name = document.createElement('strong');
      name.textContent = file.name;
      const meta = document.createElement('small');
      meta.textContent = error || formatBytes(file.size);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'icon-btn';
      remove.title = 'Remove from upload';
      remove.setAttribute('aria-label', 'Remove from upload');
      remove.textContent = '×';
      remove.style.position = 'absolute';
      remove.style.top = '5px';
      remove.style.right = '5px';
      remove.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        selectedFiles.splice(index, 1);
        renderPreviews();
      });
      card.append(image, name, meta, remove);
      previewGrid.appendChild(card);
    });

    const validCount = selectedFiles.filter(file => !validateFile(file)).length;
    const overCapacity = currentCount + validCount > maxImages;
    if (uploadButton) uploadButton.disabled = !validCount || selectedFiles.some(file => validateFile(file)) || overCapacity;
    if (overCapacity) {
      setFeedback(`Only ${Math.max(0, maxImages - currentCount)} more image${maxImages - currentCount === 1 ? '' : 's'} can be added to this product.`, true);
    } else if (selectedFiles.some(file => validateFile(file))) {
      setFeedback('Remove the invalid files before uploading.', true);
    } else if (validCount) {
      setFeedback(`${validCount} image${validCount === 1 ? '' : 's'} ready to upload.`);
    } else {
      setFeedback('');
    }
  };

  const acceptFiles = files => {
    selectedFiles = [...files];
    renderPreviews();
  };

  input?.addEventListener('change', () => acceptFiles(input.files || []));
  ['dragenter', 'dragover'].forEach(type => dropzone?.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.add('is-dragover');
  }));
  ['dragleave', 'drop'].forEach(type => dropzone?.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.remove('is-dragover');
  }));
  dropzone?.addEventListener('drop', event => acceptFiles(event.dataTransfer?.files || []));

  uploadButton?.addEventListener('click', async () => {
    if (!productId || !uploadUrl) return;
    const invalid = selectedFiles.find(file => validateFile(file));
    if (invalid || !selectedFiles.length || currentCount + selectedFiles.length > maxImages) return;
    uploadButton.disabled = true;
    let uploaded = 0;
    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index];
      setFeedback(`Uploading ${index + 1} of ${selectedFiles.length}: ${file.name}`);
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrf);
      data.append('product', productId);
      data.append('image', file, file.name);
      data.append('attribute_value', '');
      data.append('alt_text', productName);
      data.append('role', 'gallery');
      data.append('sort_order', String(currentCount + index));
      try {
        const response = await fetch(uploadUrl, { method: 'POST', body: data, credentials: 'same-origin' });
        if (!response.ok || !response.redirected || !response.url.includes('/product-media/')) {
          setFeedback(`${uploaded} uploaded. ${file.name} was rejected by the server.`, true);
          uploadButton.disabled = false;
          return;
        }
        uploaded += 1;
      } catch (error) {
        setFeedback(`${uploaded} uploaded. Upload stopped because of a network error.`, true);
        uploadButton.disabled = false;
        return;
      }
    }
    window.location.assign(`${mediaUrl}${mediaUrl.includes('?') ? '&' : '?'}notice=saved`);
  });

  const cards = () => [...root.querySelectorAll('[data-media-card]')];
  const selectedCards = () => cards().filter(card => card.querySelector('[data-media-select]')?.checked);
  const selectAll = root.querySelector('[data-media-select-all]');
  const selectedCount = root.querySelector('[data-media-selected-count]');
  const bulkDelete = root.querySelector('[data-media-bulk-delete]');
  const saveOrder = root.querySelector('[data-media-save-order]');
  const orderFeedback = root.querySelector('[data-media-order-feedback]');

  const syncSelection = () => {
    const all = cards();
    const selected = selectedCards();
    all.forEach(card => card.classList.toggle('is-selected', Boolean(card.querySelector('[data-media-select]')?.checked)));
    if (selectedCount) selectedCount.textContent = String(selected.length);
    if (bulkDelete) bulkDelete.disabled = selected.length === 0;
    if (selectAll) {
      selectAll.checked = all.length > 0 && selected.length === all.length;
      selectAll.indeterminate = selected.length > 0 && selected.length < all.length;
    }
  };

  cards().forEach(card => card.querySelector('[data-media-select]')?.addEventListener('change', syncSelection));
  selectAll?.addEventListener('change', () => {
    cards().forEach(card => {
      const checkbox = card.querySelector('[data-media-select]');
      if (checkbox) checkbox.checked = selectAll.checked;
    });
    syncSelection();
  });
  syncSelection();

  const menus = [...root.querySelectorAll('.media-card-menu')];
  menus.forEach(menu => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) return;
      menus.forEach(other => {
        if (other !== menu) other.open = false;
      });
    });
  });
  document.addEventListener('click', event => {
    if (event.target.closest('.media-card-menu')) return;
    menus.forEach(menu => { menu.open = false; });
  });

  bulkDelete?.addEventListener('click', async () => {
    const selected = selectedCards();
    if (!selected.length || !window.confirm(`Delete ${selected.length} selected image${selected.length === 1 ? '' : 's'}? This cannot be undone.`)) return;
    bulkDelete.disabled = true;
    for (const card of selected) {
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrf);
      data.append('action', 'delete');
      data.append('image_id', card.dataset.imageId || '');
      try {
        const response = await fetch(mediaUrl, { method: 'POST', body: data, credentials: 'same-origin' });
        if (!response.ok) throw new Error('Delete failed');
      } catch (error) {
        window.alert('Some images could not be deleted. Refresh the page and try again.');
        bulkDelete.disabled = false;
        return;
      }
    }
    window.location.assign(`${mediaUrl}${mediaUrl.includes('?') ? '&' : '?'}notice=deleted`);
  });

  let dragged = null;
  let orderDirty = false;
  cards().forEach(card => {
    card.addEventListener('dragstart', event => {
      if (!productId || event.target.closest('button,a,input,summary,details,label')) {
        event.preventDefault();
        return;
      }
      dragged = card;
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('is-dragging');
      cards().forEach(item => item.classList.remove('drag-target'));
      dragged = null;
    });
    card.addEventListener('dragover', event => {
      if (!dragged || dragged === card) return;
      event.preventDefault();
      card.classList.add('drag-target');
      const rect = card.getBoundingClientRect();
      const before = event.clientY < rect.top + rect.height / 2;
      card.parentElement.insertBefore(dragged, before ? card : card.nextSibling);
      orderDirty = true;
      if (saveOrder) saveOrder.disabled = false;
    });
    card.addEventListener('dragleave', () => card.classList.remove('drag-target'));
  });

  saveOrder?.addEventListener('click', async () => {
    if (!orderDirty) return;
    saveOrder.disabled = true;
    if (orderFeedback) orderFeedback.textContent = 'Saving image order…';
    const ordered = cards();
    for (let index = 0; index < ordered.length; index += 1) {
      const card = ordered[index];
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrf);
      data.append('product', card.dataset.productId || productId);
      data.append('attribute_value', card.dataset.attributeValueId || '');
      data.append('alt_text', card.dataset.altText || '');
      data.append('role', card.dataset.role || 'gallery');
      data.append('sort_order', String(index * 10));
      try {
        const response = await fetch(card.dataset.editUrl || '', { method: 'POST', body: data, credentials: 'same-origin' });
        if (!response.ok || !response.redirected) throw new Error('Order save failed');
      } catch (error) {
        if (orderFeedback) orderFeedback.textContent = 'Could not save the full order. Refresh and try again.';
        saveOrder.disabled = false;
        return;
      }
    }
    orderDirty = false;
    if (orderFeedback) orderFeedback.textContent = 'Image order saved.';
  });
})();