document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".role-add-refresh");
  if (!root) return;

  const modules = Array.from(root.querySelectorAll("[data-role-permission-group]"));
  const allInputs = Array.from(root.querySelectorAll('input[name="permissions"]'));
  const totalCount = root.querySelector("[data-role-total-count]");
  const emptySummary = root.querySelector("[data-role-empty-summary]");
  const search = root.querySelector("[data-role-permission-search]");

  const refreshModule = (module) => {
    const inputs = Array.from(module.querySelectorAll('input[name="permissions"]'));
    const selected = inputs.filter((input) => input.checked).length;
    const count = module.querySelector("[data-role-group-count]");
    const toggle = module.querySelector("[data-role-group-toggle]");
    if (count) count.textContent = selected;
    if (toggle) {
      const allSelected = inputs.length > 0 && selected === inputs.length;
      toggle.setAttribute("aria-checked", allSelected ? "true" : "false");
      toggle.classList.toggle("is-partial", selected > 0 && !allSelected);
    }

    const key = module.dataset.groupKey;
    const summary = root.querySelector(`[data-role-summary-row][data-group-key="${CSS.escape(key || "")}"]`);
    if (summary) {
      summary.hidden = selected === 0;
      const badge = summary.querySelector("b");
      if (badge) badge.textContent = selected;
    }
  };

  const refreshAll = () => {
    modules.forEach(refreshModule);
    const selected = allInputs.filter((input) => input.checked).length;
    if (totalCount) totalCount.textContent = selected;
    if (emptySummary) emptySummary.hidden = selected > 0;
  };

  const applySearch = () => {
    const query = (search?.value || "").trim().toLowerCase();
    modules.forEach((module) => {
      let visible = 0;
      module.querySelectorAll("[data-role-permission-item]").forEach((item) => {
        const haystack = `${module.dataset.groupName || ""} ${item.dataset.search || ""}`;
        const matches = !query || haystack.includes(query);
        item.hidden = !matches;
        if (matches) visible += 1;
      });
      module.hidden = visible === 0;
    });
  };

  root.addEventListener("change", (event) => {
    if (event.target.matches('input[name="permissions"]')) refreshAll();
  });

  root.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-role-group-toggle]");
    if (!toggle) return;
    const module = toggle.closest("[data-role-permission-group]");
    if (!module) return;
    const inputs = Array.from(module.querySelectorAll('input[name="permissions"]'));
    const allSelected = inputs.length > 0 && inputs.every((input) => input.checked);
    inputs.forEach((input) => {
      input.checked = !allSelected;
    });
    refreshAll();
  });

  search?.addEventListener("input", applySearch);
  refreshAll();
});
