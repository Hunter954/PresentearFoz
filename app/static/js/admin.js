(() => {
  const sidebar = document.querySelector('[data-admin-sidebar]');
  document.querySelector('[data-sidebar-toggle]')?.addEventListener('click', () => sidebar?.classList.toggle('is-open'));
  document.addEventListener('click', event => {
    if (window.innerWidth <= 900 && sidebar?.classList.contains('is-open') && !event.target.closest('[data-admin-sidebar]') && !event.target.closest('[data-sidebar-toggle]')) sidebar.classList.remove('is-open');
  });

  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      const original = button.textContent;
      button.textContent = 'Copiado!';
      setTimeout(() => button.textContent = original, 1500);
    } catch (_) { alert('Copie manualmente: ' + button.dataset.copy); }
  }));

  document.querySelectorAll('[data-color-picker]').forEach(picker => {
    const wrapper = picker.closest('.color-input');
    const text = wrapper?.querySelector('[data-color-text]');
    picker.addEventListener('input', () => { if (text) text.value = picker.value; });
    text?.addEventListener('input', () => {
      if (/^#[0-9a-fA-F]{6}$/.test(text.value)) picker.value = text.value;
    });
  });
})();
