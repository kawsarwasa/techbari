(() => {
  const role = document.querySelector('#mediaForm select[name="role"]');
  if (!role) return;

  role.dataset.searchableSelect = 'false';
  if (role._tbSearchable?.destroy) role._tbSearchable.destroy();
  role.classList.remove('tb-native-select-hidden');
})();
