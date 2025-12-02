# Airflow Complete Cheatsheet - All Concepts & Tips

## Core Concepts

### DAG (Directed Acyclic Graph)
- Workflow definition
- Collection of tasks with dependencies
- Directed = tasks flow in order
- Acyclic = no circular dependencies

### Task
- Single unit of work
- One step in the workflow
- Can succeed, fail, skip, or retry

### Task Instance
- Specific execution of a task
- Task + execution_date = task instance

### DAG Run
- Single execution of entire DAG
- All tasks in one run
- Has unique run_id

### Operator
- Template for tasks
- PythonOperator, BashOperator, etc.
- @task decorator = modern alternative

## DAG Decorator
```python
from airflow.decorators import dag, task
from datetime import datetime

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
    # Task definitions
    pass

# Instantiate
my_workflow()
```

## DAG Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `dag_id` | Unique identifier | `'data_pipeline'` |
| `schedule` | When to run | `'@daily'`, `'0 * * * *'` |
| `start_date` | Activation date | `datetime(2024, 1, 1)` |
| `catchup` | Backfill historical | `False` |
| `max_active_tasks` | Parallel limit | `16` |
| `default_args` | Task defaults | `{'retries': 3}` |
| `tags` | Organization | `['prod', 'etl']` |

## Schedule Expressions
```python
'@hourly'          # Every hour
'@daily'           # Daily at midnight
'@weekly'          # Weekly on Sunday
'@monthly'         # First of month
'*/5 * * * *'      # Every 5 minutes
'0 9 * * 1-5'      # Weekdays at 9 AM
'0 0 * * *'        # Daily at midnight
None               # Manual only
```

### Cron Format
```
minute hour day month weekday
*      *    *   *     *
0-59   0-23 1-31 1-12 0-6 (0=Sunday)
```

## Task Decorator
```python
@task(task_id="process_data")
def process_data():
    result = compute()
    return result  # Auto-pushed to XCom

# Invoke (creates task reference)
task_ref = process_data()
```

## Task Dependencies
```python
# Basic
task_a >> task_b              # a then b

# Multiple to one
[task_a, task_b] >> task_c    # Both then c

# One to multiple
task_a >> [task_b, task_c]    # a then both (parallel)

# Chain
task_a >> task_b >> task_c    # Linear flow

# Complex
[a, b] >> c >> [d, e]         # Fan-in fan-out
```

## XCom (Cross-Communication)

### Automatic (Return Value)
```python
@task
def task_a():
    return {'data': 42}

@task
def task_b(data):
    print(data)  # {'data': 42}

# Dependencies
a = task_a()
b = task_b(a)  # Auto XCom transfer
```

### Manual Push/Pull
```python
from airflow.operators.python import get_current_context

# Push
context = get_current_context()
context['task_instance'].xcom_push(key='result', value='data')

# Pull
data = context['task_instance'].xcom_pull(
    task_ids='source_task',
    key='result'
)

# Pull from multiple
results = ti.xcom_pull(task_ids=['task1', 'task2'])
```

### XCom Limitations
- Size limit: ~48 KB (depends on metadata DB)
- Stored in database
- Not for large data
- Use external storage (S3, GCS) for big files

## Trigger Rules
```python
@task(trigger_rule="all_done")
def summary():
    pass
```

| Rule | Runs When |
|------|-----------|
| `all_success` | All upstream succeeded (default) |
| `all_failed` | All upstream failed |
| `all_done` | All finished (success or fail) |
| `one_success` | At least one succeeded |
| `one_failed` | At least one failed |
| `none_failed` | No failures (success/skipped) |
| `always` | Always run |

### Use Cases
```python
# Summary/reporting
@task(trigger_rule="all_done")
def summary(): pass

# Cleanup
@task(trigger_rule="always")
def cleanup(): pass

# Alert on failure
@task(trigger_rule="one_failed")
def alert(): pass
```

## Task States

| State | Meaning | Color |
|-------|---------|-------|
| `SUCCESS` | Completed successfully | 🟢 Green |
| `FAILED` | Failed with error | 🔴 Red |
| `RUNNING` | Currently executing | 🔵 Blue |
| `QUEUED` | Waiting to run | ⚪ Gray |
| `SKIPPED` | Skipped (branching) | 🟣 Pink |
| `UP_FOR_RETRY` | Will retry | 🟡 Yellow |
| `UPSTREAM_FAILED` | Upstream failed | 🟠 Orange |

## Context Access
```python
from airflow.operators.python import get_current_context

context = get_current_context()

# Common fields
dag = context['dag']                    # DAG object
task = context['task']                  # Task object
ti = context['task_instance']           # TaskInstance
dag_run = context['dag_run']            # DagRun object
run_id = context['run_id']              # String
execution_date = context['execution_date']  # Datetime
```

## Task Instance Introspection
```python
from airflow.utils.state import State

context = get_current_context()
dag_run = context['dag_run']

# Get all tasks
tasks = dag_run.get_task_instances()

# Filter by state
failed = [t for t in tasks if t.state == State.FAILED]
success = [t for t in tasks if t.state == State.SUCCESS]

# Get IDs
failed_ids = [t.task_id for t in failed]
```

## AirflowException
```python
from airflow.exceptions import AirflowException

# Basic failure
if service_down:
    raise AirflowException("Service is down")

# With details
error = f"Critical: {service} failed\n"
error += f"Logs:\n{logs}"
raise AirflowException(error)

# Multiple failures
failures = []
for item in items:
    if not check(item):
        failures.append(f"{item} failed")
if failures:
    raise AirflowException('\n'.join(failures))
```

## Task Execution Flow

### Single Task
```
QUEUED → RUNNING → SUCCESS/FAILED
```

### With Dependencies
```
Task A (SUCCESS) → Task B (RUNNING)
Task A (FAILED) → Task B (UPSTREAM_FAILED, skipped)
```

### With Retries
```
Task (FAILED) → UP_FOR_RETRY → RUNNING → SUCCESS/FAILED
```

## Airflow Architecture

### Components
- **Scheduler**: Monitors DAGs, schedules tasks
- **Executor**: Runs tasks (Local, Celery, Kubernetes)
- **Worker**: Executes task code (Celery mode)
- **Webserver**: UI for monitoring
- **Metadata DB**: Stores state, history
- **Message Queue**: Task distribution (RabbitMQ/Redis)

### Task Lifecycle
```
1. User triggers DAG
2. Scheduler picks it up → Creates task instances
3. Scheduler queues tasks → Sends to executor
4. Executor assigns to worker
5. Worker executes Python code
6. Worker reports back → Updates DB
7. Scheduler marks complete
```

### Log Locations
```
/home/airflow/logs/
  dag_id=my_dag/
    run_id=manual__2024-01-15T10:00:00/
      task_id=my_task/
        attempt=1.log
        attempt=2.log
```

## Common Patterns

### Sequential Pipeline
```python
@dag(schedule='@daily')
def pipeline():
    @task
    def extract(): return data
    
    @task
    def transform(data): return cleaned
    
    @task
    def load(data): save(data)
    
    e = extract()
    t = transform(e)
    load(t)

pipeline()
```

### Parallel Tasks
```python
@dag(schedule='@hourly')
def parallel():
    @task
    def check_1(): pass
    
    @task
    def check_2(): pass
    
    @task
    def summary(results): pass
    
    c1 = check_1()
    c2 = check_2()
    summary([c1, c2])

parallel()
```

### Summary Task
```python
@task(trigger_rule="all_done")
def summary():
    from airflow.utils.state import State
    
    context = get_current_context()
    dag_run = context['dag_run']
    tasks = dag_run.get_task_instances()
    
    failed = [t for t in tasks if t.state == State.FAILED]
    success = [t for t in tasks if t.state == State.SUCCESS]
    
    print(f"✅ Success: {len(success)}")
    print(f"❌ Failed: {len(failed)}")
    
    return {'success': len(success), 'failed': len(failed)}
```

### Final Decision
```python
@task
def final_check(summary_result):
    context = get_current_context()
    ti = context['task_instance']
    
    failed = ti.xcom_pull(task_ids='summary', key='failed_count')
    
    if failed > 0:
        raise AirflowException(f"{failed} checks failed")
    
    return {'status': 'healthy'}
```

### Failure Classification
```python
# In task that fails
if expected_failure:
    ti.xcom_push(key='failure_type', value='EXPECTED')
    raise AirflowException("Expected failure")
else:
    ti.xcom_push(key='failure_type', value='CRITICAL')
    raise AirflowException("Critical failure")

# In summary task
for failed_task in failed_tasks:
    ftype = failed_task.xcom_pull(
        task_ids=failed_task.task_id,
        key='failure_type'
    )
    if ftype == 'EXPECTED':
        expected.append(failed_task)
    else:
        critical.append(failed_task)
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
    'email_on_retry': False,
    'execution_timeout': timedelta(hours=1),
}

@dag(default_args=default_args)
def my_dag():
    pass
```

## Key Identifiers

| Field | Meaning | Example |
|-------|---------|---------|
| `dag_id` | Workflow name | `"health_monitor"` |
| `task_id` | Task name | `"check_db"` |
| `run_id` | Run identifier | `"manual__2024-01-15T10:00:00"` |
| `execution_date` | Scheduled time | `2024-01-15 10:00:00` |
| `try_number` | Attempt number | `1`, `2`, `3` |
| `job_id` | Database ID | `12345` |

## Best Practices

### DAG Design
- Keep DAGs simple and focused
- Use meaningful task_ids
- Set appropriate timeouts
- Configure retries for flaky tasks
- Use tags for organization
- Set max_active_tasks to prevent overload

### Task Design
- Tasks should be idempotent
- One task = one logical operation
- Return small data (XCom limits)
- Use external storage for large data
- Add proper error handling
- Include logging

### Dependencies
- Make dependencies explicit
- Avoid complex fan-out patterns
- Use task groups for organization
- Document why tasks depend on each other

### Error Handling
- Raise AirflowException on failures
- Include detailed error messages
- Add logs for debugging
- Classify expected vs critical failures
- Use trigger rules appropriately

### Performance
- Set catchup=False unless needed
- Limit max_active_tasks
- Use appropriate executor
- Monitor task duration
- Optimize task code

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Task not running | Check dependencies, upstream state |
| DAG not showing | Check syntax, instantiation |
| XCom data missing | Verify push/pull task_ids |
| Task always skipped | Check trigger rule |
| Slow execution | Check task duration, reduce parallelism |
| Out of memory | Reduce max_active_tasks, optimize code |
| Retries not working | Check default_args['retries'] |

## Quick Reference

| Operation | Code |
|-----------|------|
| Define DAG | `@dag(...)` |
| Define task | `@task(...)` |
| Set dependency | `a >> b` |
| Return data | `return value` |
| Pass data | `def func(param):` |
| XCom push | `ti.xcom_push(key, val)` |
| XCom pull | `ti.xcom_pull(task_ids, key)` |
| Fail task | `raise AirflowException()` |
| Get context | `get_current_context()` |
| Get tasks | `dag_run.get_task_instances()` |
| Filter state | `[t for t in tasks if t.state == State.FAILED]` |

## Resources
- Docs: https://airflow.apache.org/docs/
- API: https://airflow.apache.org/docs/apache-airflow/stable/python-api-ref.html
- Best Practices: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
