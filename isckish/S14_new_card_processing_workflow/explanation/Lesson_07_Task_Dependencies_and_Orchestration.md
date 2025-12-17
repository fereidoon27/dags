# Lesson 07: Task Dependencies and DAG Orchestration

## What You're Learning
How to wire tasks together, define execution order, and instantiate the DAG for Airflow to run.

---

## Task Dependency Section

```python
# Define task dependencies
file_list = get_file_list()
transferred_files = transfer_card_files(file_list)

detect_files >> file_list
process_card_files(transferred_files)
```

This is the "orchestration" - defining the order tasks execute.

---

## Creating Task Instances

```python
file_list = get_file_list()
transferred_files = transfer_card_files(file_list)
```

**What's Happening Here:**

**NOT executing functions** - these are task definitions
**Creating task instances** that will run when DAG executes
**Establishing data flow** via XCom

**Breaking It Down:**

```python
file_list = get_file_list()
```
- Calls the `@task` decorated function
- Returns a **task reference** (not actual data yet)
- `file_list` is a placeholder for data that will flow through XCom

```python
transferred_files = transfer_card_files(file_list)
```
- Creates transfer task
- Passes `file_list` reference as input
- `transferred_files` is another task reference

**At Runtime:**
1. `get_file_list()` executes → returns `['/path/file1.txt', '/path/file2.txt']`
2. Airflow stores in XCom
3. `transfer_card_files()` executes → receives list from XCom
4. Returns transferred list → stored in XCom
5. Next task receives it

---

## The >> Operator (Bitshift Dependency)

```python
detect_files >> file_list
```

**What >> Does:**

Defines task execution order without data passing.

**Read as:** "detect_files must complete BEFORE file_list runs"

**Why Use It?**

When tasks don't pass data but must run in sequence:
```python
task_a >> task_b  # task_a first, then task_b
```

**In Your Code:**
```python
detect_files >> file_list
```
- Sensor must pass before getting file list
- No data flows (sensor returns bool, not used by get_file_list)
- Pure dependency relationship

---

## TIP: Task Dependencies in Airflow

### What are Dependencies?

Rules that define which tasks must complete before others can start. They create the "graph" in DAG.

### Dependency Syntax Options

**Bitshift Operator (>>):**
```python
# Single dependency
task_a >> task_b  # task_b waits for task_a

# Chain
task_a >> task_b >> task_c  # Linear sequence

# Multiple downstream
task_a >> [task_b, task_c]  # Both wait for task_a

# Multiple upstream
[task_a, task_b] >> task_c  # task_c waits for both
```

**Function Call (with @task):**
```python
# Automatic dependency + data passing
result = task_a()
task_b(result)  # task_b depends on task_a AND receives data
```

**set_downstream / set_upstream:**
```python
# Alternative syntax (less common)
task_a.set_downstream(task_b)  # Same as task_a >> task_b
task_b.set_upstream(task_a)     # Same as task_a >> task_b
```

### Common Patterns

**Linear Pipeline:**
```python
task_1 >> task_2 >> task_3 >> task_4
```

**Fan-Out (Parallel Processing):**
```python
start >> [process_a, process_b, process_c] >> end
```
All three process tasks run in parallel after start completes.

**Fan-In (Join):**
```python
[extract_a, extract_b] >> combine >> load
```
Both extracts must complete before combine runs.

**Diamond Pattern:**
```python
start >> [branch_a, branch_b]
[branch_a, branch_b] >> end
```

**Conditional Branching:**
```python
check >> [path_a, path_b]
# Only one path executes based on check result
```

### With @task Decorator

**Data Passing Creates Dependencies:**
```python
@task
def task_a() -> str:
    return "data"

@task
def task_b(input: str):
    print(input)

# This creates dependency automatically
result = task_a()
task_b(result)  # task_b depends on task_a
```

**Mixed Syntax:**
```python
sensor >> task_a()  # Sensor first, then task_a
result = task_a()
task_b(result) >> task_c()  # Chain with data passing
```

### Booklet Summary
Use `>>` for execution order without data. Use function calls with `@task` for dependencies WITH data passing. Chain with `task_a >> task_b >> task_c`. Parallel: `task_a >> [task_b, task_c]`. Dependencies create the DAG graph.

---

## Your DAG's Dependency Graph

```python
detect_files >> file_list
transferred_files = transfer_card_files(file_list)
process_card_files(transferred_files)
```

**Visual Flow:**
```
detect_files (Sensor)
      ↓ (>> operator)
get_file_list
      ↓ (function call, data passing)
transfer_card_files
      ↓ (function call, data passing)
process_card_files
```

**Breaking Down Each Connection:**

**1. detect_files >> file_list**
- Type: Pure dependency (no data)
- Meaning: Wait for sensor to pass
- Why: Need to detect files before listing them

**2. file_list → transfer_card_files(file_list)**
- Type: Dependency + data passing
- Meaning: Pass file list via XCom
- Why: Transfer needs to know which files

**3. transferred_files → process_card_files(transferred_files)**
- Type: Dependency + data passing
- Meaning: Pass transferred file list
- Why: Process only successfully transferred files

---

## DAG Instantiation

```python
# Instantiate the DAG
card_dag = card_processing_workflow()
```

**What This Does:**

**Calls the @dag decorated function:**
- Executes `card_processing_workflow()`
- Creates the DAG object
- Registers tasks and dependencies

**Assigns to variable:**
- `card_dag` holds the DAG instance
- Airflow discovers this variable
- DAG becomes available in UI

**Why Needed?**

Airflow scans Python files for DAG objects. Without this line, the DAG won't be discovered.

**Alternative Pattern:**
```python
# Some people use this
dag = card_processing_workflow()

# Or don't assign at all (works too)
card_processing_workflow()
```

All work, but assigning to a variable is clearest.

---

## Complete DAG Function Structure

```python
@dag(...)
def card_processing_workflow():
    
    # 1. Define sensor (traditional operator)
    detect_files = PythonSensor(...)
    
    # 2. Define tasks with @task decorator
    @task
    def get_file_list() -> List[str]:
        ...
    
    @task
    def transfer_card_files(file_list: List[str]) -> List[str]:
        ...
    
    @task
    def process_card_files(file_list: List[str]) -> dict:
        ...
    
    # 3. Wire tasks together (orchestration)
    file_list = get_file_list()
    transferred_files = transfer_card_files(file_list)
    
    detect_files >> file_list
    process_card_files(transferred_files)

# 4. Instantiate
card_dag = card_processing_workflow()
```

**The Four Sections:**

**1. Sensor Definition:** Traditional operator style
**2. Task Definitions:** Functions with @task decorator
**3. Orchestration:** Creating instances and dependencies
**4. Instantiation:** Making DAG discoverable

---

## Execution Flow at Runtime

```
User clicks "Trigger DAG" in Airflow UI
         ↓
Airflow Scheduler picks up the DAG
         ↓
Task 1: detect_files (Sensor)
   - Checks every 30 seconds
   - Finds files → Returns True → Passes
         ↓
Task 2: get_file_list
   - Connects to FTP server
   - Lists files
   - Returns: ['/path/file1.txt', '/path/file2.txt']
   - Stores in XCom
         ↓
Task 3: transfer_card_files
   - Receives file list from XCom
   - Connects to both servers
   - Transfers each file
   - Returns: ['/path/file1.txt', '/path/file2.txt']
   - Stores in XCom
         ↓
Task 4: process_card_files
   - Receives transferred list from XCom
   - Connects to target server
   - Executes processor script for each file
   - Returns: {'success': [...], 'failed': [...]}
   - Stores in XCom
         ↓
DAG Complete (Success or Failure based on final task)
```

---

## Why This Design Works

**Separation of Concerns:**
- Detection (sensor)
- Retrieval (get list)
- Transfer (move files)
- Processing (execute script)

**Each task is:**
- **Independent** - Can be tested alone
- **Reusable** - Could be used in other DAGs
- **Recoverable** - If one fails, restart from there

**Benefits:**

**Failure Handling:**
If transfer fails, don't process. If processing fails, files are already transferred (can retry processing).

**Monitoring:**
See exactly which step failed in Airflow UI.

**Scalability:**
Could parallelize processing multiple files in future.

---

## Alternative Dependency Patterns

**Your Code (Sequential):**
```python
detect_files >> file_list
transferred_files = transfer_card_files(file_list)
process_card_files(transferred_files)
```

**Could Be Parallel (If Appropriate):**
```python
# Process multiple files in parallel
detect_files >> file_list
files = transfer_card_files(file_list)

# Create one task per file (dynamic task mapping)
process_card_files.expand(file_path=files)
```

**Could Have Validation:**
```python
detect_files >> file_list
transferred = transfer_card_files(file_list)
validated = validate_transfers(transferred)
process_card_files(validated)
```

---

## Common Mistakes to Avoid

**❌ Wrong: Calling function without assignment**
```python
get_file_list()  # Returns task reference, but it's lost
transfer_card_files(???)  # No reference to pass
```

**✓ Correct: Assign and pass references**
```python
file_list = get_file_list()
transfer_card_files(file_list)
```

**❌ Wrong: Using >> with @task that passes data**
```python
get_file_list() >> transfer_card_files()  # Data not passed!
```

**✓ Correct: Function call for data passing**
```python
file_list = get_file_list()
transfer_card_files(file_list)  # Data flows
```

**❌ Wrong: Not instantiating DAG**
```python
@dag(...)
def my_dag():
    # tasks...

# Missing: my_dag()
# Airflow won't discover this DAG
```

**✓ Correct: Always instantiate**
```python
@dag(...)
def my_dag():
    # tasks...

dag = my_dag()  # Now Airflow can find it
```

---

## Key Takeaways

✅ **>> operator** defines execution order without data  
✅ **Function calls** create dependencies AND pass data  
✅ **Task references** are placeholders until runtime  
✅ **XCom** stores and passes data between tasks automatically  
✅ **DAG instantiation** makes DAG discoverable to Airflow  
✅ **Dependencies create the graph** in DAG (Directed Acyclic Graph)  
✅ **Each task isolated** for testing and recovery  
✅ **Sequential vs parallel** depends on use case  

---

## Complete Picture Review

You've learned an entire Airflow DAG that:

1. **Detects** files on remote server (Sensor)
2. **Retrieves** file list (Task)
3. **Transfers** files between servers (SFTP)
4. **Processes** files with remote script (SSH exec)
5. **Handles** errors and retries gracefully
6. **Tracks** results and reports status

All using:
- **SSH** for secure connections (Paramiko)
- **SFTP** for file transfers
- **Airflow** for orchestration
- **Python** for logic and control flow

You can now read, modify, and build similar workflows!

---

## What's Next

**Practice Ideas:**
1. Modify sensor `poke_interval` and observe behavior
2. Add a notification task after processing completes
3. Add file archiving after successful processing
4. Create a cleanup task to remove processed files
5. Add more detailed logging to each task
6. Implement parallel file processing

**Further Learning:**
- Dynamic task mapping (process files in parallel)
- Task groups (organize related tasks)
- Branching (conditional execution paths)
- Trigger rules (control when tasks run)
- Custom operators (create reusable components)

**You now have the foundation to build production Airflow DAGs!** 🎉
