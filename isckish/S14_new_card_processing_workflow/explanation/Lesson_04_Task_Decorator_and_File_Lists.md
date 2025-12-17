# Lesson 04: Task Decorator and File List Retrieval

## What You're Learning
How to use the `@task` decorator to create Airflow tasks and pass data between tasks.

---

## The Sensor Task Definition

```python
detect_files = PythonSensor(
    task_id='detect_card_files',
    python_callable=check_for_card_files,
    poke_interval=30,
    timeout=3600,
    mode='poke',
    queue='card_processing_queue'
)
```

**This is inside the DAG function** - defining tasks that will run.

**Task Configuration:**

**task_id**: Unique identifier for this task
- Shows as "detect_card_files" in Airflow UI
- Must be unique within the DAG

**python_callable**: Function to execute
- Points to `check_for_card_files` (from Lesson 03)
- Airflow calls this function repeatedly

**poke_interval**: Check frequency
- `30` seconds between checks
- Balance: too short = resource waste, too long = slow detection

**timeout**: Maximum wait time
- `3600` seconds = 1 hour
- If files don't appear in 1 hour, task fails

**mode**: Sensor behavior
- `'poke'` = keeps worker busy while waiting
- Alternative: `'reschedule'` releases worker between checks

**queue**: Worker queue assignment
- Routes task to `card_processing_queue`
- Matches `default_args` queue from DAG definition

---

## The get_file_list Task

```python
@task
def get_file_list() -> List[str]:
    """Get the list of detected card files"""
    files = get_card_files()
    if not files:
        raise AirflowException("No card files found - sensor passed but files disappeared")
    return files
```

---

## Understanding the @task Decorator

```python
@task
def get_file_list() -> List[str]:
```

**What @task Does:**
Converts a regular Python function into an Airflow task automatically.

**Without @task (old way):**
```python
from airflow.operators.python import PythonOperator

get_files = PythonOperator(
    task_id='get_file_list',
    python_callable=get_file_list_function
)
```

**With @task (modern way):**
```python
@task
def get_file_list() -> List[str]:
    # Function body
```

**Benefits:**
- Less boilerplate code
- Automatic task_id generation (uses function name)
- Built-in data passing between tasks
- Type hints work naturally

---

## The get_card_files Helper Function

```python
def get_card_files() -> List[str]:
    """Get list of card files from ftp server"""
    ssh = None
    try:
        ssh = create_ssh_client(SSH_CONFIG['ftp_host'])
        
        cmd = f"ls {SSH_CONFIG['card_dir']}card_batch*.txt 2>/dev/null || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files = stdout.read().decode().strip().split('\n')
        files = [f for f in files if f and f.strip()]
        
        print(f"Retrieved {len(files)} card file(s)")
        return files
        
    except Exception as e:
        raise AirflowException(f"Failed to get card files: {str(e)}")
    finally:
        if ssh:
            ssh.close()
```

**Looks Similar to check_for_card_files?**

Yes! Key difference:

**check_for_card_files (Sensor):**
- Returns `bool` (True/False)
- Used for waiting/detecting

**get_card_files (Data Retrieval):**
- Returns `List[str]` (actual file paths)
- Used for getting data after detection

**Why Two Functions?**

**Separation of Concerns:**
1. Sensor detects files exist
2. Task retrieves the actual list

**Reliability:**
Files might appear/disappear between sensor passing and task running. This validates they still exist.

---

## Validation Logic

```python
files = get_card_files()
if not files:
    raise AirflowException("No card files found - sensor passed but files disappeared")
return files
```

**The Check:**

**if not files:** Checks if list is empty
- Empty list `[]` evaluates to `False`
- `not []` becomes `True`

**raise AirflowException:** Fails the task explicitly
- Clear error message explains the problem
- Task will retry (if retries configured)

**Example Scenario:**
```
Time 10:00:00 - Sensor detects: card_batch_001.txt
Time 10:00:05 - Sensor passes
Time 10:00:06 - get_file_list runs
Time 10:00:06 - File was deleted by external process
Result: Raises exception "files disappeared"
```

**return files:** Passes list to next task
- Airflow automatically serializes and stores data
- Next task can access this list

---

## TIP: Task Data Passing with XCom

### What is XCom?

XCom (Cross-Communication) is Airflow's mechanism for passing data between tasks. When a task returns a value, Airflow stores it automatically.

### Most Common Use Cases

**Passing File Lists:**
```python
@task
def get_files() -> List[str]:
    return ['/path/file1.txt', '/path/file2.txt']

@task
def process_files(file_list: List[str]):
    for file in file_list:
        print(f"Processing {file}")

# Usage
files = get_files()
process_files(files)
```

**Passing Configuration:**
```python
@task
def get_config() -> dict:
    return {'batch_size': 100, 'mode': 'production'}

@task
def run_job(config: dict):
    batch_size = config['batch_size']
```

**Passing Simple Values:**
```python
@task
def count_records() -> int:
    return 1500

@task
def validate(count: int):
    if count > 1000:
        print("Large batch detected")
```

### Size Limitations

**Default Limit:** 48KB (depends on backend)
- SQLite: 2GB max
- PostgreSQL: 1GB max
- MySQL: Limited by max_allowed_packet

**Best Practices:**
- Pass file paths, not file contents
- Pass IDs, not full objects
- For large data, use external storage (S3, database)

### Booklet Summary
XCom passes data between tasks automatically. Task return values are stored and passed as arguments to downstream tasks. Keep data small (<48KB recommended) - pass references, not content.

---

## Task Dependency Pattern

```python
file_list = get_file_list()
```

**What This Does:**

**Calls the task:** Creates a task instance
**Returns a reference:** `file_list` is not the actual list yet
- It's a reference that downstream tasks can use
- Actual execution happens when DAG runs

**Example:**
```python
# This doesn't run the function immediately
file_list = get_file_list()  # Creates task, returns reference

# This passes the reference to next task
process_files(file_list)  # Will receive actual data at runtime
```

---

## Complete Flow Visualization

```
1. Sensor runs check_for_card_files() every 30s
         ↓ (files detected, returns True)
2. Sensor passes
         ↓
3. get_file_list task runs
         ↓
4. Calls get_card_files() helper
         ↓
5. SSH to FTP server, list files
         ↓
6. Validate files exist
         ↓
7. Return list (Airflow stores in XCom)
         ↓
8. Next task receives list from XCom
```

---

## Key Takeaways

✅ **@task decorator** converts functions into Airflow tasks automatically  
✅ **task_id** auto-generated from function name with @task  
✅ **PythonSensor** for waiting, @task for processing  
✅ **Return values** automatically passed to downstream tasks via XCom  
✅ **Type hints** (List[str], dict, int) improve code clarity  
✅ **Validation** between sensor and retrieval prevents race conditions  
✅ **queue parameter** routes tasks to specific workers  
✅ **Keep XCom data small** - pass references, not large content  

---

## What's Next

**Lesson 05:** File Transfer Task - SFTP operations and transferring files between servers
