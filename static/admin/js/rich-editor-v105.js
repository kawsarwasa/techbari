(function () {
  const ALLOWED = new Set(['P','DIV','BR','STRONG','B','EM','I','U','UL','OL','LI','H2','H3','BLOCKQUOTE']);

  function sanitizeFragment(html) {
    const template = document.createElement('template');
    template.innerHTML = html || '';

    const clean = (node) => {
      [...node.childNodes].forEach((child) => {
        if (child.nodeType === Node.COMMENT_NODE) {
          child.remove();
          return;
        }
        if (child.nodeType !== Node.ELEMENT_NODE) return;

        if (!ALLOWED.has(child.tagName)) {
          const fragment = document.createDocumentFragment();
          while (child.firstChild) fragment.appendChild(child.firstChild);
          child.replaceWith(fragment);
          clean(node);
          return;
        }

        [...child.attributes].forEach((attr) => child.removeAttribute(attr.name));
        clean(child);
      });
    };

    clean(template.content);
    return template.innerHTML;
  }

  function plainTextToHtml(text) {
    const value = (text || '').trim();
    if (!value) return '';
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML
      .split(/\n{2,}/)
      .map((part) => `<p>${part.replace(/\n/g, '<br>')}</p>`)
      .join('');
  }

  function setupEditor(toolbar) {
    if (toolbar.dataset.richReady === 'true') return;
    const label = toolbar.closest('label');
    const source = label?.querySelector('textarea.rich-area');
    if (!source) return;

    toolbar.dataset.richReady = 'true';
    toolbar.classList.add('rich-toolbar-v105');

    const select = toolbar.querySelector('select');
    if (select) {
      select.innerHTML = `
        <option value="p">Paragraph</option>
        <option value="h2">Heading 2</option>
        <option value="h3">Heading 3</option>
        <option value="blockquote">Quote</option>
      `;
      select.setAttribute('aria-label', 'Text style');
    }

    const buttons = [...toolbar.querySelectorAll('button')];
    const commandMap = ['bold', 'italic', 'underline', 'insertUnorderedList'];
    const labels = ['Bold', 'Italic', 'Underline', 'Bulleted list'];
    buttons.forEach((button, index) => {
      button.dataset.richCommand = commandMap[index] || '';
      button.title = labels[index] || 'Format';
      button.setAttribute('aria-label', labels[index] || 'Format');
    });

    const editor = document.createElement('div');
    editor.className = 'rich-area rich-editor-v105';
    editor.contentEditable = 'true';
    editor.setAttribute('role', 'textbox');
    editor.setAttribute('aria-multiline', 'true');
    editor.setAttribute('data-placeholder', 'Write the full product description...');
    editor.spellcheck = true;

    const raw = source.value || '';
    const looksLikeHtml = /<\/?[a-z][\s\S]*>/i.test(raw);
    editor.innerHTML = sanitizeFragment(looksLikeHtml ? raw : plainTextToHtml(raw));
    source.classList.add('rich-source-hidden');
    source.insertAdjacentElement('afterend', editor);

    let savedRange = null;

    const saveSelection = () => {
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      if (editor.contains(range.commonAncestorContainer)) savedRange = range.cloneRange();
    };

    const restoreSelection = () => {
      if (!savedRange) return;
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange);
    };

    const sync = () => {
      const cleaned = sanitizeFragment(editor.innerHTML);
      if (cleaned !== editor.innerHTML) {
        const current = savedRange;
        editor.innerHTML = cleaned;
        savedRange = current;
      }
      source.value = cleaned;
    };

    const refreshToolbar = () => {
      buttons.forEach((button) => {
        const command = button.dataset.richCommand;
        if (!command) return;
        let active = false;
        try { active = document.queryCommandState(command); } catch (_) { active = false; }
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });

      if (select) {
        let block = 'p';
        try {
          const value = String(document.queryCommandValue('formatBlock') || '').toLowerCase().replace(/[<>]/g, '');
          if (['p','h2','h3','blockquote'].includes(value)) block = value;
        } catch (_) {}
        select.value = block;
      }
    };

    ['keyup','mouseup','focus','input'].forEach((eventName) => {
      editor.addEventListener(eventName, () => {
        saveSelection();
        if (eventName === 'input') sync();
        refreshToolbar();
      });
    });

    editor.addEventListener('paste', (event) => {
      event.preventDefault();
      const text = event.clipboardData?.getData('text/plain') || '';
      document.execCommand('insertText', false, text);
    });

    buttons.forEach((button) => {
      button.addEventListener('mousedown', (event) => event.preventDefault());
      button.addEventListener('click', () => {
        const command = button.dataset.richCommand;
        if (!command) return;
        editor.focus();
        restoreSelection();
        try {
          document.execCommand('styleWithCSS', false, false);
          document.execCommand(command, false, null);
        } catch (_) {}
        saveSelection();
        sync();
        refreshToolbar();
      });
    });

    select?.addEventListener('mousedown', saveSelection);
    select?.addEventListener('change', () => {
      editor.focus();
      restoreSelection();
      try {
        document.execCommand('formatBlock', false, select.value || 'p');
      } catch (_) {}
      saveSelection();
      sync();
      refreshToolbar();
    });

    const form = source.closest('form');
    form?.addEventListener('submit', sync);

    try {
      document.execCommand('defaultParagraphSeparator', false, 'p');
      document.execCommand('styleWithCSS', false, false);
    } catch (_) {}

    sync();
  }

  document.querySelectorAll('.rich-toolbar').forEach(setupEditor);
})();
