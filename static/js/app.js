document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const fileNameElement = document.getElementById('fileName');
  const submitButton = document.getElementById('submitBtn');
  if (dropzone && fileInput) {
    dropzone.addEventListener('click', (event) => {
      if (!event.target.closest('label')) fileInput.click();
    });
    ['dragenter', 'dragover'].forEach((drag) =>
      dropzone.addEventListener(drag, (event) => {
        event.preventDefault();
        dropzone.classList.add('dragover');
      }),
    );
    ['dragleave', 'drop'].forEach((drag) =>
      dropzone.addEventListener(drag, () => dropzone.classList.remove('dragover')),
    );
    dropzone.addEventListener('drop', (event) => {
      event.preventDefault();
      const file = event.dataTransfer.files[0];
      if (file) setFile(file);
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) setFile(fileInput.files[0]);
    });
    function setFile(file) {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      fileInput.files = dataTransfer.files;
      fileNameElement.textContent = file.name;
      if (submitButton) submitButton.disabled = false;
    }
  }
  document.querySelectorAll('.alert').forEach((element) => {
    setTimeout(() => element.classList.remove('show'), 4000);
  });
});
