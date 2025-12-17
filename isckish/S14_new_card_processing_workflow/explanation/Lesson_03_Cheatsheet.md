# Lesson 03 Cheatsheet: Sensors & Remote Commands

## Sensor Function Pattern
```python
def check_condition() -> bool:
    """Sensor callable - must return bool"""
    ssh = None
    try:
        ssh = create_ssh_client(hostname)
        # Check condition
        if condition_met:
            return True  # Sensor passes
        else:
            return False  # Keep waiting
    except Exception as e:
        print(f"Check failed: {e}")
        return False  # Retry on error
    finally:
        if ssh:
            ssh.close()  # Always cleanup
```

## PythonSensor Configuration
```python
from airflow.sensors.python import PythonSensor

sensor = PythonSensor(
    task_id='wait_for_files',
    python_callable=check_files,  # Function to call
    poke_interval=30,             # Check every 30 seconds
    timeout=3600,                 # Max wait 1 hour
    mode='poke'                   # or 'reschedule'
)
```

## Executing SSH Commands
```python
# Execute command
stdin, stdout, stderr = ssh.exec_command('ls /path/*.txt')

# Read output
output = stdout.read().decode().strip()

# Check exit code
exit_code = stdout.channel.recv_exit_status()
```

## Safe Command Patterns
```bash
# Hide errors, never fail
ls /path/*.txt 2>/dev/null || true

# Check file existence
test -f /path/file.txt && echo "exists" || echo "missing"

# Count files
ls /path/*.txt 2>/dev/null | wc -l
```

## Processing Command Output
```python
# Bytes → String → List
files = stdout.read().decode().strip().split('\n')

# Filter empty strings
files = [f for f in files if f and f.strip()]

# Alternative filter
files = list(filter(None, files))
```

## Connection Cleanup Pattern
```python
ssh = None  # Initialize before try
try:
    ssh = create_ssh_client(host)
    # Work here
finally:
    if ssh:
        ssh.close()  # Always runs
```

## Common Sensor Patterns

### File Detection
```python
def check_files() -> bool:
    cmd = "ls /path/pattern*.txt 2>/dev/null || true"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    files = stdout.read().decode().strip().split('\n')
    return len([f for f in files if f]) > 0
```

### Time-Based
```python
from datetime import datetime

def check_time() -> bool:
    return datetime.now().hour >= 9  # After 9 AM
```

### External API
```python
import requests

def check_api() -> bool:
    response = requests.get('https://api.example.com/health')
    return response.status_code == 200
```

## Quick Reference
- **Sensor** - Task that waits for condition
- **poke_interval** - Seconds between checks
- **timeout** - Max wait time before failure
- **Return True** - Condition met, continue
- **Return False** - Keep waiting
- **2>/dev/null** - Hide stderr
- **|| true** - Never fail command
