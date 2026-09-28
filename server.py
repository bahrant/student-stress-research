#!/usr/bin/env python3
"""
FitConvert Web Server - Thin wrapper around fit_converter.py
Just receives files from browser and returns processed CSV
"""

import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from fit_converter import FitConverter

app = Flask(__name__, static_folder='.')
CORS(app)

UPLOAD_FOLDER = tempfile.mkdtemp(prefix='fitconvert_')
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# CSV column layout produced by fit_converter.formatCSV():
# MMDDYY,Hour:Minute,Heart_Rate,Stress_Level,Study,Subject
STUDY_COL_IDX   = 4
SUBJECT_COL_IDX = 5


def sanitize_field(value):
    """Strip commas/newlines so free-text values can't break the (unquoted) CSV."""
    return (value or '').replace(',', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def apply_study_subject(line, study, subject):
    """Overwrite the Study/Subject columns of a single data row."""
    parts = line.split(',')
    while len(parts) <= SUBJECT_COL_IDX:
        parts.append('')
    parts[STUDY_COL_IDX]   = study
    parts[SUBJECT_COL_IDX] = subject
    return ','.join(parts)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/process', methods=['POST'])
def process_upload():
    """Receive ZIP, process with fit_converter.py, return CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file.filename or not file.filename.lower().endswith('.zip'):
            return jsonify({'error': 'Please upload a ZIP file'}), 400

        # Save upload
        filename = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(upload_path)

        # Check size
        if os.path.getsize(upload_path) > MAX_FILE_SIZE:
            os.unlink(upload_path)
            return jsonify({'error': 'File too large (max 500MB)'}), 400

        # Process with fit_converter.py
        output_csv = os.path.join(UPLOAD_FOLDER, f'{filename}_output.csv')
        converter = FitConverter()
        success = converter.process_zip_file(upload_path, output_csv)

        if not success or not os.path.exists(output_csv):
            return jsonify({'error': 'Failed to process FIT files'}), 500

        # Read CSV
        with open(output_csv, 'r') as f:
            csv_content = f.read()

        # Extract date range for frontend
        lines = csv_content.strip().split('\n')
        data_lines = [line for line in lines[1:] if line.strip()]

        available_dates = set()
        for line in data_lines:
            parts = line.split(',')
            if len(parts) >= 1:
                mmddyy = parts[0]
                mm, dd, yy = mmddyy[0:2], mmddyy[2:4], mmddyy[4:6]
                available_dates.add(f"20{yy}-{mm}-{dd}")

        available_dates_list = sorted(list(available_dates))

        # Cleanup
        try:
            os.unlink(upload_path)
            os.unlink(output_csv)
        except:
            pass

        return jsonify({
            'success': True,
            'csvData': csv_content,
            'recordCount': len(data_lines),
            'minDate': available_dates_list[0] if available_dates_list else None,
            'maxDate': available_dates_list[-1] if available_dates_list else None,
            'availableDates': available_dates_list
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/filter', methods=['POST'])
def filter_data():
    """Filter CSV by date range and waking hours"""
    try:
        data = request.get_json()
        csv_content = data.get('csvData', '')
        start_date = data.get('startDate', '')  # YYYY-MM-DD
        end_date = data.get('endDate', '')
        exclude_non_waking  = data.get('excludeNonWaking', False)
        omit_missing        = data.get('omitMissingData', False)
        omit_missing_stress = data.get('omitMissingStress', False)
        study               = sanitize_field(data.get('study', ''))
        subject             = sanitize_field(data.get('subject', ''))

        # Convert YYYY-MM-DD to a sortable YYYYMMDD integer for comparison
        def to_date_int(yyyy_mm_dd):
            parts = yyyy_mm_dd.split('-')
            return int(parts[0] + parts[1] + parts[2]) if len(parts) == 3 else None

        # Convert MMDDYY row value to the same YYYYMMDD integer
        def mmddyy_to_date_int(mmddyy):
            if len(mmddyy) != 6:
                return None
            mm, dd, yy = mmddyy[0:2], mmddyy[2:4], mmddyy[4:6]
            return int(f"20{yy}{mm}{dd}")

        start_date_int = to_date_int(start_date) if start_date else None
        end_date_int = to_date_int(end_date) if end_date else None

        # Filter CSV
        lines = csv_content.strip().split('\n')
        filtered = [lines[0]] if lines else []

        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue

            date_str, time_str = parts[0], parts[1]

            # Date filter — compare as integers (YYYYMMDD) so ordering is chronological
            row_date_int = mmddyy_to_date_int(date_str)
            if row_date_int is None:
                continue
            if start_date_int and row_date_int < start_date_int:
                continue
            if end_date_int and row_date_int > end_date_int:
                continue

            # Waking hours filter (exclude 11pm-5:59am)
            # Exclude: 23:00-23:59 and 00:00-05:59
            if exclude_non_waking:
                try:
                    hour = int(time_str.split(':')[0])
                    # Exclude hour 23 (11pm) and hours 0-5 (midnight to 5:59am)
                    if hour == 23 or hour < 6:
                        continue
                except:
                    pass

            # Omit missing data: drop rows where Heart_Rate is blank
            # AND Stress_Level is blank or negative
            if omit_missing:
                hr_val     = parts[2].strip() if len(parts) > 2 else ''
                stress_val = parts[3].strip() if len(parts) > 3 else ''
                try:
                    stress_is_missing = (not stress_val) or (float(stress_val) < 0)
                except ValueError:
                    stress_is_missing = not stress_val
                if (not hr_val) and stress_is_missing:
                    continue

            # Omit missing stress: drop rows where Stress_Level is blank or <= 1
            if omit_missing_stress:
                stress_val = parts[3].strip() if len(parts) > 3 else ''
                try:
                    if (not stress_val) or (float(stress_val) <= 1):
                        continue
                except ValueError:
                    if not stress_val:
                        continue

            filtered.append(apply_study_subject(line, study, subject))

        return jsonify({
            'success': True,
            'csvData': '\n'.join(filtered),
            'recordCount': len(filtered) - 1
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/process_and_filter', methods=['POST'])
def process_and_filter():
    """Receive ZIP + filter params, process FIT files, filter by date/time, return filtered CSV."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file.filename or not file.filename.lower().endswith('.zip'):
            return jsonify({'error': 'Please upload a ZIP file'}), 400

        start_date = request.form.get('startDate', '')   # YYYY-MM-DD
        end_date = request.form.get('endDate', '')
        exclude_non_waking  = request.form.get('excludeNonWaking',  'false').lower() == 'true'
        omit_missing        = request.form.get('omitMissingData',   'false').lower() == 'true'
        omit_missing_stress = request.form.get('omitMissingStress', 'false').lower() == 'true'
        study               = sanitize_field(request.form.get('study', ''))
        subject             = sanitize_field(request.form.get('subject', ''))

        # Save upload
        filename = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(upload_path)

        if os.path.getsize(upload_path) > MAX_FILE_SIZE:
            os.unlink(upload_path)
            return jsonify({'error': 'File too large (max 500MB)'}), 400

        # Process FIT files → full CSV
        output_csv = os.path.join(UPLOAD_FOLDER, f'{filename}_output.csv')
        converter = FitConverter()
        success = converter.process_zip_file(upload_path, output_csv)

        if not success or not os.path.exists(output_csv):
            return jsonify({'error': 'Failed to process FIT files'}), 500

        with open(output_csv, 'r') as f:
            csv_content = f.read()

        # Date filter helpers — convert to YYYYMMDD integers for correct chronological comparison
        def to_date_int(yyyy_mm_dd):
            parts = yyyy_mm_dd.split('-')
            return int(parts[0] + parts[1] + parts[2]) if len(parts) == 3 else None

        def mmddyy_to_date_int(mmddyy):
            if len(mmddyy) != 6:
                return None
            mm, dd, yy = mmddyy[0:2], mmddyy[2:4], mmddyy[4:6]
            return int(f"20{yy}{mm}{dd}")

        start_date_int = to_date_int(start_date) if start_date else None
        end_date_int = to_date_int(end_date) if end_date else None

        # Apply date/time filter
        lines = csv_content.strip().split('\n')
        filtered = [lines[0]] if lines else []

        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue

            date_str, time_str = parts[0], parts[1]

            row_date_int = mmddyy_to_date_int(date_str)
            if row_date_int is None:
                continue
            if start_date_int and row_date_int < start_date_int:
                continue
            if end_date_int and row_date_int > end_date_int:
                continue

            if exclude_non_waking:
                try:
                    hour = int(time_str.split(':')[0])
                    if hour == 23 or hour < 6:
                        continue
                except Exception:
                    pass

            # Omit missing data: drop rows where Heart_Rate is blank
            # AND Stress_Level is blank or negative
            if omit_missing:
                hr_val     = parts[2].strip() if len(parts) > 2 else ''
                stress_val = parts[3].strip() if len(parts) > 3 else ''
                try:
                    stress_is_missing = (not stress_val) or (float(stress_val) < 0)
                except ValueError:
                    stress_is_missing = not stress_val
                if (not hr_val) and stress_is_missing:
                    continue

            # Omit missing stress: drop rows where Stress_Level is blank or <= 1
            if omit_missing_stress:
                stress_val = parts[3].strip() if len(parts) > 3 else ''
                try:
                    if (not stress_val) or (float(stress_val) <= 1):
                        continue
                except ValueError:
                    if not stress_val:
                        continue

            filtered.append(apply_study_subject(line, study, subject))

        # Cleanup temp files
        try:
            os.unlink(upload_path)
            os.unlink(output_csv)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'csvData': '\n'.join(filtered),
            'recordCount': len(filtered) - 1
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 FitConvert Server")
    print("="*60)
    print("📂 Temp folder:", UPLOAD_FOLDER)
    print("🌐 Open: http://localhost:5001")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5001, debug=True)
