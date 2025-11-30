# Lesson 06: Embedded Bash Scripts & Output Parsing

## Overview

This function builds a complex bash script inside Python, executes it remotely or locally, and parses the structured output. It's like having a Swiss Army knife that runs different tools and organizes the results.

**Key learning:**
- Multi-line strings with triple quotes
- Bash script construction in Python
- Temporary files
- Regex pattern matching
- HERE documents for SSH

---

## Multi-Line String Building (Lines 311-360)

### Conditional Script Building

```python
should_calc_logs = hostname in AIRFLOW_NODES_WITH_LOGS

if should_calc_logs:
    logs_calc = '''
if [ -d "/home/rocky/airflow/logs" ]; then
    cd /home/rocky/airflow/logs 2>/dev/null && logs_size=$(du -sh . 2>/dev/null | awk '{print $1}') || logs_size="N/A"
else
    logs_size="N/A"
fi
'''
else:
    logs_calc = 'logs_size="N/A"'
```

**What's happening:**
- Some servers have Airflow logs, some don't
- Build different bash code depending on server type
- Triple quotes `'''` preserve line breaks and formatting

**Bash breakdown:**
```bash
# Check if directory exists
if [ -d "/path" ]; then

# Redirect errors to /dev/null (suppress errors)
2>/dev/null

# Command chaining
command1 && command2 || command3
# && = run command2 if command1 succeeds
# || = run command3 if command2 fails

# du -sh = disk usage, summary, human-readable
# awk '{print $1}' = print first column
```

---

### Main Monitoring Script

```python
monitoring_script = f'''
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}' | cut -d'%' -f1)
cpu_cores=$(nproc)

mem_info=$(free -m | grep Mem)
mem_total=$(echo "$mem_info" | awk '{{print $2}}')
mem_percent=$(awk "BEGIN {{printf \\"%.2f\\", ($mem_used / $mem_total) * 100}}")

disk_info=$(df -h / | tail -1)
disk_percent=$(echo "$disk_info" | awk '{{print $5}}' | sed 's/%//')

top_cpu=$(ps aux --sort=-%cpu | head -6 | tail -5 | awk '{{printf "%s|%s|%s\\n", $11, $3, $2}}')

{logs_calc}

echo "CPU_USAGE=$cpu_usage"
echo "LOGS_SIZE=$logs_size"
echo "TOP_CPU_START"
echo "$top_cpu"
echo "TOP_CPU_END"
'''
```

**F-string with bash variables - the escaping:**

```python
# Python variable - single braces
f"Python: {python_var}"

# Bash variable inside f-string - double braces
f"Bash: ${{bash_var}}"
# {{ becomes { in output
# }} becomes } in output

# Example:
f"echo {{$USER}}"  # Output: echo ${USER}
```

**Escaping quotes in nested contexts:**
```python
# Three levels of quotes:
f"awk \"BEGIN {{printf \\"%.2f\\", value}}\""
# Outer: f"..." (Python f-string)
# Middle: \"...\" (Bash string)
# Inner: \\"...\\" (AWK string)
```

**Key bash commands:**

```bash
# CPU
top -bn1              # Batch mode, one iteration
grep "Cpu(s)"         # Filter CPU line
cut -d'%' -f1         # Cut at %, take field 1

# Memory
free -m               # Show in MB
awk '{print $2}'      # Second column

# Disk
df -h /               # Disk free, human-readable, root partition
sed 's/%//'           # Strip % character

# Top processes
ps aux --sort=-%cpu   # All processes, sorted by CPU (descending)
head -6 | tail -5     # Skip header, get top 5
```

**Structured output format:**
```bash
echo "KEY=value"      # Simple key-value
echo "MARKER_START"   # Section markers
echo "$data"
echo "MARKER_END"
```

Example output:
```
CPU_USAGE=15.2
CPU_CORES=4
MEM_TOTAL=16384
TOP_CPU_START
python|12.5|1234
java|8.3|5678
TOP_CPU_END
```

---

## 🎓 TIP: Temporary Files

**What is tempfile?**
Creates temporary files that are automatically cleaned up.

```python
import tempfile

# Create temporary file
with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
    tf.write("#!/bin/bash\necho 'Hello'")
    temp_path = tf.name  # Get the file path

# File still exists here (delete=False)
# Use it
subprocess.run(['bash', temp_path])

# Manually delete when done
os.unlink(temp_path)
```

**Parameters:**
- `mode='w'` - Write mode
- `suffix='.sh'` - File extension
- `delete=False` - Don't auto-delete when closed

**Why use tempfile?**
- Unique filenames (no collisions)
- Platform-independent location
- Secure permissions

---

## Execution: Local vs Remote (Lines 362-388)

### Local Execution with Temporary File

```python
if is_local_check:
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
        tf.write(monitoring_script)
        temp_script = tf.name
    
    try:
        cmd = f"bash {temp_script}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
    finally:
        os.unlink(temp_script)
```

**Flow:**
1. Create temp file (e.g., `/tmp/tmpXYZ123.sh`)
2. Write bash script to it
3. Execute with bash
4. Delete temp file (even if error occurs)

**`finally` block:**
- Runs no matter what (success, error, exception)
- Perfect for cleanup
- Ensures temp file is deleted

---

### Remote Execution with HERE Document

```python
else:
    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'bash -s' <<'ENDSCRIPT'\n{monitoring_script}\nENDSCRIPT"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
```

**HERE document syntax:**
```bash
ssh user@host 'bash -s' <<'ENDSCRIPT'
# Multi-line script here
echo "Line 1"
echo "Line 2"
ENDSCRIPT
```

**How it works:**
- `bash -s` - Read script from stdin
- `<<'ENDSCRIPT'` - Start HERE document (quoted to prevent expansion)
- Script content
- `ENDSCRIPT` - End marker

**Example built command:**
```bash
ssh rocky@10.101.20.202 'bash -s' <<'ENDSCRIPT'
cpu_usage=$(top -bn1 | grep "Cpu(s)")
echo "CPU_USAGE=$cpu_usage"
ENDSCRIPT
```

---

## Output Parsing (Lines 393-434)

### Simple Key-Value Parsing

```python
output = result.stdout
metrics = {'status': 'success', 'hostname': hostname, 'ip': ip}

for line in output.split('\n'):
    if '=' in line and not line.startswith('TOP_'):
        key, value = line.split('=', 1)
        metrics[key.lower()] = value.strip()
```

**String split with limit:**
```python
line = "MEM_PERCENT=85.50"
key, value = line.split('=', 1)
# key = "MEM_PERCENT"
# value = "85.50"

# Why 1? Limits splits
line = "URL=http://example.com/page?a=1&b=2"
parts = line.split('=', 1)
# ['URL', 'http://example.com/page?a=1&b=2']
# Without 1, would split on ALL = signs
```

**Result:**
```python
metrics = {
    'status': 'success',
    'hostname': 'haproxy-1',
    'cpu_usage': '15.2',
    'mem_percent': '85.50',
    'disk_percent': '45'
}
```

---

### 🎓 TIP: Regex Pattern Matching

**Extract text between markers:**

```python
import re

text = """
Some text
TOP_CPU_START
python|12.5|1234
java|8.3|5678
TOP_CPU_END
More text
"""

pattern = r'TOP_CPU_START\n(.*?)\nTOP_CPU_END'
match = re.search(pattern, text, re.DOTALL)

if match:
    content = match.group(1)
    # content = "python|12.5|1234\njava|8.3|5678"
```

**Pattern explanation:**
- `r'...'` - Raw string (backslashes literal)
- `TOP_CPU_START\n` - Start marker + newline
- `(.*?)` - Capture group, non-greedy
- `\nTOP_CPU_END` - Newline + end marker
- `re.DOTALL` - Make `.` match newlines too

**`match.group(1)`:**
- `group(0)` - Entire match
- `group(1)` - First capture group `(...)`
- `group(2)` - Second capture group (if exists)

---

### Complex Data Parsing

```python
top_cpu_section = re.search(r'TOP_CPU_START\n(.*?)\nTOP_CPU_END', output, re.DOTALL)
if top_cpu_section:
    metrics['top_cpu'] = []
    for line in top_cpu_section.group(1).strip().split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) == 3:
                metrics['top_cpu'].append({
                    'process': parts[0],
                    'cpu_percent': parts[1],
                    'pid': parts[2]
                })
```

**Input data:**
```
TOP_CPU_START
python|12.5|1234
java|8.3|5678
nginx|5.2|9012
TOP_CPU_END
```

**Parsing flow:**
```python
# 1. Extract section
content = "python|12.5|1234\njava|8.3|5678\nnginx|5.2|9012"

# 2. Split into lines
lines = ["python|12.5|1234", "java|8.3|5678", "nginx|5.2|9012"]

# 3. Split each line by |
parts = ["python", "12.5", "1234"]

# 4. Build dictionary
{'process': 'python', 'cpu_percent': '12.5', 'pid': '1234'}

# 5. Append to list
metrics['top_cpu'] = [
    {'process': 'python', 'cpu_percent': '12.5', 'pid': '1234'},
    {'process': 'java', 'cpu_percent': '8.3', 'pid': '5678'},
    {'process': 'nginx', 'cpu_percent': '5.2', 'pid': '9012'}
]
```

**Final metrics structure:**
```python
{
    'status': 'success',
    'hostname': 'celery-1',
    'cpu_usage': '15.2',
    'cpu_cores': '4',
    'mem_percent': '85.50',
    'disk_percent': '45',
    'top_cpu': [
        {'process': 'python', 'cpu_percent': '12.5', 'pid': '1234'},
        {'process': 'java', 'cpu_percent': '8.3', 'pid': '5678'}
    ],
    'top_mem': [
        {'process': 'postgres', 'mem_percent': '25.1', 'pid': '3456'}
    ]
}
```

---

## Key Takeaways

✅ **Triple quotes** - Preserve multi-line bash scripts in Python

✅ **F-string escaping** - `{{bash_var}}` becomes `${bash_var}`

✅ **Temporary files** - Safe, unique files with `tempfile`

✅ **HERE documents** - Send multi-line scripts via SSH

✅ **finally block** - Cleanup that always runs

✅ **Regex extraction** - `re.search()` with capture groups

✅ **Split with limit** - `split('=', 1)` handles values with delimiters

✅ **Structured output** - Key=Value + markers for complex data

---

## What's Next?

Lesson 07 will cover:
- The Airflow DAG decorator (`@dag`)
- DAG configuration and scheduling
- Task decorators (`@task`)
- Dynamic task generation
- Task dependencies

**Ready to continue?** 🚀
