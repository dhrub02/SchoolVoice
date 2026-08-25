document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('suggestionForm');
  if (!form) return;

  const categoryRow = document.getElementById('categoryRow');
  const message = document.getElementById('message');
  const charCount = document.getElementById('charCount');
  const charStatus = document.getElementById('charStatus');
  const honestCheck = document.getElementById('honestCheck');
  const errorList = document.getElementById('errorList');
  const submitBtn = document.getElementById('submitBtn');
  const noteFly = document.getElementById('noteFly');
  const successPanel = document.getElementById('successPanel');
  const againBtn = document.getElementById('againBtn');

  let activeCategory = categoryRow.querySelector('.chip.is-active').dataset.value;

  categoryRow.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    categoryRow.querySelectorAll('.chip').forEach((c) => c.classList.remove('is-active'));
    chip.classList.add('is-active');
    activeCategory = chip.dataset.value;
  });

  message.addEventListener('input', () => {
    const len = message.value.length;
    charCount.textContent = len < 20 ? `${len} / 20 minimum` : `${len} / 2000`;
    charCount.classList.toggle('is-ok', len >= 20);
    charStatus.textContent = `${len} / 2000`;
  });

  function showErrors(msgs) {
    errorList.innerHTML = '';
    msgs.forEach((m) => {
      const li = document.createElement('li');
      li.textContent = m;
      errorList.appendChild(li);
    });
    errorList.classList.toggle('is-visible', msgs.length > 0);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    showErrors([]);
    submitBtn.disabled = true;
    submitBtn.textContent = 'Pinning…';

    try {
      const res = await fetch('/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: activeCategory,
          message: message.value,
          honest_check: honestCheck.checked,
        }),
      });
      const data = await res.json();

      if (!data.ok) {
        showErrors(data.errors || ['Something went wrong. Please try again.']);
        submitBtn.disabled = false;
        submitBtn.textContent = 'Pin this note →';
        return;
      }

      // signature animation: note flies up into the slot
      noteFly.classList.remove('is-flying');
      void noteFly.offsetWidth; // restart animation
      noteFly.classList.add('is-flying');

      setTimeout(() => {
        form.classList.add('is-hidden');
        successPanel.classList.add('is-visible');
      }, 650);
    } catch (err) {
      showErrors(['Could not reach the server. Please check your connection and try again.']);
      submitBtn.disabled = false;
      submitBtn.textContent = 'Pin this note →';
    }
  });

  againBtn.addEventListener('click', () => {
    form.reset();
    activeCategory = categoryRow.querySelector('.chip').dataset.value;
    categoryRow.querySelectorAll('.chip').forEach((c, i) => c.classList.toggle('is-active', i === 0));
    charCount.textContent = '0 / 20 minimum';
    charStatus.textContent = '0 / 2000';
    charCount.classList.remove('is-ok');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Pin this note →';
    successPanel.classList.remove('is-visible');
    form.classList.remove('is-hidden');
  });
});
