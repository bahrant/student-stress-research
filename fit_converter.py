#!/usr/bin/env python3
"""
FIT Converter - Raw Event Stream Approach
Preserves FIT's timeline of messages without forced alignment
One row per message, with message type preserved
"""

import sys
import os
import zipfile
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Add FIT SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FitSDKRelease_21.171.00/py'))

from garmin_fit_sdk import Decoder, Stream

# Try to import pytz for proper timezone handling
try:
    import pytz
    PACIFIC_TZ = pytz.timezone('America/Los_Angeles')
    HAS_PYTZ = True
except ImportError:
    print("⚠️  Warning: pytz not installed. Install with: pip install pytz")
    HAS_PYTZ = False
    PACIFIC_TZ = None


class FitConverter:
    def __init__(self):
        self.all_events = []  # Raw event stream

    def process_fit_file(self, fit_file_path):
        """
        Process a single FIT file and extract ALL messages as raw events
        Each event preserves: timestamp, message_type, and all available fields
        """
        try:
            stream = Stream.from_file(fit_file_path)
            decoder = Decoder(stream)
            messages, errors = decoder.read()

            if errors:
                print(f"  ⚠️  Decoder errors in {os.path.basename(fit_file_path)}: {len(errors)}")

            # Extract record messages (activity data - HR during workouts)
            if 'record_mesgs' in messages:
                for record in messages['record_mesgs']:
                    timestamp = record.get('timestamp')
                    if timestamp:
                        self.all_events.append({
                            'timestamp': timestamp,
                            'message_type': 'record',
                            'heart_rate': record.get('heart_rate'),
                            'stress_level': None,  # Not in record messages
                            'source_file': os.path.basename(fit_file_path)
                        })

            # Extract monitoring messages (all-day background data)
            # Note: monitoring messages are MIXED - different sub-types interleaved
            if 'monitoring_mesgs' in messages:
                from datetime import timedelta

                # Find base timestamp (start of day reference)
                base_timestamp = None
                for monitor in messages['monitoring_mesgs']:
                    if 'timestamp' in monitor and monitor['timestamp']:
                        base_timestamp = monitor['timestamp']
                        break

                for monitor in messages['monitoring_mesgs']:
                    timestamp = None

                    # Handle full timestamp (appears periodically)
                    if 'timestamp' in monitor and monitor['timestamp']:
                        timestamp = monitor['timestamp']

                    # Handle 16-bit timestamp (seconds since midnight)
                    elif 'timestamp_16' in monitor and base_timestamp:
                        # timestamp_16 = seconds since 00:00:00 of the day
                        day_start = base_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        timestamp = day_start + timedelta(seconds=monitor['timestamp_16'])

                    if timestamp:
                        heart_rate = monitor.get('heart_rate')
                        # Only add if has data (skip empty monitoring messages)
                        if heart_rate is not None:
                            self.all_events.append({
                                'timestamp': timestamp,
                                'message_type': 'monitoring',
                                'heart_rate': heart_rate,
                                'stress_level': None,
                                'source_file': os.path.basename(fit_file_path)
                            })

            # Extract stress level messages (sparse stress events)
            if 'stress_level_mesgs' in messages:
                for stress_msg in messages['stress_level_mesgs']:
                    timestamp = stress_msg.get('stress_level_time')
                    stress_value = stress_msg.get('stress_level_value')

                    if timestamp:
                        self.all_events.append({
                            'timestamp': timestamp,
                            'message_type': 'stress_level',
                            'heart_rate': None,  # Not in stress messages
                            'stress_level': stress_value,
                            'source_file': os.path.basename(fit_file_path)
                        })

            return True

        except Exception as e:
            print(f"  ❌ Error processing {os.path.basename(fit_file_path)}: {e}")
            return False

    def find_fit_files_in_zip(self, zip_path, extract_dir):
        """
        Recursively find all FIT files in a ZIP, including nested ZIPs
        """
        fit_files = []

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            # Walk through extracted files
            for root, dirs, files in os.walk(extract_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)

                    # Check for FIT files
                    if filename.lower().endswith('.fit'):
                        fit_files.append(file_path)

                    # Check for nested ZIP files
                    elif filename.lower().endswith('.zip'):
                        nested_extract = tempfile.mkdtemp(prefix='nested_zip_')
                        nested_fits = self.find_fit_files_in_zip(file_path, nested_extract)
                        fit_files.extend(nested_fits)

            return fit_files

        except Exception as e:
            print(f"Error extracting ZIP: {e}")
            return []

    def convert_timestamp_to_pacific(self, timestamp):
        """
        Convert timestamp to Pacific time and format as MMDDYY and HH:MM
        Properly handles DST if pytz is available
        """
        try:
            # FIT timestamps are datetime objects in UTC
            if isinstance(timestamp, datetime):
                # Ensure UTC timezone is set
                if timestamp.tzinfo is None:
                    utc_time = timestamp.replace(tzinfo=timezone.utc)
                else:
                    utc_time = timestamp

                # Convert to Pacific Time with proper DST handling
                if HAS_PYTZ and PACIFIC_TZ:
                    pacific_time = utc_time.astimezone(PACIFIC_TZ)
                else:
                    # Fallback: simple UTC-8 offset (doesn't handle DST)
                    pacific_offset = -8 * 3600  # seconds
                    pacific_time = datetime.fromtimestamp(utc_time.timestamp() + pacific_offset)

                # Format date as MMDDYY
                date_str = pacific_time.strftime('%m%d%y')

                # Format time as HH:MM
                time_str = pacific_time.strftime('%H:%M')

                return date_str, time_str, pacific_time
            else:
                return None, None, None

        except Exception as e:
            print(f"Error converting timestamp: {e}")
            return None, None, None

    def generate_csv(self, output_path):
        """
        Generate CSV with raw event stream
        Format: MMDDYY,Hour:Minute,Message_Type,Heart_Rate,Stress_Level
        One row per message, preserving event semantics
        """
        if not self.all_events:
            print("No events to write")
            return 0

        # Convert timestamps and prepare events
        processed_events = []
        for event in self.all_events:
            date_str, time_str, sort_time = self.convert_timestamp_to_pacific(event['timestamp'])

            if date_str and time_str and sort_time:
                processed_events.append({
                    'date': date_str,
                    'time': time_str,
                    'message_type': event['message_type'],
                    'heart_rate': event['heart_rate'] if event['heart_rate'] is not None else '',
                    'stress_level': event['stress_level'] if event['stress_level'] is not None else '',
                    'sort_time': sort_time,
                    'source_file': event.get('source_file', '')
                })

        # Sort by timestamp (preserves chronological event order)
        processed_events.sort(key=lambda x: x['sort_time'])

        # Write CSV
        with open(output_path, 'w') as f:
            # Header - Raw Event Stream format
            f.write('MMDDYY,Hour:Minute,Message_Type,Heart_Rate,Stress_Level,Source_File\n')

            # Data rows - one per message event
            for event in processed_events:
                f.write(f"{event['date']},{event['time']},{event['message_type']},{event['heart_rate']},{event['stress_level']},{event['source_file']}\n")

        return len(processed_events)

    def formatCSV(self, csv_path, study='', subject=''):
        """
        Post-process a generated CSV file:
        1. Remove personal email column if present
        2. Add 'Study' and 'Subject' columns (blank by default, or use passed-in values)
        3. Merge rows that share the same date and time into a single row,
           combining heart_rate and stress_level values side-by-side
        Returns the number of merged rows written.
        """
        from collections import OrderedDict

        with open(csv_path, 'r') as f:
            lines = [line.rstrip('\n') for line in f.readlines()]

        if not lines:
            return 0

        # Parse header and identify column indices (case-insensitive)
        raw_header = lines[0].split(',')
        col_idx = {col.strip().lower(): i for i, col in enumerate(raw_header)}

        # Resolve expected column names flexibly
        def find_col(candidates):
            for name in candidates:
                if name in col_idx:
                    return col_idx[name]
            return None

        date_i   = find_col(['mmddyy'])
        time_i   = find_col(['hour:minute'])
        hr_i     = find_col(['heart_rate'])
        stress_i = find_col(['stress_level'])
        source_i = find_col(['source_file'])

        # Identify and skip any email columns
        email_indices = {i for key, i in col_idx.items() if 'email' in key}

        # Parse data rows into structured dicts
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(',')

            def get(i):
                return parts[i].strip() if i is not None and i < len(parts) else ''

            rows.append({
                'date':   get(date_i),
                'time':   get(time_i),
                'hr':     get(hr_i),
                'stress': get(stress_i),
                'source': get(source_i),
            })

        # Merge rows sharing the same (date, time) key.
        # Insertion order is preserved (rows are already chronologically sorted).
        merged = OrderedDict()
        for row in rows:
            key = (row['date'], row['time'])
            if key not in merged:
                merged[key] = {
                    'date':    row['date'],
                    'time':    row['time'],
                    'hr':      '',
                    'stress':  '',
                    'sources': set(),
                }

            entry = merged[key]

            # First non-empty heart_rate wins
            if row['hr'] and not entry['hr']:
                entry['hr'] = row['hr']

            # First non-empty stress_level wins
            if row['stress'] and not entry['stress']:
                entry['stress'] = row['stress']

            # Collect unique source files
            if row['source']:
                entry['sources'].add(row['source'])

        # Write reformatted CSV
        with open(csv_path, 'w') as f:
            f.write('MMDDYY,Hour:Minute,Heart_Rate,Stress_Level,Study,Subject\n')
            for entry in merged.values():
                f.write(
                    f"{entry['date']},{entry['time']},"
                    f"{entry['hr']},{entry['stress']},"
                    f"{study},{subject}\n"
                )

        return len(merged)

    def print_message_statistics(self):
        """
        Print statistics about what message types were found
        """
        message_counts = {}
        for event in self.all_events:
            msg_type = event['message_type']
            message_counts[msg_type] = message_counts.get(msg_type, 0) + 1

        print("\n=== Message Type Statistics ===")
        for msg_type, count in sorted(message_counts.items()):
            print(f"  {msg_type}: {count:,} events")

        # Count events with data
        hr_count = sum(1 for e in self.all_events if e['heart_rate'] is not None)
        stress_count = sum(1 for e in self.all_events if e['stress_level'] is not None)

        print(f"\n=== Data Availability ===")
        print(f"  Events with heart rate: {hr_count:,}")
        print(f"  Events with stress level: {stress_count:,}")

    def process_zip_file(self, zip_path, output_csv_path):
        """
        Main processing function: extract ZIP, process FIT files, generate CSV
        """
        print(f"\n{'='*60}")
        print(f"FitConvert - Raw Event Stream Extraction")
        print(f"Processing: {os.path.basename(zip_path)}")
        print(f"{'='*60}\n")

        # Create temp directory for extraction
        extract_dir = tempfile.mkdtemp(prefix='fitconvert_')

        try:
            # Find all FIT files
            print("📁 Extracting ZIP and searching for FIT files...")
            fit_files = self.find_fit_files_in_zip(zip_path, extract_dir)

            if not fit_files:
                print("❌ No FIT files found in ZIP")
                return False

            print(f"✅ Found {len(fit_files)} FIT files\n")

            # Process each FIT file
            print("⚙️  Processing FIT files...")
            processed_count = 0
            failed_count = 0

            for fit_file in fit_files:
                print(f"   Processing: {os.path.basename(fit_file)}")
                if self.process_fit_file(fit_file):
                    processed_count += 1
                else:
                    failed_count += 1

            print(f"\n✅ Processed: {processed_count} files")
            if failed_count > 0:
                print(f"⚠️  Failed: {failed_count} files")

            # Print statistics
            self.print_message_statistics()

            # Generate CSV
            print(f"\n📝 Generating raw event stream CSV...")
            event_count = self.generate_csv(output_csv_path)

            print(f"✅ CSV generated: {output_csv_path}")
            print(f"📊 Total events: {event_count:,}")

            # Format CSV: merge rows by timestamp, add Study/Subject columns
            print(f"🔧 Formatting CSV (merging rows by timestamp)...")
            merged_count = self.formatCSV(output_csv_path)
            print(f"📊 Merged rows: {merged_count:,}")
            print(f"\n{'='*60}")
            print("✅ Processing complete!")
            print(f"{'='*60}\n")

            return True

        except Exception as e:
            print(f"❌ Error during processing: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temp directory: {e}")


def main():
    """
    Command-line interface
    """
    if len(sys.argv) < 3:
        print("Usage: python fit_converter.py <input.zip> <output.csv>")
        print("\nExample:")
        print("  python fit_converter.py garmin_data.zip output.csv")
        print("\nOutput format: Raw event stream (one row per message)")
        print("  MMDDYY,Hour:Minute,Message_Type,Heart_Rate,Stress_Level,Source_File")
        sys.exit(1)

    input_zip = sys.argv[1]
    output_csv = sys.argv[2]

    # Check if input exists
    if not os.path.exists(input_zip):
        print(f"❌ Error: Input file not found: {input_zip}")
        sys.exit(1)

    # Process
    converter = FitConverter()
    success = converter.process_zip_file(input_zip, output_csv)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
