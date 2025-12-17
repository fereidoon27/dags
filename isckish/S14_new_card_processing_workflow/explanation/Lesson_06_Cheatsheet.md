# Lesson 06 Cheatsheet: Remote Script Execution

## Basic Command Execution Pattern
```python
# Execute command
cmd = "python3 /path/script.py /path/file.txt"
stdin, stdout, stderr = ssh.exec_command(cmd)

# Wait for completion and get exit code
exit_code = stdout.channel.recv_exit_status()

# Read outputs
output = stdout.read().decode()
error = stderr.read().decode()

# Check result
if exit_code == 0:
    print("Success:", output)
else:
    print(f"Failed (code {exit_code}):", error)
```

## Results Tracking Pattern
```python
@task
def process_files(file_list: List[str]) -> dict:
    results = {'success': [], 'failed': []}
    ssh = None
    
    try:
        ssh = create_ssh_client(hostname)
        
        for file_path in file_list:
            cmd = f"python3 script.py {file_path}"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                results['success'].append(file_path)
            else:
                results['failed'].append(file_path)
        
        if results['failed']:
            raise AirflowException(f"Failed: {results['failed']}")
        
        return results
    finally:
        if ssh:
            ssh.close()
```

## Common Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Misuse/wrong arguments |
| 126 | Permission denied |
| 127 | Command not found |
| 130 | Interrupted (Ctrl+C) |

## Setting Exit Codes in Python
```python
import sys

# Success
sys.exit(0)

# Failure
sys.exit(1)

# Custom codes
sys.exit(2)  # Invalid arguments
sys.exit(3)  # Custom error

# Implicit (normal end = 0)
def main():
    process_data()
    # Exits with 0

# Implicit (exception = 1)
def main():
    raise ValueError("error")  # Exits with 1
```

## Command Output Processing
```python
# Read and clean output
output = stdout.read().decode().strip()
error = stderr.read().decode().strip()

# Check if output exists
if output:
    print(f"Output: {output}")

if error:
    print(f"Error: {error}")

# Get specific lines
lines = output.split('\n')
first_line = lines[0]
```

## Command Patterns

### Run Python Script
```python
cmd = f"python3 /path/script.py {arg1} {arg2}"
stdin, stdout, stderr = ssh.exec_command(cmd)
```

### Run with Environment Variables
```python
cmd = f"export VAR=value && python3 script.py"
stdin, stdout, stderr = ssh.exec_command(cmd)
```

### Run in Specific Directory
```python
cmd = f"cd /path/dir && python3 script.py"
stdin, stdout, stderr = ssh.exec_command(cmd)
```

### Multiple Commands
```python
cmd = "command1 && command2 && command3"
stdin, stdout, stderr = ssh.exec_command(cmd)
```

### Conditional Execution
```python
# Run command2 only if command1 succeeds
cmd = "command1 && command2"

# Run command2 only if command1 fails
cmd = "command1 || command2"
```

## Checking Command Success
```python
# Method 1: Exit code
exit_code = stdout.channel.recv_exit_status()
if exit_code == 0:
    print("Success")

# Method 2: Check stderr
error = stderr.read().decode()
if not error:
    print("No errors")

# Method 3: Check output content
output = stdout.read().decode()
if "SUCCESS" in output:
    print("Task completed")
```

## Summary Statistics Pattern
```python
print(f"\n📊 Processing Summary:")
print(f"   Total: {len(file_list)}")
print(f"   Success: {len(results['success'])}")
print(f"   Failed: {len(results['failed'])}")
print(f"   Success Rate: {len(results['success'])/len(file_list)*100:.1f}%")
```

## Error Handling Strategies
```python
# Strategy 1: Fail fast
if exit_code != 0:
    raise AirflowException(f"Command failed: {error}")

# Strategy 2: Collect all errors
if results['failed']:
    raise AirflowException(f"Failed files: {results['failed']}")

# Strategy 3: Warn but continue
if exit_code != 0:
    print(f"⚠️  Warning: {error}")
    # Continue processing
```

## Timeout Pattern
```python
# Set command timeout
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)

# Catch timeout
try:
    exit_code = stdout.channel.recv_exit_status()
except socket.timeout:
    print("Command timed out")
```

## Quick Reference
- **exec_command()** - Execute remote command
- **recv_exit_status()** - Wait for completion, get exit code
- **Exit code 0** - Success
- **Exit code non-zero** - Failure
- **stdout** - Normal output
- **stderr** - Error output
- **decode()** - Bytes to string
- **strip()** - Remove whitespace
- **Get exit code FIRST** - Before reading streams
