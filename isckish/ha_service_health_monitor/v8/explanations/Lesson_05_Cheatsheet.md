# Lesson 05 Cheatsheet: File Operations & Glob

## File Existence
```python
import os

# Check if file exists
if os.path.exists('/path/to/file.log'):
    print("File exists")

# Check file vs directory
os.path.isfile('/path')   # True if file
os.path.isdir('/path')    # True if directory
```

## Reading Files (with statement)
```python
# Read entire file
with open('file.txt', 'r') as f:
    content = f.read()

# Read all lines
with open('file.txt', 'r') as f:
    lines = f.readlines()  # ['line1\n', 'line2\n', ...]

# Read line by line (memory efficient)
with open('file.txt', 'r') as f:
    for line in f:
        process(line)

# Get last N lines
with open('file.txt', 'r') as f:
    lines = f.readlines()
    last_100 = lines[-100:]
```

## Glob Pattern Matching
```python
import glob

# All .log files in directory
files = glob.glob('*.log')
files = glob.glob('/var/log/*.log')

# Specific pattern
files = glob.glob('report_*.pdf')
files = glob.glob('backup_2024*.sql')

# Any file in subdirectories
files = glob.glob('logs/*/*.log')

# Recursive search
files = glob.glob('**/*.py', recursive=True)

# Returns empty list if no matches
files = glob.glob('nonexistent*')  # []
```

## Finding Latest File
```python
import os
import glob

# Get all matching files
files = glob.glob('/logs/*.log')

if files:
    # Find most recent by creation time
    latest = max(files, key=os.path.getctime)
    
    # Or by modification time
    latest = max(files, key=os.path.getmtime)
```

## File Timestamps
```python
import os

# Creation time
created = os.path.getctime('/path/file.log')

# Modification time
modified = os.path.getmtime('/path/file.log')

# Access time
accessed = os.path.getatime('/path/file.log')

# Returns: seconds since epoch (e.g., 1705324800.123)

# Convert to readable format
from datetime import datetime
timestamp = os.path.getctime('file.log')
readable = datetime.fromtimestamp(timestamp)
print(readable)  # 2024-01-15 14:30:45.123
```

## Airflow Log Structure
```
/home/rocky/airflow/logs/
  dag_id=my_dag/
    run_id=manual__2024-01-15T10:00:00/
      task_id=task1/
        attempt=1.log
        attempt=2.log
      task_id=task2/
        attempt=1.log
```

## Airflow Context Access
```python
from airflow.operators.python import get_current_context

context = get_current_context()

# Common fields
dag_id = context['dag'].dag_id
task_id = context['task'].task_id
run_id = context['run_id']
try_number = context['ti'].try_number
execution_date = context['execution_date']
```

## Common Patterns

### Check & Read File
```python
import os

file_path = '/path/to/file.log'

if os.path.exists(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
else:
    print("File not found")
```

### Find & Read Latest
```python
import glob
import os

pattern = '/logs/backup_*.sql'
files = glob.glob(pattern)

if files:
    latest = max(files, key=os.path.getctime)
    with open(latest, 'r') as f:
        data = f.read()
else:
    print("No files found")
```

### Read Last N Lines
```python
with open('large_file.log', 'r') as f:
    lines = f.readlines()
    
    # Get last 100 lines
    if len(lines) > 100:
        last_lines = lines[-100:]
    else:
        last_lines = lines
    
    # Join back to string
    content = ''.join(last_lines)
```

### Airflow Log Path Building
```python
from airflow.operators.python import get_current_context

context = get_current_context()

log_path = (
    f"/home/rocky/airflow/logs/"
    f"dag_id={context['dag'].dag_id}/"
    f"run_id={context['run_id']}/"
    f"task_id={context['task'].task_id}/"
    f"attempt={context['ti'].try_number}.log"
)
```

### Fallback Strategy
```python
import os
import glob

# Try exact path first
if os.path.exists(exact_path):
    with open(exact_path, 'r') as f:
        content = f.read()
else:
    # Fallback: search with pattern
    files = glob.glob(pattern)
    if files:
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r') as f:
            content = f.read()
    else:
        content = "No files found"
```

## Quick Reference

| Operation | Code | Returns |
|-----------|------|---------|
| File exists | `os.path.exists(path)` | Boolean |
| Read file | `with open(f) as f: f.read()` | String |
| Read lines | `f.readlines()` | List |
| Find files | `glob.glob('*.log')` | List of paths |
| Latest file | `max(files, key=os.path.getctime)` | Path |
| Creation time | `os.path.getctime(path)` | Timestamp |
| Last N items | `list[-N:]` | Sliced list |

## Glob Wildcards

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` | Any characters | `*.log` → all .log files |
| `?` | One character | `file?.txt` → file1.txt, fileA.txt |
| `[abc]` | One of set | `file[123].log` → file1.log, file2.log |
| `**` | Recursive | `**/*.py` → all .py in subdirs |

## Troubleshooting

### File not found
```python
# ❌ Assumes file exists
with open('file.log') as f:
    content = f.read()

# ✅ Check first
if os.path.exists('file.log'):
    with open('file.log') as f:
        content = f.read()
```

### Memory issues with large files
```python
# ❌ Loads entire file
with open('huge.log') as f:
    content = f.read()

# ✅ Read last N lines only
with open('huge.log') as f:
    lines = f.readlines()
    content = ''.join(lines[-1000:])

# ✅ Process line by line
with open('huge.log') as f:
    for line in f:
        process(line)
```

### Empty glob result
```python
# ❌ Assumes files exist
latest = max(glob.glob('*.log'), key=os.path.getctime)

# ✅ Check first
files = glob.glob('*.log')
if files:
    latest = max(files, key=os.path.getctime)
```

### Wrong path separator
```python
# ❌ Windows-style on Linux
path = 'logs\\file.log'

# ✅ Use forward slash or os.path.join
path = 'logs/file.log'
path = os.path.join('logs', 'file.log')
```
