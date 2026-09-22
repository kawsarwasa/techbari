(() => {
  const root = document.querySelector('[data-global-search]');
  if (!root) return;

  const input = root.querySelector('[data-global-search-input]');
  const panel = root.querySelector('[data-global-search-results]');
  const endpoint = root.dataset.searchUrl;
  if (!input || !panel || !endpoint) return;

  let timer = null;
  let controller = null;
  let activeIndex = -1;

  const close = () => {
    panel.hidden = true;
    activeIndex = -1;
  };

  const setMessage = (message) => {
    panel.replaceChildren();
    const node = document.createElement('div');
    node.className = 'global-search-message';
    node.textContent = message;
    panel.appendChild(node);
    panel.hidden = false;
    activeIndex = -1;
  };

  const focusResult = (index) => {
    const links = [...panel.querySelectorAll('[data-global-search-result]')];
    if (!links.length) return;
    activeIndex = Math.max(0, Math.min(index, links.length - 1));
    links.forEach((link, i) => link.classList.toggle('active', i === activeIndex));
    links[activeIndex].scrollIntoView({block: 'nearest'});
  };

  const render = (results) => {
    panel.replaceChildren();
    activeIndex = -1;

    if (!results.length) {
      setMessage('No matching products, orders or customers found.');
      return;
    }

    const groups = ['Product', 'Order', 'Customer'];
    groups.forEach((type) => {
      const rows = results.filter((item) => item.type === type);
      if (!rows.length) return;

      const heading = document.createElement('div');
      heading.className = 'global-search-group-title';
      heading.textContent = type === 'Product' ? 'Products' : type === 'Order' ? 'Orders' : 'Customers';
      panel.appendChild(heading);

      rows.forEach((item) => {
        const link = document.createElement('a');
        link.className = 'global-search-result';
        link.href = item.url;
        link.dataset.globalSearchResult = '1';

        const icon = document.createElement('span');
        icon.className = 'global-search-result-icon';
        icon.textContent = item.type.charAt(0);

        const copy = document.createElement('span');
        copy.className = 'global-search-result-copy';

        const title = document.createElement('strong');
        title.textContent = item.title;

        const meta = document.createElement('small');
        meta.textContent = item.meta || '';

        copy.append(title, meta);

        const status = document.createElement('span');
        status.className = 'global-search-result-status';
        status.textContent = item.status || item.type;

        link.append(icon, copy, status);
        panel.appendChild(link);
      });
    });

    const footer = document.createElement('div');
    footer.className = 'global-search-footer';
    footer.textContent = '↑↓ Navigate · Enter Open · Esc Close';
    panel.appendChild(footer);
    panel.hidden = false;
  };

  const runSearch = async () => {
    const query = input.value.trim();
    if (query.length < 2) {
      if (query.length) setMessage('Type at least 2 characters to search.');
      else close();
      return;
    }

    if (controller) controller.abort();
    controller = new AbortController();
    setMessage('Searching…');

    try {
      const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'},
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('Search request failed');
      const data = await response.json();
      if (input.value.trim() !== query) return;
      render(data.results || []);
    } catch (error) {
      if (error.name === 'AbortError') return;
      setMessage('Search is temporarily unavailable.');
    }
  };

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(runSearch, 180);
  });

  input.addEventListener('focus', () => {
    if (input.value.trim().length >= 2) runSearch();
  });

  input.addEventListener('keydown', (event) => {
    const links = [...panel.querySelectorAll('[data-global-search-result]')];
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (panel.hidden && input.value.trim().length >= 2) runSearch();
      else focusResult(activeIndex + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusResult(activeIndex <= 0 ? links.length - 1 : activeIndex - 1);
    } else if (event.key === 'Enter' && activeIndex >= 0 && links[activeIndex]) {
      event.preventDefault();
      window.location.assign(links[activeIndex].href);
    } else if (event.key === 'Escape') {
      close();
      input.blur();
    }
  });

  document.addEventListener('click', (event) => {
    if (!root.contains(event.target)) close();
  });

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      input.focus();
      input.select();
    }
  });
})();
