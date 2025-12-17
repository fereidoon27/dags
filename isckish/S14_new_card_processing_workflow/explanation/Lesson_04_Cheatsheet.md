# Lesson 04 Cheatsheet: @task Decorator & Data Passing

## @task Decorator Pattern
```python
from airflow.decorators import task
from typing import List

@task
def my_task() -> List[str]:
    """Task automatically created from function"""
    result = do_work()
    return result  # Stored in XCom automatically
```

## PythonSensor vs @task
```python
# Sensor - waits for condition
sensor = PythonSensor(
    task_id='wait_for_files',
    python_callable=check_files,  # Returns bool
    poke_interval=30,
    timeout=3600
)

# Task - processes data
@task
def get_data() -> List[str]:
    return retrieve_data()  # Returns actual data
```

## Data Passing Between Tasks
```python
@task
def task_a() -> List[str]:
    return ['item1', 'item2']  # Returns data

@task
def task_b(items: List[str]):  # Receives data
    for item in items:
        print(item)

# Wire them together
result = task_a()
task_b(result)  # Data passed via XCom
```

## Common Type Hints
```python
from typing import List, Dict, Optional

@task
def return_list() -> List[str]:
    return ['a', 'b', 'c']

@task
def return_dict() -> Dict[str, int]:
    return {'count': 100}

@task
def return_optional() -> Optional[str]:
    return None  # or return "value"

@task
def no_return() -> None:
    print("Side effect only")
```

## Validation Patterns
```python
@task
def validate_data(data: List[str]) -> List[str]:
    # Check data exists
    if not data:
        raise AirflowException("No data received")
    
    # Check data quality
    if len(data) < 5:
        raise AirflowException(f"Expected 5+ items, got {len(data)}")
    
    return data
```

## XCom Data Size Guidelines
```python
# ✓ Good - Pass references
@task
def get_files() -> List[str]:
    return ['/path/file1.txt', '/path/file2.txt']

# ✓ Good - Pass small metadata
@task
def get_config() -> dict:
    return {'batch_id': '12345', 'count': 100}

# ✗ Bad - Pass large content
@task
def get_content() -> str:
    return file_content  # Could be MBs of data
```

## Task Configuration Options
```python
@task(
    task_id='custom_name',      # Override default name
    retries=3,                   # Override DAG default
    retry_delay=timedelta(minutes=5),
    queue='special_queue',       # Route to specific queue
    pool='limited_pool'          # Limit concurrency
)
def my_task():
    pass
```

## Common Patterns

### Sequential Tasks
```python
result1 = task_a()
result2 = task_b(result1)
task_c(result2)
```

### Parallel Tasks
```python
result1 = task_a()
result2 = task_b()
task_c([result1, result2])  # Both must complete first
```

### Conditional Logic
```python
@task
def decide() -> str:
    if condition:
        return "option_a"
    return "option_b"

@task
def process(option: str):
    if option == "option_a":
        # Do something
    else:
        # Do something else
```

## Quick Reference
- **@task** - Converts function to Airflow task
- **Return value** - Stored in XCom, passed to downstream
- **Type hints** - Document expected data types
- **XCom limit** - Keep under 48KB (pass refs, not content)
- **task_id** - Auto-generated from function name
- **Validation** - Check data before processing
