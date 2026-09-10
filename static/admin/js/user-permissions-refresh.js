document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".user-form-refresh");
  if (!root) return;

  const search = root.querySelector("[data-permission-search]");
  const modules = Array.from(root.querySelectorAll("[data-permission-group]"));
  const allInputs = Array.from(root.querySelectorAll('input[name="extra_permissions"]'));
  const totalCount = root.querySelector("[data-permission-count]");

  const refreshCounts = () => {
    if (totalCount) totalCount.textContent = allInputs.filter((input) => input.checked).length;
    modules.forEach((module) => {
      const count = module.querySelector("[data-group-count]");
      if (!count) return;
      count.textContent = module.querySelectorAll('input[name="extra_permissions"]:checked').length;
    });
  };

  const applySearch = () => {
    const query = (search?.value || "").trim().toLowerCase();
    modules.forEach((module) => {
      let visible = 0;
      module.querySelectorAll("[data-permission-item]").forEach((item) => {
        const haystack = `${item.dataset.search || ""} ${module.dataset.groupName || ""}`;
        const match = !query || haystack.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      module.hidden = visible === 0;
    });
  };

  root.addEventListener("change", (event) => {
    if (event.target.matches('input[name="extra_permissions"]')) refreshCounts();
  });

  root.addEventListener("click", (event) => {
    const selectButton = event.target.closest("[data-select-group]");
    const clearButton = event.target.closest("[data-clear-group]");
    const button = selectButton || clearButton;
    if (!button) return;

    const module = button.closest("[data-permission-group]");
    if (!module) return;
    const checked = Boolean(selectButton);
    module.querySelectorAll('[data-permission-item]:not([hidden]) input[name="extra_permissions"]').forEach((input) => {
      input.checked = checked;
    });
    refreshCounts();
  });

  search?.addEventListener("input", applySearch);
  refreshCounts();
});
