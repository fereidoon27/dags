# Python Complete Cheatsheet - All Tips

## Imports
```python
import module                  # Full module
from module import function    # Specific function
from module import *           # Everything (avoid)
```

## Error Handling
```python
try:
    risky_code()
except:
    fallback()

try:
    operation()
except FileNotFoundError:
    handle_missing()
except Exception as e:
    print(f"Error: {e}")

finally:
    cleanup()  # Always runs
```

## Functions
```python
# Basic
def func(param):
    return result

# Default parameters
def func(required, optional=default):
    pass

# Type hints
def func(param: str, num: int = 0) -> str:
    return result

# Multiple returns
def func():
    return val1, val2

a, b = func()  # Unpack
```

## Dictionaries
```python
# Create
data = {}
data = {'key': 'value'}

# Add/modify
data['key'] = 'value'

# Safe access
value = data.get('key', default)
if 'key' in data:
    value = data['key']

# Iterate
for key, value in data.items():
    pass
```

## Lists
```python
# Create
items = []
items = [1, 2, 3]

# Add
items.append(value)
items.extend([a, b, c])

# Slice
last_n = items[-n:]
first_n = items[:n]
items[start:end]

# Check
if items:              # Has items
if not items:          # Empty
if value in items:     # Contains
```

## Sets (Deduplication)
```python
# Create
unique = set()
unique = {1, 2, 3}

# Add (auto-deduplicates)
unique.add(value)

# Check (fast)
if value in unique:
    pass

# Remove duplicates
unique = set([1, 2, 2, 3])  # {1, 2, 3}
```

## List Comprehensions
```python
# Basic
result = [item for item in collection if condition]

# Examples
evens = [x for x in nums if x % 2 == 0]
ids = [task.id for task in tasks]
upper = [s.upper() for s in strings]
```

## Tuples
```python
# Create (immutable)
data = (a, b, c)

# Unpack
x, y, z = data

# In loops
for name, ip, service in servers:
    pass
```

## Strings
```python
# F-strings
f"Value: {var}"
f"Math: {x + y}"
f"{var:10}"      # Width 10
f"{var:>10}"     # Right-align
f"{var:06}"      # Zero-pad

# Methods
s.strip()               # Remove whitespace
s.split()               # Split on whitespace
s.split('/', 1)         # Split once
s.replace(old, new)     # Replace
'|'.join(list)          # Join
s[:10]                  # First 10 chars
s[-10:]                 # Last 10 chars
if 'text' in s:         # Contains
s.upper() / s.lower()   # Case
```

## Files
```python
# Read
with open('file.txt', 'r') as f:
    content = f.read()
    lines = f.readlines()
    for line in f:
        pass

# Write
with open('file.txt', 'w') as f:
    f.write("text")

# Check existence
import os
if os.path.exists('file.txt'):
    pass
```

## Glob (File Search)
```python
import glob

# Find files
files = glob.glob('*.log')
files = glob.glob('/path/*.txt')
files = glob.glob('**/*.py', recursive=True)

# Returns list (empty if no matches)
```

## Subprocess (Shell Commands)
```python
import subprocess

# Run command
result = subprocess.run(
    'ls -l',
    shell=True,
    capture_output=True,
    text=True,
    timeout=10
)

# Access results
result.returncode  # 0 = success
result.stdout      # Output
result.stderr      # Errors

# Check success
if result.returncode == 0:
    pass
```

## SSH Commands
```python
cmd = f'ssh user@{ip} "command"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
```

## Regex
```python
import re

# Search
match = re.search(r'pattern', text)
if match:
    content = match.group(1)  # First capture group

# Flags
re.DOTALL      # . matches newlines
re.IGNORECASE  # Case insensitive

# Pattern: r'START\n(.*?)\nEND'
# Captures text between markers
```

## Temporary Files
```python
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
    tf.write("content")
    temp_path = tf.name

# Use file
subprocess.run(['bash', temp_path])

# Cleanup
os.unlink(temp_path)
```

## Multi-line Strings
```python
# Triple quotes
script = '''
line 1
line 2
'''

# F-string with bash vars
script = f'''
python_var={my_var}
bash_var=${{BASH_VAR}}
'''
# {{ becomes {
# }} becomes }
```

## Context Managers (with)
```python
# Auto-cleanup
with resource as r:
    use(r)
# Auto-closed

# Multiple
with open('a') as f1, open('b') as f2:
    pass
```

## Conditionals
```python
# Ternary
value = x if condition else y

# Multiple conditions
if x and y:
if x or y:
if not x:

# In lists
items = [x for x in lst if x > 0]
```

## String Formatting
```python
# Alignment
f"{text:15}"      # Width 15, left
f"{text:>15}"     # Right-align
f"{text:^15}"     # Center
f"{num:06}"       # Zero-pad: 000042

# Precision
f"{float:.2f}"    # 2 decimals

# Truncate
text[:47] + "..." if len(text) > 50 else text
```

## Common Patterns

### Safe dictionary access
```python
value = data.get('key', 'default')
if hasattr(obj, 'attr'):
    value = obj.attr
```

### Deduplication
```python
seen = set()
unique = []
for item in items:
    if item not in seen:
        seen.add(item)
        unique.append(item)
```

### Build error message
```python
error = f"Failed: {reason}\n"
error += f"Details: {details}\n"
try:
    error += fetch_logs()
except:
    error += "Couldn't fetch logs"
raise Exception(error)
```

### Check and split
```python
if '=' in line:
    key, value = line.split('=', 1)
```

### Filter and map
```python
# Get IDs of failed items
failed_ids = [item.id for item in items if item.status == 'failed']

# Transform
squared = [x**2 for x in numbers]
```

### File operations
```python
# Check then read
if os.path.exists(path):
    with open(path) as f:
        data = f.read()

# Find latest
files = glob.glob('*.log')
if files:
    latest = max(files, key=os.path.getctime)
```

## Key Libraries

### os
```python
os.path.exists(path)
os.path.isfile(path)
os.path.isdir(path)
os.path.getctime(path)  # Creation time
os.path.getmtime(path)  # Modification time
os.getpid()             # Process ID
os.unlink(path)         # Delete file
```

### subprocess
```python
subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
```

### psycopg2 (PostgreSQL)
```python
conn = psycopg2.connect(host=h, database=db, user=u, password=p, connect_timeout=5)
cur = conn.cursor()
cur.execute("SELECT * FROM table WHERE id = %s", (id,))
rows = cur.fetchall()
conn.commit()
cur.close()
conn.close()
```

### pika (RabbitMQ)
```python
credentials = pika.PlainCredentials('user', 'pass')
conn = pika.BlockingConnection(
    pika.ConnectionParameters(host=ip, port=5672, credentials=credentials, socket_timeout=5)
)
conn.close()
```

## Best Practices
- Use `with` for files
- Set timeouts on network operations
- Use parameterized queries (SQL)
- Check file existence before opening
- Handle exceptions gracefully
- Use f-strings over .format()
- Prefer list comprehensions when clear
- Use sets for membership testing
- Always close connections
- Use type hints for documentation

## Quick Troubleshooting
| Issue | Fix |
|-------|-----|
| KeyError | Use `.get(key, default)` |
| AttributeError | Use `hasattr(obj, 'attr')` |
| File not found | Check `os.path.exists()` |
| Timeout | Add `timeout=N` |
| Empty split | Use `split(sep, 1)` |
| No output | Add `capture_output=True` |
| Hanging | Add timeout to subprocess/network |
