# Lesson 06: Remote Script Execution and Result Handling

## What You're Learning
How to execute scripts on remote servers, capture their output, check exit codes, and handle success/failure scenarios.

---

## The process_card_files Task

```python
@task
def process_card_files(file_list: List[str]) -> dict:
    """Execute card_processor.py on target-1 for each file"""
    ssh = None
    results = {'success': [], 'failed': []}
    
    try:
        ssh = create_ssh_client(SSH_CONFIG['target_host'])
        
        for file_path in file_list:
            filename = Path(file_path).name
            print(f"⚙️  Processing: {filename}")
            
            cmd = f"python3 {SSH_CONFIG['processor_script']} {file_path}"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            if exit_code == 0:
                results['success'].append(filename)
                print(f"✓ {filename} processed successfully")
                if output:
                    print(f"   Output: {output.strip()}")
            else:
                results['failed'].append(filename)
                print(f"✗ {filename} processing failed (exit code: {exit_code})")
                if error:
                    print(f"   Error: {error.strip()}")
        
        print(f"\n📊 Processing Summary:")
        print(f"   Success: {len(results['success'])}")
        print(f"   Failed: {len(results['failed'])}")
        
        if results['failed']:
            raise AirflowException(f"Processing failed for: {results['failed']}")
        
        return results
        
    except Exception as e:
        raise AirflowException(f"File processing failed: {str(e)}")
    finally:
        if ssh:
            ssh.close()
```

---

## Results Dictionary Structure

```python
results = {'success': [], 'failed': []}
```

**Dictionary with Two Lists:**

**Key 'success':** Stores successfully processed files
**Key 'failed':** Stores files that failed processing

**Why This Structure?**
- Clear categorization of outcomes
- Easy to report statistics
- Returned to caller for downstream decisions

**Example After Processing:**
```python
results = {
    'success': ['card_batch_001.txt', 'card_batch_002.txt'],
    'failed': ['card_batch_003.txt']
}
```

---

## Building the Command

```python
cmd = f"python3 {SSH_CONFIG['processor_script']} {file_path}"
```

**f-string Construction:**

**Template:**
```
python3 /path/to/script.py /path/to/file.txt
```

**Actual Example:**
```bash
python3 /home/rocky/scripts/card_processor.py /home/rocky/card/in/card_batch_001.txt
```

**Breaking It Down:**
- `python3` - Execute using Python 3
- `SSH_CONFIG['processor_script']` - Gets `/home/rocky/scripts/card_processor.py`
- `file_path` - The file to process

**What card_processor.py Does:**
- Reads the card batch file
- Processes/validates the data
- Exits with code 0 (success) or non-zero (failure)

---

## Executing the Command

```python
stdin, stdout, stderr = ssh.exec_command(cmd)
```

**Three Output Streams:**

**stdin:** Standard input (for sending data to command)
- Not used here - the script doesn't need input

**stdout:** Standard output (normal output)
- Where `print()` statements go
- Success messages, results

**stderr:** Standard error (error messages)
- Where errors and warnings go
- Exception tracebacks

**Example Script Output:**
```python
# card_processor.py might print:
print("Processing 150 records...")  # Goes to stdout
print("Validation complete")        # Goes to stdout

# If error occurs:
raise Exception("Invalid format")   # Goes to stderr
```

---

## Capturing Exit Code

```python
exit_code = stdout.channel.recv_exit_status()
```

**What is Exit Code?**

Every command returns a number when it finishes:
- **0** = Success
- **Non-zero** = Failure (1, 2, 127, etc.)

**How Python Scripts Set Exit Codes:**
```python
# card_processor.py might do:
import sys

# Success case
sys.exit(0)

# Failure case
sys.exit(1)

# Or if exception not caught
# Python automatically exits with code 1
```

**recv_exit_status() Behavior:**
- **Blocks** until command completes
- Returns the exit code
- Must be called **before** reading stdout/stderr

**Example:**
```python
# Command succeeds
exit_code = stdout.channel.recv_exit_status()  # Returns 0

# Command fails
exit_code = stdout.channel.recv_exit_status()  # Returns 1 (or other non-zero)
```

---

## Reading Output Streams

```python
output = stdout.read().decode()
error = stderr.read().decode()
```

**Processing Each Stream:**

**stdout.read():** 
- Reads all standard output as bytes
- Example: `b'Processing complete\n'`

**.decode():**
- Converts bytes to string
- Example: `'Processing complete\n'`

**Why After exit_code?**
If you read stdout/stderr **before** getting exit code, the command might not finish properly.

**Example Outputs:**
```python
# Successful run
output = "Processing 150 records\nValidation complete\n"
error = ""

# Failed run
output = "Processing 150 records\n"
error = "Traceback (most recent call last):\nValueError: Invalid format\n"
```

---

## Conditional Result Handling

```python
if exit_code == 0:
    results['success'].append(filename)
    print(f"✓ {filename} processed successfully")
    if output:
        print(f"   Output: {output.strip()}")
else:
    results['failed'].append(filename)
    print(f"✗ {filename} processing failed (exit code: {exit_code})")
    if error:
        print(f"   Error: {error.strip()}")
```

**Success Path (exit_code == 0):**

1. Add filename to success list
2. Print success message
3. If there's output, print it (trimmed)

**Failure Path (exit_code != 0):**

1. Add filename to failed list
2. Print failure message with exit code
3. If there's error output, print it (trimmed)

**Why .strip()?**
Removes extra newlines and whitespace for cleaner logs.

**Example Output:**
```
⚙️  Processing: card_batch_001.txt
✓ card_batch_001.txt processed successfully
   Output: Processed 150 records

⚙️  Processing: card_batch_002.txt
✗ card_batch_002.txt processing failed (exit code: 1)
   Error: ValueError: Invalid card number on line 45
```

---

## TIP: Exit Codes and Error Handling

### What are Exit Codes?

Numbers that programs return to indicate success or failure. Convention: 0 = success, non-zero = error.

### Most Common Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Everything worked |
| 1 | General error | Unhandled exception |
| 2 | Misuse | Wrong arguments |
| 126 | Permission denied | Can't execute file |
| 127 | Command not found | python3 not installed |
| 130 | Ctrl+C | Script interrupted |

### Setting Exit Codes in Python

**Explicit:**
```python
import sys

if data_valid:
    sys.exit(0)  # Success
else:
    sys.exit(1)  # Failure
```

**Implicit:**
```python
# Normal completion = exit 0
def main():
    process_data()
    # Exits with 0

# Uncaught exception = exit 1
def main():
    raise ValueError("Bad data")  # Python exits with 1
```

**In Shell Scripts:**
```bash
#!/bin/bash
if [ -f "file.txt" ]; then
    echo "File exists"
    exit 0
else
    echo "File missing"
    exit 1
fi
```

### Checking Exit Codes in Bash

```bash
# Run command
python3 script.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "Success"
else
    echo "Failed with code: $?"
fi
```

### Booklet Summary
Exit codes: 0 = success, non-zero = failure. Use `sys.exit(code)` to set explicitly, or Python sets automatically (0 for normal, 1 for exceptions). Check with `recv_exit_status()` in Paramiko or `$?` in bash.

---

## Final Summary and Failure Check

```python
print(f"\n📊 Processing Summary:")
print(f"   Success: {len(results['success'])}")
print(f"   Failed: {len(results['failed'])}")

if results['failed']:
    raise AirflowException(f"Processing failed for: {results['failed']}")

return results
```

**Summary Report:**
- Shows total successes
- Shows total failures
- Gives clear overview of batch processing

**Failure Check:**
```python
if results['failed']:
```
- If any files failed, raise exception
- Task marked as failed in Airflow
- Triggers retry logic (if configured)

**Why Fail the Task?**
Even if some files succeed, failures indicate problems that need attention.

**Example Output:**
```
📊 Processing Summary:
   Success: 2
   Failed: 1

AirflowException: Processing failed for: ['card_batch_003.txt']
```

---

## Complete Processing Flow

```
1. Connect to target server
         ↓
2. For each file in list:
   a. Build python3 command
   b. Execute command via SSH
   c. Wait for command to complete (get exit code)
   d. Read stdout and stderr
   e. Check exit code
      → 0: Add to success list, log output
      → Non-zero: Add to failed list, log error
         ↓
3. Print summary statistics
         ↓
4. If any failures: Raise exception
   Else: Return results dictionary
         ↓
5. Close SSH connection (always)
```

---

## Key Takeaways

✅ **Results dictionary** tracks success/failure separately  
✅ **f-strings** build dynamic commands easily  
✅ **exec_command()** returns stdin, stdout, stderr  
✅ **recv_exit_status()** blocks until command completes  
✅ **Exit code 0** = success, non-zero = failure  
✅ **Read stdout/stderr AFTER** getting exit code  
✅ **.strip()** cleans output for logging  
✅ **Fail task** if any files fail processing  
✅ **Return results** for downstream decision-making  

---

## What's Next

**Lesson 07:** Task Dependencies and DAG Orchestration - Wiring tasks together and understanding execution flow
