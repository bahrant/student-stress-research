# formatCSV Function - REFINED Implementation Plan
## Based on Actual Current Output (Exampleoutput.png)

---

## Current CSV Structure Analysis

### Actual Columns (from screenshot)
```
Date, Time, Message_Type, Heart_Rate, Stress_Level, Source_File
```

### Real Data Examples
```csv
22525,15:28,monitoring,,75,bahrant3@gmail.com_314744734613.fit
22525,15:29,monitoring,,73,bahrant3@gmail.com_314744734613.fit
22625,06:25,stress_level,,-2,bahrant3@gmail.com_314744734613.fit
22625,06:30,stress_level,,13,bahrant3@gmail.com_314744734613.fit
```

### Key Observations
1. **✅ Time already 24-hour format** - Times like `15:28`, `06:25` confirm 24hr
2. **Email in Source_File** - Column contains `bahrant3@gmail.com_314744734613.fit`
3. **Message types separate data**:
   - `monitoring` rows: Heart_Rate is EMPTY, Stress_Level has values
   - `stress_level` rows: Heart_Rate is EMPTY, Stress_Level has values
   
   **WAIT - Looking closer at the image:**
   - Monitoring rows (15:28-15:47) have values in column 4 (likely Heart_Rate): 75, 73, 85, 95, etc.
   - Stress_level rows (06:25-06:44) have values in column 5 (Stress_Level): -2, -1, 13, 4, etc.

4. **Date format**: `22525` likely = May 25, 2022 (DDMYY or MMDYY - needs confirmation)

---

## Required Transformations

### BEFORE (Current Output)
```csv
Date,Time,Message_Type,Heart_Rate,Stress_Level,Source_File
22525,15:28,monitoring,75,,bahrant3@gmail.com_314744734613.fit
22525,15:29,monitoring,73,,bahrant3@gmail.com_314744734613.fit
22625,06:30,stress_level,,13,bahrant3@gmail.com_314744734613.fit
```

### AFTER (Formatted Output)
```csv
Date,Time,Study,Subject,Heart_Rate,Stress_Level
22525,15:28,,,75,
22525,15:29,,,73,
22625,06:30,,,13
```

**With parameters: `study="StressStudy", subject="P001"`**
```csv
Date,Time,Study,Subject,Heart_Rate,Stress_Level
22525,15:28,StressStudy,P001,75,
22525,15:29,StressStudy,P001,73,
22625,06:30,StressStudy,P001,,13
```

---

## Aggregation Strategy - SIMPLIFIED

Based on the real data, aggregation is simpler than initially thought:

### Case 1: Different message types at SAME time
```csv
# Input (if this occurs):
22525,15:28,monitoring,75,,file.fit
22525,15:28,stress_level,,23,file.fit

# Output (combined):
22525,15:28,StressStudy,P001,75,23
```

### Case 2: Same message type at SAME time (rare but possible)
```csv
# Input:
22525,15:28,monitoring,75,,file1.fit
22525,15:28,monitoring,78,,file2.fit

# Output (using "last" strategy):
22525,15:28,StressStudy,P001,78,
```

**Recommended default:** `last` value (most recent reading)

---

## Implementation Plan

### Function Signature
```python
def formatCSV(self, input_csv_path, output_csv_path, 
              study="", subject="", 
              aggregation="last"):
    """
    Post-process generated CSV for research-ready format.
    
    Transformations:
    1. Remove Source_File column (contains email)
    2. Add Study and Subject columns
    3. Combine rows with same date+time
    4. Remove Message_Type column
    
    Args:
        input_csv_path: Path to raw CSV from generate_csv()
        output_csv_path: Path for formatted output
        study: Study name (default: empty string)
        subject: Subject ID (default: empty string)
        aggregation: Strategy when multiple values at same time
                    Options: "first", "last", "max", "min", "avg"
                    Default: "last"
    
    Returns:
        int: Number of formatted rows written
    """
```

### Processing Algorithm

```python
def formatCSV(self, input_csv_path, output_csv_path, 
              study="", subject="", aggregation="last"):
    
    # Step 1: Read and parse raw CSV
    grouped_data = {}  # key: (date, time), value: {'hr': [], 'stress': []}
    
    with open(input_csv_path, 'r') as f:
        lines = f.readlines()
        header = lines[0].strip()  # Skip header
        
        for line in lines[1:]:
            parts = line.strip().split(',')
            if len(parts) < 6:
                continue
                
            date = parts[0]
            time = parts[1]
            msg_type = parts[2]
            hr = parts[3]
            stress = parts[4]
            # parts[5] is source_file - we skip it
            
            key = (date, time)
            if key not in grouped_data:
                grouped_data[key] = {'hr': [], 'stress': []}
            
            # Collect non-empty values
            if hr and hr.strip():
                grouped_data[key]['hr'].append(float(hr))
            if stress and stress.strip():
                grouped_data[key]['stress'].append(float(stress))
    
    # Step 2: Aggregate and format
    formatted_rows = []
    for (date, time) in sorted(grouped_data.keys()):
        data = grouped_data[(date, time)]
        
        # Aggregate heart rate
        if data['hr']:
            hr_val = self._aggregate(data['hr'], aggregation)
        else:
            hr_val = ''
        
        # Aggregate stress
        if data['stress']:
            stress_val = self._aggregate(data['stress'], aggregation)
        else:
            stress_val = ''
        
        formatted_rows.append({
            'date': date,
            'time': time,
            'study': study,
            'subject': subject,
            'heart_rate': hr_val,
            'stress_level': stress_val
        })
    
    # Step 3: Write formatted CSV
    with open(output_csv_path, 'w') as f:
        # New header (no Message_Type, no Source_File)
        f.write('Date,Time,Study,Subject,Heart_Rate,Stress_Level\n')
        
        for row in formatted_rows:
            f.write(f"{row['date']},{row['time']},{row['study']},{row['subject']},"
                   f"{row['heart_rate']},{row['stress_level']}\n")
    
    return len(formatted_rows)

def _aggregate(self, values, strategy):
    """Helper to aggregate list of numeric values"""
    if not values:
        return ''
    
    if strategy == 'first':
        return values[0]
    elif strategy == 'last':
        return values[-1]
    elif strategy == 'max':
        return max(values)
    elif strategy == 'min':
        return min(values)
    elif strategy == 'avg':
        return round(sum(values) / len(values), 1)
    else:
        return values[-1]  # default
```

---

## Integration Options

### Option A: Standalone Function (RECOMMENDED)
Keep formatCSV separate from main processing:

```python
# Usage:
converter = FitConverter()
converter.process_zip_file('input.zip', 'raw_output.csv')  # Generate raw
converter.formatCSV('raw_output.csv', 'formatted.csv', 
                   study='StressStudy', subject='P001')  # Format
```

**Pros:**
- Preserves raw data
- User can generate both versions
- Easier to debug

### Option B: Automatic Formatting
Add option to main() CLI:

```bash
python fit_converter.py input.zip output.csv --format --study StressStudy --subject P001
```

**Pros:**
- Single command
- Convenient for end users

### Option C: Separate Script
Create `format_csv.py` as standalone tool:

```bash
python format_csv.py raw.csv formatted.csv --study StressStudy --subject P001
```

**Pros:**
- Completely modular
- Can be used independently

---

## Validation & Testing

### Test Case 1: Basic Transformation
**Input:**
```csv
Date,Time,Message_Type,Heart_Rate,Stress_Level,Source_File
22525,15:28,monitoring,75,,email@gmail.com_file.fit
22525,15:29,monitoring,73,,email@gmail.com_file.fit
```

**Expected Output:**
```csv
Date,Time,Study,Subject,Heart_Rate,Stress_Level
22525,15:28,,,75,
22525,15:29,,,73,
```

### Test Case 2: Same Time Aggregation
**Input:**
```csv
Date,Time,Message_Type,Heart_Rate,Stress_Level,Source_File
22525,15:28,monitoring,75,,file1.fit
22525,15:28,monitoring,78,,file2.fit
22525,15:28,stress_level,,23,file3.fit
```

**Expected Output (aggregation="last"):**
```csv
Date,Time,Study,Subject,Heart_Rate,Stress_Level
22525,15:28,,,78,23
```

### Test Case 3: With Study/Subject
**Input:** (same as Test Case 1)
**Parameters:** `study="MyStudy", subject="S001"`

**Expected Output:**
```csv
Date,Time,Study,Subject,Heart_Rate,Stress_Level
22525,15:28,MyStudy,S001,75,
22525,15:29,MyStudy,S001,73,
```

---

## Data Loss Assessment

### What Gets Lost
1. **Source_File column** - Email addresses and FIT filenames removed
2. **Message_Type column** - Can't distinguish monitoring vs stress_level sources
3. **Within-minute duplicates** - If multiple readings at same time, only aggregated value kept

### What Gets Preserved
1. **All unique timestamps** - One row per unique date+time combination
2. **All data values** - Heart rate and stress readings (aggregated if duplicates)
3. **Chronological order** - Sorted by date+time

### Mitigation
- Always keep original raw CSV
- Document aggregation strategy used
- Provide both raw and formatted versions to researchers

---

## Final Questions for User

1. **Aggregation strategy preference:**
   - `last` (most recent) - RECOMMENDED for physiological data
   - `max` (peak value) - Good for heart rate analysis
   - `avg` (average) - Good for smoothing data
   - `first` (earliest reading)
   
2. **Integration preference:**
   - Option A: Separate function call (keeps raw + formatted)
   - Option B: CLI flag (automatic if requested)
   - Option C: Standalone script
   
3. **Default behavior for Study/Subject:**
   - Leave blank if not provided? ✓
   - Or require as mandatory parameters?

---

## Implementation Checklist

- [ ] Add `formatCSV()` method to FitConverter class
- [ ] Add `_aggregate()` helper method
- [ ] Add CLI integration (if Option B chosen)
- [ ] Update documentation
- [ ] Create test cases
- [ ] Test with real data from Exampleoutput.png
- [ ] Verify email addresses removed
- [ ] Verify Message_Type column removed
- [ ] Verify Study/Subject columns added
- [ ] Verify aggregation works correctly

---

## Ready for Implementation

The plan is complete and feasible. The function will:
✅ Remove email-containing Source_File column
✅ Add Study and Subject columns (blank by default)
✅ Combine rows with same date+time
✅ Remove Message_Type column
✅ Preserve 24-hour time format (already in source)

Awaiting user confirmation on aggregation strategy preference before proceeding to Code mode for implementation.
