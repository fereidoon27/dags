# Lesson 03: File Detection with Sensors

## What You're Learning
How Airflow sensors work to detect files on remote servers, and how to execute commands over SSH.

---

## The check_for_card_files Function

```python
def check_for_card_files() -> bool:
    """Sensor function to detect card files on ftp server"""
    ssh = None
    try:
        ssh = create_ssh_client(SSH_CONFIG['ftp_host'])
        
        # List files matching pattern
        cmd = f"ls {SSH_CONFIG['card_dir']}card_batch*.txt 2>/dev/null || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files = stdout.read().decode().strip().split('\n')
        files = [f for f in files if f and f.strip()]  # Remove empty strings
        
        if files:
            print(f"✓ Detected {len(files)} card file(s): {files}")
            return True
        else:
            print("⏳ No card files detected yet, waiting...")
            return False
            
    except Exception as e:
        print(f"⚠️  Sensor check failed: {str(e)}")
        return False
    finally:
        if ssh:
            ssh.close()
```

---

## Function Purpose and Return Value

```python
def check_for_card_files() -> bool:
```

**Returns Boolean:**
- `True` = Files found, sensor passes, workflow continues
- `False` = No files yet, sensor waits and checks again

**Airflow Sensor Behavior:**
When this function returns `False`, Airflow waits (`poke_interval=30` seconds), then calls it again. Repeats until `True` or timeout.

---

## Connection Management Pattern

```python
ssh = None
try:
    ssh = create_ssh_client(SSH_CONFIG['ftp_host'])
    # ... work ...
except Exception as e:
    print(f"⚠️  Sensor check failed: {str(e)}")
    return False
finally:
    if ssh:
        ssh.close()
```

**The Pattern:**

**Initialize to None:** `ssh = None` before try block
- Why? So `finally` block can check if connection exists

**Create Connection:** Uses the function from Lesson 02

**finally block:** ALWAYS runs (even if exception occurs)
- Checks if `ssh` exists (`if ssh:`)
- Closes connection to prevent resource leaks

**Error Handling:**
- Returns `False` on error (sensor will retry)
- Prints warning but doesn't crash the DAG

---

## Executing Remote Commands

```python
cmd = f"ls {SSH_CONFIG['card_dir']}card_batch*.txt 2>/dev/null || true"
stdin, stdout, stderr = ssh.exec_command(cmd)
```

**The Command:**
```bash
ls /home/rocky/card/in/card_batch*.txt 2>/dev/null || true
```

**Command Breakdown:**

**ls /home/rocky/card/in/card_batch*.txt**
- List files matching the pattern
- `*` is a wildcard (matches anything)
- Example matches: `card_batch_001.txt`, `card_batch_20250116.txt`

**2>/dev/null**
- Redirects error messages to nowhere
- If no files found, `ls` normally shows error - this hides it

**|| true**
- "OR true" - ensures command always exits successfully
- If `ls` fails (no files), `true` runs and returns success
- Prevents SSH command from showing as failed

**exec_command() Returns Three Objects:**
- `stdin` - Input stream (not used here)
- `stdout` - Standard output (command results)
- `stderr` - Error output (error messages)

---

## Processing Command Output

```python
files = stdout.read().decode().strip().split('\n')
files = [f for f in files if f and f.strip()]  # Remove empty strings
```

**Step-by-Step Processing:**

**stdout.read()** 
- Reads raw bytes from command output
- Example: `b'/home/rocky/card/in/card_batch_001.txt\n/home/rocky/card/in/card_batch_002.txt\n'`

**.decode()**
- Converts bytes to string
- Example: `'/home/rocky/card/in/card_batch_001.txt\n/home/rocky/card/in/card_batch_002.txt\n'`

**.strip()**
- Removes leading/trailing whitespace and newlines
- Example: `'/home/rocky/card/in/card_batch_001.txt\n/home/rocky/card/in/card_batch_002.txt'`

**.split('\n')**
- Splits string by newline into list
- Example: `['/home/rocky/card/in/card_batch_001.txt', '/home/rocky/card/in/card_batch_002.txt']`

**List Comprehension:**
```python
files = [f for f in files if f and f.strip()]
```
- Filters out empty strings and whitespace-only strings
- `f` - keeps non-empty strings
- `f.strip()` - keeps strings that have content after stripping whitespace

**Example:**
```python
# Before filtering
files = ['/path/file1.txt', '', '  ', '/path/file2.txt']

# After filtering
files = ['/path/file1.txt', '/path/file2.txt']
```

---

## Conditional Return Logic

```python
if files:
    print(f"✓ Detected {len(files)} card file(s): {files}")
    return True
else:
    print("⏳ No card files detected yet, waiting...")
    return False
```

**Boolean Evaluation:**
- `if files:` checks if list has items
- Empty list `[]` evaluates to `False`
- List with items evaluates to `True`

**Example Scenarios:**

**Scenario 1: Files Found**
```python
files = ['/home/rocky/card/in/card_batch_001.txt']
# Output: ✓ Detected 1 card file(s): ['/home/rocky/card/in/card_batch_001.txt']
# Returns: True → Sensor passes → Workflow continues
```

**Scenario 2: No Files**
```python
files = []
# Output: ⏳ No card files detected yet, waiting...
# Returns: False → Airflow waits 30s → Checks again
```

---

## TIP: Airflow Sensors

### What are Sensors?

Tasks that wait for a condition to be met before allowing workflow to proceed. They "poke" (check) repeatedly until success or timeout.

### Most Common Use Cases

**File Detection:**
```python
# Wait for files to arrive
def check_files() -> bool:
    return files_exist()

sensor = PythonSensor(
    task_id='wait_for_files',
    python_callable=check_files,
    poke_interval=30,  # Check every 30 seconds
    timeout=3600       # Give up after 1 hour
)
```

**Database Records:**
```python
# Wait for data to be ready
def check_data_ready() -> bool:
    return query_database()
```

**External System Status:**
```python
# Wait for API to be available
def check_api_health() -> bool:
    return api_is_healthy()
```

### Sensor Modes

**Poke Mode (default):**
- Occupies a worker slot while waiting
- Checks condition, waits, checks again
- Simple but uses resources

**Reschedule Mode:**
- Releases worker slot between checks
- Better for long waits
- Slightly more complex

### Booklet Summary
Sensors wait for conditions. Return `True` = proceed, `False` = wait and retry. Configure `poke_interval` (check frequency) and `timeout` (max wait time). Use for file detection, data availability, or external dependencies.

---

## Complete Execution Flow

```
1. Airflow calls check_for_card_files()
         ↓
2. Connect to FTP server via SSH
         ↓
3. Execute ls command to list files
         ↓
4. Process output: bytes → string → list
         ↓
5. Filter out empty strings
         ↓
6. Check if files exist
         ↓
   YES: Return True (sensor passes)
   NO:  Return False (wait 30s, retry)
         ↓
7. Close SSH connection (always)
```

---

## Key Takeaways

✅ **Sensor functions return bool** - True = condition met, False = keep waiting  
✅ **exec_command()** executes shell commands on remote server  
✅ **2>/dev/null** hides error messages from commands  
✅ **|| true** ensures command never fails  
✅ **stdout.read().decode()** converts command output to string  
✅ **List comprehension** filters empty values efficiently  
✅ **finally block** ensures connections always close  
✅ **poke_interval** controls how often sensor checks  

---

## What's Next

**Lesson 04:** Retrieving File Lists - The `get_card_files()` function and task data passing
