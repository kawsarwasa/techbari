(() => {
  const tabs = [...document.querySelectorAll('[data-v103-tab]')];
  const panels = [...document.querySelectorAll('[data-v103-panel]')];
  if (!tabs.length || !panels.length) return;

  const openTab = (name) => {
    tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.v103Tab === name));
    panels.forEach((panel) => panel.classList.toggle('active', panel.dataset.v103Panel === name));
  };

  tabs.forEach((tab) => tab.addEventListener('click', () => openTab(tab.dataset.v103Tab)));
})();
