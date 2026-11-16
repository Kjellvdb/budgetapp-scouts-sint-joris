document.addEventListener('DOMContentLoaded', () => {
  const globalCostInput = document.getElementById('globalCostInput');
  const applyGlobalCostButton = document.getElementById('applyGlobalCostBtn');
  const globalCostForm = document.getElementById('globalCostForm');

  function submitGlobalCost() {
    if (!globalCostInput) return;
    const costValue = globalCostInput.value;
    if (!costValue) return;
    const formattedCost = parseFloat(costValue).toFixed(2);
    fetch('/leden/update-all-cost', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cost: parseFloat(costValue) }),
    }).then((response) => {
      if (response.ok) {
        document.querySelectorAll('.member-cost').forEach((input) => {
          input.value = formattedCost;
        });
        const modalElement = document.getElementById('setAllBudgetModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();
      } else {
        alert('Fout bij toepassen kostprijs voor iedereen.');
      }
    });
  }

  if (applyGlobalCostButton) {
    applyGlobalCostButton.addEventListener('click', submitGlobalCost);
  }
  if (globalCostForm) {
    globalCostForm.addEventListener('submit', function (event) {
      event.preventDefault();
      submitGlobalCost();
    });
  }
  if (globalCostInput) {
    globalCostInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        submitGlobalCost();
      }
    });
  }

  document.querySelectorAll('.member-status').forEach((element) => {
    element.addEventListener('change', function () {
      const row = this.dataset.row;
      const field = this.dataset.field;
      const value = this.value;
      if (field === 'betaald') {
        if (value === 'Ja') {
          this.className =
            'form-select form-select-sm member-status status-paid bg-success-subtle text-success-emphasis';
        } else {
          this.className = 'form-select form-select-sm member-status status-paid bg-danger-subtle text-danger-emphasis';
        }
      }
      fetch('/leden/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(row), field: field, value: value }),
      }).then((response) => {
        if (!response.ok) {
          console.error('Fout bij opslaan van wijziging');
        }
      });
    });
  });

  document.querySelectorAll('.member-cost').forEach((input) => {
    if (input.value) {
      input.value = parseFloat(input.value).toFixed(2);
    }
    input.addEventListener('change', function () {
      if (this.value) {
        this.value = parseFloat(this.value).toFixed(2);
      }
      const row = this.dataset.row;
      const value = this.value;
      fetch('/leden/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(row), field: 'kost', value: parseFloat(value) }),
      }).then((response) => {
        if (!response.ok) console.error('Fout bij opslaan kostprijs');
      });
    });
  });
});
