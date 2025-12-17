# Python Quick Reference - All Tips

## Type Hints
```python
from typing import List, Dict, Optional

def func(name: str) -> str:
def get_files() -> List[str]:
def get_config() -> Dict[str, int]:
def maybe_value() -> Optional[str]:
def no_return() -> None:
```

## String Operations
```python
# F-strings
name = "John"
message = f"Hello {name}"
cmd = f"python3 {script} {arg}"

# String methods
text.strip()           # Remove whitespace
text.split('\n')       # Split by newline
text.decode()          # Bytes to string
text.encode()          # String to bytes
```

## List Operations
```python
# List comprehension
files = [f for f in files if f and f.strip()]
nums = [x*2 for x in range(10)]

# Filter empty/None
items = [x for x in items if x]
items = list(filter(None, items))

# Append
items.append('new')

# Length
count = len(items)
```

## Dictionary Operations
```python
# Create
config = {'host': '10.0.0.1', 'user': 'admin'}

# Access
value = config['key']
value = config.get('key', 'default')

# Add/update
config['new_key'] = 'value'

# Check key exists
if 'key' in config:

# Track results
results = {'success': [], 'failed': []}
results['success'].append(item)
```

## Boolean Evaluation
```python
# Empty = False
if []:           # False
if {}:           # False
if "":           # False
if None:         # False
if 0:            # False

# Not empty = True
if [1,2,3]:      # True
if "text":       # True

# Explicit None check
if value is None:
if value is not None:

# Multiple conditions
if not files or files is None:
```

## File Path Operations
```python
from pathlib import Path

path = Path('/home/user/file.txt')
path.name      # 'file.txt'
path.parent    # '/home/user'
path.stem      # 'file'
path.suffix    # '.txt'

# Build paths
new_path = Path('/home') / 'user' / 'file.txt'
```

## Exception Handling
```python
# Basic try/except
try:
    risky_operation()
except Exception as e:
    print(f"Error: {str(e)}")

# Specific exceptions
except FileNotFoundError:
except PermissionError:
except ValueError:

# Finally (always runs)
try:
    do_work()
finally:
    cleanup()

# Raise exceptions
raise ValueError("Bad input")
raise Exception(f"Failed: {error}")
```

## Context Managers (with)
```python
# File handling
with open('file.txt', 'r') as f:
    content = f.read()

# Auto-closes even if error

# SFTP
with sftp.file(path, 'r') as remote_file:
    data = remote_file.read()
```

## Function Patterns
```python
# Basic function
def my_func(param: str) -> int:
    return 42

# Default parameters
def func(name: str = "default"):

# Variable arguments
def func(*args, **kwargs):

# Docstrings
def func():
    """Brief description of function"""
    pass
```

## None Initialization Pattern
```python
# For cleanup in finally
ssh = None
sftp = None
try:
    ssh = create_connection()
    # work
finally:
    if ssh:
        ssh.close()
```

## Exit Codes
```python
import sys

# Success
sys.exit(0)

# Failure
sys.exit(1)

# Custom codes
sys.exit(2)

# Implicit (normal = 0, exception = 1)
def main():
    process()  # Exits 0 if completes
```

## Bytes vs Strings
```python
# Bytes
data = b'hello'
type(data)  # <class 'bytes'>

# Bytes to string
text = data.decode()

# String to bytes
data = text.encode()

# Reading bytes
content = file.read()  # Returns bytes
text = content.decode()
```

## Common Patterns

### Validation
```python
if not data or data is None:
    raise Exception("No data")

if len(data) < 5:
    raise Exception("Too few items")
```

### Progress Tracking
```python
processed = []
for item in items:
    process(item)
    processed.append(item)
return processed
```

### Cleanup Pattern
```python
resource = None
try:
    resource = acquire()
    use(resource)
except Exception as e:
    handle_error(e)
finally:
    if resource:
        resource.close()
```

### Conditional Logging
```python
if output:
    print(f"Output: {output.strip()}")

if error:
    print(f"Error: {error.strip()}")
```

## Quick Operators
```python
# Comparison
==  # Equal
!=  # Not equal
>   # Greater
<   # Less
>=  # Greater or equal
<=  # Less or equal

# Logical
and  # Both true
or   # Either true
not  # Negate

# Identity
is      # Same object
is not  # Different object

# Membership
in      # Contains
not in  # Doesn't contain
```

## Common Mistakes
```python
# ✗ Wrong
if data == None:      # Use 'is None'
if not data == []:    # Use 'if not data:'

# ✓ Correct
if data is None:
if not data:
```

## Useful Built-ins
```python
len(items)           # Length
range(10)            # 0-9
enumerate(items)     # Index + value
zip(list1, list2)    # Combine lists
sorted(items)        # Sort
sum(numbers)         # Sum
min(numbers)         # Minimum
max(numbers)         # Maximum
```

## List/Dict Shortcuts
```python
# Get first item
first = items[0]

# Get last item
last = items[-1]

# Slice
first_three = items[:3]
last_three = items[-3:]

# Check empty
if not items:  # Empty
if items:      # Not empty

# Count items
count = len(items)

# Dictionary values
for key, value in config.items():
for key in config.keys():
for value in config.values():
```
