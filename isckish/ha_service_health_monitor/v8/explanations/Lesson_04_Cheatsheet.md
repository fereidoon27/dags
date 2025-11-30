# Lesson 04 Cheatsheet: Sets, Tuples & Grep Patterns

## Sets (Deduplication)
```python
# Create
items = set()
items = {1, 2, 3}

# Add (ignores duplicates)
items.add(4)
items.add(2)  # No effect

# Check membership (fast!)
if "value" in items:
    print("Found")

# Remove duplicates from list
unique = set([1, 2, 2, 3, 3])  # {1, 2, 3}
```

## Deduplication Pattern
```python
seen = set()
unique_results = []

for item in all_items:
    if item not in seen:
        seen.add(item)
        unique_results.append(item)
```

## Tuples
```python
# Create (immutable)
config = ('name', '10.0.0.1', 'service')

# Access
name = config[0]
ip = config[1]

# Unpack
name, ip, service = config

# List of tuples
servers = [
    ('server1', '10.0.0.1', 'web'),
    ('server2', '10.0.0.2', 'db'),
]

# Unpack in loop
for name, ip, service in servers:
    print(f"{name}: {ip}")
```

## Grep Patterns
```bash
# Extended regex (-E flag)
grep -E 'pattern1|pattern2'     # OR
grep -E '(error|warning)'       # Grouped

# In pipeline
journalctl -n 100 | grep -E '(task_id|run_id)' | tail -50
```

## String Operations
```python
# Split on whitespace
text = "Scheduler haproxy-1"
parts = text.split()  # ['Scheduler', 'haproxy-1']
hostname = parts[1]   # 'haproxy-1'

# String multiplication
separator = '=' * 80  # 80 equal signs

# Join list
lines = ['line1', 'line2', 'line3']
text = '\n'.join(lines)

# Split into lines
text = "line1\nline2\nline3"
lines = text.split('\n')  # ['line1', 'line2', 'line3']
```

## Airflow Task Identifiers

| Field | Meaning | Example |
|-------|---------|---------|
| `dag_id` | Workflow name | `"health_monitor"` |
| `task_id` | Task name | `"check_db"` |
| `run_id` | Run identifier | `"manual__2024-01-15"` |
| `execution_date` | Scheduled time | `2024-01-15 10:00:00` |
| `try_number` | Attempt number | `1`, `2`, `3` |
| `job_id` | Database ID | `12345` |

## Common Patterns

### Multi-Server Log Collection
```python
all_logs = []
seen_lines = set()

servers = [('server1', '10.0.0.1'), ('server2', '10.0.0.2')]

for name, ip in servers:
    logs = fetch_logs(ip)
    
    new_logs = []
    for line in logs.split('\n'):
        if line and line not in seen_lines:
            seen_lines.add(line)
            new_logs.append(line)
    
    if new_logs:
        all_logs.append(f"=== {name} ===\n" + '\n'.join(new_logs))

return '\n\n'.join(all_logs)
```

### Grep Pattern Building
```python
# Build OR pattern
patterns = []
if task_id:
    patterns.append(task_id)
if run_id:
    patterns.append(run_id)

grep_pattern = '|'.join(patterns)  # "task1|run_123"

# Use in command
cmd = f"grep -E '({grep_pattern})' logfile"
```

### Extract from Tuple
```python
component_name = "Scheduler haproxy-1"
parts = component_name.split()
role = parts[0]      # "Scheduler"
hostname = parts[1]  # "haproxy-1"

# One-liner
hostname = component_name.split()[1]
```

## Pipeline Commands
```bash
# Get logs → Filter → Limit
journalctl -u service -n 100 | grep 'pattern' | tail -50

# Components
journalctl -u service -n 100    # Last 100 lines
| grep -E '(p1|p2)'              # Filter with OR
| tail -50                       # Keep last 50 matches
```

## Conditional String Building
```python
# Header with dynamic width
width = 80
header = f"\n{'='*width}\n📋 {title}:\n{'='*width}\n"

# Conditional message
if new_items:
    msg = f"Found {len(new_items)} items"
else:
    msg = "No items found"
```

## Quick Reference

| Operation | Code | Use |
|-----------|------|-----|
| Create set | `s = set()` | Unique collection |
| Add to set | `s.add(x)` | Add item |
| Check membership | `if x in s:` | Fast lookup |
| Remove dupes | `set(list)` | Unique values |
| Unpack tuple | `a, b, c = tuple` | Assign vars |
| Split string | `s.split()` | List of parts |
| String repeat | `'x' * 5` | `'xxxxx'` |
| Join list | `'\n'.join(list)` | Combine with separator |

## Troubleshooting

### Duplicates not removed
```python
# ❌ Checking list (slow)
if item not in results_list:
    results_list.append(item)

# ✅ Using set (fast)
seen = set()
if item not in seen:
    seen.add(item)
```

### Index error on split
```python
# ❌ Assumes format
hostname = name.split()[1]  # Crashes if no space

# ✅ Safe
parts = name.split()
if len(parts) > 1:
    hostname = parts[1]
```

### Wrong grep pattern
```python
# ❌ Missing quotes
cmd = f"grep {pattern} file"  # Breaks with spaces

# ✅ Quoted
cmd = f"grep '{pattern}' file"

# ✅ Extended regex
cmd = f"grep -E '({pattern})' file"
```
