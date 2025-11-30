# Lesson 05: File Operations & Airflow Log Structure

## Overview

This function reads Airflow worker log files directly from the filesystem. Unlike journalctl logs (system service logs), these are the actual execution logs where your task's `print()` statements and errors appear.

**Key learning:**
- Airflow's log directory structure
- File pattern matching with `glob`
- File existence checking
- Finding latest files by creation time
- Reading files safely

---

## 🎓 AIRFLOW CONCEPT: Log File Organization

**Airflow's log directory structure:**

```
/home/rocky/airflow/logs/
├── dag_id=health_monitor_v8/
│   ├── run_id=manual__2024-01-15T10:00:00/
│   │   ├── task_id=check_postgresql/
│   │   │   ├── attempt=1.log
│   │   │   ├── attempt=2.log
│   │   │   └── attempt=3.log
│   │   ├── task_id=check_rabbitmq/
│   │   │   └── attempt=1.log
│   │   └── task_id=check_scheduler/
│   │       └── attempt=1.log
│   └── run_id=scheduled__2024-01-15T09:00:00/
│       └── ...
└── dag_id=another_dag/
    └── ...
```

**Path components explained:**

| Component | What it identifies | Example |
|-----------|-------------------|---------|
| `dag_id=X` | Which DAG/workflow | `dag_id=health_monitor_v8` |
| `run_id=X` | Specific DAG execution | `run_id=manual__2024-01-15T10:00:00` |
| `task_id=X` | Individual task | `task_id=check_postgresql` |
| `attempt=N.log` | Retry attempt number | `attempt=2.log` (second try) |

**Why organized this way?**
- Easy to find specific task logs
- Separate logs per retry attempt
- Parallel task runs don't collide
- Filesystem naturally organizes by hierarchy

---

## Code Walkthrough

### Function Setup & Context Extraction (Lines 271-280)

```python
def fetch_airflow_worker_logs() -> str:
    """Fetch Airflow worker logs for the current task"""
    try:
        context = get_current_context()
        dag_id = context['dag'].dag_id
        task_id = context['task'].task_id
        run_id = context['run_id']
        try_number = context['ti'].try_number
        
        log_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/attempt={try_number}.log"
```

**Getting context data:**
```python
context = get_current_context()
# Returns Airflow execution context - everything about current task run

dag_id = context['dag'].dag_id
# Access: context dict → 'dag' object → dag_id property

task_id = context['task'].task_id
# Access: context dict → 'task' object → task_id property

run_id = context['run_id']
# Direct access from context dict

try_number = context['ti'].try_number
# Access: context dict → 'ti' (task instance) → try_number
```

**Example values:**
```python
dag_id = "ha_service_health_monitor_v8"
task_id = "check_postgresql_vip"
run_id = "manual__2024-01-15T14:30:00"
try_number = 1

# Built path:
log_pattern = "/home/rocky/airflow/logs/dag_id=ha_service_health_monitor_v8/run_id=manual__2024-01-15T14:30:00/task_id=check_postgresql_vip/attempt=1.log"
```

**Understanding `context` object:**

```python
context = {
    'dag': DAG_object,           # DAG instance
    'task': Task_object,         # Current task
    'ti': TaskInstance_object,   # Task instance with metadata
    'run_id': 'manual__...',     # String identifier
    'execution_date': datetime,  # When scheduled
    'params': {...},             # User parameters
    'conf': {...},               # Configuration
    # ... many more fields
}
```

---

### 🎓 TIP: The glob Module

**What is glob?**
Finds files matching a pattern using wildcards.

**Wildcards:**
- `*` - Matches any characters (zero or more)
- `?` - Matches exactly one character
- `[abc]` - Matches one character from set
- `**` - Matches directories recursively

**Basic usage:**
```python
import glob

# Find all .log files in directory
files = glob.glob('/var/log/*.log')
# Returns: ['/var/log/system.log', '/var/log/app.log', ...]

# Find specific pattern
files = glob.glob('/logs/task_*.txt')
# Matches: task_1.txt, task_abc.txt, task_123.txt

# Recursive search
files = glob.glob('/logs/**/*.log', recursive=True)
# Searches all subdirectories
```

**Common patterns:**
```python
# All Python files in directory
glob.glob('*.py')

# All files with specific prefix
glob.glob('report_*.pdf')

# Specific subdirectory pattern
glob.glob('logs/*/error.log')

# Multiple extensions
for ext in ['*.txt', '*.log', '*.csv']:
    files = glob.glob(ext)
```

**Returns:**
- List of matching file paths
- Empty list `[]` if no matches
- Paths can be relative or absolute

---

### File Existence Check (Lines 282-287)

```python
print(f"🔍 Searching for worker log at: {log_pattern}")

if os.path.exists(log_pattern):
    with open(log_pattern, 'r') as f:
        lines = f.readlines()
        return ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
```

**File existence check:**
```python
os.path.exists(log_pattern)
# Returns: True if file exists, False otherwise
# Works for files AND directories
```

**The `with` statement:**
```python
with open(log_pattern, 'r') as f:
    # File is open here, assigned to variable 'f'
    lines = f.readlines()
    # Process lines
# File automatically closes here, even if error occurs
```

**Why use `with`?**
- Automatically closes file (even on exceptions)
- Prevents resource leaks
- Cleaner than manual `f.close()`

**Traditional approach (avoid):**
```python
f = open(log_pattern, 'r')
try:
    lines = f.readlines()
finally:
    f.close()  # Must manually close
```

**Reading strategies:**
```python
# Read entire file as string
content = f.read()

# Read all lines into list
lines = f.readlines()  # ['line1\n', 'line2\n', ...]

# Read line by line (memory efficient)
for line in f:
    process(line)
```

**Limiting output:**
```python
lines = f.readlines()
# lines might be: ['line1\n', 'line2\n', ... 'line500\n']

return ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
# Breakdown:
# len(lines) > 200     → Check if more than 200 lines
# lines[-200:]         → Last 200 lines (negative indexing)
# ''.join(...)         → Combine list into single string
# if ... else ...      → Return last 200 OR all if fewer
```

**Example:**
```python
# Scenario 1: File has 500 lines
lines = f.readlines()  # 500 lines
len(lines) > 200       # True
lines[-200:]           # Lines 301-500 (last 200)
result = ''.join(lines[-200:])  # Last 200 lines as string

# Scenario 2: File has 50 lines
lines = f.readlines()  # 50 lines
len(lines) > 200       # False
result = ''.join(lines)  # All 50 lines as string
```

---

### Glob Pattern Matching (Lines 288-297)

```python
else:
    glob_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/*.log"
    matching_files = glob.glob(glob_pattern)
    
    if matching_files:
        latest_file = max(matching_files, key=os.path.getctime)
        with open(latest_file, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
    
    return f"⚠️ Worker log file not found"
```

**Fallback strategy:**
When exact file doesn't exist, search for ANY attempt log.

**Glob pattern:**
```python
glob_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/*.log"

# Example result:
# "/home/rocky/airflow/logs/dag_id=health_monitor/run_id=manual__2024/task_id=check_db/*.log"

# Matches:
# - attempt=1.log
# - attempt=2.log
# - attempt=3.log
# - ANY .log file in that directory
```

**Finding latest file:**
```python
matching_files = glob.glob(glob_pattern)
# Returns: ['/path/attempt=1.log', '/path/attempt=2.log', '/path/attempt=3.log']

latest_file = max(matching_files, key=os.path.getctime)
```

**Understanding `max()` with `key` parameter:**

```python
# Basic max (largest value)
numbers = [1, 5, 3, 9, 2]
largest = max(numbers)  # 9

# max with key function
files = ['file1.log', 'file2.log', 'file3.log']
latest = max(files, key=os.path.getctime)

# How it works:
# 1. For each file, call os.path.getctime(file)
# 2. os.path.getctime returns creation timestamp
# 3. max returns the file with highest (most recent) timestamp
```

**`os.path.getctime()` - Get creation time:**
```python
import os

timestamp = os.path.getctime('/path/to/file.log')
# Returns: 1705324800.123456 (seconds since epoch)

# Example comparison:
file1_time = os.path.getctime('attempt=1.log')  # 1705320000
file2_time = os.path.getctime('attempt=2.log')  # 1705324800
file3_time = os.path.getctime('attempt=3.log')  # 1705329600

# max() picks file3 (highest timestamp = most recent)
```

**Why find latest?**
- Task might have multiple retry attempts
- We want the most recent execution log
- Older attempts might not reflect current state

---

### 🎓 PRACTICAL EXAMPLE: Complete Flow

**Scenario:** Task failed twice, succeeded on third try

```python
# Task details:
dag_id = "data_pipeline"
task_id = "validate_data"
run_id = "scheduled__2024-01-15T08:00:00"
try_number = 3

# Step 1: Build expected path
log_pattern = "/home/rocky/airflow/logs/dag_id=data_pipeline/run_id=scheduled__2024-01-15T08:00:00/task_id=validate_data/attempt=3.log"

# Step 2: Check if exists
if os.path.exists(log_pattern):
    # File exists! Read it directly
    with open(log_pattern, 'r') as f:
        lines = f.readlines()
        # lines = ['2024-01-15 08:00:10 Starting validation\n',
        #          '2024-01-15 08:00:15 Checking schema\n',
        #          '2024-01-15 08:00:20 Validation passed\n']
        return ''.join(lines)

# Step 3: If not found, search for any attempt
glob_pattern = "/home/rocky/airflow/logs/dag_id=data_pipeline/run_id=scheduled__2024-01-15T08:00:00/task_id=validate_data/*.log"

matching_files = glob.glob(glob_pattern)
# matching_files = [
#     '/path/attempt=1.log',  # Created at 1705320000
#     '/path/attempt=2.log',  # Created at 1705324800
#     '/path/attempt=3.log'   # Created at 1705329600 (latest)
# ]

# Step 4: Find most recent
latest_file = max(matching_files, key=os.path.getctime)
# latest_file = '/path/attempt=3.log'

# Step 5: Read latest file
with open(latest_file, 'r') as f:
    lines = f.readlines()
    return ''.join(lines[-200:])  # Last 200 lines
```

---

### Error Handling (Lines 299-301)

```python
except Exception as e:
    return f"⚠️ Error fetching worker logs: {str(e)}"
```

**Catches any exception:**
- File permission errors
- Missing directories
- Context access errors
- Encoding issues

**Returns error message instead of crashing:**
```python
# Example errors:
"⚠️ Error fetching worker logs: Permission denied"
"⚠️ Error fetching worker logs: No such file or directory"
"⚠️ Error fetching worker logs: 'NoneType' object has no attribute 'dag_id'"
```

---

## 🎓 FILE OPERATIONS COMPARISON

**Three approaches used in this code:**

| Method | Use Case | Example |
|--------|----------|---------|
| **Exact path** | Know full path | `os.path.exists('/path/to/file.log')` |
| **Glob pattern** | Search by pattern | `glob.glob('/logs/*.log')` |
| **Find latest** | Get most recent | `max(files, key=os.path.getctime)` |

**When to use each:**

```python
# 1. EXACT PATH - Fastest, when you know the path
if os.path.exists(exact_path):
    with open(exact_path) as f:
        return f.read()

# 2. GLOB - When path varies or multiple files
files = glob.glob('logs/*.log')
for file in files:
    process(file)

# 3. LATEST FILE - When you need most recent
all_backups = glob.glob('backup_*.sql')
if all_backups:
    latest = max(all_backups, key=os.path.getmtime)
    restore(latest)
```

---

## Key Takeaways

✅ **Airflow log structure** - Organized by dag_id/run_id/task_id/attempt

✅ **Context object** - Rich information about current task execution

✅ **`os.path.exists()`** - Check before opening files

✅ **`with` statement** - Safe file handling with auto-close

✅ **`glob.glob()`** - Pattern matching for file search

✅ **`max()` with key** - Find latest file by timestamp

✅ **List slicing** - `lines[-200:]` gets last 200 items

✅ **Fallback strategy** - Try exact path, then glob pattern, then error

---

## What's Next?

Lesson 06 will cover:
- Advanced bash script building in Python
- System resource monitoring (CPU, memory, disk)
- Multi-line f-strings for complex scripts
- Parsing command output

**Ready to continue?** 🚀
