(function () {
  const selector = 'textarea[name="description"].rich-area, textarea#id_description';

  function hideLegacyToolbar(source) {
    const field = source.closest('label');
    const toolbar = field ? field.querySelector('.rich-toolbar') : null;
    if (toolbar) {
      toolbar.hidden = true;
      toolbar.setAttribute('aria-hidden', 'true');
    }
  }

  function initEditor(source) {
    if (!source || source.dataset.joditReady === 'true') return;
    source.dataset.joditReady = 'true';
    hideLegacyToolbar(source);

    if (!window.Jodit || typeof window.Jodit.make !== 'function') {
      source.classList.add('jodit-editor-fallback');
      return;
    }

    const desktopButtons = [
      'paragraph', '|', 'bold', 'italic', 'underline', '|',
      'ul', 'ol', '|', 'undo', 'redo', '|', 'eraser'
    ];
    const mobileButtons = [
      'bold', 'italic', 'underline', '|', 'ul', 'ol', '|', 'undo', 'redo'
    ];

    try {
      const editor = window.Jodit.make(source, {
        height: 280,
        minHeight: 220,
        maxHeight: 520,
        toolbarAdaptive: false,
        toolbarSticky: false,
        buttons: desktopButtons,
        buttonsMD: desktopButtons,
        buttonsSM: mobileButtons,
        buttonsXS: mobileButtons,
        statusbar: false,
        showCharsCounter: false,
        showWordsCounter: false,
        showXPathInStatusbar: false,
        spellcheck: true,
        enter: 'p',
        placeholder: 'Write the full product description...',
        askBeforePasteHTML: false,
        askBeforePasteFromWord: false,
        cleanHTML: {
          fillEmptyParagraph: false,
          removeEmptyElements: false
        }
      });

      editor.events.on('change', function (value) {
        source.value = value || '';
      });

      const form = source.closest('form');
      if (form) {
        form.addEventListener('submit', function () {
          source.value = editor.value || '';
        });
      }
    } catch (error) {
      console.error('TechBari Jodit editor failed to initialize:', error);
      source.classList.add('jodit-editor-fallback');
    }
  }

  function initialize() {
    document.querySelectorAll(selector).forEach(initEditor);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
