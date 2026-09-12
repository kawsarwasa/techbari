(function () {
  const ROOT_SELECTOR = '[data-cms-content-editor]';
  const ALLOWED = new Set(['P','BR','STRONG','B','EM','I','U','UL','OL','LI','H2','H3','BLOCKQUOTE','SPAN']);
  const FONT_SIZES = new Set(['12px','14px','16px','18px','20px','24px','28px','32px']);
  const LEGACY_FONT_SIZES = {
    '1': '12px',
    '2': '12px',
    '3': '14px',
    '4': '18px',
    '5': '24px',
    '6': '28px',
    '7': '32px',
  };

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

  function normalizeColor(value) {
    const raw = String(value || '').trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(raw)) return raw;
    if (/^#[0-9a-f]{3}$/.test(raw)) {
      return `#${raw.slice(1).split('').map((part) => part + part).join('')}`;
    }
    const rgb = raw.match(/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(?:1|1\.0+))?\s*\)$/);
    if (!rgb) return '';
    const channels = rgb.slice(1, 4).map(Number);
    if (channels.some((channel) => channel < 0 || channel > 255)) return '';
    return `#${channels.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
  }

  function safeInlineStyle(node) {
    const declarations = [];
    const fontSize = String(node.style?.fontSize || '').trim().toLowerCase();
    const color = normalizeColor(node.style?.color || '');
    if (FONT_SIZES.has(fontSize)) declarations.push(`font-size:${fontSize}`);
    if (color) declarations.push(`color:${color}`);
    return declarations.join(';');
  }

  function replaceLegacyFont(font, forcedSize) {
    const span = document.createElement('span');
    const color = normalizeColor(font.getAttribute('color') || font.style?.color || '');
    const legacySize = String(font.getAttribute('size') || '').trim();
    const fontSize = forcedSize && FONT_SIZES.has(forcedSize)
      ? forcedSize
      : LEGACY_FONT_SIZES[legacySize] || '';
    if (fontSize) span.style.fontSize = fontSize;
    if (color) span.style.color = color;
    while (font.firstChild) span.appendChild(font.firstChild);
    font.replaceWith(span);
  }

  function normalizeLegacyFonts(container, forcedSize) {
    Array.from(container.querySelectorAll('font')).forEach((font) => replaceLegacyFont(font, forcedSize));
  }

  function sanitizeHTML(html) {
    const template = document.createElement('template');
    template.innerHTML = html || '';
    normalizeLegacyFonts(template.content);

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

        const style = node.tagName === 'SPAN' ? safeInlineStyle(node) : '';
        Array.from(node.attributes).forEach((attr) => node.removeAttribute(attr.name));
        if (style) node.setAttribute('style', style);
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
    const fontSize = root.querySelector('[data-editor-font-size]');
    const color = root.querySelector('[data-editor-color]');
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

    let savedRange = null;

    const saveRange = () => {
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      if (surface.contains(range.commonAncestorContainer)) savedRange = range.cloneRange();
    };

    const restoreRange = () => {
      if (!savedRange) return;
      const selection = window.getSelection();
      if (!selection) return;
      try {
        selection.removeAllRanges();
        selection.addRange(savedRange);
      } catch (_) {
        savedRange = null;
      }
    };

    const sync = (message) => {
      normalizeLegacyFonts(surface);
      source.value = sanitizeHTML(surface.innerHTML);
      if (status && message) status.textContent = message;
    };

    const focusEditor = () => {
      try { surface.focus({ preventScroll: true }); }
      catch (_) { surface.focus(); }
    };

    const prepareSelection = () => {
      focusEditor();
      restoreRange();
      try { document.execCommand('styleWithCSS', false, false); } catch (_) {}
    };

    ['keyup','mouseup','focus'].forEach((eventName) => surface.addEventListener(eventName, saveRange));
    surface.addEventListener('input', () => {
      saveRange();
      sync('Unsaved changes');
    });

    root.querySelectorAll('[data-editor-command]').forEach((button) => {
      button.addEventListener('mousedown', (event) => {
        event.preventDefault();
        saveRange();
      });
      button.addEventListener('click', () => {
        prepareSelection();
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
        normalizeLegacyFonts(surface);
        saveRange();
        sync('Unsaved changes');
      });
    });

    if (block) {
      block.addEventListener('mousedown', saveRange);
      block.addEventListener('focus', saveRange);
      block.addEventListener('change', () => {
        prepareSelection();
        const tag = String(block.value || 'P').toLowerCase();
        let applied = false;
        try { applied = document.execCommand('formatBlock', false, tag); } catch (_) {}
        if (!applied) {
          try { document.execCommand('formatBlock', false, `<${tag}>`); } catch (_) {}
        }
        saveRange();
        sync('Unsaved changes');
      });
    }

    if (fontSize) {
      fontSize.addEventListener('mousedown', saveRange);
      fontSize.addEventListener('focus', saveRange);
      fontSize.addEventListener('change', () => {
        const size = String(fontSize.value || '').toLowerCase();
        if (!FONT_SIZES.has(size)) return;
        prepareSelection();
        normalizeLegacyFonts(surface);
        document.execCommand('fontSize', false, '7');
        normalizeLegacyFonts(surface, size);
        saveRange();
        sync('Unsaved changes');
      });
    }

    if (color) {
      color.addEventListener('mousedown', saveRange);
      color.addEventListener('focus', saveRange);
      color.addEventListener('input', () => {
        const selectedColor = normalizeColor(color.value);
        if (!selectedColor) return;
        prepareSelection();
        document.execCommand('foreColor', false, selectedColor);
        normalizeLegacyFonts(surface);
        saveRange();
        sync('Unsaved changes');
      });
    }

    surface.addEventListener('paste', (event) => {
      event.preventDefault();
      insertPlainText(event.clipboardData?.getData('text/plain') || '');
      saveRange();
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
