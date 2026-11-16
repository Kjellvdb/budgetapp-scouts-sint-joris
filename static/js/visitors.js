document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('visitorTable');
  const globalCostInput = document.getElementById('globalVisitorCostInput');
  const applyGlobalCostButton = document.getElementById('applyGlobalVisitorCostBtn');
  const globalCostForm = document.getElementById('globalVisitorCostForm');

  function submitGlobalVisitorCost() {
    if (!globalCostInput) return;
    const costValue = globalCostInput.value;
    if (!costValue) return;
    const formattedCost = parseFloat(costValue).toFixed(2);
    fetch('/fourage/update-all-cost', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cost: parseFloat(costValue) }),
    }).then((response) => {
      if (response.ok) {
        document.querySelectorAll('.visitor-cost').forEach((input) => {
          input.value = formattedCost;
        });
        const modalElement = document.getElementById('setAllVisitorCostModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();
      } else {
        alert('Fout bij toepassen kostprijs voor alle bezoekers.');
      }
    });
  }

  function updateDeleteButtonState() {
    const selectedRows = table.querySelectorAll('tbody tr.table-active');
    const count = selectedRows.length;
    const countElement = document.getElementById('selectedCount');
    const deleteButton = document.getElementById('deleteSelectedBtn');
    if (countElement) countElement.textContent = count;
    if (deleteButton) deleteButton.disabled = count === 0;
  }

  if (applyGlobalCostButton) {
    applyGlobalCostButton.addEventListener('click', submitGlobalVisitorCost);
  }
  if (globalCostForm) {
    globalCostForm.addEventListener('submit', function (event) {
      event.preventDefault();
      submitGlobalVisitorCost();
    });
  }
  if (globalCostInput) {
    globalCostInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        submitGlobalVisitorCost();
      }
    });
  }

  if (table) {
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    let lastSelectedRow = null;
    rows.forEach((row, index) => {
      row.addEventListener('click', (event) => {
        if (event.ctrlKey || event.metaKey) {
          row.classList.toggle('table-active');
          lastSelectedRow = row;
        } else if (event.shiftKey && lastSelectedRow) {
          const startIndex = rows.indexOf(lastSelectedRow);
          const endIndex = index;
          const [min, max] = [Math.min(startIndex, endIndex), Math.max(startIndex, endIndex)];
          rows.forEach((row, index) => {
            if (index >= min && index <= max) {
              row.classList.add('table-active');
            }
          });
        } else {
          rows.forEach((row) => row.classList.remove('table-active'));
          row.classList.add('table-active');
          lastSelectedRow = row;
        }
        updateDeleteButtonState();
      });
    });
    const deleteButton = document.getElementById('deleteSelectedBtn');
    const deleteModalElement = document.getElementById('deleteConfirmModal');
    let deleteModal = deleteModalElement ? new bootstrap.Modal(deleteModalElement) : null;
    let pendingRowIndices = [];
    if (deleteButton && deleteModalElement) {
      deleteButton.addEventListener('click', () => {
        const selectedRows = table.querySelectorAll('tbody tr.table-active');
        pendingRowIndices = Array.from(selectedRows).map((row) => parseInt(row.dataset.rowIdx));
        if (pendingRowIndices.length === 0) return;
        const textElement = document.getElementById('deleteConfirmText');
        if (textElement) {
          textElement.textContent = `Weet je zeker dat je ${pendingRowIndices.length} bezoeker(s) wilt verwijderen?`;
        }
        deleteModal.show();
      });
      const confirmDeleteButton = document.getElementById('confirmDeleteBtn');
      if (confirmDeleteButton) {
        confirmDeleteButton.replaceWith(confirmDeleteButton.cloneNode(true));
        document.getElementById('confirmDeleteBtn').addEventListener('click', () => {
          if (pendingRowIndices.length === 0) return;
          fetch('/fourage/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rows: pendingRowIndices }),
          }).then((response) => {
            if (response.ok) {
              location.reload();
            } else {
              alert('Fout bij het verwijderen van bezoekers.');
              deleteModal.hide();
            }
          });
        });
      }
    }
  }

  document.querySelectorAll('.visitor-status').forEach((element) => {
    element.addEventListener('change', function () {
      const row = this.dataset.row;
      const field = this.dataset.field;
      const value = this.value;
      if (field === 'betaald') {
        if (value === 'Ja') {
          this.className =
            'form-select form-select-sm visitor-status status-paid bg-success-subtle text-success-emphasis';
        } else {
          this.className =
            'form-select form-select-sm visitor-status status-paid bg-danger-subtle text-danger-emphasis';
        }
      }
      fetch('/fourage/update', {
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

  document.querySelectorAll('.visitor-cost').forEach((input) => {
    if (input.value) {
      input.value = parseFloat(input.value).toFixed(2);
    }
    input.addEventListener('change', function () {
      if (this.value) {
        this.value = parseFloat(this.value).toFixed(2);
      }
      const row = this.dataset.row;
      const value = this.value;
      fetch('/fourage/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(row), field: 'kost', value: parseFloat(value) }),
      }).then((response) => {
        if (!response.ok) console.error('Fout bij opslaan kostprijs');
      });
    });
  });

  document.querySelectorAll('.visitor-name').forEach((input) => {
    input.addEventListener('change', function () {
      const row = this.dataset.row;
      const value = this.value;
      fetch('/fourage/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(row), field: 'naam', value: value }),
      }).then((response) => {
        if (!response.ok) console.error('Fout bij opslaan van naam');
      });
    });
  });
});
