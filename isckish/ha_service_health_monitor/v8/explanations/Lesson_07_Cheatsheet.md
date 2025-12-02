# Lesson 07 Cheatsheet: Airflow DAG & Tasks

## DAG Decorator
```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
    dag_id='my_workflow',
    schedule='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_tasks=10,
    default_args={'owner': 'airflow', 'retries': 2},
    tags=['production']
)
def my_workflow():
    # Task definitions here
    pass

# Instantiate
dag_instance = my_workflow()
```

## Task Decorator
```python
@task(task_id="my_task")
def my_task():
    result = process_data()
    return result  # Stored in XCom

# Invoke (creates task reference)
task_ref = my_task()
```

## Schedule Expressions
```python
# Cron format: minute hour day month weekday
'*/5 * * * *'    # Every 5 minutes
'0 * * * *'      # Hourly
'0 0 * * *'      # Daily midnight
'0 9 * * 1-5'    # Weekdays at 9 AM

# Shortcuts
'@hourly'
'@daily'
'@weekly'
'@monthly'
None             # Manual only
```

## DAG Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `dag_id` | Unique identifier | `'data_pipeline'` |
| `schedule` | When to run | `'@daily'` |
| `start_date` | Activation date | `datetime(2024, 1, 1)` |
| `catchup` | Backfill historical | `False` |
| `max_active_tasks` | Parallel limit | `16` |
| `default_args` | Task defaults | `{'retries': 3}` |
| `tags` | Organization | `['prod', 'etl']` |

## Task Dependencies
```python
# Basic
task_a >> task_b  # a then b

# Multiple to one
[task_a, task_b] >> task_c

# One to multiple  
task_a >> [task_b, task_c]

# Chain
task_a >> task_b >> task_c >> task_d

# Complex
[task_a, task_b] >> task_c >> [task_d, task_e]
```

## XCom (Cross-Communication)
```python
# Auto push (return value)
@task
def task_a():
    return {'data': 42}

# Auto pull (parameter)
@task
def task_b(result):
    print(result)  # {'data': 42}

# Dependencies
a = task_a()
b = task_b(a)  # Auto XCom transfer

# Manual push
from airflow.operators.python import get_current_context
context = get_current_context()
context['task_instance'].xcom_push(key='mykey', value='mydata')

# Manual pull
data = context['task_instance'].xcom_pull(
    task_ids='task_a',
    key='mykey'
)
```

## Default Args
```python
from datetime import timedelta

default_args = {
    'owner': 'airflow',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email': ['alert@company.com'],
    'email_on_failure': True,
    'execution_timeout': timedelta(hours=1),
}

@dag(default_args=default_args)
def my_dag():
    pass
```

## Complete Example
```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
    dag_id='etl_pipeline',
    schedule='0 2 * * *',  # 2 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False
)
def etl_pipeline():
    
    @task
    def extract():
        return {'records': 1000}
    
    @task
    def transform(data):
        return {'cleaned': data['records'] * 0.95}
    
    @task
    def load(data):
        print(f"Loading {data['cleaned']}")
        return 'Success'
    
    # Flow
    raw = extract()
    cleaned = transform(raw)
    load(cleaned)

etl_pipeline()
```

## Parallel Tasks
```python
@dag(schedule='@hourly')
def parallel_dag():
    
    @task
    def check_db1():
        return 'db1_ok'
    
    @task
    def check_db2():
        return 'db2_ok'
    
    @task
    def check_db3():
        return 'db3_ok'
    
    @task
    def summary(results):
        print(results)
    
    # All run in parallel
    db1 = check_db1()
    db2 = check_db2()
    db3 = check_db3()
    
    # Then summary
    summary([db1, db2, db3])

parallel_dag()
```

## Common Patterns

### Sequential Pipeline
```python
task1 >> task2 >> task3 >> task4
```

### Fan-out Fan-in
```python
start >> [task_a, task_b, task_c] >> end
```

### Conditional Logic
```python
@task
def check_condition():
    return True

@task
def process_if_true():
    pass

condition = check_condition()
process = process_if_true()

# Dependency
condition >> process
```

## Airflow Concepts

| Term | Definition |
|------|------------|
| **DAG** | Workflow definition |
| **Task** | Single operation |
| **Task Instance** | Specific task execution |
| **DAG Run** | Single DAG execution |
| **XCom** | Task communication |
| **Dependency** | Execution order |
| **Operator** | Task type (Python, Bash, etc) |

## Quick Reference

| Operation | Code |
|-----------|------|
| Define DAG | `@dag(...)` |
| Define task | `@task(...)` |
| Dependency | `a >> b` |
| Return data | `return value` |
| Access data | `def func(param):` |
| Manual XCom push | `ti.xcom_push(key, val)` |
| Manual XCom pull | `ti.xcom_pull(task_ids, key)` |

## Troubleshooting

### DAG not appearing in UI
```python
# ❌ Missing instantiation
@dag(dag_id='my_dag')
def my_dag():
    pass
# No dag_instance = my_dag()

# ✅ Instantiate
dag_instance = my_dag()
```

### Tasks not running in order
```python
# ❌ No dependencies
task_a()
task_b()  # May run before task_a

# ✅ Set dependency
a = task_a()
b = task_b()
a >> b
```

### XCom data not passing
```python
# ❌ Not using return/parameter
@task
def task_a():
    data = {'x': 1}
    # Not returned

@task
def task_b():
    # Can't access data
    pass

# ✅ Return and parameter
@task
def task_a():
    return {'x': 1}

@task
def task_b(data):
    print(data)  # {'x': 1}

a = task_a()
b = task_b(a)
```

### Catchup creating too many runs
```python
# ❌ Catchup enabled with old start_date
start_date=datetime(2020, 1, 1)  # 4 years ago!
catchup=True  # Thousands of backfill runs

# ✅ Disable catchup
catchup=False
```
