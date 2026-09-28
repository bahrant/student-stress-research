# FitConvert - FIT to CSV Converter

Clean, simple FIT file processor that extracts stress and heart rate data into CSV format.

## 🎯 What It Does

1. **Ingests** FIT files (from ZIP archives, including nested ZIPs)
2. **Converts** them to CSV with proper timestamps (Pacific Time)
3. **Combines** all data into a single CSV
4. **Keeps only**: Date, Time, Heart Rate, Stress Level

## 🚀 Quick Start

```bash
./start.sh
```

Then open your browser to: **http://localhost:5000**

## 📋 Requirements

- Python 3.7+
- Modern web browser

## 🔧 Manual Setup (if start.sh doesn't work)

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python3 server.py
```

## 📖 How to Use

### Web Interface

1. **Start the server**: Run `./start.sh`
2. **Open browser**: Go to http://localhost:5000
3. **Upload ZIP**: Drag and drop your ZIP file containing FIT files
4. **Wait for processing**: The app will extract and process all FIT files
5. **Filter (optional)**: Select date range and waking hours filter
6. **Download**: Get your CSV file

### Command Line

```bash
python3 fit_converter.py input.zip output.csv
```

## 📊 Output Format

```csv
MMDDYY,Hour:Minute,Stress Level,Heart Rate
022525,08:24,45,72
022525,08:29,48,75
022625,06:15,38,68
```

**Columns:**
- `MMDDYY`: Date in MMDDYY format (Pacific Time)
- `Hour:Minute`: Time in HH:MM format (Pacific Time)
- `Stress Level`: 0-100 scale (empty if not available)
- `Heart Rate`: BPM (empty if not available)

## 🗂️ File Structure

```
FitConverter/
├── fit_converter.py      # Core processor (uses Python FIT SDK)
├── server.py             # Thin Flask wrapper for web interface
├── index.html            # Web UI
├── script.js             # Frontend logic
├── styles.css            # Styling
├── start.sh              # Startup script
├── requirements.txt      # Python dependencies
└── FitSDKRelease_21.171.00/  # Garmin FIT SDK (included)
```

## ✨ Features

- **Nested ZIP support**: Automatically extracts FIT files from nested ZIPs
- **Date range filtering**: Select specific date ranges
- **Waking hours filter**: Exclude data from 11pm-6am
- **Duplicate removal**: Automatically removes duplicate timestamps
- **Proper timezone handling**: Converts UTC to Pacific Time
- **Error handling**: Graceful handling of corrupt or invalid FIT files

## 🐛 Troubleshooting

### "No FIT files found"
- Make sure your ZIP contains `.fit` files
- Check if FIT files are in nested folders/ZIPs (this is supported)

### "Failed to process FIT files"
- Some FIT files may be corrupt - check console for specific errors
- Try processing individual FIT files to identify problematic ones

### Port 5000 already in use
```bash
# Kill existing process
lsof -ti:5000 | xargs kill -9

# Or change port in server.py (last line)
app.run(host='0.0.0.0', port=8000, debug=True)
```

### Import errors
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

## 🔍 Testing

Test with your actual data:

```bash
python3 fit_converter.py ../84d7fe25-7214-4709-b518-0c3003d1503e_1/DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1.zip test_output.csv
```

## 📝 Notes

- All timestamps are converted to **Pacific Time** (UTC-8)
- Duplicate timestamps are automatically merged
- Empty stress/heart rate values are preserved as empty cells
- The server is stateless - no data is stored permanently
- Temporary files are automatically cleaned up

## 🆘 Support

If you encounter issues:
1. Check the console output for detailed error messages
2. Verify your FIT files are valid
3. Ensure you have Python 3.7+ installed
4. Check that port 5000 is available
