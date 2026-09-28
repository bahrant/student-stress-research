# Software Design Document: FitConverter Web Application

**Prepared for:** Junior Developer  
**Date:** 2026-04-11  
**Project:** FitConverter — FIT File to CSV Processor  
**Files being replaced:** `index.html`, `script.js`, `styles.css`

---

## 1. Overview

FitConverter is a single-page web application that lets a user:

1. Upload a `.zip` file containing Garmin `.FIT` activity files
2. Filter the resulting data by date range
3. Download a filtered `.csv` with stress and heart rate data

The frontend communicates with a local Python backend (`server.py`) running at `http://localhost:5000`. You are rebuilding the frontend only — do not change the backend.

---

## 2. File Structure

```
FitConverter/
├── index.html       ← You are rebuilding this (and its companions)
├── script.js        ← Frontend logic (class-based vanilla JS)
├── styles.css       ← All styling, light mode via CSS variables
└── server.py        ← Backend (do NOT touch)
```

**External dependencies (loaded via CDN — keep these):**
- `flatpickr` — date picker library
  - CSS: `https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css`
  - JS: `https://cdn.jsdelivr.net/npm/flatpickr`

---

## 3. Page Layout

The page is a single centered column (`max-width: 900px`). Top to bottom:

```
[ Header ]
  - App title: "FitConvert"
  - Subtitle: "Convert FIT files to CSV format with stress and heart rate data"
  - Dark/Light mode toggle button (top-right corner of header)

[ Main Card ]
  - Step 1: Upload Section
  - Step 2: Date Filter Section  ← locked until file is uploaded
  - Processing Spinner           ← hidden by default
  - Results / Download           ← hidden by default
```

---

## 4. Component Breakdown

### 4.1 Header

- Title `h1`: "FitConverter"
- Subtitle `p`: "Convert FIT files to CSV format with stress and heart rate data"


---

### 4.2 Step 1 — Upload Section (`section.upload-section`)

**Upload Drop Zone (`div#uploadArea`)**

- Dashed border box, large padding, centered content
- Contains:
  - A folder icon (emoji or SVG)
  - Text: "Drop your ZIP file here or click to browse"
  - A hidden `<input type="file" id="fileInput" accept=".zip">`
  - A visible `button#browseBtn` that triggers `fileInput.click()`
- Behaviors:
  - Clicking anywhere on `#uploadArea` also triggers `fileInput.click()`
  - Drag-and-drop: add `.dragover` class on `dragover` event, remove on `dragleave`, handle file on `drop`
  - On file selected: replace the inner HTML of `#uploadArea` with a success state showing the filename and filesize, plus a "Select Different File" button that calls `location.reload()`
  - Validation: only accept `.zip` files, reject files over 100 MB — show an inline error message if either fails

**Upload Status Bar (`div#uploadStatus`)**

- Styled bar (left blue border) below the drop zone
- Default text: placeholder/instructions
- After a file is selected: shows "Scanning FIT files to populate date range..."
- After the background scan completes: shows record count and date span (e.g., "12,340 records found. Data spans 2024-01-01 -> 2024-06-30")
- If scan fails: shows a warning that the server may not be running and tells user to enter dates manually

---

### 4.3 Step 2 — Date Filter Section (`section#filterSection`)

**Locked state:** This entire section starts with `.disabled` applied (CSS: `opacity: 0.5; pointer-events: none`). It is unlocked as soon as the background scan completes.

**Two date pickers (side by side on desktop, stacked on mobile)**

Each picker (`input#startDate`, `input#endDate`) is:
- A read-only text input (typing disabled)
- Initialized with the `flatpickr` library
- Calendar days that have actual data in the dataset are highlighted with a small blue dot below the day number (via a `.has-data` CSS class applied during `onDayCreate`)
- Auto-filled to the min/max of the available date range once the background scan finishes
- Constrained: `minDate` and `maxDate` are set to the bounds of the actual data

**"Exclude non-waking hours" checkbox (`input#excludeNonWaking`)**

- Checked by default
- Label: "Exclude non-waking hours (11pm - 6am)"
- Help text: "Omit data from 11:00 PM to 6:00 AM from the CSV output"

**Action Buttons**

- `button#maxRangeBtn` — "Set max date range": Sets both pickers to the full available date range. Disabled until scan completes.
- `button#filterBtn` — "Return filtered .csv": The primary CTA. Disabled until both dates are selected and valid (start ≤ end). Sends data to the backend.
- Help text below buttons: "Dates are auto-filled to the full range of your data. Adjust as needed, then click 'Return filtered .csv'."

---

### 4.4 Processing Spinner (`div#processingStatus`)

- Hidden (`display: none`) by default
- Shown while an API request is in-flight
- Contains a CSS `spin` animation spinner and text: "Processing FIT files..."
- Hidden again once the request resolves (success or error)

---

### 4.5 Results Panel (`div#results`)

- Hidden (`display: none`) by default
- Shown after a successful filter operation
- Contains:
  - Heading: "Processing Complete"
  - Text: "Found X records between [start] and [end]. Your filtered CSV file is ready for download."
  - `button#downloadBtn` — "Download CSV" (green gradient button)
    - Creates a Blob from the CSV string and triggers a browser download
    - Filename format: `fitconvert_filtered_YYYY-MM-DD_to_YYYY-MM-DD.csv`

---

## 5. API Calls

All requests go to `http://localhost:5000`. Do not change these URLs.

| Endpoint | Method | When called | What it does |
|---|---|---|---|
| `/api/process` | POST (FormData) | Background, right after file select | Sends the ZIP, gets back `csvData` (full CSV string), `availableDates` (array of `YYYY-MM-DD`), and `recordCount` |
| `/api/filter` | POST (JSON) | On "Return filtered .csv" — if background scan already finished | Sends cached `csvData` + `startDate`, `endDate`, `excludeNonWaking`; gets back filtered `csvData` and `recordCount` |
| `/api/process_and_filter` | POST (FormData) | On "Return filtered .csv" — if background scan has NOT finished yet | Sends the ZIP + filter params in one shot; gets back filtered `csvData` and `recordCount` |

All responses are JSON. Check `result.success === true`. On failure, show an error message via `showError()`.

---

## 6. State Machine / Flow

```
App starts
  └─> Step 2 locked, spinner hidden, results hidden

User selects a .zip file
  └─> Step 2 unlocked immediately
  └─> Upload area replaced with success view
  └─> Background: POST to /api/process (runs async)
        ├─ Success: store rawCsvData + availableDates
        │           auto-fill date pickers, update status bar
        └─ Failure: show "server may not be running" warning

User selects dates (flatpickr) → validateDateSelection()
  └─> filterBtn enabled when startDate && endDate && start <= end

User clicks "Return filtered .csv"
  └─> Show spinner, disable filterBtn
  └─> if rawCsvData exists: POST /api/filter (fast path)
      else: POST /api/process_and_filter (slow path)
        ├─ Success: store filteredCsvData, show results panel
        └─ Failure: showError(), hide spinner

User clicks "Download CSV"
  └─> Create Blob from filteredCsvData, trigger download link
```

---

## 7. Error Handling

Use a `showError(message)` function that:
- Creates (or reuses) a `div.error-message` inside `#uploadStatus`
- Styles it with a red background (`#f8d7da`), dark red text (`#721c24`), rounded border
- Auto-removes itself after 5 seconds

---

## 8. Theming

Use CSS custom properties (`--var-name`) for all colors. Two sets:
- Default (`:root`) = light mode
- `body.dark-mode` = dark mode overrides

Key variables to implement:

| Variable | Light | Dark |
|---|---|---|
| `--bg-gradient-start` | `#6fa8dc` | `#1a1a2e` |
| `--bg-gradient-mid` | `#4a90e2` | `#16213e` |
| `--bg-gradient-end` | `#2c5aa0` | `#0f1419` |
| `--card-bg` | `rgba(255,255,255,0.95)` | `rgba(30,30,40,0.95)` |
| `--text-primary` | `#333` | `#e0e0e0` |
| `--text-secondary` | `#2c3e50` | `#ffffff` |

All color transitions should use `transition: ... 0.3s ease`.

The body background is a `linear-gradient(135deg, start 0%, mid 50%, end 100%)`.

---

## 9. Responsive Design

At `max-width: 768px`:
- `.container` padding reduces to `15px`
- `main` padding reduces to `25px`
- `.date-inputs` switches from 2-column grid to single column
- Header `h1` font-size reduces to `2rem`
- Upload area padding reduces

---

## 10. Key ID/Class Reference

| Element | ID or Class |
|---|---|
| File drop zone | `#uploadArea` |
| File input (hidden) | `#fileInput` |
| Browse button | `#browseBtn` |
| Upload status bar | `#uploadStatus` |
| Date filter section | `#filterSection` |
| Start date input | `#startDate` |
| End date input | `#endDate` |
| Exclude non-waking checkbox | `#excludeNonWaking` |
| Max range button | `#maxRangeBtn` |
| Filter/submit button | `#filterBtn` |
| Processing spinner wrapper | `#processingStatus` |
| Results panel | `#results` |
| Download button | `#downloadBtn` |
| Theme toggle button | `#themeToggle` |
| Theme icon span | `.theme-icon` |
| Disabled filter section state | `.filter-section.disabled` |
| Drag active state | `.upload-area.dragover` |
| File selected state | `.upload-area.file-selected` |
| Calendar days with data | `.flatpickr-day.has-data` |

---

## 11. Notes for the Rebuild

- The JS is written as a single ES6 class `FitConverter` instantiated on `DOMContentLoaded`. Keep this pattern.
- `flatpickr` is initialized on both date inputs after a file is selected, not on page load.
- The "Select Different File" button in the success state uses `location.reload()` — this is intentional, it resets the whole app.
- `URL.createObjectURL` / `URL.revokeObjectURL` is used for the download — don't use a data URI approach.
- File size is formatted with a helper: `formatFileSize(bytes)` using KB/MB/GB units.
- Theme is read from `localStorage` key `"theme"` (values: `"dark"` or `"light"`), falling back to `prefers-color-scheme`.
