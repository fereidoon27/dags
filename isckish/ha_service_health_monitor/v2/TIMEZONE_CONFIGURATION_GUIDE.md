# Airflow Timezone Configuration Guide
## Fixing Timestamp Inconsistencies in HA Environment

## Understanding the Problem

You're seeing:
- **Task logs**: Show local time (e.g., `11:22:49 +0330` - Asia/Tehran)
- **UI/Database**: Show UTC time (e.g., `07:51:00`)

This is actually **expected Airflow behavior**, but can be confusing. Here's why:

### How Airflow Handles Timezones

1. **Internal Storage (Database)**: Airflow **always** stores times in UTC
2. **Display (UI)**: Airflow displays times based on `default_timezone` setting
3. **Task Logs**: Use the system timezone of the worker running the task

## Complete Solution

### Step 1: Verify System Timezone on ALL Nodes

Run this on **every** VM (schedulers, workers, webservers):

```bash
# Check current timezone
timedatectl

# Should show:
# Time zone: Asia/Tehran (CST, +0330)

# If not set correctly, fix it:
sudo timedatectl set-timezone Asia/Tehran

# Verify
date
# Should show: Tue Oct 28 14:30:00 +0330 2025
```

**Critical**: Reboot or restart all Airflow services after timezone changes:
```bash
sudo systemctl restart airflow-scheduler
sudo systemctl restart airflow-webserver
sudo systemctl restart airflow-worker
```

### Step 2: Update airflow.cfg on ALL Airflow Nodes

On **all nodes** (haproxy-1, haproxy-2, scheduler-2, celery-1, celery-2, nfs-1, nfs-2):

Edit `/home/rocky/airflow/airflow.cfg`:

```ini
[core]
# ... other settings ...
default_timezone = Asia/Tehran

# IMPORTANT: Use timezone-aware configuration
# This ensures all datetime operations use Asia/Tehran
dags_are_paused_at_creation = False

[webserver]
# ... other settings ...
default_ui_timezone = Asia/Tehran

[logging]
# ... other settings ...
# This ensures logs use local timezone
log_timezone_format = %Y-%m-%d %H:%M:%S %Z
```

### Step 3: Update DAG Definitions

For **new DAGs**, use timezone-aware datetime:

```python
from datetime import datetime
from airflow import DAG
import pendulum

# Option 1: Use pendulum (recommended)
local_tz = pendulum.timezone('Asia/Tehran')

dag = DAG(
    dag_id='example_dag',
    start_date=datetime(2025, 10, 1, tzinfo=local_tz),
    schedule='0 9 * * *',  # 9 AM Tehran time
    catchup=False,
)

# Option 2: Use pytz
from pytz import timezone
tehran_tz = timezone('Asia/Tehran')

dag = DAG(
    dag_id='example_dag',
    start_date=tehran_tz.localize(datetime(2025, 10, 1)),
    schedule='0 9 * * *',
    catchup=False,
)
```

### Step 4: Restart All Airflow Services

On **each node**, restart services:

```bash
# Schedulers (haproxy-1, scheduler-2)
sudo systemctl restart airflow-scheduler

# Webservers (haproxy-1, haproxy-2)
sudo systemctl restart airflow-webserver

# Workers (celery-1, celery-2)
sudo systemctl restart airflow-worker

# DAG Processors (nfs-1, nfs-2)
sudo systemctl restart airflow-dag-processor
```

### Step 5: Clear Browser Cache

After restarting services:
1. Clear your browser cache completely
2. Or use incognito/private browsing mode
3. Log back into Airflow UI

### Step 6: Database Timezone Consideration (Optional but Recommended)

PostgreSQL timezone should also be set. Run on **one** PostgreSQL node:

```bash
# Connect to database
export PGPASSWORD=airflow_pass
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db

# Inside psql:
SHOW timezone;
-- Should show: UTC (this is fine - Airflow expects UTC)

-- If you want to change it (NOT recommended for Airflow):
-- ALTER DATABASE airflow_db SET timezone = 'Asia/Tehran';

-- Exit
\q
```

**Important**: Keep PostgreSQL in UTC. Airflow is designed for this.

## Understanding What You'll See After Fix

After proper configuration:

### 1. Airflow UI
- **Run IDs**: Will show in Asia/Tehran time
- **Start Date/End Date**: Will show in Asia/Tehran time  
- **Example**: `2025-10-28T14:30:00+03:30`

### 2. Task Logs
- **Timestamps**: Will show Asia/Tehran time with `+0330`
- **Example**: `[2025-10-28, 14:30:00 +0330] {taskinstance.py:1234} INFO - Starting task`

### 3. Database (if you query directly)
- **All times stored in UTC**: This is correct!
- **Example**: `2025-10-28 11:00:00` (UTC) = `2025-10-28 14:30:00 +0330` (Tehran)

### 4. Schedule Times
When you set `schedule='0 9 * * *'`:
- **With timezone-aware start_date**: Runs at 9 AM Tehran time
- **Without timezone**: Runs at 9 AM UTC (12:30 PM Tehran)

## Verification Script

Create and run this verification script on a worker node:

```python
# File: /tmp/verify_timezone.py
import pendulum
from datetime import datetime
import pytz
import os

print("=" * 80)
print("TIMEZONE VERIFICATION")
print("=" * 80)

# System timezone
print(f"\n1. System TZ environment: {os.environ.get('TZ', 'Not set')}")

# Python timezone
from datetime import datetime
now = datetime.now()
print(f"2. Python datetime.now(): {now}")
print(f"   Timezone info: {now.tzinfo}")

# Pendulum
tehran = pendulum.now('Asia/Tehran')
print(f"\n3. Pendulum Asia/Tehran: {tehran}")
print(f"   UTC equivalent: {tehran.in_timezone('UTC')}")

# Pytz
tehran_tz = pytz.timezone('Asia/Tehran')
now_tehran = datetime.now(tehran_tz)
print(f"\n4. Pytz Asia/Tehran: {now_tehran}")

# Airflow config (if accessible)
try:
    from airflow.configuration import conf
    default_tz = conf.get('core', 'default_timezone')
    print(f"\n5. Airflow default_timezone: {default_tz}")
except Exception as e:
    print(f"\n5. Could not read Airflow config: {e}")

print("=" * 80)
```

Run it:
```bash
cd /tmp
python3 verify_timezone.py
```

**Expected output:**
```
================================================================================
TIMEZONE VERIFICATION
================================================================================

1. System TZ environment: Not set
2. Python datetime.now(): 2025-10-28 14:30:00.123456
   Timezone info: None

3. Pendulum Asia/Tehran: 2025-10-28T14:30:00.123456+03:30
   UTC equivalent: 2025-10-28T11:00:00.123456+00:00

4. Pytz Asia/Tehran: 2025-10-28 14:30:00.123456+03:30

5. Airflow default_timezone: Asia/Tehran
================================================================================
```

## Testing with a Sample DAG

Deploy this test DAG to verify timezone handling:

```python
# File: /home/rocky/airflow/dags/test_timezone.py
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum

local_tz = pendulum.timezone('Asia/Tehran')

def print_timezone_info(**context):
    """Print timezone information"""
    from datetime import datetime
    import pendulum
    
    print("=" * 80)
    print("TASK TIMEZONE INFO")
    print("=" * 80)
    
    # Execution date from context
    exec_date = context['execution_date']
    print(f"Execution Date: {exec_date}")
    print(f"Type: {type(exec_date)}")
    print(f"Timezone: {exec_date.tzinfo}")
    
    # Current time
    now_utc = pendulum.now('UTC')
    now_tehran = pendulum.now('Asia/Tehran')
    
    print(f"\nCurrent time UTC: {now_utc}")
    print(f"Current time Tehran: {now_tehran}")
    
    # Task start time
    task_start = context['ti'].start_date
    print(f"\nTask start time: {task_start}")
    
    print("=" * 80)

with DAG(
    dag_id='timezone_test',
    description='Test timezone handling',
    start_date=datetime(2025, 10, 28, 9, 0, tzinfo=local_tz),  # 9 AM Tehran
    schedule='0 9 * * *',  # Daily at 9 AM Tehran
    catchup=False,
    tags=['test', 'timezone'],
) as dag:
    
    test_task = PythonOperator(
        task_id='print_tz_info',
        python_callable=print_timezone_info,
    )
```

**What to verify:**
1. DAG appears in UI with start_date showing Tehran time
2. When triggered manually, execution_date shows Tehran time
3. Task logs show timestamps with `+0330`
4. Scheduled run happens at 9:00 AM Tehran time (not UTC)

## Common Issues and Solutions

### Issue 1: UI still shows UTC after config changes

**Solution:**
```bash
# Clear Airflow metadata cache
airflow db clean --clean-before-timestamp "2025-10-28" --yes

# Restart webserver with cache clear
sudo systemctl stop airflow-webserver
rm -rf /tmp/airflow*
sudo systemctl start airflow-webserver
```

### Issue 2: Some logs show UTC, some show Tehran

**Cause**: Mixed worker nodes with different configurations

**Solution**: 
```bash
# Verify timezone on ALL workers
for host in celery-1 celery-2; do
    echo "=== $host ==="
    ssh rocky@$host 'timedatectl | grep "Time zone"'
done

# If inconsistent, fix each one:
ssh rocky@celery-1 'sudo timedatectl set-timezone Asia/Tehran'
ssh rocky@celery-2 'sudo timedatectl set-timezone Asia/Tehran'
```

### Issue 3: Scheduled tasks run at wrong time

**Problem**: DAG start_date is not timezone-aware

**Solution**: Always use timezone-aware datetimes:
```python
# ❌ WRONG - naive datetime
start_date=datetime(2025, 10, 28, 9, 0)

# ✅ CORRECT - timezone-aware
start_date=datetime(2025, 10, 28, 9, 0, tzinfo=pendulum.timezone('Asia/Tehran'))
```

### Issue 4: HAProxy nodes show different times

**Cause**: NTP not synchronized

**Solution**:
```bash
# Check NTP status on all nodes
for ip in 10.101.20.202 10.101.20.146; do
    echo "=== Node $ip ==="
    ssh rocky@$ip 'timedatectl status | grep -E "(Local time|NTP)"'
done

# Enable NTP sync if needed
sudo timedatectl set-ntp true

# Force sync
sudo systemctl restart chronyd
```

## Deployment Checklist

Use this checklist to ensure everything is configured:

```
□ System timezone set to Asia/Tehran on ALL nodes
□ Verified with 'timedatectl' on each node
□ airflow.cfg updated with default_timezone = Asia/Tehran
□ airflow.cfg updated with default_ui_timezone = Asia/Tehran  
□ All Airflow services restarted on all nodes
□ Browser cache cleared
□ Test DAG deployed with timezone-aware start_date
□ Test DAG runs at expected local time
□ Task logs show +0330 timezone offset
□ UI displays times in Tehran timezone
□ NTP synchronized across all nodes
```

## Advanced: Logging Configuration

For even better timezone handling in logs, update your log format:

Edit `/home/rocky/airflow/airflow.cfg`:

```ini
[logging]
# ... other settings ...

# Custom log format with timezone
log_format = [%%(asctime)s] {%%(filename)s:%%(lineno)d} %%(levelname)s - %%(message)s
log_format_with_timezone = [%%(asctime)s %Z] {%%(filename)s:%%(lineno)d} %%(levelname)s - %%(message)s

# Ensure logs use local timezone
logging_config_class = airflow.config_templates.airflow_local_settings.DEFAULT_LOGGING_CONFIG
```

## Monitoring Timezone Consistency

Add this to your health monitor DAG to check timezone consistency:

```python
@task(task_id="check_timezone_consistency")
def check_timezone_consistency():
    """Verify all nodes have consistent timezone configuration"""
    from datetime import datetime
    import subprocess
    
    nodes = {
        'haproxy-1': '10.101.20.202',
        'haproxy-2': '10.101.20.146',
        'scheduler-2': '10.101.20.132',
        'celery-1': '10.101.20.199',
        'celery-2': '10.101.20.200',
    }
    
    results = {}
    for hostname, ip in nodes.items():
        cmd = f"ssh rocky@{ip} 'timedatectl | grep \"Time zone\"'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        results[hostname] = result.stdout.strip()
        print(f"{hostname}: {result.stdout.strip()}")
    
    # Check if all are Asia/Tehran
    expected = "Time zone: Asia/Tehran"
    mismatched = [h for h, tz in results.items() if expected not in tz]
    
    if mismatched:
        raise AirflowException(
            f"Timezone mismatch detected on: {', '.join(mismatched)}"
        )
    
    print("✅ All nodes have consistent timezone (Asia/Tehran)")
    return {'status': 'consistent', 'timezone': 'Asia/Tehran'}
```

## Final Notes

1. **PostgreSQL stays in UTC**: This is by design. Airflow converts to/from UTC automatically.

2. **Consistency is key**: All Airflow nodes MUST have the same timezone configuration.

3. **Always use timezone-aware datetimes in DAGs**: This prevents ambiguity.

4. **Log timestamps**: Will always show the timezone of the worker that executed the task.

5. **UI display**: Controlled by `default_ui_timezone` in airflow.cfg.

After following this guide, you should see consistent timezone handling across your entire Airflow HA cluster!
