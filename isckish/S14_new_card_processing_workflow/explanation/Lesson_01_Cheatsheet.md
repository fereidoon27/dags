# Lesson 01 Cheatsheet: DAG Basics

## DAG Decorator Syntax
```python
@dag(
    dag_id='unique_name',           # Required: DAG identifier
    start_date=datetime(2025, 1, 1), # When DAG becomes active
    schedule_interval=None,          # None = manual trigger only
    catchup=False,                   # No backfill past runs
    tags=['category'],               # Organize in UI
    default_args={                   # Apply to all tasks
        'owner': 'airflow',
        'retries': 2
    }
)
def my_workflow():
    # Define tasks here
    pass
```

## Schedule Intervals
| Value | Behavior |
|-------|----------|
| `None` | Manual trigger only |
| `'@daily'` | Every day at midnight |
| `'@hourly'` | Every hour |
| `'@weekly'` | Every Sunday midnight |
| `'0 9 * * *'` | Every day at 9 AM (cron) |

## Configuration Pattern
```python
# Centralize settings
CONFIG = {
    'host': '10.101.20.164',
    'user': 'rocky',
    'key_file': '/path/to/key'
}

# Use everywhere
hostname = CONFIG['host']
```

## Essential Imports
```python
from datetime import datetime              # DAG dates
from airflow.decorators import dag, task  # Define workflows
from airflow.exceptions import AirflowException  # Error handling
```

## Key Concepts
- **DAG**: Workflow with tasks and dependencies
- **dag_id**: Unique name visible in Airflow UI
- **catchup=False**: Only run current scheduled time, skip historical
- **default_args**: Settings inherited by all tasks
- **schedule_interval**: Controls automatic execution

## Common Patterns
```python
# Manual trigger workflow
schedule_interval=None

# Daily batch processing
schedule_interval='@daily'

# Retry failed tasks
default_args={'retries': 2}

# Route to specific worker queue
default_args={'queue': 'my_queue'}
```
