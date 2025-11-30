# Lesson 03 Cheatsheet: Subprocess & Remote Commands

## Type Hints
```python
# Basic syntax
def func(param: type) -> return_type:
    pass

# Common types
def greet(name: str) -> str:
    return f"Hello {name}"

def add(x: int, y: int) -> int:
    return x + y

def is_valid(data: str) -> bool:
    return len(data) > 0

# With defaults
def connect(host: str, port: int = 5432) -> bool:
    pass

# Optional (might be None)
from typing import Optional
def find(id: int) -> Optional[str]:
    return None  # or return a string
```

## subprocess.run()
```python
import subprocess

# Basic usage
result = subprocess.run(
    'ls -l',
    shell=True,
    capture_output=True,
    text=True,
    timeout=10
)

# Access results
print(result.returncode)  # 0 = success
print(result.stdout)      # Normal output
print(result.stderr)      # Error output

# Check success
if result.returncode == 0:
    print("Success!")

# With timeout handling
try:
    result = subprocess.run(cmd, timeout=5)
except subprocess.TimeoutExpired:
    print("Timed out!")
```

## SSH Commands
```python
# Basic SSH
cmd = 'ssh user@host "command"'

# With options
cmd = 'ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no user@ip "ls"'

# In subprocess
result = subprocess.run(
    f'ssh user@{ip} "command"',
    shell=True,
    capture_output=True,
    text=True,
    timeout=15
)
```

## Common Patterns

### Local vs Remote Command
```python
def run_command(ip: str, hostname: str, cmd: str) -> str:
    current = get_current_hostname()
    
    if current == hostname:
        # Local
        full_cmd = f"sudo {cmd}"
    else:
        # Remote
        full_cmd = f'ssh rocky@{ip} "sudo {cmd}"'
    
    result = subprocess.run(
        full_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=15
    )
    return result.stdout
```

### Command with Error Handling
```python
try:
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        return result.stdout
    else:
        return f"Error: {result.stderr}"
        
except subprocess.TimeoutExpired:
    return "Command timed out"
except Exception as e:
    return f"Error: {e}"
```

## String Operations
```python
# Remove whitespace
text = "  hello  ".strip()  # "hello"

# Replace substring
text = "Hello World".replace("World", "Python")

# Check substring
if "error" in text:
    print("Found!")

# Multiple operations
text = text.strip().replace('[Invalid]', '').lower()
```

## journalctl Commands
```bash
# Last N lines
journalctl -u service-name -n 100

# No pager (all at once)
journalctl --no-pager

# Specific time format
journalctl -o short-iso

# Combined
sudo journalctl -u airflow-scheduler --no-pager -n 100 -o short-iso
```

## Quick Reference

| Operation | Code | Result |
|-----------|------|--------|
| Run command | `subprocess.run(cmd, shell=True)` | Executes |
| Capture output | `capture_output=True, text=True` | Strings |
| Set timeout | `timeout=10` | Max seconds |
| Check success | `result.returncode == 0` | Boolean |
| SSH remote | `ssh user@ip "cmd"` | Remote exec |
| Type hint | `def f(x: int) -> str:` | Documents |

## Common journalctl Options

| Option | Purpose | Example |
|--------|---------|---------|
| `-u SERVICE` | Filter by service | `-u nginx` |
| `-n N` | Last N lines | `-n 50` |
| `--no-pager` | No interactive mode | `--no-pager` |
| `-o FORMAT` | Output format | `-o short-iso` |
| `--since` | Time filter | `--since "1 hour ago"` |

## Troubleshooting

### Command fails silently
```python
# ❌ No error checking
result = subprocess.run(cmd, shell=True)

# ✅ Check return code
result = subprocess.run(cmd, shell=True)
if result.returncode != 0:
    print(f"Failed: {result.stderr}")
```

### Timeout not working
```python
# ❌ No timeout
result = subprocess.run(cmd, shell=True)

# ✅ With timeout
result = subprocess.run(cmd, shell=True, timeout=10)
```

### Can't see output
```python
# ❌ Output not captured
result = subprocess.run(cmd, shell=True)

# ✅ Capture output
result = subprocess.run(
    cmd, 
    shell=True, 
    capture_output=True, 
    text=True
)
print(result.stdout)
```

### SSH escaping issues
```python
# ❌ Wrong quotes
cmd = f"ssh user@{ip} 'sudo ls'"  # Single quotes break f-string

# ✅ Escaped quotes
cmd = f'ssh user@{ip} "sudo ls"'  # Works

# ✅ Alternative
cmd = f"ssh user@{ip} \"sudo ls\""  # Escaped
```
