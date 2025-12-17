# Airflow Quick Reference - All Tips

## Core Concepts

### DAG (Directed Acyclic Graph)
- Workflow definition with tasks and dependencies
- Directed: Tasks have execution order
- Acyclic: No circular dependencies
- Each DAG has unique `dag_id`

### Tasks
- Individual units of work in a DAG
- Execute independently
- Can pass data via XCom
- Have states: success, failed, running, skipped

### XCom (Cross-Communication)
- Stores data between tasks (max ~48KB recommended)
- Automatic with `@task` decorator
- Pass references, not large content
- Serialized and stored in Airflow metadata database

### Scheduler
- Triggers DAGs based on schedule
- Monitors task completion
- Manages dependencies
- Handles retries

### Executor
- Runs tasks on workers
- Types: Local, Celery, Kubernetes
- Tasks routed via queues

## DAG Definition

### @dag Decorator
```python
from airflow.decorators import dag
from datetime import datetime

@dag(
    dag_id='unique_name',              # Required: Unique identifier
    start_date=datetime(2025, 1, 1),   # When DAG becomes active
    schedule_interval=None,             # None = manual only
    catchup=False,                      # No backfill past runs
    tags=['category'],                  # Organize in UI
    default_args={                      # Apply to all tasks
        'owner': 'airflow',
        'retries': 2,
        'queue': 'default'
    },
    description='What this DAG does'
)
def my_workflow():
    # Define tasks here
    pass

# Instantiate
dag = my_workflow()
```

### Schedule Intervals
```python
schedule_interval=None          # Manual trigger only
schedule_interval='@daily'      # Every day at midnight
schedule_interval='@hourly'     # Every hour
schedule_interval='@weekly'     # Sunday midnight
schedule_interval='0 9 * * *'   # 9 AM daily (cron)
```

### default_args
```python
default_args={
    'owner': 'airflow',           # DAG owner
    'retries': 2,                 # Retry failed tasks
    'retry_delay': timedelta(minutes=5),
    'queue': 'queue_name',        # Worker queue
    'pool': 'pool_name',          # Limit concurrency
    'execution_timeout': timedelta(hours=1)
}
```

## Task Definition

### @task Decorator
```python
from airflow.decorators import task
from typing import List, Dict

@task
def my_task(input: str) -> str:
    """Task description"""
    result = process(input)
    return result  # Stored in XCom automatically

# With overrides
@task(
    task_id='custom_name',
    retries=3,
    queue='special_queue'
)
def another_task():
    pass
```

### Task Return Values
```python
# Single value
@task
def get_count() -> int:
    return 100

# List
@task
def get_files() -> List[str]:
    return ['file1.txt', 'file2.txt']

# Dictionary
@task
def get_config() -> Dict[str, int]:
    return {'batch_size': 100, 'timeout': 300}

# None (side effects only)
@task
def send_notification() -> None:
    send_email()
```

## Sensors

### PythonSensor
```python
from airflow.sensors.python import PythonSensor

def check_condition() -> bool:
    # Return True when condition met
    return files_exist()

sensor = PythonSensor(
    task_id='wait_for_files',
    python_callable=check_condition,  # Must return bool
    poke_interval=30,                 # Check every 30s
    timeout=3600,                     # Max wait 1 hour
    mode='poke'                       # or 'reschedule'
)
```

### Sensor Modes
- **poke**: Keeps worker busy, good for short waits
- **reschedule**: Releases worker between checks, good for long waits

### Sensor Return Values
- `True`: Condition met, pass and continue workflow
- `False`: Not ready yet, wait and check again
- Never raise exception for "not ready" state

## Task Dependencies

### >> Operator (Bitshift)
```python
# Single dependency
task_a >> task_b

# Chain
task_a >> task_b >> task_c

# Parallel (fan-out)
task_a >> [task_b, task_c]

# Join (fan-in)
[task_a, task_b] >> task_c

# Diamond
start >> [branch_a, branch_b]
[branch_a, branch_b] >> end
```

### Function Calls (Data Passing)
```python
# Automatic dependency + data passing
result = task_a()
task_b(result)

# Multiple inputs
result1 = task_a()
result2 = task_b()
task_c(result1, result2)
```

### Mixed Dependencies
```python
# Sensor + data tasks
sensor >> task_a()
result = task_a()
task_b(result) >> task_c()
```

## Data Passing (XCom)

### Automatic with @task
```python
@task
def producer() -> List[str]:
    return ['item1', 'item2']  # Stored in XCom

@task
def consumer(items: List[str]):  # Retrieved from XCom
    for item in items:
        print(item)

# Wire together
items = producer()
consumer(items)
```

### Size Limits
- Keep under 48KB (varies by backend)
- SQLite: 2GB max
- PostgreSQL: 1GB max
- MySQL: Limited by max_allowed_packet

### Best Practices
- Pass file paths, not file contents
- Pass IDs, not full objects
- Use external storage (S3, DB) for large data

## Exception Handling

### AirflowException
```python
from airflow.exceptions import AirflowException

@task
def my_task():
    if error_condition:
        raise AirflowException("Clear error message")
```

### Benefits
- Recognized by Airflow
- Triggers retry logic
- Logged properly in UI
- Shows in task logs

### Task States After Exception
- Failed → Retry (if retries configured)
- Failed → Up for retry → Running
- Failed (final) → DAG fails

## Common Patterns

### Input Validation
```python
@task
def process(data: List[str]) -> List[str]:
    if not data or data is None:
        raise AirflowException("No data to process")
    
    if len(data) < 1:
        raise AirflowException("Empty data list")
    
    return process_items(data)
```

### Result Tracking
```python
@task
def process_files(files: List[str]) -> dict:
    results = {'success': [], 'failed': []}
    
    for file in files:
        try:
            process(file)
            results['success'].append(file)
        except Exception as e:
            results['failed'].append(file)
    
    if results['failed']:
        raise AirflowException(f"Failed: {results['failed']}")
    
    return results
```

### Resource Cleanup
```python
@task
def ssh_task():
    ssh = None
    try:
        ssh = create_ssh_client()
        # Do work
        return result
    except Exception as e:
        raise AirflowException(f"Failed: {e}")
    finally:
        if ssh:
            ssh.close()
```

## Traditional Operators

### PythonOperator
```python
from airflow.operators.python import PythonOperator

def my_function():
    print("Hello")

task = PythonOperator(
    task_id='run_python',
    python_callable=my_function
)
```

### BashOperator
```python
from airflow.operators.bash import BashOperator

task = BashOperator(
    task_id='run_bash',
    bash_command='echo "Hello"'
)
```

### Mixing with @task
```python
@dag(...)
def my_dag():
    # Traditional operator
    sensor = PythonSensor(...)
    
    # @task decorator
    @task
    def process():
        pass
    
    # Wire together
    sensor >> process()
```

## DAG Execution Flow

### Runtime Sequence
```
1. Trigger DAG (manual or scheduled)
2. Scheduler picks up DAG
3. Check start_date and schedule
4. Execute tasks respecting dependencies
5. Store return values in XCom
6. Pass data to downstream tasks
7. Mark DAG complete/failed
```

### Task States
- **Queued**: Waiting for executor
- **Running**: Currently executing
- **Success**: Completed successfully
- **Failed**: Error occurred
- **Up for retry**: Will retry
- **Skipped**: Intentionally skipped
- **Upstream failed**: Dependency failed

## Configuration Best Practices

### Centralize Config
```python
CONFIG = {
    'host': '10.0.0.1',
    'user': 'admin',
    'key_file': '/path/to/key'
}

# Use everywhere
hostname = CONFIG['host']
```

### Use Variables
```python
from airflow.models import Variable

api_key = Variable.get("api_key")
config = Variable.get("config", deserialize_json=True)
```

### Use Connections
```python
from airflow.hooks.base import BaseHook

conn = BaseHook.get_connection('my_conn_id')
host = conn.host
login = conn.login
```

## Logging

### Print Statements
```python
@task
def my_task():
    print("Starting processing")  # Shows in task logs
    result = process()
    print(f"Processed {len(result)} items")
    return result
```

### Python Logging
```python
import logging

@task
def my_task():
    logging.info("Starting task")
    logging.warning("Warning message")
    logging.error("Error message")
```

## Trigger Rules

### Default (all_success)
```python
# Task runs only if all upstream tasks succeed
```

### Common Rules
```python
@task(trigger_rule='all_success')    # All upstream success (default)
@task(trigger_rule='all_failed')     # All upstream failed
@task(trigger_rule='all_done')       # All upstream done (success or fail)
@task(trigger_rule='one_success')    # At least one success
@task(trigger_rule='one_failed')     # At least one failed
@task(trigger_rule='none_failed')    # No upstream failures
```

## Dynamic Task Mapping

### Expand Pattern
```python
@task
def get_items() -> List[str]:
    return ['item1', 'item2', 'item3']

@task
def process_item(item: str):
    print(f"Processing {item}")

# Creates 3 parallel tasks
items = get_items()
process_item.expand(item=items)
```

## Common Mistakes

### ✗ Wrong Patterns
```python
# Not assigning task reference
get_data()  # Lost!
process(???)

# Using >> with data passing
get_data() >> process()  # Data not passed!

# Not instantiating DAG
@dag(...)
def my_dag():
    pass
# Missing: my_dag()

# Reading XCom manually (with @task)
# @task handles it automatically
```

### ✓ Correct Patterns
```python
# Assign references
result = get_data()
process(result)

# Use >> for pure dependencies only
sensor >> task()

# Always instantiate
dag = my_dag()

# Let @task handle XCom
# Just pass task references
```

## Quick Reference Summary

### Key Points
- **DAG** = Workflow with tasks and dependencies
- **Task** = Unit of work
- **XCom** = Data passing (auto with @task)
- **Sensor** = Wait for condition (return bool)
- **>>** = Execution order without data
- **Function call** = Dependency + data passing
- **schedule_interval** = When DAG runs
- **catchup=False** = No historical runs
- **AirflowException** = Proper error handling
- **Instantiate** = Call @dag function
- **Keep XCom small** = < 48KB

### Execution Flow
```
Trigger → Scheduler → Check dependencies → 
Run tasks → Store XCom → Pass data → Complete
```

### Task Creation
```python
@task
def my_task(input: type) -> return_type:
    result = process(input)
    return result
```

### Dependency Creation
```python
# No data
task_a >> task_b

# With data
result = task_a()
task_b(result)
```
