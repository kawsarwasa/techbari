(function () {
  'use strict';

  const root = document.querySelector('[data-homepage-sections]');
  if (!root) return;

  const rows = Array.from(root.querySelectorAll('[data-section-select]'));
  const panels = Array.from(root.querySelectorAll('[data-section-panel]'));
  const previews = Array.from(root.querySelectorAll('[data-preview-section]'));
  const storefrontPreview = root.querySelector('[data-storefront-preview]');

  function getPanel(id) {
    return root.querySelector('[data-section-panel="' + id + '"]');
  }

  function selectSection(id) {
    rows.forEach((row) => {
      const active = row.dataset.sectionSelect === id;
      row.classList.toggle('active', active);
      row.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    panels.forEach((panel) => {
      const active = panel.dataset.sectionPanel === id;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });

    previews.forEach((preview) => {
      const active = preview.dataset.previewSection === id;
      preview.hidden = !active;
      preview.classList.toggle('active', active);
    });
  }

  rows.forEach((row) => {
    row.addEventListener('click', function (event) {
      if (event.target.closest('[data-section-toggle]')) return;
      selectSection(row.dataset.sectionSelect);
    });
  });

  root.querySelectorAll('[data-section-toggle]').forEach((toggle) => {
    toggle.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();

      const id = toggle.dataset.sectionToggle;
      const checkbox = root.querySelector('[data-enabled-input="' + id + '"]');
      if (!checkbox) return;

      checkbox.checked = !checkbox.checked;
      checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      selectSection(id);
    });
  });

  root.querySelectorAll('[data-enabled-input]').forEach((checkbox) => {
    function syncEnabledState() {
      const id = checkbox.dataset.enabledInput;
      const toggle = root.querySelector('[data-section-toggle="' + id + '"]');
      if (!toggle) return;
      toggle.classList.toggle('on', checkbox.checked);
      toggle.setAttribute('aria-checked', checkbox.checked ? 'true' : 'false');
    }

    checkbox.addEventListener('change', syncEnabledState);
    syncEnabledState();
  });

  root.querySelectorAll('[data-title-input]').forEach((input) => {
    function syncTitle() {
      const id = input.dataset.titleInput;
      const previewTitle = root.querySelector('[data-preview-title="' + id + '"]');
      const row = root.querySelector('[data-section-select="' + id + '"] .hps-section-copy strong');
      const value = (input.value || '').trim();
      if (previewTitle) previewTitle.textContent = value || 'Homepage Section';
      if (row && value) row.textContent = value;
    }

    input.addEventListener('input', syncTitle);
  });

  root.querySelectorAll('[data-order-input]').forEach((input) => {
    function syncOrder() {
      const id = input.dataset.orderInput;
      const order = root.querySelector('[data-section-select="' + id + '"] .hps-order');
      if (order) order.textContent = '# ' + ((input.value || '').trim() || '0');
    }

    input.addEventListener('input', syncOrder);
  });

  root.querySelectorAll('[data-preview-mode]').forEach((button) => {
    button.addEventListener('click', function () {
      root.querySelectorAll('[data-preview-mode]').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      if (storefrontPreview) storefrontPreview.classList.toggle('mobile', button.dataset.previewMode === 'mobile');
    });
  });

  const firstRow = rows[0];
  if (firstRow) selectSection(firstRow.dataset.sectionSelect);
})();
