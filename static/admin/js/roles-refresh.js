document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".roles-refresh");
  if (!root) return;

  const rows = Array.from(root.querySelectorAll("[data-role-row]"));
  const tabs = Array.from(root.querySelectorAll("[data-role-filter]"));
  const search = root.querySelector("[data-role-search]");
  const shown = root.querySelector("[data-role-shown]");
  let activeFilter = "all";

  const applyFilters = () => {
    const query = (search?.value || "").trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const kind = row.dataset.kind || "system";
      const matchesFilter = activeFilter === "all" || kind === activeFilter;
      const matchesSearch = !query || (row.dataset.search || "").includes(query);
      row.hidden = !(matchesFilter && matchesSearch);
      if (!row.hidden) visible += 1;
    });
    if (shown) shown.textContent = visible;
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activeFilter = tab.dataset.roleFilter || "all";
      tabs.forEach((item) => item.classList.toggle("is-active", item === tab));
      applyFilters();
    });
  });
  search?.addEventListener("input", applyFilters);

  const donut = root.querySelector("[data-role-donut]");
  const legendRows = Array.from(root.querySelectorAll("[data-role-legend]"));
  const colors = ["#1677ff", "#7c4dff", "#2d9bf0", "#1bb7a8", "#f49a22", "#e95b67", "#0f9d8a", "#9a6bff"];
  const counts = legendRows.map((row) => Number(row.dataset.staffCount || 0));
  const total = counts.reduce((sum, value) => sum + value, 0);

  if (donut) {
    if (total > 0) {
      let cursor = 0;
      const segments = counts.map((count, index) => {
        const start = cursor;
        cursor += (count / total) * 100;
        return `${colors[index % colors.length]} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
      });
      donut.style.setProperty("--role-gradient", `conic-gradient(${segments.join(",")})`);
    }
    const totalNode = donut.querySelector("[data-role-total-staff]");
    if (totalNode) totalNode.textContent = total;
  }

  legendRows.forEach((row, index) => {
    row.style.setProperty("--dot", colors[index % colors.length]);
    const count = Number(row.dataset.staffCount || 0);
    const percent = total ? Math.round((count / total) * 100) : 0;
    const percentNode = row.querySelector("[data-role-percent]");
    if (percentNode) percentNode.textContent = `${percent}%`;
  });

  applyFilters();
});
