document.querySelectorAll('[data-color-editor]').forEach(editor => {
  const list = editor.querySelector('[data-color-list]');
  const empty = editor.querySelector('[data-colors-empty]');
  editor.addEventListener('click', event => {
    const remove = event.target.closest('[data-remove-color]');
    if (remove) {
      remove.closest('.admin-color-row').remove();
      empty.hidden = list.children.length > 0;
    }
    if (event.target.closest('[data-add-color]')) {
      const row = editor.querySelector('template').content.cloneNode(true);
      list.append(row);
      empty.hidden = true;
      list.lastElementChild.querySelector('[name="color_name"]').focus();
    }
  });
});
