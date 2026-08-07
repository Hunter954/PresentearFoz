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

  const bulk = document.querySelector('[data-bulk-image-upload]');
  if (bulk) {
    const form = bulk.querySelector('[data-bulk-image-form]');
    const filesInput = bulk.querySelector('[data-bulk-files]');
    const folderInput = bulk.querySelector('[data-bulk-folder]');
    const dropzone = bulk.querySelector('[data-bulk-dropzone]');
    const queue = bulk.querySelector('[data-bulk-queue]');
    const count = bulk.querySelector('[data-bulk-count]');
    const current = bulk.querySelector('[data-bulk-current]');
    const submit = bulk.querySelector('[data-bulk-submit]');
    const progress = bulk.querySelector('[data-bulk-progress]');
    const success = bulk.querySelector('[data-bulk-success]');
    const missing = bulk.querySelector('[data-bulk-missing]');
    const errors = bulk.querySelector('[data-bulk-errors]');
    const log = bulk.querySelector('[data-bulk-log]');
    const csrf = bulk.querySelector('[data-bulk-csrf]')?.value || '';
    const allowed = /\.(png|jpe?g|webp|gif)$/i;
    let selectedFiles = [];
    let running = false;

    const fileSku = file => file.name.replace(/\.[^.]+$/, '').trim().toUpperCase();
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[char]);
    const showSelection = fileList => {
      if (running) return;
      selectedFiles = Array.from(fileList || []).filter(file => allowed.test(file.name));
      queue.hidden = selectedFiles.length === 0;
      count.textContent = `${selectedFiles.length} foto${selectedFiles.length === 1 ? '' : 's'}`;
      current.textContent = selectedFiles.length ? 'Prontas para atualizar pelas SKUs dos arquivos' : 'Nenhuma imagem selecionada';
      progress.style.width = '0%';
      submit.innerHTML = '<i class="bi bi-arrow-repeat"></i> Atualizar fotos';
      success.textContent = '0';
      missing.textContent = '0';
      errors.textContent = '0';
      log.innerHTML = '';
      log.hidden = true;
    };

    filesInput?.addEventListener('change', event => showSelection(event.target.files));
    folderInput?.addEventListener('change', event => showSelection(event.target.files));

    ['dragenter', 'dragover'].forEach(type => dropzone?.addEventListener(type, event => {
      event.preventDefault();
      if (!running) dropzone.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach(type => dropzone?.addEventListener(type, event => {
      event.preventDefault();
      dropzone.classList.remove('is-dragging');
    }));
    dropzone?.addEventListener('drop', event => showSelection(event.dataTransfer?.files));

    form?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!selectedFiles.length || running) return;
      running = true;
      submit.disabled = true;
      filesInput.disabled = true;
      folderInput.disabled = true;
      log.hidden = false;
      log.innerHTML = '';

      let okCount = 0;
      let missingCount = 0;
      let errorCount = 0;

      for (let index = 0; index < selectedFiles.length; index += 1) {
        const file = selectedFiles[index];
        const sku = fileSku(file);
        current.textContent = `Enviando ${index + 1} de ${selectedFiles.length}: ${file.name}`;
        const data = new FormData();
        data.append('csrf_token', csrf);
        data.append('image', file, file.name);

        let result = null;
        let status = 0;
        try {
          const response = await fetch(form.action, { method: 'POST', body: data, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
          status = response.status;
          result = await response.json();
        } catch (_) {
          result = { ok: false, error: 'Falha de conexão durante o envio.' };
        }

        const row = document.createElement('div');
        if (result?.ok) {
          okCount += 1;
          row.className = 'bulk-log-row success';
          row.innerHTML = `<i class="bi bi-check-circle-fill"></i><span><strong>${escapeHtml(sku)}</strong> — ${escapeHtml(result.product || 'Produto atualizado')}</span>`;
        } else if (status === 404 || result?.status === 'not_found') {
          missingCount += 1;
          row.className = 'bulk-log-row warning';
          row.innerHTML = `<i class="bi bi-search"></i><span><strong>${escapeHtml(sku)}</strong> — SKU não encontrado</span>`;
        } else {
          errorCount += 1;
          row.className = 'bulk-log-row danger';
          row.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i><span><strong>${escapeHtml(sku || file.name)}</strong> — ${escapeHtml(result?.error || 'Erro ao enviar')}</span>`;
        }
        log.appendChild(row);
        success.textContent = String(okCount);
        missing.textContent = String(missingCount);
        errors.textContent = String(errorCount);
        progress.style.width = `${Math.round(((index + 1) / selectedFiles.length) * 100)}%`;
      }

      current.textContent = `Concluído: ${okCount} atualizada${okCount === 1 ? '' : 's'}, ${missingCount} SKU${missingCount === 1 ? '' : 's'} não encontrado${missingCount === 1 ? '' : 's'}, ${errorCount} erro${errorCount === 1 ? '' : 's'}.`;
      submit.innerHTML = '<i class="bi bi-check2"></i> Concluído';
      submit.disabled = false;
      filesInput.disabled = false;
      folderInput.disabled = false;
      running = false;
    });
  }
})();
