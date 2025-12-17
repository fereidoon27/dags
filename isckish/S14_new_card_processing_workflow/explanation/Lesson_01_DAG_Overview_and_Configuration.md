# Lesson 01: DAG Overview and Configuration

## What You're Learning
You have an **Airflow DAG** (Directed Acyclic Graph) that automates file processing between servers using SSH. This lesson covers the big picture and initial configuration.

---

## What This DAG Does

**Real-World Scenario:**
Your company receives card batch files on an FTP server. These files need to be:
1. Detected automatically when they arrive
2. Transferred to a processing server
3. Processed by a Python script
4. All done securely via SSH

**The Workflow:**
```
FTP Server (10.101.20.164)
    ↓ [Detect card files]
    ↓ [Transfer via SSH]
Target Server (10.101.20.201)
    ↓ [Process files]
    ✓ [Complete]
```

---

## DAG Structure Overview

Your code has these main components:

### 1. **Configuration** (Lines 1-23)
- Imports and SSH connection details
- Server IPs, paths, credentials

### 2. **Helper Functions** (Lines 26-91)
- `create_ssh_client()` - Connects to servers
- `check_for_card_files()` - Detects files (sensor function)
- `get_card_files()` - Retrieves file list

### 3. **DAG Definition** (Lines 94-108)
- Metadata: DAG name, schedule, owner, retries

### 4. **Tasks** (Lines 109-205)
- Sensor task - Waits for files
- Get file list - Retrieves detected files
- Transfer task - Moves files between servers
- Process task - Runs processing script

### 5. **Task Dependencies** (Lines 208-213)
- Defines execution order

---

## Configuration Deep Dive

```python
SSH_CONFIG = {
    'user': 'rocky',
    'key_file': '/home/rocky/.ssh/id_ed25519',
    'ftp_host': '10.101.20.164',
    'target_host': '10.101.20.201',
    'card_dir': '/home/rocky/card/in/',
    'processor_script': '/home/rocky/scripts/card_processor.py'
}
```

**What's happening:**
- **Dictionary** storing all SSH connection details
- **Why?** Centralizes configuration - change once, affects everywhere
- **Security:** Uses SSH key authentication (no passwords)

**Key Details:**
- `key_file` - Ed25519 private key (modern SSH encryption)
- `ftp_host` - Where files arrive
- `target_host` - Where files are processed
- `card_dir` - Directory to monitor for new files

**Example Usage:**
When connecting to FTP server:
```python
hostname = SSH_CONFIG['ftp_host']  # Gets '10.101.20.164'
```

---

## Imports Explained

```python
from datetime import datetime
from pathlib import Path
import paramiko
from typing import List

from airflow.decorators import dag, task
from airflow.sensors.python import PythonSensor
from airflow.exceptions import AirflowException
```

**Grouped by Purpose:**

**Standard Python Libraries:**
- `datetime` - For DAG start date
- `pathlib.Path` - Modern file path handling
- `typing.List` - Type hints for function parameters

**SSH Library:**
- `paramiko` - Python's SSH client library (connects to remote servers)

**Airflow Components:**
- `@dag, @task` - Decorators to define workflows
- `PythonSensor` - Waits for a condition (file detection)
- `AirflowException` - Raises errors that Airflow understands

---

## DAG Decorator Breakdown

```python
@dag(
    dag_id='S14_new_card_processing_workflow',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['card-processing'],
    default_args={
        'owner': 'airflow',
        'queue': 'card_processing_queue',
        'retries': 2
    },
    description='Secure SSH-based card file processing workflow'
)
```

**Core Settings:**

**dag_id**: Unique identifier in Airflow UI
- Must be unique across all DAGs
- Example: Shows as "S14_new_card_processing_workflow" in dashboard

**start_date**: When DAG becomes active
- `datetime(2025, 1, 1)` means "available from Jan 1, 2025"

**schedule_interval**: When DAG runs automatically
- `None` means **manual trigger only** (no automatic runs)
- Alternative examples: `'@daily'`, `'0 9 * * *'` (9 AM daily)

**catchup**: Backfill past runs?
- `False` means "only run for current time" (no historical runs)

**tags**: Organizing label in UI
- `['card-processing']` groups similar DAGs

**default_args**: Settings for ALL tasks
- `owner` - Who owns this DAG
- `queue` - Which worker queue processes tasks
- `retries` - Retry failed tasks 2 times before giving up

---

## TIP: Understanding DAG Schedulers

### What is schedule_interval?

Controls when Airflow automatically triggers your DAG.

### Most Common Use Cases

**Manual Trigger Only:**
```python
schedule_interval=None  # Run only when you click "Trigger DAG"
```

**Daily at Midnight:**
```python
schedule_interval='@daily'  # Runs every day at 00:00
```

**Hourly:**
```python
schedule_interval='@hourly'  # Every hour
```

**Custom Cron:**
```python
schedule_interval='0 9 * * *'  # Every day at 9 AM
# Format: minute hour day month day_of_week
```

### Booklet Summary
`schedule_interval=None` → Manual triggers only. Use cron expressions or presets (`@daily`, `@hourly`) for automatic scheduling.

---

## Key Takeaways

✅ **DAG** = Workflow definition with tasks and dependencies  
✅ **Configuration dictionary** centralizes all SSH settings  
✅ **schedule_interval=None** means manual trigger only  
✅ **catchup=False** prevents backfilling old runs  
✅ **default_args** apply to all tasks (retries, queue, owner)  
✅ **paramiko** handles SSH connections to remote servers  

---

## What's Next

**Lesson 02:** SSH Connection Management - Creating secure SSH clients with error handling
