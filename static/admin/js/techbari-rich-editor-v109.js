(function () {
  const ROOT_SELECTOR = '[data-techbari-editor]';

  function sanitizeHTML(html) {
    const template = document.createElement('template');
    template.innerHTML = html || '';
    const allowed = new Set(['P','BR','STRONG','B','EM','I','U','UL','OL','LI','H2','H3','BLOCKQUOTE']);

    const clean = (node) => {
      Array.from(node.childNodes).forEach((child) => {
        if (child.nodeType === Node.COMMENT_NODE) {
          child.remove();
          return;
        }
        if (child.nodeType !== Node.ELEMENT_NODE) return;
        if (!allowed.has(child.tagName)) {
          const fragment = document.createDocumentFragment();
          while (child.firstChild) fragment.appendChild(child.firstChild);
          child.replaceWith(fragment);
          clean(node);
          return;
        }
        Array.from(child.attributes).forEach((attr) => child.removeAttribute(attr.name));
        clean(child);
      });
    };

    clean(template.content);
    return template.innerHTML;
  }

  function normalizeInitialValue(value) {
    if (!value) return '';
    if (/<\/?[a-z][\s\S]*>/i.test(value)) return sanitizeHTML(value);
    const holder = document.createElement('div');
    holder.textContent = value;
    return holder.innerHTML
      .split(/\n{2,}/)
      .map((part) => `<p>${part.replace(/\n/g, '<br>')}</p>`)
      .join('');
  }

  function closestEditableNode(editor, node) {
    let current = node && node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    while (current && current !== editor) {
      if (current.parentElement === editor) return current;
      current = current.parentElement;
    }
    return null;
  }

  function wrapSelection(editor, tagName) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount || selection.isCollapsed) return false;
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return false;

    const wrapper = document.createElement(tagName);
    try {
      range.surroundContents(wrapper);
    } catch (_) {
      const fragment = range.extractContents();
      wrapper.appendChild(fragment);
      range.insertNode(wrapper);
    }

    selection.removeAllRanges();
    const nextRange = document.createRange();
    nextRange.selectNodeContents(wrapper);
    selection.addRange(nextRange);
    return true;
  }

  function toggleInline(editor, tagName) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;

    const node = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
      ? range.commonAncestorContainer.parentElement
      : range.commonAncestorContainer;
    const active = node && node.closest ? node.closest(tagName.toLowerCase()) : null;
    if (active && editor.contains(active)) {
      const fragment = document.createDocumentFragment();
      while (active.firstChild) fragment.appendChild(active.firstChild);
      active.replaceWith(fragment);
      return;
    }
    wrapSelection(editor, tagName);
  }

  function setBlock(editor, tagName) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;

    const block = closestEditableNode(editor, range.startContainer);
    if (!block) return;
    const target = document.createElement(tagName);
    target.innerHTML = block.innerHTML || '<br>';
    block.replaceWith(target);

    const nextRange = document.createRange();
    nextRange.selectNodeContents(target);
    nextRange.collapse(false);
    selection.removeAllRanges();
    selection.addRange(nextRange);
  }

  function toggleList(editor, ordered) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;

    const current = closestEditableNode(editor, range.startContainer);
    if (!current) return;

    const listTag = ordered ? 'OL' : 'UL';
    const existingList = current.closest && current.closest('ul,ol');
    if (existingList && editor.contains(existingList)) {
      const paragraph = document.createElement('p');
      paragraph.innerHTML = Array.from(existingList.querySelectorAll(':scope > li'))
        .map((li) => li.innerHTML)
        .join('<br>');
      existingList.replaceWith(paragraph);
      return;
    }

    const list = document.createElement(listTag);
    const li = document.createElement('li');
    li.innerHTML = current.innerHTML || '<br>';
    list.appendChild(li);
    current.replaceWith(list);
  }

  function init(root) {
    const source = root.querySelector('textarea[data-editor-source]');
    const editor = root.querySelector('[data-editor-surface]');
    const blockSelect = root.querySelector('[data-editor-block]');
    if (!source || !editor || root.dataset.editorReady === 'true') return;

    root.dataset.editorReady = 'true';
    editor.innerHTML = normalizeInitialValue(source.value);

    let savedRange = null;
    const saveRange = () => {
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      if (editor.contains(range.commonAncestorContainer)) savedRange = range.cloneRange();
    };
    const restoreRange = () => {
      if (!savedRange) return;
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange);
    };
    const sync = () => {
      source.value = sanitizeHTML(editor.innerHTML);
    };

    ['keyup','mouseup','input','focus'].forEach((eventName) => {
      editor.addEventListener(eventName, () => {
        saveRange();
        if (eventName === 'input') sync();
      });
    });

    root.querySelectorAll('[data-editor-command]').forEach((button) => {
      button.addEventListener('mousedown', (event) => event.preventDefault());
      button.addEventListener('click', () => {
        editor.focus();
        restoreRange();
        const command = button.dataset.editorCommand;
        if (command === 'bold') toggleInline(editor, 'STRONG');
        if (command === 'italic') toggleInline(editor, 'EM');
        if (command === 'underline') toggleInline(editor, 'U');
        if (command === 'ul') toggleList(editor, false);
        if (command === 'ol') toggleList(editor, true);
        saveRange();
        sync();
      });
    });

    blockSelect?.addEventListener('mousedown', saveRange);
    blockSelect?.addEventListener('change', () => {
      editor.focus();
      restoreRange();
      setBlock(editor, blockSelect.value || 'P');
      saveRange();
      sync();
    });

    editor.addEventListener('paste', (event) => {
      event.preventDefault();
      const text = event.clipboardData?.getData('text/plain') || '';
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(text);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      saveRange();
      sync();
    });

    source.closest('form')?.addEventListener('submit', sync);
    sync();
  }

  function initialize() {
    document.querySelectorAll(ROOT_SELECTOR).forEach(init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
