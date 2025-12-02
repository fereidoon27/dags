# Lesson 07: Airflow DAG & Task Decorators

## Overview

This is where we shift from helper functions to defining the actual Airflow workflow. The `@dag` and `@task` decorators transform regular Python functions into Airflow-managed workflow components.

**Key learning:**
- DAG decorator and configuration
- Task decorator pattern
- Task dependencies with `>>`
- XCom for inter-task communication
- DAG instantiation

---

## 🎓 AIRFLOW CONCEPT: DAGs and Tasks

**What is a DAG?**
- **D**irected **A**cyclic **G**raph
- Workflow definition with tasks and dependencies
- Directed = tasks flow in specific order
- Acyclic = no circular dependencies
- Graph = visual representation

**Hierarchy:**
```
DAG (Workflow)
├── Task 1 (Step)
├── Task 2 (Step)
├── Task 3 (Step)
└── Task 4 (Step)

Dependencies:
Task 1 → Task 2 → Task 4
Task 1 → Task 3 → Task 4
```

**Key concepts:**

| Term | Meaning | Example |
|------|---------|---------|
| **DAG** | Complete workflow | Health monitoring pipeline |
| **Task** | Single step/operation | Check database connection |
| **Task Instance** | Specific execution of task | Check DB on 2024-01-15 10:00 |
| **DAG Run** | Single execution of DAG | Full health check run |
| **Dependency** | Order relationship | A must finish before B |

---

## The @dag Decorator (Lines 453-465)

```python
@dag(
    dag_id='ha_service_health_monitor_v8',
    description='Monitor all HA services - V8 with comprehensive logging and VM inventory',
    schedule='*/2 * * * *',
    start_date=datetime(2025, 10, 12),
    catchup=False,
    max_active_tasks=16,
    default_args={
        'owner': 'airflow',
        'retries': 0,
    },
    tags=['monitoring', 'health-check', 'v8'],
)
def ha_service_health_monitor_v8():
```

**What @dag does:**
- Transforms function into DAG definition
- Function body becomes task definitions
- Function name becomes default dag_id (if not specified)

### DAG Parameters Explained

**`dag_id='ha_service_health_monitor_v8'`**
- Unique identifier in Airflow
- Shows in UI, used in commands
- Convention: descriptive, version suffix

**`schedule='*/2 * * * *'`**
- Cron expression: every 2 minutes
- Format: `minute hour day month weekday`

**Cron examples:**
```
'*/2 * * * *'    # Every 2 minutes
'0 * * * *'      # Every hour
'0 0 * * *'      # Daily at midnight
'0 9 * * 1'      # Every Monday at 9 AM
'@hourly'        # Every hour (shortcut)
'@daily'         # Daily at midnight
None             # Manual trigger only
```

**`start_date=datetime(2025, 10, 12)`**
- When DAG becomes active
- No runs scheduled before this date
- Historical date = immediate start
- Future date = wait until then

**`catchup=False`**
- Don't run missed historical runs
- `True` = backfill from start_date to now
- `False` = only run current/future

**Example catchup behavior:**
```python
# Scenario: DAG paused for 2 hours, runs hourly
start_date = datetime(2024, 1, 15, 10, 0)
current_time = datetime(2024, 1, 15, 14, 0)

# catchup=True → Runs for 10:00, 11:00, 12:00, 13:00, 14:00 (5 runs)
# catchup=False → Runs only for 14:00 (1 run)
```

**`max_active_tasks=16`**
- Maximum tasks running simultaneously
- Limits parallelism
- Prevents resource exhaustion

**`default_args={...}`**
- Default configuration for all tasks
- Can be overridden per task

**Common default_args:**
```python
default_args = {
    'owner': 'airflow',           # Who owns this DAG
    'retries': 3,                  # Auto-retry failed tasks
    'retry_delay': timedelta(minutes=5),
    'email': ['alerts@company.com'],
    'email_on_failure': True,
    'execution_timeout': timedelta(hours=1),
}
```

**`tags=['monitoring', 'health-check', 'v8']`**
- Organize DAGs in UI
- Filter by tags
- Purely informational

---

## The @task Decorator (Lines 468-474)

```python
@task(task_id="detect_nfs_active_node")
def detect_nfs_node():
    active = detect_active_nfs_node()
    print(f"🔍 Active NFS Node: {active}")
    return active

active_nfs = detect_nfs_node()
```

**What @task does:**
- Transforms function into Airflow task
- Function becomes executable unit
- Return value stored in XCom

**Task execution:**
```python
# NOT a regular function call - creates task object
active_nfs = detect_nfs_node()

# active_nfs is NOT the return value
# It's a task reference (XComArg object)
# Actual execution happens when Airflow runs the task
```

**Task with parameter (Lines 476-548):**

```python
@task(task_id="check_system_resources")
def check_system_resources():
    """Monitor system resources across all nodes"""
    all_metrics = {}
    
    for hostname, ip in ALL_NODES.items():
        metrics = get_system_resources(ip, hostname)
        all_metrics[hostname] = metrics
    
    # Store in XCom for other tasks
    context = get_current_context()
    context['task_instance'].xcom_push(key='system_metrics', value=all_metrics)
    
    return all_metrics
```

---

## 🎓 AIRFLOW CONCEPT: XCom (Cross-Communication)

**What is XCom?**
Small message passing between tasks - like passing notes between workers.

**How it works:**

```python
# Task A - Push data
@task
def task_a():
    data = {'result': 42}
    return data  # Automatically pushed to XCom

# Task B - Pull data
@task
def task_b(upstream_result):
    # upstream_result automatically pulled from task_a's return
    print(upstream_result)  # {'result': 42}
```

**Manual XCom operations:**

```python
# Push with custom key
context = get_current_context()
context['task_instance'].xcom_push(key='custom_key', value='my_data')

# Pull by key
data = context['task_instance'].xcom_pull(
    task_ids='other_task',
    key='custom_key'
)
```

**XCom limitations:**
- Size limit (typically 48 KB in Postgres)
- Stored in database
- Not for large data
- Use external storage (S3, GCS) for big data

**Example usage in code (Line 546):**
```python
context['task_instance'].xcom_push(key='system_metrics', value=all_metrics)
# Stores all_metrics so other tasks can access it later
```

---

## Task Invocation & Dependencies (Lines 1357-1383)

### Task Invocation

```python
# Create task instances by calling decorated functions
nfs = check_nfs_services(active_nfs)
haproxy = check_haproxy_services()
scheduler_svc = check_scheduler_services()
# ... more tasks

sys_resources = check_system_resources()
summary = health_summary()
final = final_status_check(summary)
```

**What's happening:**
- Calling decorated function creates task
- Variables store task references (not results)
- Tasks don't execute yet - just defined

**With parameters:**
```python
nfs = check_nfs_services(active_nfs)
# active_nfs is output from detect_nfs_node task
# Airflow automatically passes the value at runtime
```

### Setting Dependencies

**Bit shift operator `>>`:**

```python
# Single dependency
task_a >> task_b
# Read as: "task_a then task_b"
# task_b runs after task_a completes

# Multiple tasks to one
[task_a, task_b, task_c] >> task_d
# All three must complete before task_d

# One task to multiple
task_a >> [task_b, task_c]
# task_b and task_c both run after task_a (in parallel)

# Chaining
task_a >> task_b >> task_c
# Linear: a → b → c
```

**In the code:**

```python
# Service checks (8 tasks) → summary
[nfs, haproxy, scheduler_svc, webserver, rabbitmq_svc, postgresql_svc, celery_svc, ftp] >> summary

# Cluster checks (6 tasks) → summary  
[pg_vip, rabbitmq_cluster, scheduler_hb, celery_workers, sys_resources, vm_inventory] >> summary

# Summary → final
summary >> final
```

**Visual representation:**
```
nfs ────────┐
haproxy ────┤
scheduler ──┤
webserver ──┼─→ summary ─→ final
rabbitmq ───┤
postgresql ─┤
celery ─────┤
ftp ────────┘

pg_vip ─────┐
rmq_cluster ┤
sched_hb ───┼─→ summary ─→ final
celery_wkr ─┤
sys_res ────┤
vm_inv ─────┘
```

**Execution flow:**
1. All 14 checks run in parallel (up to max_active_tasks limit)
2. When all complete, summary runs
3. When summary completes, final runs

---

## DAG Instantiation (Line 1386)

```python
dag_instance = ha_service_health_monitor_v8()
```

**Why needed?**
- Decorator alone doesn't register DAG
- Calling function creates DAG instance
- Airflow discovers this instance

**How Airflow finds DAGs:**
1. Scans files in `dags/` folder
2. Looks for DAG objects
3. Registers them in metadata database

**Alternative pattern (older style):**
```python
# Old way - explicit DAG context
with DAG(
    dag_id='my_dag',
    schedule='@daily',
    start_date=datetime(2024, 1, 1)
) as dag:
    
    task1 = PythonOperator(
        task_id='task1',
        python_callable=my_function
    )
    task2 = PythonOperator(
        task_id='task2',
        python_callable=another_function
    )
    
    task1 >> task2

# Decorator way is cleaner, more Pythonic
```

---

## 🎓 PRACTICAL EXAMPLE: Simple DAG

```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
    dag_id='data_pipeline',
    schedule='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False
)
def data_pipeline():
    
    @task
    def extract():
        print("Extracting data")
        return {'rows': 1000}
    
    @task
    def transform(data):
        print(f"Transforming {data['rows']} rows")
        return {'rows': data['rows'], 'cleaned': 950}
    
    @task
    def load(data):
        print(f"Loading {data['cleaned']} rows")
        return 'Success'
    
    # Define flow
    extracted = extract()
    transformed = transform(extracted)
    load(transformed)

# Create instance
data_pipeline()
```

**Execution:**
```
extract() returns {'rows': 1000}
    ↓ (passed via XCom)
transform(data) receives {'rows': 1000}, returns {'rows': 1000, 'cleaned': 950}
    ↓ (passed via XCom)
load(data) receives {'rows': 1000, 'cleaned': 950}
```

---

## Key Takeaways

✅ **@dag decorator** - Transforms function into workflow definition

✅ **@task decorator** - Transforms function into executable task

✅ **dag_id** - Unique identifier, shows in UI

✅ **schedule** - Cron expression for automation

✅ **catchup** - Whether to backfill historical runs

✅ **XCom** - Cross-task communication for small data

✅ **`>>`operator** - Sets task dependencies (execution order)

✅ **Task invocation** - Creates task references, not execution

✅ **DAG instantiation** - Required for Airflow to discover DAG

---

## What's Next?

Lesson 08 will cover:
- Task groups for organization
- Dynamic task mapping
- Trigger rules (all_done, all_success, one_failed)
- Task failure handling
- Real monitoring task implementation

**Ready to continue?** 🚀
