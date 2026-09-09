(function () {
  const ROOT_SELECTOR = '[data-cms-content-editor]';
  const ALLOWED = new Set(['P','BR','STRONG','B','EM','I','U','UL','OL','LI','H2','H3','BLOCKQUOTE']);

  function escapeText(text) {
    const holder = document.createElement('div');
    holder.textContent = text || '';
    return holder.innerHTML;
  }

  function plainTextToHTML(value) {
    const text = String(value || '').replace(/\r\n?/g, '\n');
    if (!text.trim()) return '';
    return text
      .split(/\n{2,}/)
      .map((part) => `<p>${escapeText(part).replace(/\n/g, '<br>')}</p>`)
      .join('');
  }

  function sanitizeHTML(html) {
    const template = document.createElement('template');
    template.innerHTML = html || '';

    function clean(parent) {
      Array.from(parent.childNodes).forEach((node) => {
        if (node.nodeType === Node.COMMENT_NODE) {
          node.remove();
          return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;

        if (node.tagName === 'DIV') {
          const paragraph = document.createElement('p');
          while (node.firstChild) paragraph.appendChild(node.firstChild);
          node.replaceWith(paragraph);
          clean(paragraph);
          return;
        }

        if (!ALLOWED.has(node.tagName)) {
          const fragment = document.createDocumentFragment();
          while (node.firstChild) fragment.appendChild(node.firstChild);
          node.replaceWith(fragment);
          clean(parent);
          return;
        }

        Array.from(node.attributes).forEach((attr) => node.removeAttribute(attr.name));
        clean(node);
      });
    }

    clean(template.content);
    return template.innerHTML;
  }

  function initialHTML(value) {
    const raw = String(value || '');
    return /<\s*\/?\s*[a-z][^>]*>/i.test(raw) ? sanitizeHTML(raw) : plainTextToHTML(raw);
  }

  function insertPlainText(text) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();

    const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
    const fragment = document.createDocumentFragment();
    lines.forEach((line, index) => {
      if (index) fragment.appendChild(document.createElement('br'));
      fragment.appendChild(document.createTextNode(line));
    });

    const tail = fragment.lastChild;
    range.insertNode(fragment);
    if (tail) {
      range.setStartAfter(tail);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }

  function init(root) {
    if (root.dataset.editorReady === 'true') return;
    const source = root.querySelector('[data-editor-source]');
    const surface = root.querySelector('[data-editor-surface]');
    const block = root.querySelector('[data-editor-block]');
    const status = root.querySelector('[data-editor-status]');
    if (!source || !surface) return;

    try {
      surface.innerHTML = initialHTML(source.value);
      document.execCommand('defaultParagraphSeparator', false, 'p');
      root.dataset.editorReady = 'true';
    } catch (error) {
      console.error('TechBari CMS editor failed to initialize', error);
      return;
    }

    const sync = (message) => {
      source.value = sanitizeHTML(surface.innerHTML);
      if (status && message) status.textContent = message;
    };

    const focusEditor = () => {
      try { surface.focus({ preventScroll: true }); }
      catch (_) { surface.focus(); }
    };

    root.querySelectorAll('[data-editor-command]').forEach((button) => {
      button.addEventListener('mousedown', (event) => event.preventDefault());
      button.addEventListener('click', () => {
        focusEditor();
        const command = button.dataset.editorCommand;
        const commandMap = {
          bold: 'bold',
          italic: 'italic',
          underline: 'underline',
          ul: 'insertUnorderedList',
          ol: 'insertOrderedList',
          clear: 'removeFormat',
          undo: 'undo',
          redo: 'redo',
        };
        const nativeCommand = commandMap[command];
        if (!nativeCommand) return;
        document.execCommand(nativeCommand, false, null);
        sync('Unsaved changes');
      });
    });

    if (block) {
      block.addEventListener('change', () => {
        focusEditor();
        const tag = String(block.value || 'P').toLowerCase();
        document.execCommand('formatBlock', false, `<${tag}>`);
        sync('Unsaved changes');
      });
    }

    surface.addEventListener('input', () => sync('Unsaved changes'));

    surface.addEventListener('paste', (event) => {
      event.preventDefault();
      insertPlainText(event.clipboardData?.getData('text/plain') || '');
      sync('Unsaved changes');
    });

    surface.addEventListener('blur', () => sync('Ready to save'));
    source.closest('form')?.addEventListener('submit', () => sync('Saving…'));
    sync('Ready to save');
  }

  function boot() {
    document.querySelectorAll(ROOT_SELECTOR).forEach(init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
