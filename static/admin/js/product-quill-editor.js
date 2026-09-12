(function () {
  const ROOT_SELECTOR = '[data-product-rich-editor]';
  const SIZE_VALUES = ['12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px'];
  const ALLOWED_TAGS = new Set(['P', 'BR', 'STRONG', 'B', 'EM', 'I', 'U', 'S', 'UL', 'OL', 'LI', 'H2', 'H3', 'BLOCKQUOTE', 'SPAN']);
  const SAFE_ALIGN = new Set(['left', 'center', 'right', 'justify']);
  const SAFE_HEX = /^#[0-9a-f]{6}$/i;
  const SAFE_RGB = /^rgb\(\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*\)$/i;

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

  function safeStyle(node) {
    const safe = [];
    const declarations = String(node.getAttribute('style') || '').split(';');
    declarations.forEach((declaration) => {
      if (!declaration.includes(':')) return;
      const splitAt = declaration.indexOf(':');
      const name = declaration.slice(0, splitAt).trim().toLowerCase();
      const value = declaration.slice(splitAt + 1).trim().toLowerCase();
      if (name === 'font-size' && node.tagName === 'SPAN' && SIZE_VALUES.includes(value)) {
        safe.push(`font-size:${value}`);
      } else if ((name === 'color' || name === 'background-color') && node.tagName === 'SPAN' && (SAFE_HEX.test(value) || SAFE_RGB.test(value))) {
        safe.push(`${name}:${value}`);
      } else if (name === 'text-align' && ['P', 'H2', 'H3', 'BLOCKQUOTE', 'LI'].includes(node.tagName) && SAFE_ALIGN.has(value)) {
        safe.push(`text-align:${value}`);
      }
    });
    return safe.join(';');
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

        if (['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED'].includes(node.tagName)) {
          node.remove();
          return;
        }

        if (node.tagName === 'DIV') {
          const paragraph = document.createElement('p');
          while (node.firstChild) paragraph.appendChild(node.firstChild);
          node.replaceWith(paragraph);
          clean(paragraph);
          return;
        }

        if (!ALLOWED_TAGS.has(node.tagName)) {
          const fragment = document.createDocumentFragment();
          while (node.firstChild) fragment.appendChild(node.firstChild);
          node.replaceWith(fragment);
          clean(parent);
          return;
        }

        const style = safeStyle(node);
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

  function registerFormats() {
    const Quill = window.Quill;
    if (!Quill) return false;
    try {
      const SizeStyle = Quill.import('attributors/style/size');
      SizeStyle.whitelist = SIZE_VALUES;
      Quill.register(SizeStyle, true);

      const AlignStyle = Quill.import('attributors/style/align');
      Quill.register(AlignStyle, true);

      const ColorStyle = Quill.import('attributors/style/color');
      Quill.register(ColorStyle, true);

      const BackgroundStyle = Quill.import('attributors/style/background');
      Quill.register(BackgroundStyle, true);
    } catch (error) {
      console.warn('TechBari: Quill style registration fallback', error);
    }
    return true;
  }

  function init(root) {
    if (root.dataset.productRichReady === 'true') return;
    const source = root.querySelector('[data-product-rich-source]');
    const host = root.querySelector('[data-product-quill-host]');
    const status = root.querySelector('[data-product-rich-status]');
    if (!source || !host) return;

    if (!window.Quill) {
      if (status) status.textContent = 'Rich editor unavailable — textarea mode';
      return;
    }

    try {
      const quill = new window.Quill(host, {
        theme: 'snow',
        placeholder: 'Write the full product description here…',
        formats: ['header', 'size', 'bold', 'italic', 'underline', 'strike', 'color', 'background', 'list', 'align', 'blockquote'],
        modules: {
          toolbar: [
            [{ header: [2, 3, false] }, { size: SIZE_VALUES }],
            ['bold', 'italic', 'underline', 'strike'],
            [{ color: [] }, { background: [] }],
            [{ list: 'ordered' }, { list: 'bullet' }],
            [{ align: [] }],
            ['blockquote', 'clean'],
          ],
          history: { delay: 700, maxStack: 100, userOnly: true },
        },
      });

      const startingHTML = initialHTML(source.value);
      if (startingHTML) quill.clipboard.dangerouslyPasteHTML(0, startingHTML, 'silent');

      const sync = (message) => {
        const isEmpty = !quill.getText().trim();
        const exported = typeof quill.getSemanticHTML === 'function' ? quill.getSemanticHTML() : quill.root.innerHTML;
        source.value = isEmpty ? '' : sanitizeHTML(exported);
        if (status && message) status.textContent = message;
      };

      quill.on('text-change', (_delta, _oldDelta, sourceName) => {
        if (sourceName === 'silent') return;
        sync('Unsaved changes');
      });

      source.closest('form')?.addEventListener('submit', () => sync('Saving…'));
      root.dataset.productRichReady = 'true';
      sync('Ready to save');
    } catch (error) {
      console.error('TechBari product editor failed to initialize', error);
      if (status) status.textContent = 'Rich editor unavailable — textarea mode';
    }
  }

  function boot() {
    if (!registerFormats()) {
      document.querySelectorAll(ROOT_SELECTOR).forEach((root) => {
        const status = root.querySelector('[data-product-rich-status]');
        if (status) status.textContent = 'Rich editor unavailable — textarea mode';
      });
      return;
    }
    document.querySelectorAll(ROOT_SELECTOR).forEach(init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
