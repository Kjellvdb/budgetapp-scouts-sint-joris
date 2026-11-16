flatpickr('.flatpickr-date', {
  locale: 'nl',
  dateFormat: 'd/m/Y',
  allowInput: true,
});

document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('expensesTable');
  const dateInputs = document.querySelectorAll('#addExpenseModal input[type="date"]');
  const today = new Date().toISOString().split('T')[0];
  const catSelect = document.getElementById('modalCategorie');
  const persoonContainer = document.getElementById('modalPersoonContainer');
  const betaaldContainer = document.getElementById('modalBetaaldContainer');
  const persoonInput = document.getElementById('modalPersoon');
  const betaaldInput = document.getElementById('modalBetaald');
  const scanModal = document.getElementById('scanTicketModal');
  const scanUploadZone = document.getElementById('scanUploadZone');
  const scanFileInput = document.getElementById('scanFileInput');
  const scanThumbnails = document.getElementById('scanThumbnails');
  const scanStatus = document.getElementById('scanStatus');
  const scanStatusText = document.getElementById('scanStatusText');
  const scanError = document.getElementById('scanError');
  const scanWarning = document.getElementById('scanWarning');
  const scanPreviewContainer = document.getElementById('scanPreviewContainer');
  const scanPreviewBody = document.getElementById('scanPreviewBody');
  const scanStartButton = document.getElementById('scanStartBtn');
  const scanSaveButton = document.getElementById('scanSaveBtn');
  if (!scanModal) return;
  if (catSelect) {
    catSelect.addEventListener('change', togglePersonalFields);
    togglePersonalFields();
  }
  dateInputs.forEach((input) => {
    if (!input.value) {
      input.value = today;
    }
  });

  function getLevenshteinDistance(a, b) {
    const matrix = [];
    for (let i = 0; i <= b.length; i++) {
      matrix[i] = [i];
    }
    for (let j = 0; j <= a.length; j++) {
      matrix[0][j] = j;
    }
    for (let i = 1; i <= b.length; i++) {
      for (let j = 1; j <= a.length; j++) {
        if (b.charAt(i - 1) === a.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(matrix[i - 1][j - 1] + 1, Math.min(matrix[i][j - 1] + 1, matrix[i - 1][j] + 1));
        }
      }
    }
    return matrix[b.length][a.length];
  }

  function getTop5Matches(query, options) {
    if (!query) return options.slice(0, 5);
    const query_lowered = query.toLowerCase();

    const scored = options.map((name) => {
      const lowerName = name.toLowerCase();
      let score = getLevenshteinDistance(query_lowered, lowerName);
      if (lowerName.includes(query_lowered)) score -= 5;
      if (lowerName.startsWith(query_lowered)) score -= 10;
      return { name, score };
    });

    scored.sort((a, b) => a.score - b.score);
    return scored.slice(0, 3).map((score) => score.name);
  }

  function togglePersonalFields() {
    if (!catSelect) return;
    const isPersonal = catSelect.value === 'Persoonlijk';
    if (persoonContainer) persoonContainer.style.display = isPersonal ? 'block' : 'none';
    if (betaaldContainer) betaaldContainer.style.display = isPersonal ? 'block' : 'none';
    if (persoonInput) persoonInput.required = isPersonal;
    if (!isPersonal && persoonInput) persoonInput.value = '';
    if (!isPersonal && betaaldInput) betaaldInput.value = 'Nee';
  }

  function triggerFieldChange(element, field, value) {
    const row = element.dataset.row;
    fetch('/uitgaven/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ row: parseInt(row), field: field, value: value }),
    }).then((response) => {
      if (!response.ok) console.error('Fout bij opslaan veld');
    });
  }

  function isValidDate(day, month, year) {
    if (year < 2000 || year > 2100) return false;
    if (month < 1 || month > 12) return false;
    if (day < 1) return false;
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  }

  function setDateError(input, message) {
    input.classList.add('is-invalid');
    input.title = message;
    let feedback = input.parentElement.querySelector('.date-feedback');
    if (!feedback) {
      feedback = document.createElement('div');
      feedback.className = 'date-feedback invalid-feedback';
      feedback.style.display = 'block';
      input.parentElement.appendChild(feedback);
    }
    feedback.textContent = message;
  }

  function clearDateError(input) {
    input.classList.remove('is-invalid');
    input.title = '';
    const feedback = input.parentElement.querySelector('.date-feedback');
    if (feedback) feedback.remove();
  }

  function handleScanFiles(newFiles) {
    const images = newFiles.filter((file) => file.type.startsWith('image/'));
    if (!images.length) return;
    scanFiles = [...scanFiles, ...images].slice(0, 10);
    renderScanThumbnails();
    scanStartButton.disabled = false;
    scanPreviewContainer.classList.add('d-none');
    scanSaveButton.classList.add('d-none');
    scanError.classList.add('d-none');
    scanWarning.classList.add('d-none');
  }

  function renderScanThumbnails() {
    scanThumbnails.innerHTML = '';
    scanFiles.forEach((file, index) => {
      const url = URL.createObjectURL(file);
      const wrapper = document.createElement('div');
      wrapper.className = 'scan-thumb-wrapper';
      const image = document.createElement('img');
      image.src = url;
      image.className = 'scan-thumb-img rounded border';

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'scan-thumb-remove btn btn-danger';
      button.innerHTML = '×';
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        scanFiles.splice(index, 1);
        renderScanThumbnails();
        scanStartButton.disabled = scanFiles.length === 0;
      });

      wrapper.append(image, button);
      scanThumbnails.appendChild(wrapper);
    });
  }

  function renderScanPreview(expenses) {
    scanPreviewBody.innerHTML = '';
    const isoToDisplay = (iso) => {
      if (!iso) return '';
      const parts = iso.split('-');
      return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : iso;
    };
    expenses.forEach((expense) => {
      const tr = document.createElement('tr');
      const tdCheckbox = document.createElement('td');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'form-check-input scan-row-check';
      checkbox.checked = true;
      tdCheckbox.appendChild(checkbox);
      tr.appendChild(tdCheckbox);
      const tdDate = document.createElement('td');
      const dateInput = document.createElement('input');
      dateInput.type = 'text';
      dateInput.className = 'form-control form-control-sm text-center scan-field scan-field-datum';
      dateInput.dataset.field = 'datum';
      dateInput.value = isoToDisplay(expense.datum);
      dateInput.placeholder = 'DD/MM/YYYY';
      tdDate.appendChild(dateInput);
      tr.appendChild(tdDate);
      const tdItem = document.createElement('td');
      tdItem.className = 'text-start';
      const itemInput = document.createElement('input');
      itemInput.type = 'text';
      itemInput.className = 'form-control form-control-sm scan-field';
      itemInput.dataset.field = 'item';
      itemInput.value = expense.item;
      tdItem.appendChild(itemInput);
      tr.appendChild(tdItem);
      const tdAantal = document.createElement('td');
      const aantalInput = document.createElement('input');
      aantalInput.type = 'number';
      aantalInput.min = '1';
      aantalInput.step = '1';
      aantalInput.className = 'form-control form-control-sm text-center scan-field';
      aantalInput.dataset.field = 'aantal';
      aantalInput.value = parseInt(expense.aantal, 10) || 1;
      aantalInput.className += ' scan-field-aantal';
      tdAantal.appendChild(aantalInput);
      tr.appendChild(tdAantal);
      const tdPrijs = document.createElement('td');
      const prijsInput = document.createElement('input');
      prijsInput.type = 'number';
      prijsInput.step = '0.01';
      prijsInput.className = 'form-control form-control-sm text-center scan-field';
      prijsInput.dataset.field = 'prijs';
      prijsInput.value = expense.prijs.toFixed(2);
      prijsInput.className += ' scan-field-prijs';
      tdPrijs.appendChild(prijsInput);
      tr.appendChild(tdPrijs);
      const tdCategorie = document.createElement('td');
      const categorieSelect = document.createElement('select');
      categorieSelect.className = 'form-select form-select-sm scan-field';
      categorieSelect.dataset.field = 'categorie';
      ['Algemeen', 'Alcohol', 'Sterke drank', 'Persoonlijk'].forEach((categorie) => {
        const option = document.createElement('option');
        option.value = categorie;
        option.textContent = categorie;
        if (categorie === expense.categorie) option.selected = true;
        categorieSelect.appendChild(option);
      });
      tdCategorie.appendChild(categorieSelect);
      tr.appendChild(tdCategorie);
      scanPreviewBody.appendChild(tr);
    });
  }

  function collectScanRows() {
    const rows = [];
    scanPreviewBody.querySelectorAll('tr').forEach((tr) => {
      const checkbox = tr.querySelector('.scan-row-check');
      if (!checkbox || !checkbox.checked) return;
      const get = (field) => tr.querySelector(`.scan-field[data-field="${field}"]`)?.value?.trim() || '';
      const dateParts = get('datum').split('/');
      const iso =
        dateParts.length === 3 && dateParts[2].length === 4
          ? `${dateParts[2]}-${dateParts[1].padStart(2, '0')}-${dateParts[0].padStart(2, '0')}`
          : new Date().toISOString().split('T')[0];
      rows.push({
        datum: iso,
        item: get('item'),
        aantal: parseInt(get('aantal')) || 1,
        prijs: parseFloat(get('prijs')) || 0,
        categorie: get('categorie'),
      });
    });
    return rows;
  }

  let scanFiles = [];
  function resetScanModal() {
    scanFiles = [];
    if (scanFileInput) scanFileInput.value = '';
    if (scanThumbnails) scanThumbnails.innerHTML = '';
    scanError.classList.add('d-none');
    scanWarning.classList.add('d-none');
    scanStatus.classList.add('d-none');
    scanPreviewContainer.classList.add('d-none');
    if (scanPreviewBody) scanPreviewBody.innerHTML = '';
    scanStartButton.disabled = true;
    scanSaveButton.classList.add('d-none');
  }

  async function saveScanRow(row) {
    const field = new URLSearchParams();
    field.append('datum', row.datum);
    field.append('item', row.item);
    field.append('aantal', row.aantal);
    field.append('prijs', row.prijs.toFixed(2));
    field.append('categorie', row.categorie);
    field.append('persoon', '');
    field.append('betaald', 'Nee');
    const response = await fetch('/uitgaven/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: field.toString(),
      redirect: 'manual',
    });
    if (!response.ok && response.type !== 'opaqueredirect') {
      throw new Error(`HTTP ${response.status}`);
    }
  }

  function updateDeleteButtonState() {
    const selectedRows = table.querySelectorAll('tbody tr.table-active');
    const count = selectedRows.length;
    const countElement = document.getElementById('selectedCount');
    const deleteButton = document.getElementById('deleteSelectedBtn');
    if (countElement) countElement.textContent = count;
    if (deleteButton) deleteButton.disabled = count === 0;
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
          textElement.textContent = `Weet je zeker dat je ${pendingRowIndices.length} uitgave(n) wilt verwijderen?`;
        }
        deleteModal.show();
      });
      const confirmDeleteButton = document.getElementById('confirmDeleteBtn');
      if (confirmDeleteButton) {
        confirmDeleteButton.replaceWith(confirmDeleteButton.cloneNode(true));
        document.getElementById('confirmDeleteBtn').addEventListener('click', () => {
          if (pendingRowIndices.length === 0) return;
          fetch('/uitgaven/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rows: pendingRowIndices }),
          }).then((response) => {
            if (response.ok) {
              location.reload();
            } else {
              alert('Fout bij het verwijderen van uitgaven.');
              deleteModal.hide();
            }
          });
        });
      }
    }
  }

  document.querySelectorAll('.category-select').forEach((select) => {
    select.addEventListener('change', function () {
      const isPersonal = this.value === 'Persoonlijk';
      const tr = this.closest('tr');
      const personInput = tr.querySelector('.person-input');
      const paidSelect = tr.querySelector('.paid-select');
      triggerFieldChange(this, 'categorie', this.value);
      if (personInput) {
        personInput.disabled = !isPersonal;
        if (!isPersonal) {
          personInput.value = '';
          personInput.classList.remove('is-invalid', 'border-danger');
          personInput.placeholder = '';
          triggerFieldChange(personInput, 'persoon', '');
        } else {
          personInput.placeholder = '⚠️ Naam verplicht';
          if (!personInput.value) {
            personInput.classList.add('is-invalid', 'border-danger');
          }
        }
      }
      if (paidSelect) {
        paidSelect.disabled = !isPersonal;
        if (!isPersonal) {
          paidSelect.value = '';
          triggerFieldChange(paidSelect, 'betaald', '');
        } else {
          paidSelect.value = 'Nee';
          triggerFieldChange(paidSelect, 'betaald', 'Nee');
        }
      }
    });
  });

  document.querySelectorAll('.person-input').forEach((input) => {
    const dropdown = input.parentElement.querySelector('.autocomplete-dropdown');
    function positionDropdown() {
      if (!dropdown) return;
      const rectangle = input.getBoundingClientRect();
      dropdown.style.top = rectangle.bottom + window.scrollY + 'px';
      dropdown.style.left = rectangle.left + 'px';
      dropdown.style.width = rectangle.width + 'px';
    }
    input.addEventListener('input', function () {
      const query = this.value.trim();
      if (!dropdown) return;
      if (query.length === 0) {
        dropdown.style.display = 'none';
        return;
      }
      const matches = getTop5Matches(query, window.appPersons || []);
      if (matches.length === 0) {
        dropdown.style.display = 'none';
        return;
      }
      dropdown.innerHTML = '';
      matches.forEach((match) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'list-group-item list-group-item-action list-group-item-light py-1 px-2 small';
        item.textContent = match;
        item.addEventListener('mousedown', (event) => {
          event.preventDefault();
          input.value = match;
          dropdown.style.display = 'none';
          input.dispatchEvent(new Event('change'));
          input.classList.remove('is-invalid', 'border-danger');
        });
        dropdown.appendChild(item);
      });
      positionDropdown();
      dropdown.style.display = 'block';
    });
    input.addEventListener('blur', () => {
      setTimeout(() => {
        if (dropdown) dropdown.style.display = 'none';
      }, 200);
    });
  });

  document.querySelectorAll('.expense-field').forEach((element) => {
    element.addEventListener('change', function () {
      if (this.classList.contains('category-select')) return;
      const row = this.dataset.row;
      const field = this.dataset.field;
      let value = this.value;
      if (this.type === 'number') {
        if (field === 'aantal') {
          value = parseInt(value, 10) || 1;
          this.value = value;
        } else {
          value = parseFloat(value) || 0;
          this.value = value.toFixed(2);
        }
      }
      fetch('/uitgaven/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(row), field: field, value: value }),
      }).then((response) => {
        if (!response.ok) console.error('Fout bij opslaan van uitgave veld');
      });
    });
  });

  document.querySelectorAll('.date-input').forEach((input) => {
    input.addEventListener('input', function () {
      let value = this.value.replace(/[^\d]/g, '');
      if (value.length >= 3) value = value.slice(0, 2) + '/' + value.slice(2);
      if (value.length >= 6) value = value.slice(0, 5) + '/' + value.slice(5);
      this.value = value.slice(0, 10);
      if (value.replace(/\//g, '').length === 8) {
        const parts = this.value.split('/');
        const [day, month, year] = [parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2])];
        if (!isValidDate(day, month, year)) {
          setDateError(this, 'Ongeldige datum');
        } else {
          clearDateError(this);
        }
      } else {
        clearDateError(this);
      }
    });
    input.addEventListener('change', function () {
      const display = this.value;
      const parts = display.split('/');
      if (parts.length !== 3 || parts[2].length !== 4) return;
      const [day, month, year] = [parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2])];
      if (!isValidDate(day, month, year)) {
        setDateError(this, 'Ongeldige datum');
        return;
      }
      clearDateError(this);
      const iso = `${parts[2]}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      this.dataset.iso = iso;
      fetch('/uitgaven/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row: parseInt(this.dataset.row), field: this.dataset.field, value: iso }),
      }).then((response) => {
        if (!response.ok) console.error('Fout bij opslaan van datum');
      });
    });
  });

  scanModal.addEventListener('hidden.bs.modal', resetScanModal);

  scanUploadZone.addEventListener('click', () => scanFileInput.click());

  scanUploadZone.addEventListener('dragover', (event) => {
    event.preventDefault();
    scanUploadZone.style.borderColor = '#dc3545';
  });

  scanUploadZone.addEventListener('dragleave', () => {
    scanUploadZone.style.borderColor = '';
  });

  scanUploadZone.addEventListener('drop', (event) => {
    event.preventDefault();
    scanUploadZone.style.borderColor = '';
    handleScanFiles([...event.dataTransfer.files]);
  });

  scanFileInput.addEventListener('change', () => {
    handleScanFiles([...scanFileInput.files]);
  });

  scanStartButton.addEventListener('click', async () => {
    if (!scanFiles.length) return;
    scanError.classList.add('d-none');
    scanWarning.classList.add('d-none');
    scanPreviewContainer.classList.add('d-none');
    scanSaveButton.classList.add('d-none');
    scanStatus.classList.remove('d-none');
    scanStatusText.textContent = 'Bezig met uploaden…';
    scanStartButton.disabled = true;
    const formData = new FormData();
    scanFiles.forEach((file) => formData.append('files', file));
    let response;
    try {
      response = await fetch('/uitgaven/scan', { method: 'POST', body: formData });
    } catch (error) {
      scanStatus.classList.add('d-none');
      scanError.textContent = `Netwerkfout: ${error.message}`;
      scanError.classList.remove('d-none');
      scanStartButton.disabled = false;
      return;
    }
    if (!response.ok) {
      scanStatus.classList.add('d-none');
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      scanError.textContent = `Fout: ${error.detail || response.statusText}`;
      scanError.classList.remove('d-none');
      scanStartButton.disabled = false;
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop();
      for (const frame of frames) {
        const line = frame.trim();
        if (!line.startsWith('data:')) continue;
        let payload;
        try {
          payload = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }
        if (payload.status) {
          scanStatusText.textContent = payload.status;
        }
        if (payload.error) {
          scanStatus.classList.add('d-none');
          scanError.textContent = `Fout: ${payload.error}`;
          scanError.classList.remove('d-none');
          scanStartButton.disabled = false;
          return;
        }
        if (payload.done) {
          scanStatus.classList.add('d-none');
          scanStartButton.disabled = false;
          if (payload.warning) {
            scanWarning.textContent = payload.warning;
            scanWarning.classList.remove('d-none');
          }
          if (!payload.expenses || !payload.expenses.length) {
            scanError.textContent = 'Geen items gevonden op het ticket.';
            scanError.classList.remove('d-none');
            return;
          }
          renderScanPreview(payload.expenses);
          scanPreviewContainer.classList.remove('d-none');
          scanSaveButton.classList.remove('d-none');
        }
      }
    }
  });

  scanSaveButton.addEventListener('click', async () => {
    const rows = collectScanRows();
    if (!rows.length) {
      scanError.textContent = 'Geen rijen geselecteerd.';
      scanError.classList.remove('d-none');
      return;
    }
    scanSaveButton.disabled = true;
    scanStatus.classList.remove('d-none');
    scanStatusText.textContent = `Bezig met opslaan (0 / ${rows.length})…`;
    scanError.classList.add('d-none');
    try {
      const response = await fetch('/uitgaven/add-all', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rows }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      scanStatusText.textContent = `Opgeslagen (${result.added} / ${rows.length})`;
      const modal = bootstrap.Modal.getInstance(scanModal);
      if (modal) modal.hide();
      location.reload();
    } catch (error) {
      scanStatus.classList.add('d-none');
      scanError.textContent = `Fout bij het opslaan van de uitgaven: ${error.message}`;
      scanError.classList.remove('d-none');
      scanSaveButton.disabled = false;
    }
  });
});
