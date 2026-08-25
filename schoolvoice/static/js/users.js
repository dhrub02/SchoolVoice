document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.remove-user-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = parseInt(btn.dataset.id, 10);
      const name = btn.dataset.name;
      if (!confirm(`Remove staff account "${name}"? They won't be able to sign in anymore.`)) {
        return;
      }

      const row = btn.closest('.user-row');
      row.style.opacity = '0.4';

      try {
        const res = await fetch('/admin/users/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id }),
        });
        const data = await res.json();
        if (data.ok) {
          row.style.transform = 'translateX(12px)';
          setTimeout(() => row.remove(), 250);
        } else {
          row.style.opacity = '1';
          alert(data.error || 'Could not remove that account.');
        }
      } catch (err) {
        row.style.opacity = '1';
        alert('Could not reach the server.');
      }
    });
  });
});
