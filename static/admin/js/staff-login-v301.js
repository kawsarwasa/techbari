(() => {
  const toggle = document.querySelector('[data-staff-password-toggle]');
  const input = document.getElementById('staffPassword');
  if (!toggle || !input) return;

  toggle.addEventListener('click', () => {
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    toggle.textContent = showing ? 'Show' : 'Hide';
    toggle.setAttribute('aria-pressed', showing ? 'false' : 'true');
  });
})();