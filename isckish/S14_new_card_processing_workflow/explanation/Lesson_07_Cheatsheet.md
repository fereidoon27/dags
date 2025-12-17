# Lesson 07 Cheatsheet: Task Dependencies

## Basic Dependency Syntax

### >> Operator (Bitshift)
```python
# Single dependency
task_a >> task_b  # task_b runs after task_a

# Chain
task_a >> task_b >> task_c

# Multiple downstream (parallel)
task_a >> [task_b, task_c]  # Both wait for task_a

# Multiple upstream (join)
[task_a, task_b] >> task_c  # task_c waits for both
```

### Function Calls (with @task)
```python
# Automatic dependency + data passing
@task
def task_a() -> str:
    return "data"

@task
def task_b(data: str):
    print(data)

# Wire together
result = task_a()
task_b(result)  # Depends on task_a AND receives data
```

## Common Dependency Patterns

### Linear Pipeline
```python
task_1 >> task_2 >> task_3 >> task_4
```

### Fan-Out (Parallel)
```python
start >> [process_a, process_b, process_c] >> end
```

### Fan-In (Join)
```python
[extract_a, extract_b] >> combine >> load
```

### Diamond
```python
start >> [branch_a, branch_b]
[branch_a, branch_b] >> end
```

### Mixed Dependencies
```python
# Sensor + data passing tasks
sensor >> task_a()
result = task_a()
task_b(result) >> task_c()
```

## Complete DAG Structure
```python
from airflow.decorators import dag, task
from datetime import datetime

@dag(
    dag_id='my_workflow',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False
)
def my_workflow():
    
    # Define tasks
    @task
    def task_a() -> str:
        return "data"
    
    @task
    def task_b(data: str):
        print(data)
    
    # Wire dependencies
    result = task_a()
    task_b(result)

# Instantiate
dag = my_workflow()
```

## Data Passing Examples

### Single Value
```python
@task
def get_count() -> int:
    return 100

@task
def use_count(count: int):
    print(f"Count: {count}")

count = get_count()
use_count(count)
```

### List
```python
@task
def get_files() -> List[str]:
    return ['file1.txt', 'file2.txt']

@task
def process_files(files: List[str]):
    for f in files:
        print(f)

files = get_files()
process_files(files)
```

### Dictionary
```python
@task
def get_config() -> dict:
    return {'env': 'prod', 'batch_size': 100}

@task
def run_job(config: dict):
    print(config['env'])

config = get_config()
run_job(config)
```

## Mixing Operators and @task

### Sensor + Tasks
```python
from airflow.sensors.python import PythonSensor

@dag(...)
def my_dag():
    # Traditional operator
    sensor = PythonSensor(
        task_id='wait',
        python_callable=check_condition,
        poke_interval=30
    )
    
    # @task decorated
    @task
    def process():
        pass
    
    # Wire together
    sensor >> process()
```

## Dependency Rules

### ✓ Correct Patterns
```python
# Pure dependency
task_a >> task_b

# Data passing
result = task_a()
task_b(result)

# Combined
sensor >> task_a()
result = task_a()
task_b(result)

# Multiple
task_a >> [task_b, task_c]
```

### ✗ Wrong Patterns
```python
# ✗ Function call without assignment
get_data()  # Task reference lost!
process(???)

# ✗ Using >> with data tasks
get_data() >> process()  # Data not passed!

# ✗ Not instantiating
@dag(...)
def my_dag():
    pass
# Missing: my_dag()
```

## DAG Instantiation
```python
# Method 1: Assign to variable
dag = my_workflow()

# Method 2: Use DAG name
my_workflow_dag = my_workflow()

# Method 3: Just call (works but less clear)
my_workflow()
```

## Task Execution Flow
```
1. DAG triggered
   ↓
2. Scheduler checks dependencies
   ↓
3. Runs tasks in order
   ↓
4. XCom stores return values
   ↓
5. Downstream tasks receive data
   ↓
6. DAG completes
```

## Dependency Visualization
```python
# Your code:
detect_files >> file_list
transferred = transfer_card_files(file_list)
process_card_files(transferred)

# Creates this graph:
detect_files
    ↓
get_file_list
    ↓
transfer_card_files
    ↓
process_card_files
```

## Advanced Patterns

### Conditional Branching
```python
from airflow.operators.python import BranchPythonOperator

def choose_branch():
    if condition:
        return 'task_a'
    return 'task_b'

branch = BranchPythonOperator(
    task_id='branch',
    python_callable=choose_branch
)

branch >> [task_a, task_b]
```

### Dynamic Task Mapping
```python
@task
def get_items() -> List[str]:
    return ['item1', 'item2', 'item3']

@task
def process_item(item: str):
    print(item)

# Process each item in parallel
items = get_items()
process_item.expand(item=items)
```

## Quick Reference
- **>>** - Execution order, no data
- **Function call** - Dependency + data passing
- **XCom** - Automatic data storage/retrieval
- **Instantiate** - Call dag function at module level
- **Chain** - `task_a >> task_b >> task_c`
- **Parallel** - `task_a >> [task_b, task_c]`
- **Join** - `[task_a, task_b] >> task_c`
