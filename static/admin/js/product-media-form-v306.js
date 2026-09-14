(() => {
  const form = document.getElementById('mediaForm');
  if (!form) return;

  const role = form.querySelector('select[name="role"]');
  if (role) {
    role.dataset.searchableSelect = 'false';
    if (role._tbSearchable?.destroy) role._tbSearchable.destroy();
    role.classList.remove('tb-native-select-hidden');
  }

  const fileInput = form.querySelector('#id_image');
  const replaceControl = document.getElementById('mediaReplaceControl');
  const removeChoice = document.getElementById('mediaRemoveChoice');
  const removeCheckbox = document.getElementById('removeCurrentImage');
  const removeWarning = document.getElementById('mediaRemoveWarning');

  if (!fileInput || !removeCheckbox || !removeChoice || !replaceControl) return;

  const syncMediaChoice = () => {
    const removing = removeCheckbox.checked;
    const replacing = fileInput.files && fileInput.files.length > 0;

    if (removing) {
      fileInput.value = '';
      fileInput.disabled = true;
      replaceControl.hidden = true;
      removeChoice.hidden = false;
      if (removeWarning) removeWarning.hidden = false;
      return;
    }

    fileInput.disabled = false;
    replaceControl.hidden = false;
    removeChoice.hidden = replacing;
    if (removeWarning) removeWarning.hidden = true;
  };

  removeCheckbox.addEventListener('change', syncMediaChoice);
  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      removeCheckbox.checked = false;
    }
    syncMediaChoice();
  });

  form.addEventListener('submit', () => {
    if (!removeCheckbox.checked) return;

    const deleteUrl = form.dataset.deleteUrl;
    const imageId = form.dataset.imageId;
    if (!deleteUrl || !imageId) return;

    fileInput.value = '';
    fileInput.disabled = true;
    form.action = deleteUrl;

    let actionInput = form.querySelector('input[name="action"]');
    if (!actionInput) {
      actionInput = document.createElement('input');
      actionInput.type = 'hidden';
      actionInput.name = 'action';
      form.appendChild(actionInput);
    }
    actionInput.value = 'delete';

    let imageIdInput = form.querySelector('input[name="image_id"]');
    if (!imageIdInput) {
      imageIdInput = document.createElement('input');
      imageIdInput.type = 'hidden';
      imageIdInput.name = 'image_id';
      form.appendChild(imageIdInput);
    }
    imageIdInput.value = imageId;
  });

  syncMediaChoice();
})();
