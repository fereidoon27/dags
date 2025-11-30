# Lesson 06 Cheatsheet: Bash Scripts in Python

## Multi-Line Strings
```python
# Triple quotes preserve formatting
script = '''
line 1
line 2
line 3
'''

# F-string with bash variables
script = f'''
python_var={my_var}
bash_var=${{MY_VAR}}
'''
# {{ becomes { 
# }} becomes }
```

## F-String Escaping
```python
# Python variable
f"{python_var}"

# Bash variable in f-string
f"${{bash_var}}"

# Nested quotes
f"awk \"BEGIN {{printf \\"%.2f\\", val}}\""
```

## Temporary Files
```python
import tempfile
import os

# Create temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
    tf.write("#!/bin/bash\necho hello")
    temp_path = tf.name

# Use it
subprocess.run(['bash', temp_path])

# Clean up
os.unlink(temp_path)
```

## Finally Block
```python
# Always runs, even on error
temp_file = create_temp()
try:
    process(temp_file)
finally:
    os.unlink(temp_file)  # Always deleted
```

## SSH HERE Documents
```bash
# Send multi-line script via SSH
ssh user@host 'bash -s' <<'ENDSCRIPT'
echo "Line 1"
echo "Line 2"
ENDSCRIPT

# In Python
cmd = f"""ssh user@{ip} 'bash -s' <<'END'
{script}
END"""
```

## Regex Pattern Matching
```python
import re

# Extract between markers
text = "START\ncontent\nEND"
match = re.search(r'START\n(.*?)\nEND', text, re.DOTALL)
if match:
    content = match.group(1)

# Flags
re.DOTALL   # . matches newlines
re.MULTILINE  # ^ and $ match line boundaries
re.IGNORECASE  # Case insensitive

# Groups
match.group(0)  # Full match
match.group(1)  # First (...)
match.group(2)  # Second (...)
```

## String Split with Limit
```python
# Without limit
"a=b=c".split('=')  # ['a', 'b', 'c']

# With limit
"a=b=c".split('=', 1)  # ['a', 'b=c']

# Use case: key-value with = in value
line = "URL=http://site.com?a=1"
key, value = line.split('=', 1)
# key = 'URL'
# value = 'http://site.com?a=1'
```

## Bash Commands Quick Reference
```bash
# CPU
top -bn1 | grep "Cpu(s)" | awk '{print $2}'

# Memory
free -m | grep Mem | awk '{print $2}'

# Disk
df -h / | tail -1 | awk '{print $5}'

# Top processes
ps aux --sort=-%cpu | head -6 | tail -5

# Directory size
du -sh /path

# Suppress errors
command 2>/dev/null

# Command chaining
cmd1 && cmd2 || cmd3
# && runs if success
# || runs if failure
```

## Common Patterns

### Build & Execute Local Script
```python
import tempfile
import subprocess

script = '''
#!/bin/bash
echo "Running on $(hostname)"
df -h /
'''

with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
    tf.write(script)
    temp_path = tf.name

try:
    result = subprocess.run(
        ['bash', temp_path],
        capture_output=True,
        text=True,
        timeout=30
    )
    print(result.stdout)
finally:
    os.unlink(temp_path)
```

### Execute Remote Script
```python
script = '''
hostname
uptime
free -m
'''

cmd = f"ssh user@{ip} 'bash -s' <<'ENDSCRIPT'\n{script}\nENDSCRIPT"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
```

### Parse Key-Value Output
```python
output = """
CPU=15.2
MEM=85.5
DISK=45
"""

metrics = {}
for line in output.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        metrics[key.lower()] = value.strip()

# metrics = {'cpu': '15.2', 'mem': '85.5', 'disk': '45'}
```

### Parse Sectioned Output
```python
import re

output = """
START
data1|value1
data2|value2
END
"""

match = re.search(r'START\n(.*?)\nEND', output, re.DOTALL)
if match:
    items = []
    for line in match.group(1).split('\n'):
        if line.strip():
            parts = line.split('|')
            items.append({'name': parts[0], 'value': parts[1]})
```

## Quick Reference

| Operation | Code | Result |
|-----------|------|--------|
| Multi-line string | `'''text'''` | Preserves formatting |
| Bash var in f-string | `f"${{var}}"` | `${var}` |
| Temp file | `tempfile.NamedTemporaryFile()` | Unique temp path |
| Cleanup | `finally: os.unlink(f)` | Always runs |
| Regex extract | `re.search(r'(.*)', s)` | Capture content |
| Split with limit | `s.split('=', 1)` | Max 2 parts |
| Regex group | `match.group(1)` | First capture |

## Troubleshooting

### Bash variables not working in f-string
```python
# ❌ Single braces
f"${var}"  # Interpreted as Python variable

# ✅ Double braces
f"${{var}}"  # Becomes ${var}
```

### Temp file not deleted on error
```python
# ❌ No cleanup
temp = create_temp()
process(temp)  # Error here = no cleanup
os.unlink(temp)

# ✅ Finally block
temp = create_temp()
try:
    process(temp)
finally:
    os.unlink(temp)  # Always runs
```

### Split breaks on value with delimiter
```python
# ❌ Splits all occurrences
"URL=http://site.com?a=1".split('=')
# ['URL', 'http://site.com?a', '1']

# ✅ Limit splits
"URL=http://site.com?a=1".split('=', 1)
# ['URL', 'http://site.com?a=1']
```

### Regex doesn't match newlines
```python
# ❌ Missing DOTALL flag
re.search(r'START(.*?)END', text)

# ✅ With DOTALL
re.search(r'START(.*?)END', text, re.DOTALL)
```
