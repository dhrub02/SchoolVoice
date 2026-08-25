(function () {
  const root = document.documentElement;
  const stored = null; // no localStorage per artifact-safety practice; falls back to system preference
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  let theme = stored || (prefersDark ? 'dark' : 'light');
  root.setAttribute('data-theme', theme);

  function applyKnob() {
    const knob = document.getElementById('themeKnob');
    if (knob) knob.textContent = theme === 'dark' ? '☾' : '☀︎';
  }
  applyKnob();

  document.addEventListener('DOMContentLoaded', () => {
    applyKnob();
    const toggle = document.getElementById('themeToggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        theme = theme === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', theme);
        applyKnob();
      });
    }

    // scroll reveal
    const revealEls = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.1 });
      revealEls.forEach((el) => io.observe(el));
    } else {
      revealEls.forEach((el) => el.classList.add('is-visible'));
    }
  });
})();
