document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.rest-toggle-btn').forEach((button) => {
    button.addEventListener('click', function () {
      const naam = this.dataset.naam;
      const currentRest = this.dataset.rest === 'true';
      const newRest = !currentRest;
      fetch('/overzicht/update-rest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ naam: naam, value: newRest }),
      }).then((response) => {
        if (response.ok) {
          location.reload();
        } else {
          alert('Fout bij opslaan rest betaald status.');
        }
      });
    });
  });
});
