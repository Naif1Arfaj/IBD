/* Interaction stays native: links and disclosures work without JavaScript. */
(() => {
  const navigationToggle = document.querySelector('.rail-toggle');
  if (navigationToggle) {
    const setNavigation = collapsed => {
      document.documentElement.classList.toggle('nav-collapsed', collapsed);
      navigationToggle.setAttribute('aria-expanded', String(!collapsed));
      const label = collapsed ? 'Expand navigation' : 'Collapse navigation';
      navigationToggle.setAttribute('aria-label', label);
      navigationToggle.title = label;
    };
    let collapsed = false;
    try { collapsed = localStorage.getItem('ibd-navigation') === 'collapsed'; } catch (_) { /* Storage may be disabled. */ }
    setNavigation(collapsed);
    navigationToggle.addEventListener('click', () => {
      const next = !document.documentElement.classList.contains('nav-collapsed');
      setNavigation(next);
      try { localStorage.setItem('ibd-navigation', next ? 'collapsed' : 'expanded'); } catch (_) { /* Keep the current-page preference. */ }
    });
  }
  const openParents = element => {
    for (let node = element.parentElement; node; node = node.parentElement) {
      if (node.tagName === 'DETAILS') node.open = true;
    }
  };
  const revealTarget = target => {
    if (target.tagName === 'DETAILS') target.open = true;
    openParents(target);
    if (target.matches('.evidence-item')) target.querySelector('summary').focus({ preventScroll: true });
    else if (target.matches('input, select, textarea, [tabindex]')) target.focus({ preventScroll: true });
  };
  document.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', () => {
    const target = document.getElementById(link.hash.slice(1));
    if (!target) return;
    revealTarget(target);
  }));
  window.addEventListener('hashchange', () => {
    const target = document.getElementById(location.hash.slice(1));
    if (target) revealTarget(target);
  });
  if (location.hash) {
    const target = document.getElementById(location.hash.slice(1));
    if (target) revealTarget(target);
  }
  document.addEventListener('invalid', event => openParents(event.target), true);
  document.querySelectorAll('form[data-busy]').forEach(form => form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.dataset.original = button.innerHTML;
    button.disabled = true;
    button.classList.add('loading');
    form.setAttribute('aria-busy', 'true');
    const label = button.querySelector('.lbl');
    if (label) label.textContent = form.dataset.busy;
  }));
  window.addEventListener('pageshow', () => document.querySelectorAll('button[data-original]').forEach(button => {
    button.innerHTML = button.dataset.original;
    button.disabled = false;
    button.classList.remove('loading');
    button.form.removeAttribute('aria-busy');
  }));
  document.addEventListener('click', event => document.querySelectorAll('.header-tools details[open]').forEach(detail => {
    if (!detail.contains(event.target)) detail.open = false;
  }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelectorAll('.header-tools details[open]').forEach(detail => {
      detail.open = false;
      detail.querySelector('summary').focus();
    });
  });
  // Print the clinical summary and the details the nurse has chosen to expand.
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
  const errors = document.getElementById('error-summary');
  if (errors) errors.focus();
})();
