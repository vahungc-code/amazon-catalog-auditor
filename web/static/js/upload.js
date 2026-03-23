document.addEventListener('DOMContentLoaded', function () {
    const fileInput = document.getElementById('clr-file');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const uploadBtn = document.getElementById('upload-btn');
    const submitBtn = document.getElementById('submit-btn');

    if (!fileInput) return;

    // File selected via input
    fileInput.addEventListener('change', function () {
        if (fileInput.files.length > 0) {
            showFile(fileInput.files[0]);
        }
    });

    function showFile(file) {
        fileName.textContent = file.name + ' (' + formatSize(file.size) + ')';
        fileInfo.classList.remove('d-none');
        // Hide the "Upload Your CLR File" label, show the submit button
        if (uploadBtn) uploadBtn.classList.add('d-none');
        if (submitBtn) {
            submitBtn.classList.remove('d-none');
            submitBtn.disabled = false;
        }
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
});
