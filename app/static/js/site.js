(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const toast = document.querySelector('[data-toast]');
  let toastTimer;

  function showToast(message, isError = false) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle('is-error', isError);
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 3200);
  }

  async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (!['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase())) {
      headers.set('X-CSRFToken', csrf);
    }
    const response = await fetch(url, {...options, headers});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.message || 'Não foi possível concluir a operação.');
    return data;
  }

  function updateCartUI(cart) {
    document.querySelectorAll('[data-cart-count]').forEach(el => el.textContent = cart.count || 0);
    document.querySelectorAll('[data-cart-label]').forEach(el => {
      const count = cart.count || 0;
      el.textContent = `${count} ${count === 1 ? 'item' : 'itens'}`;
    });
    if (cart.token) {
      localStorage.setItem('presentear_cart_token', cart.token);
      document.body.dataset.cartToken = cart.token;
    }
  }

  async function restoreCart() {
    const serverToken = document.body.dataset.cartToken;
    const savedToken = localStorage.getItem('presentear_cart_token');
    if (serverToken) {
      localStorage.setItem('presentear_cart_token', serverToken);
      return;
    }
    if (!savedToken) return;
    try {
      const data = await api('/api/cart/restore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: savedToken})
      });
      updateCartUI(data.cart);
      if (data.cart.count > 0) window.location.reload();
    } catch (_) {
      localStorage.removeItem('presentear_cart_token');
    }
  }

  document.querySelectorAll('.js-add-to-cart').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      const original = button?.textContent;
      if (button) { button.disabled = true; button.textContent = 'Adicionando...'; }
      try {
        const data = await api('/api/cart/items', {method: 'POST', body: new FormData(form)});
        updateCartUI(data.cart);
        showToast(data.message || 'Produto adicionado ao carrinho.');
      } catch (error) {
        showToast(error.message, true);
      } finally {
        if (button) { button.disabled = false; button.textContent = original; }
      }
    });
  });

  document.querySelectorAll('[data-qty-minus]').forEach(button => button.addEventListener('click', () => {
    const input = button.parentElement.querySelector('input');
    const min = Number(input.min || 1);
    input.value = Math.max(min, Number(input.value || min) - 1);
  }));
  document.querySelectorAll('[data-qty-plus]').forEach(button => button.addEventListener('click', () => {
    const input = button.parentElement.querySelector('input');
    input.value = Number(input.value || input.min || 1) + 1;
  }));

  document.querySelectorAll('[data-cart-item]').forEach(item => {
    const itemId = item.dataset.cartItem;
    const input = item.querySelector('[data-cart-quantity]');
    let timer;
    input?.addEventListener('change', () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        try {
          const data = await api(`/api/cart/items/${itemId}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({quantity: Number(input.value || 1)})
          });
          updateCartUI(data.cart);
          window.location.reload();
        } catch (error) { showToast(error.message, true); }
      }, 250);
    });
    item.querySelector('[data-remove-item]')?.addEventListener('click', async () => {
      if (!confirm('Remover este item do carrinho?')) return;
      try {
        const data = await api(`/api/cart/items/${itemId}`, {method: 'DELETE'});
        updateCartUI(data.cart);
        item.remove();
        window.location.reload();
      } catch (error) { showToast(error.message, true); }
    });
  });

  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      showToast('Código copiado.');
    } catch (_) { showToast('Não foi possível copiar automaticamente.', true); }
  }));

  document.querySelector('[data-menu-toggle]')?.addEventListener('click', () => {
    document.querySelector('[data-mobile-menu]')?.classList.toggle('is-open');
  });

  document.querySelectorAll('[data-gallery-thumb]').forEach(button => button.addEventListener('click', () => {
    const main = document.querySelector('[data-gallery-main]');
    if (main) main.src = button.dataset.galleryThumb;
    document.querySelectorAll('[data-gallery-thumb]').forEach(el => el.classList.remove('is-active'));
    button.classList.add('is-active');
  }));

  const slider = document.querySelector('[data-slider]');
  if (slider) {
    const slides = [...slider.querySelectorAll('.hero-slide')];
    const dots = [...slider.querySelectorAll('[data-slide-dot]')];
    let current = 0;
    const activate = index => {
      current = index;
      slides.forEach((slide, i) => slide.classList.toggle('is-active', i === index));
      dots.forEach((dot, i) => dot.classList.toggle('is-active', i === index));
    };
    dots.forEach(dot => dot.addEventListener('click', () => activate(Number(dot.dataset.slideDot))));
    if (slides.length > 1) setInterval(() => activate((current + 1) % slides.length), 6500);
  }

  const searchInput = document.querySelector('.search-form input[name="q"]');
  const suggestions = document.querySelector('[data-search-suggestions]');
  let searchTimer;
  searchInput?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const term = searchInput.value.trim();
    if (term.length < 2) { suggestions?.classList.remove('is-open'); return; }
    searchTimer = setTimeout(async () => {
      try {
        const results = await api(`/api/search?q=${encodeURIComponent(term)}`);
        if (!suggestions) return;
        suggestions.innerHTML = results.map(result => `<a href="${result.url}"><img src="${result.image}" alt=""><span><strong>${escapeHtml(result.name)}</strong><small>${escapeHtml(result.sku)}</small></span></a>`).join('');
        suggestions.classList.toggle('is-open', results.length > 0);
      } catch (_) {}
    }, 220);
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.search-form')) suggestions?.classList.remove('is-open');
  });

  function escapeHtml(text) {
    return String(text).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[char]));
  }

  restoreCart();
})();
