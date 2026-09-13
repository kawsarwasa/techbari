(() => {
  const page = document.querySelector('.variant-builder-v2');
  if (!page) return;

  const steps = [...page.querySelectorAll('.builder-progress-step')];
  const lines = [...page.querySelectorAll('.builder-progress-line')];
  const generator = page.querySelector('[data-variant-generator]');
  const previewPanel = page.querySelector('[data-preview-panel]');

  const setProgress = activeIndex => {
    steps.forEach((step, index) => {
      step.classList.toggle('is-active', index === activeIndex);
      step.classList.toggle('is-complete', index < activeIndex);
    });
    lines.forEach((line, index) => line.classList.toggle('is-complete', index < activeIndex));
  };

  const attributesReady = () => {
    if (!generator) return false;
    const toggles = [...generator.querySelectorAll('[data-attribute-toggle]:checked')];
    if (!toggles.length) return false;
    return toggles.every(toggle => {
      const group = generator.querySelector(`[data-builder-attribute][data-attribute-id="${toggle.value}"]`);
      return Boolean(group?.querySelector('input[name="value_ids"]:checked:not(:disabled)'));
    });
  };

  const syncProgress = () => {
    if (!generator) {
      setProgress(0);
      return;
    }
    if (previewPanel && !previewPanel.hidden) {
      setProgress(3);
      return;
    }
    setProgress(attributesReady() ? 2 : 1);
  };

  generator?.addEventListener('change', () => window.requestAnimationFrame(syncProgress));
  generator?.querySelector('[data-preview-button]')?.addEventListener('click', () => {
    window.setTimeout(syncProgress, 0);
  });
  if (previewPanel) {
    new MutationObserver(syncProgress).observe(previewPanel, { attributes: true, attributeFilter: ['hidden'] });
  }

  syncProgress();
})();
