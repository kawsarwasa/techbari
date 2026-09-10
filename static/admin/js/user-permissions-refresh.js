document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".user-form-refresh");
  if (!root) return;

  const search = root.querySelector("[data-permission-search]");
  const modules = Array.from(root.querySelectorAll("[data-permission-group]"));
  const allInputs = Array.from(root.querySelectorAll('input[name="extra_permissions"]'));
  const totalCount = root.querySelector("[data-permission-count]");

  const buildModuleToggles = () => {
    modules.forEach((module) => {
      const actions = module.querySelector(".uf-perm-module-actions");
      if (!actions) return;

      actions.innerHTML = "";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "uf-module-toggle";
      toggle.setAttribute("role", "switch");
      toggle.setAttribute("aria-checked", "false");
      toggle.setAttribute("aria-label", `Toggle all ${module.dataset.groupName || "module"} permissions`);
      toggle.setAttribute("title", "Select all permissions in this module");
      toggle.dataset.groupToggle = "";
      toggle.innerHTML = '<span class="uf-module-toggle-track" aria-hidden="true"><span class="uf-module-toggle-thumb"></span></span>';
      actions.appendChild(toggle);
    });
  };

  const syncModuleToggle = (module) => {
    const inputs = Array.from(module.querySelectorAll('input[name="extra_permissions"]'));
    const toggle = module.querySelector("[data-group-toggle]");
    if (!toggle || !inputs.length) return;

    const selected = inputs.filter((input) => input.checked).length;
    const allSelected = selected === inputs.length;
    const partial = selected > 0 && !allSelected;

    toggle.classList.toggle("is-on", allSelected);
    toggle.classList.toggle("is-partial", partial);
    toggle.setAttribute("aria-checked", allSelected ? "true" : "false");
    toggle.setAttribute(
      "title",
      allSelected
        ? "Clear all permissions in this module"
        : partial
          ? "Some permissions selected — click to select all"
          : "Select all permissions in this module"
    );
  };

  const refreshCounts = () => {
    if (totalCount) totalCount.textContent = allInputs.filter((input) => input.checked).length;
    modules.forEach((module) => {
      const count = module.querySelector("[data-group-count]");
      if (count) {
        count.textContent = module.querySelectorAll('input[name="extra_permissions"]:checked').length;
      }
      syncModuleToggle(module);
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
    const toggle = event.target.closest("[data-group-toggle]");
    if (!toggle) return;

    const module = toggle.closest("[data-permission-group]");
    if (!module) return;

    const inputs = Array.from(module.querySelectorAll('input[name="extra_permissions"]'));
    const allSelected = inputs.length > 0 && inputs.every((input) => input.checked);
    const nextChecked = !allSelected;

    inputs.forEach((input) => {
      input.checked = nextChecked;
    });
    refreshCounts();
  });

  search?.addEventListener("input", applySearch);
  buildModuleToggles();
  refreshCounts();
});
