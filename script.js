'use strict';

class FitConverter {
  constructor() {
    // Cache DOM references
    this.uploadArea       = document.getElementById('uploadArea');
    this.fileInput        = document.getElementById('fileInput');
    this.browseBtn        = document.getElementById('browseBtn');
    this.uploadStatus     = document.getElementById('uploadStatus');
    this.filterSection    = document.getElementById('filterSection');
    this.startDateInput   = document.getElementById('startDate');
    this.endDateInput     = document.getElementById('endDate');
    this.excludeNonWaking = document.getElementById('excludeNonWaking');
    this.omitMissingData   = document.getElementById('omitMissingData');
    this.omitMissingStress = document.getElementById('omitMissingStress');
    this.maxRangeBtn      = document.getElementById('maxRangeBtn');
    this.filterBtn        = document.getElementById('filterBtn');
    this.processingStatus = document.getElementById('processingStatus');
    this.results          = document.getElementById('results');
    this.resultsText      = document.getElementById('resultsText');
    this.downloadBtn      = document.getElementById('downloadBtn');
    this.lastNameInput    = document.getElementById('lastName');
    this.watchIdInput     = document.getElementById('watchId');
    this.studentIdInput   = document.getElementById('studentId');
    this.studyInput       = document.getElementById('study');
    this.themeToggle      = document.getElementById('themeToggle');

    // Application state
    this.selectedFile     = null;
    this.rawCsvData       = null;
    this.filteredCsvData  = null;
    this.availableDates   = [];
    this.minDate          = null;
    this.maxDate          = null;
    this.startPicker      = null;
    this.endPicker        = null;
    this.scanComplete     = false;

    this.setupTheme();
    this.setupUploadHandlers();
    this.setupButtonHandlers();
  }

  // ------------------------------------------------------------------
  // Theme — persisted in localStorage, falls back to prefers-color-scheme
  // ------------------------------------------------------------------
  setupTheme() {
    const saved       = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark      = saved ? saved === 'dark' : prefersDark;

    if (isDark) document.body.classList.add('dark-mode');
    this.updateThemeIcon(isDark);

    this.themeToggle.addEventListener('click', () => {
      const dark = document.body.classList.toggle('dark-mode');
      localStorage.setItem('theme', dark ? 'dark' : 'light');
      this.updateThemeIcon(dark);
    });
  }

  updateThemeIcon(isDark) {
    const icon = this.themeToggle.querySelector('.theme-icon');
    icon.textContent = isDark ? '☀️' : '🌙';
    this.themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  }

  // ------------------------------------------------------------------
  // Upload — click, drag-and-drop, file-input change
  // ------------------------------------------------------------------
  setupUploadHandlers() {
    this.uploadArea.addEventListener('click', () => {
      if (!this.uploadArea.classList.contains('file-selected')) {
        this.fileInput.click();
      }
    });

    this.browseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.fileInput.click();
    });

    this.fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) this.handleFileSelect(e.target.files[0]);
    });

    this.uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.uploadArea.classList.add('dragover');
    });

    this.uploadArea.addEventListener('dragleave', () => {
      this.uploadArea.classList.remove('dragover');
    });

    this.uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      this.uploadArea.classList.remove('dragover');
      if (e.dataTransfer.files.length) this.handleFileSelect(e.dataTransfer.files[0]);
    });
  }

  handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      this.showError('Only .zip files are accepted.');
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      this.showError('File is too large. Maximum size is 100 MB.');
      return;
    }

    this.selectedFile = file;

    // Replace drop zone with success state
    this.uploadArea.classList.add('file-selected');
    this.uploadArea.innerHTML = `
      <div class="file-selected-icon">✅</div>
      <div class="file-selected-name">${this.escapeHtml(file.name)}</div>
      <div class="file-selected-size">${this.formatFileSize(file.size)}</div>
      <button class="btn-secondary" onclick="location.reload()">Select Different File</button>
    `;

    // Unlock Step 2 immediately
    this.filterSection.classList.remove('disabled');

    this.updateUploadStatus('Scanning FIT files to populate date range...');
    this.startBackgroundScan(file);
  }

  // ------------------------------------------------------------------
  // Background Scan — POST /api/process, runs while user sets dates
  // ------------------------------------------------------------------
  async startBackgroundScan(file) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp   = await fetch('http://localhost:5001/api/process', { method: 'POST', body: formData });
      const result = await resp.json();

      if (!result.success) {
        this.updateUploadStatus(
          `⚠️ Server error: ${result.error || 'Unknown error'}. You can enter dates manually.`
        );
        return;
      }

      this.rawCsvData     = result.csvData;
      this.availableDates = result.availableDates || [];
      this.minDate        = result.minDate;
      this.maxDate        = result.maxDate;
      this.scanComplete   = true;

      const count = (result.recordCount || 0).toLocaleString();
      this.updateUploadStatus(
        `${count} records found. Data spans ${this.minDate} &rarr; ${this.maxDate}`
      );

      this.setupDatePickers();
      this.maxRangeBtn.disabled = false;

    } catch {
      this.updateUploadStatus(
        '⚠️ Could not reach the server. It may not be running. You can enter dates manually.'
      );
    }
  }

  updateUploadStatus(html) {
    this.uploadStatus.innerHTML = `<p>${html}</p>`;
  }

  // ------------------------------------------------------------------
  // Date Pickers — initialized with flatpickr after scan completes
  // ------------------------------------------------------------------
  setupDatePickers() {
    const dateSet = new Set(this.availableDates);

    const onDayCreate = (_dObj, _dStr, _fp, dayElem) => {
      if (!dayElem.dateObj) return;
      const d    = dayElem.dateObj;
      const y    = d.getFullYear();
      const m    = String(d.getMonth() + 1).padStart(2, '0');
      const day  = String(d.getDate()).padStart(2, '0');
      if (dateSet.has(`${y}-${m}-${day}`)) {
        dayElem.classList.add('has-data');
      }
    };

    const commonConfig = {
      dateFormat:  'Y-m-d',
      allowInput:  false,
      onDayCreate,
      onChange:    () => this.validateDateSelection(),
    };

    this.startPicker = flatpickr(this.startDateInput, {
      ...commonConfig,
      minDate:     this.minDate || undefined,
      maxDate:     this.maxDate || undefined,
      defaultDate: this.minDate || undefined,
    });

    this.endPicker = flatpickr(this.endDateInput, {
      ...commonConfig,
      minDate:     this.minDate || undefined,
      maxDate:     this.maxDate || undefined,
      defaultDate: this.maxDate || undefined,
    });

    this.validateDateSelection();
  }

  validateDateSelection() {
    // Name / ID / study fields are all optional — only a valid date range is required.
    const start = this.startDateInput.value;
    const end   = this.endDateInput.value;
    this.filterBtn.disabled = !(start && end && start <= end);
  }

  // Subject column = Last Name + last-4 of Student ID, joined by '_' (only non-empty parts).
  buildSubject() {
    const lastName  = this.lastNameInput.value.trim();
    const studentId = this.studentIdInput.value.trim();
    return [lastName, studentId].filter(Boolean).join('_');
  }

  // ------------------------------------------------------------------
  // Button Handlers
  // ------------------------------------------------------------------
  setupButtonHandlers() {
    this.maxRangeBtn.addEventListener('click', () => {
      if (this.startPicker && this.endPicker && this.minDate && this.maxDate) {
        this.startPicker.setDate(this.minDate);
        this.endPicker.setDate(this.maxDate);
        this.validateDateSelection();
      }
    });

    this.lastNameInput.addEventListener('input', () => this.validateDateSelection());
    this.watchIdInput.addEventListener('input',  () => this.validateDateSelection());
    this.filterBtn.addEventListener('click', () => this.handleFilter());
    this.downloadBtn.addEventListener('click', () => this.downloadCSV());
  }

  // ------------------------------------------------------------------
  // Filter — fast path (cached CSV) or slow path (re-process + filter)
  // ------------------------------------------------------------------
  async handleFilter() {
    const startDate        = this.startDateInput.value;
    const endDate          = this.endDateInput.value;
    const excludeNonWaking = this.excludeNonWaking.checked;
    const omitMissingData   = this.omitMissingData.checked;
    const omitMissingStress = this.omitMissingStress.checked;
    const study             = this.studyInput.value.trim();
    const subject           = this.buildSubject();

    this.processingStatus.style.display = 'flex';
    this.results.style.display          = 'none';
    this.filterBtn.disabled             = true;

    try {
      let result;

      if (this.rawCsvData) {
        // Fast path: background scan finished, filter cached CSV server-side
        const resp = await fetch('http://localhost:5001/api/filter', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ csvData: this.rawCsvData, startDate, endDate, excludeNonWaking, omitMissingData, omitMissingStress, study, subject }),
        });
        result = await resp.json();
      } else {
        // Slow path: scan hasn't finished yet — process and filter in one round-trip
        const formData = new FormData();
        formData.append('file',             this.selectedFile);
        formData.append('startDate',        startDate);
        formData.append('endDate',          endDate);
        formData.append('excludeNonWaking', String(excludeNonWaking));
        formData.append('omitMissingData',   String(omitMissingData));
        formData.append('omitMissingStress', String(omitMissingStress));
        formData.append('study',             study);
        formData.append('subject',           subject);

        const resp = await fetch('http://localhost:5001/api/process_and_filter', {
          method: 'POST',
          body:   formData,
        });
        result = await resp.json();
      }

      if (!result.success) {
        this.showError(result.error || 'An error occurred while filtering.');
        return;
      }

      this.filteredCsvData = result.csvData;
      this.showResults(result.recordCount, startDate, endDate);

    } catch {
      this.showError('Could not reach the server. Make sure it is running on port 5000.');
    } finally {
      this.processingStatus.style.display = 'none';
      this.validateDateSelection();
    }
  }

  showResults(recordCount, startDate, endDate) {
    const count = (recordCount || 0).toLocaleString();
    this.resultsText.textContent =
      `Found ${count} records between ${startDate} and ${endDate}. Your filtered CSV file is ready for download.`;
    this.results.style.display = 'block';
    this.results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ------------------------------------------------------------------
  // Download — Blob URL, auto-revoked
  // ------------------------------------------------------------------
  downloadCSV() {
    if (!this.filteredCsvData) return;

    const lastName = this.lastNameInput.value.trim();
    const watchId  = this.watchIdInput.value.trim();
    // Fields are optional — build the name from whatever is filled, fall back to 'output'.
    const base     = [lastName, watchId].filter(Boolean).join('_') || 'output';
    const filename = `${base}.csv`;

    const blob = new Blob([this.filteredCsvData], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);

    const link    = document.createElement('a');
    link.href     = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  // ------------------------------------------------------------------
  // Error handling — inline, auto-dismisses after 5 s
  // ------------------------------------------------------------------
  showError(message) {
    const existing = this.uploadStatus.querySelector('.error-message');
    if (existing) existing.remove();

    const el       = document.createElement('div');
    el.className   = 'error-message';
    el.textContent = message;
    this.uploadStatus.appendChild(el);

    setTimeout(() => el.remove(), 5000);
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  formatFileSize(bytes) {
    if (bytes < 1024)                  return `${bytes} B`;
    if (bytes < 1024 * 1024)           return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024)    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }

  escapeHtml(str) {
    const div     = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

document.addEventListener('DOMContentLoaded', () => new FitConverter());
