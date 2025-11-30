# Lesson 04: Multi-Server Log Collection & Deduplication

## Overview

This function searches for task-specific logs across multiple Airflow components (schedulers and workers). It's like searching security camera footage from multiple cameras for a specific event - you want to find all relevant clips without duplicates.

**Key learning:**
- Airflow task execution flow across components
- Set-based deduplication
- Grep pattern matching in logs
- Tuple unpacking in loops

---

## 🎓 AIRFLOW CONCEPT: Task Execution Architecture

**Understanding the flow:**

When you run a task in Airflow, multiple components are involved:

1. **Scheduler** - Decides when to run tasks, monitors task states
2. **Worker** (Celery) - Actually executes the task code
3. **Webserver** - Shows UI, handles user requests
4. **Database** - Stores task states, metadata

**Example task lifecycle:**
```
User triggers DAG 
    ↓
Scheduler picks it up → Creates task instances
    ↓
Scheduler queues task → Sends to Celery queue (RabbitMQ)
    ↓
Worker receives task → Executes Python code
    ↓
Worker reports back → Updates database
    ↓
Scheduler marks complete
```

**Why search multiple components?**
- Scheduler logs: Task queuing, state changes
- Worker logs: Actual execution, print statements, errors

**Key Airflow terms in this code:**

| Term | What it means | Example |
|------|---------------|---------|
| `dag_id` | Unique name of the workflow | `"health_monitor_v8"` |
| `task_id` | Specific task within DAG | `"check_postgresql_vip"` |
| `run_id` | Unique ID for this DAG run | `"manual__2024-01-15T10:30:00"` |
| `execution_date` | When task was scheduled | `2024-01-15 10:30:00` |
| `try_number` | Attempt number (1, 2, 3...) | `1` (first try) |
| `job_id` | Database ID for this job | `12345` |

---

## Code Walkthrough

### Setup and Pattern Creation (Lines 212-216)

```python
def fetch_task_specific_logs(identifiers: dict, lines: int = 100) -> str:
    """Fetch logs with grep pattern across Airflow components"""
    grep_pattern = format_identifiers_for_grep(identifiers)
    
    print(f"\n🔍 Searching for task-specific logs using pattern: {grep_pattern}")
```

**What happens:**
- Uses identifiers dictionary we built earlier
- Creates grep pattern like: `"check_db|manual__2024|12345"`
- This pattern will search for ANY of these strings in logs

**Example:**
```python
# Input
identifiers = {
    'task_id': 'check_postgresql',
    'run_id': 'manual__2024-01-15',
    'job_id': 45678
}

# grep_pattern becomes: "check_postgresql|manual__2024-01-15|45678"
# grep -E matches lines containing ANY of these
```

---

### Deduplication Setup (Lines 218-219)

```python
all_logs = []
all_log_lines = set()
```

**Two data structures:**

**`all_logs` (list)**: Stores formatted log sections
- Order matters
- Can have duplicates
- Final output

**`all_log_lines` (set)**: Tracks unique log lines
- No duplicates possible
- Fast lookup (`in` check is O(1))
- Prevents same log appearing twice

**Why both?**
- List preserves order and formatting
- Set ensures uniqueness

---

### 🎓 TIP: Sets for Deduplication

**What is a set?**
Unordered collection of unique items.

```python
# Create set
unique_items = set()
unique_items = {1, 2, 3}  # Or with initial values

# Add items
unique_items.add(4)
unique_items.add(2)  # Ignored - already exists

# Check membership (very fast)
if "value" in unique_items:
    print("Found!")

# Sets automatically remove duplicates
numbers = [1, 2, 2, 3, 3, 3]
unique = set(numbers)  # {1, 2, 3}
```

**Use cases:**
- Remove duplicates from lists
- Fast membership testing
- Set operations (union, intersection)

**Example: Log deduplication**
```python
seen_logs = set()
unique_logs = []

for log in all_server_logs:
    if log not in seen_logs:
        seen_logs.add(log)
        unique_logs.append(log)
# Result: unique_logs has no duplicates
```

---

### Components Configuration (Lines 221-226)

```python
components = [
    ('Scheduler haproxy-1', '10.101.20.202', 'airflow-scheduler'),
    ('Scheduler scheduler-2', '10.101.20.132', 'airflow-scheduler'),
    ('Worker celery-1', '10.101.20.199', 'airflow-worker'),
    ('Worker celery-2', '10.101.20.200', 'airflow-worker'),
]
```

**Structure: List of tuples**
Each tuple contains: `(display_name, ip_address, service_name)`

**Why tuples?**
- Immutable (can't accidentally change)
- Lighter than dictionaries
- Perfect for fixed configuration
- Easy to unpack in loops

**Example unpacking:**
```python
component = ('Scheduler haproxy-1', '10.101.20.202', 'airflow-scheduler')
name, ip, service = component
# name = 'Scheduler haproxy-1'
# ip = '10.101.20.202'
# service = 'airflow-scheduler'
```

---

### Main Loop with Tuple Unpacking (Line 228)

```python
for component_name, ip, service in components:
```

**Tuple unpacking in action:**
```python
# Instead of this:
for component in components:
    name = component[0]
    ip = component[1]
    service = component[2]

# We do this (cleaner):
for component_name, ip, service in components:
    # Variables ready to use
```

**Each iteration:**
- Iteration 1: `component_name='Scheduler haproxy-1'`, `ip='10.101.20.202'`, `service='airflow-scheduler'`
- Iteration 2: `component_name='Scheduler scheduler-2'`, `ip='10.101.20.132'`, `service='airflow-scheduler'`
- etc.

---

### Extracting Hostname (Lines 230-232)

```python
current_host = get_current_hostname()
hostname = component_name.split()[1]
is_local_check = (current_host == hostname)
```

**String split trick:**
```python
component_name = 'Scheduler haproxy-1'
parts = component_name.split()
# parts = ['Scheduler', 'haproxy-1']

hostname = parts[1]  # 'haproxy-1'
# Or directly:
hostname = component_name.split()[1]
```

**Why `.split()[1]`?**
- `split()` breaks on whitespace → `['Scheduler', 'haproxy-1']`
- `[1]` gets second element → `'haproxy-1'`
- We only need the hostname, not the prefix

---

### Building Search Command (Lines 234-237)

```python
if is_local_check:
    cmd = f"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso | grep -E '({grep_pattern})' | tail -50"
else:
    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso | grep -E '({grep_pattern})' | tail -50\""
```

**Command pipeline breakdown:**

**Local command:**
```bash
sudo journalctl -u airflow-scheduler --no-pager -n 100 -o short-iso | grep -E '(check_db|run_123)' | tail -50
```

**Pipeline stages:**
1. `journalctl ...` → Get last 100 lines of service logs
2. `| grep -E '(pattern)'` → Filter only matching lines
3. `| tail -50` → Keep last 50 matches

**Grep flags:**
- `-E` = Extended regex (allows `|` for OR)
- `(pattern)` = Parentheses group the pattern

**Example execution:**
```python
# Assume grep_pattern = "task_123|manual_run"
# This searches for lines containing EITHER "task_123" OR "manual_run"

# Sample log line that would match:
"2024-01-15 10:30:45 [task_123] Starting execution"
"2024-01-15 10:31:00 Running manual_run workflow"
```

---

### Deduplication Logic (Lines 247-261)

```python
if result.returncode == 0 and result.stdout.strip():
    output = result.stdout
    if '[Invalid date]' in output:
        output = output.replace('[Invalid date]', '')
    
    new_lines = []
    for line in output.split('\n'):
        if line.strip() and line not in all_log_lines:
            all_log_lines.add(line)
            new_lines.append(line)
    
    if new_lines:
        all_logs.append(f"\n{'='*80}\n📋 {component_name} logs for this task:\n{'='*80}\n" + '\n'.join(new_lines))
    else:
        all_logs.append(f"\n⭕ No unique logs found in {component_name}")
```

**Deduplication process:**

```python
new_lines = []  # Fresh logs from this component
for line in output.split('\n'):  # Each log line
    if line.strip() and line not in all_log_lines:  # Not empty AND not seen before
        all_log_lines.add(line)      # Mark as seen
        new_lines.append(line)       # Keep for output
```

**Example scenario:**
```python
# Component 1 returns:
all_log_lines = set()
output1 = "Log A\nLog B\nLog C"

for line in output1.split('\n'):
    if line not in all_log_lines:
        all_log_lines.add(line)
        new_lines.append(line)
# Result: all_log_lines = {'Log A', 'Log B', 'Log C'}

# Component 2 returns:
output2 = "Log B\nLog D"

for line in output2.split('\n'):
    if line not in all_log_lines:  # 'Log B' is already in set!
        all_log_lines.add(line)
        new_lines.append(line)
# Result: Only 'Log D' is added (Log B skipped as duplicate)
```

**Formatting output:**
```python
# Creating section header
header = f"\n{'='*80}\n📋 {component_name} logs for this task:\n{'='*80}\n"
# '='*80 creates 80 equals signs: "===============...==============="

# Joining new lines
body = '\n'.join(new_lines)

# Complete section
all_logs.append(header + body)
```

**Result format:**
```
================================================================================
📋 Scheduler haproxy-1 logs for this task:
================================================================================
2024-01-15 10:30:45 Task check_db queued
2024-01-15 10:30:46 Task check_db sent to celery

================================================================================
📋 Worker celery-1 logs for this task:
================================================================================
2024-01-15 10:30:50 Executing task check_db
2024-01-15 10:30:51 Database connection successful
```

---

### Error Handling & Final Return (Lines 262-268)

```python
else:
    all_logs.append(f"\n⭕ No relevant logs found in {component_name}")

except Exception as e:
    all_logs.append(f"\n⚠️ Error fetching logs from {component_name}: {str(e)}")

return '\n'.join(all_logs) if all_logs else "⚠️ No task-specific logs fetched"
```

**Three possible outcomes per component:**
1. **Success with logs**: Formatted log section added
2. **Success no logs**: "No relevant logs found" message
3. **Error**: Error message added

**Final return:**
- Joins all sections with newlines
- Fallback message if completely empty

---

## 🎓 REAL-WORLD EXAMPLE

**Scenario:** Task fails on celery-1 worker

```python
# identifiers passed in:
{
    'task_id': 'check_database',
    'run_id': 'scheduled__2024-01-15T10:00:00',
    'job_id': 789,
    'try_number': 2  # Second attempt
}

# grep_pattern created:
"check_database|scheduled__2024-01-15T10:00:00|789"

# Function searches 4 components:
# 1. Scheduler haproxy-1:   Finds "Task check_database queued at 10:00:01"
# 2. Scheduler scheduler-2: No matches
# 3. Worker celery-1:       Finds "Task check_database failed: DB timeout"
# 4. Worker celery-2:       No matches

# Output:
"""
================================================================================
📋 Scheduler haproxy-1 logs for this task:
================================================================================
2024-01-15 10:00:01 Task check_database queued for execution

================================================================================
📋 Worker celery-1 logs for this task:
================================================================================
2024-01-15 10:00:05 Executing task check_database attempt #2
2024-01-15 10:00:10 Database connection timeout after 5 seconds
2024-01-15 10:00:10 Task check_database failed: DB timeout

⭕ No relevant logs found in Scheduler scheduler-2
⭕ No relevant logs found in Worker celery-2
"""
```

---

## Key Takeaways

✅ **Airflow architecture** - Tasks flow through scheduler → queue → worker

✅ **Sets prevent duplicates** - `set()` for fast membership testing

✅ **Tuple unpacking** - Clean loop syntax: `for name, ip, service in items:`

✅ **Grep patterns** - Search multiple terms: `grep -E '(term1|term2|term3)'`

✅ **String multiplication** - `'='*80` creates separator lines

✅ **Deduplication pattern** - Check set membership before adding to results

---

## What's Next?

Lesson 05 will cover:
- File operations with `glob` pattern matching
- Reading Airflow worker log files
- File timestamps and sorting
- The `with` statement for safe file handling

**Ready to continue?** 🚀
