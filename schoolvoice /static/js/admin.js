document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.status-select').forEach((select) => {
    select.addEventListener('change', async () => {
      const id = select.dataset.id;
      const status = select.value;
      const card = select.closest('.note-card');
      card.style.transition = 'opacity 0.3s ease';
      card.style.opacity = '0.5';

      try {
        const res = await fetch('/admin/update_status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, status }),
        });
        const data = await res.json();
        if (data.ok) {
          card.style.opacity = '1';
        } else {
          card.style.opacity = '1';
          alert('Could not update status. Please try again.');
        }
      } catch (err) {
        card.style.opacity = '1';
        alert('Could not reach the server.');
      }
    });
  });

  const modal = document.getElementById('deleteModal');
  const modalCancel = document.getElementById('modalCancel');
  const modalConfirm = document.getElementById('modalConfirm');
  let pendingDelete = null; // { id, card, btn }

  function openModal(id, card, btn) {
    pendingDelete = { id, card, btn };
    modal.classList.add('is-visible');
  }

  function closeModal() {
    modal.classList.remove('is-visible');
    pendingDelete = null;
  }

  modalCancel.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal(); // click on the dim backdrop
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('is-visible')) closeModal();
  });

  modalConfirm.addEventListener('click', async () => {
    if (!pendingDelete) return;
    const { id, card, btn } = pendingDelete;

    modalConfirm.disabled = true;
    modalConfirm.textContent = 'Deleting…';
    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    card.style.opacity = '0.4';
    btn.disabled = true;

    try {
      const res = await fetch('/admin/delete_suggestion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      const data = await res.json();
      if (data.ok) {
        card.style.transform = 'scale(0.95)';
        setTimeout(() => card.remove(), 250);
        closeModal();
      } else {
        card.style.opacity = '1';
        btn.disabled = false;
        alert(data.error || 'Could not delete that note.');
        closeModal();
      }
    } catch (err) {
      card.style.opacity = '1';
      btn.disabled = false;
      alert('Could not reach the server.');
      closeModal();
    }

    modalConfirm.disabled = false;
    modalConfirm.textContent = 'Delete note';
  });

  document.querySelectorAll('.delete-note-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const card = btn.closest('.note-card');
      openModal(id, card, btn);
    });
  });
});
