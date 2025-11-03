# Airflow Logs: Complete Understanding & Analysis Guide

## Table of Contents
1. [Understanding Airflow Architecture & Logs](#understanding-airflow-architecture--logs)
2. [Types of Airflow Logs](#types-of-airflow-logs)
3. [Log Locations & Structure](#log-locations--structure)
4. [Analyzing Your Health Monitor Logs](#analyzing-your-health-monitor-logs)
5. [Common Patterns & What They Mean](#common-patterns--what-they-mean)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Best Practices](#best-practices)

---

## Understanding Airflow Architecture & Logs

### Core Components in Your HA Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIRFLOW HA ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  Webserver   │────▶│  Scheduler   │────▶│   Workers    │   │
│  │  (UI/API)    │     │ (Orchestrate)│     │ (Execute)    │   │
│  │              │     │              │     │              │   │
│  │ haproxy-1    │     │ haproxy-1    │     │ celery-1     │   │
│  │ haproxy-2    │     │ scheduler-2  │     │ celery-2     │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                     │                     │          │
│         │                     ▼                     │          │
│         │              ┌──────────────┐            │          │
│         └─────────────▶│  PostgreSQL  │◀───────────┘          │
│                        │   (Metadata) │                       │
│                        │              │                       │
│                        │ VIP: 10.101.20.210                  │
│                        └──────────────┘                       │
│                               │                               │
│                               │                               │
│                        ┌──────────────┐                       │
│                        │   RabbitMQ   │                       │
│                        │   (Queue)    │                       │
│                        │              │                       │
│                        │ rabbit-1,2,3 │                       │
│                        └──────────────┘                       │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              DAG Processor (NFS HA)                   │    │
│  │  nfs-1 (Active) / nfs-2 (Passive)                    │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### What Each Component Does

1. **Webserver**: Provides the UI you see in your browser
   - Shows DAG status, task logs, etc.
   - Multiple instances for HA (haproxy-1, haproxy-2)

2. **Scheduler**: The brain of Airflow
   - Reads DAG files
   - Determines which tasks to run and when
   - Sends tasks to the executor (Celery in your case)
   - Multiple instances for HA (haproxy-1, scheduler-2)

3. **Workers** (Celery Workers): Execute the actual tasks
   - Receive task commands from RabbitMQ
   - Run your Python code
   - Report results back to metadata DB

4. **Metadata Database** (PostgreSQL): Stores everything
   - DAG runs, task states, connections, variables
   - Used by all components

5. **Message Queue** (RabbitMQ): Task distribution
   - Scheduler sends tasks here
   - Workers pick them up

6. **DAG Processor** (on NFS): Parses DAG files
   - One active, one passive for HA

---

## Types of Airflow Logs

### 1. Task Logs
**Location**: `/home/rocky/airflow/logs/dag_id=<DAG_NAME>/run_id=<RUN_ID>/task_id=<TASK_ID>/attempt=<N>.log`

**What they contain**: 
- Output from your task Python code (print statements)
- Task execution start/end times
- Success/failure status
- Error stack traces

**Example**:
```
[2025-11-01 15:13:00] {taskinstance.py:1234} INFO - Running task...
✅ haproxy-1 - airflow-scheduler is ACTIVE
[2025-11-01 15:13:02] {taskinstance.py:1456} INFO - Task completed successfully
```

### 2. Scheduler Logs
**Location**: Viewed via `journalctl -u airflow-scheduler`

**What they contain**:
- Task scheduling decisions
- DAG parsing events
- Heartbeat information
- Task state changes

**Example from your logs**:
```
2025-11-01T15:13:41 scheduler-2 airflow-scheduler[2978490]: 
    <TaskInstance: ha_service_health_monitor_enhanced_v3.check_celery_2_airflow_worker 
    scheduled__2025-11-01T11:40:00+00:00 [scheduled]>
```

### 3. Worker Logs
**Location**: Viewed via `journalctl -u airflow-worker`

**What they contain**:
- Tasks received from queue
- Task execution commands
- Celery worker health

**Example from your logs**:
```
2025-11-01T15:13:00 celery-2 airflow-worker[1815742]: 
    [2025-11-01 15:13:00,149: INFO/MainProcess] 
    Task airflow.providers.celery.executors.celery_executor_utils.execute_command
    [ee7350f3-2cc7-4d4b-89e7-b8e641bd72b6] received
```

### 4. Webserver Logs
**Location**: Viewed via `journalctl -u airflow-webserver`

**What they contain**:
- HTTP requests to the UI/API
- User actions
- Authentication events

### 5. Service Logs (systemd journals)
**Location**: Viewed via `journalctl -u <service-name>`

**What they contain**:
- Service start/stop events
- System-level errors
- Service health status

---

## Log Locations & Structure

### Your System's Log Structure

```
/home/rocky/airflow/logs/
│
├── dag_id=ha_service_health_monitor_enhanced_v3/
│   ├── run_id=scheduled__2025-11-01T11:40:00+00:00/
│   │   ├── task_id=check_haproxy_1_airflow_scheduler/
│   │   │   └── attempt=1.log          ← Individual task log
│   │   ├── task_id=check_celery_1_airflow_worker/
│   │   │   └── attempt=1.log
│   │   ├── task_id=health_summary/
│   │   │   └── attempt=1.log
│   │   └── ...
│   │
│   ├── run_id=scheduled__2025-11-01T11:42:00+00:00/
│   │   └── ...
│   └── ...
│
├── dag_id=another_dag/
│   └── ...
│
└── dag_processor_manager/
    └── dag_processor_manager.log
```

### Understanding Log Filenames

**Format**: `dag_id=<NAME>/run_id=<RUN_ID>/task_id=<TASK>/attempt=<N>.log`

- `dag_id`: Your DAG name
- `run_id`: Unique identifier for this DAG run
  - `scheduled__YYYY-MM-DDTHH:MM:SS` for scheduled runs
  - `manual__YYYY-MM-DDTHH:MM:SS` for manually triggered runs
- `task_id`: The specific task within the DAG
- `attempt`: Retry number (starts at 1)

---

## Analyzing Your Health Monitor Logs

### Understanding Your stop_logs.txt Output

Let's break down what you're seeing:

#### 1. Log Entry Structure

```
2025-11-01T15:13:00+0330 celery-2 airflow-worker[1815742]: [2025-11-01 15:13:00,149: INFO/MainProcess] Task ... received
│                        │              │                 │                                           │
│                        │              │                 │                                           └─ Message
│                        │              │                 └─ Log level and process
│                        │              └─ Process ID (PID)
│                        └─ Service name
└─ Timestamp with timezone
```

#### 2. The [Invalid date] Issue (NOW FIXED)

**What was happening**:
```
2025-11-01T15:13:41+0330 scheduler-2 airflow-scheduler-ha2[Invalid date] {scheduler_job_runner.py:487} INFO - ...
                                                             ^^^^^^^^^^^^^^
```

This occurred because:
- The `short-iso` journalctl format sometimes fails to parse certain log entries
- Particularly when log entries have non-standard formats

**How it's fixed in v3**:
- Changed to `short-precise` format with explicit output fields
- Added deduplication logic to remove duplicate entries

#### 3. Duplicate Entries (NOW FIXED)

**What was happening**:
Lines 7-10 were identical to lines 11-14 in your log output.

**Why it happened**:
Your DAG was collecting logs from multiple sources without deduplication:
- Scheduler logs from haproxy-1
- Scheduler logs from scheduler-2
- Worker logs from both celery-1 and celery-2
- All showing the same task from different perspectives

**How it's fixed in v3**:
Added `deduplicate_log_lines()` function that:
- Tracks unique log lines using a set
- Preserves the first occurrence of each line
- Maintains chronological order

### What Good Logs Look Like

#### Successful Health Check Run:
```
✅ haproxy-1 - airflow-scheduler is ACTIVE
✅ haproxy-1 - airflow-webserver is ACTIVE
✅ celery-1 - airflow-worker is ACTIVE
✅ PostgreSQL VIP (10.101.20.210:5000) is ACCESSIBLE
✅ RabbitMQ Cluster: 3/3 nodes healthy
✅ 2 Active Scheduler(s):
   - haproxy-1 (heartbeat: 2025-11-01 15:13:40)
   - scheduler-2 (heartbeat: 2025-11-01 15:13:41)
✅ 2 Celery Worker(s) Active

🏥  HEALTH CHECK SUMMARY
════════════════════════════════════════════════════════════════════════
✅ Successful: 35
❌ Total Failed: 1
   ├─ Critical Failures: 0
   └─ Expected Passive Failures: 1

⏸️  EXPECTED PASSIVE NODE FAILURES (inactive as expected):
   - check_nfs_2_airflow_dag_processor

✅ All critical services are healthy - DAG SUCCESS
```

#### Failed Service Detection:
```
❌ celery-2 - airflow-worker is NOT ACTIVE

================================================================================
📋 Recent logs from celery-2:
================================================================================
Nov 01 15:28:15 systemd[1]: airflow-worker.service: Main process exited
Nov 01 15:28:15 systemd[1]: airflow-worker.service: Failed with result 'exit-code'
Nov 01 15:28:15 systemd[1]: Failed to start Airflow Worker

🚨 DAG FAILED: 1 critical service(s) are down!
Failed services: check_celery_2_airflow_worker
```

---

## Common Patterns & What They Mean

### 1. Task Received & Executed
```
[INFO/MainProcess] Task ... received
[INFO/ForkPoolWorker-4] Executing command in Celery: ['airflow', 'tasks', 'run', ...]
[INFO/ForkPoolWorker-4] Filling up the DagBag from /home/rocky/airflow/dags/...
[INFO/ForkPoolWorker-4] Running <TaskInstance: ... [queued]> on host celery-2
```

**Meaning**: A task was successfully picked up by a worker and is executing.

**What's happening**:
1. Worker receives task from RabbitMQ queue
2. Worker spawns a subprocess to execute it
3. Worker loads the DAG definition
4. Task starts running

### 2. Task Queued but Not Executing
```
<TaskInstance: ... [scheduled]>
INFO - Not executing ... since the number of tasks running or queued from DAG ... 
is >= to the DAG's max_active_tasks limit of 16
```

**Meaning**: Task is ready but waiting due to concurrency limits.

**What's happening**:
- Your DAG has `max_active_tasks=16` limit
- Too many tasks from this DAG are already running
- Task will execute when slots free up

**Action**: This is normal; Airflow is managing concurrency.

### 3. External Executor ID Assignment
```
INFO - Setting external_id for <TaskInstance: ... [queued]> to e540e8ef-e776-40e7-8ef5-da4b14093ae4
```

**Meaning**: Scheduler assigned a Celery task ID.

**What's happening**:
- Scheduler sends task to Celery/RabbitMQ
- Task gets a UUID for tracking
- Workers use this ID to identify the task

### 4. Task Completed
```
Task airflow.providers.celery.executors.celery_executor_utils.execute_command[...] 
succeeded in 1.385s: None
```

**Meaning**: Task finished successfully in 1.385 seconds.

### 5. Service Inactive Detection
```
❌ celery-2 - airflow-worker is NOT ACTIVE

📋 Recent logs from celery-2:
Nov 01 15:14:30 systemd[1]: Stopping Airflow Worker...
Nov 01 15:14:31 systemd[1]: airflow-worker.service: Succeeded.
```

**Meaning**: The service was intentionally stopped.

**Action**: Investigate why it stopped (manual stop, crash, or restart).

---

## Troubleshooting Guide

### Problem 1: Service Shows as Failed

**What you'll see**:
```
❌ haproxy-1 - airflow-scheduler is NOT ACTIVE
```

**Steps to diagnose**:

1. **Check the collected logs in the task output**:
   - Look for error messages
   - Look for "Failed to start" or "exit-code"

2. **Common causes**:
   - Service crashed: Look for Python exceptions or segmentation faults
   - Configuration error: Look for "Config" or "Invalid" in logs
   - Resource exhaustion: Look for "Out of memory" or "No space"
   - Dependency failure: Look for connection errors to DB/RabbitMQ

3. **SSH to the node and check**:
   ```bash
   ssh rocky@10.101.20.202
   sudo systemctl status airflow-scheduler
   sudo journalctl -u airflow-scheduler -n 100
   ```

### Problem 2: No Active Schedulers

**What you'll see**:
```
❌ NO ACTIVE SCHEDULERS FOUND

📋 Scheduler logs from haproxy-1:
...
📋 Scheduler logs from scheduler-2:
...
```

**Common causes**:
- Both schedulers crashed
- Database connection issue
- Lock file problems
- DAG parsing errors

**Steps**:
1. Check if schedulers are running: `sudo systemctl status airflow-scheduler`
2. Check database connectivity: Try connecting to PostgreSQL VIP
3. Look for errors in the collected logs

### Problem 3: RabbitMQ Quorum Lost

**What you'll see**:
```
❌ RabbitMQ QUORUM LOST: Only 1/3 nodes healthy
```

**Meaning**: Your RabbitMQ cluster doesn't have enough healthy nodes.

**Impact**: 
- Tasks cannot be queued
- Workers cannot receive new tasks
- DAG execution will stall

**Steps**:
1. Check individual node logs in the task output
2. Common issues:
   - Network partitions
   - Erlang cookie mismatch
   - Resource exhaustion
   - Port 5672 connectivity

### Problem 4: No Celery Workers

**What you'll see**:
```
❌ NO CELERY WORKERS AVAILABLE
```

**Impact**: No tasks can execute.

**Steps**:
1. Check worker service status on celery-1 and celery-2
2. Verify RabbitMQ connectivity (workers need this)
3. Check worker logs for connection errors

### Problem 5: High Resource Usage

**What you'll see** (in new v3 monitoring):
```
⚠️  RESOURCE WARNINGS:
   ⚠️  celery-1: HIGH CPU usage (95.40%)
   ⚠️  haproxy-1: HIGH MEMORY usage (92.15%)
```

**Steps**:
1. Check top processes in the resource report
2. Identify which process is consuming resources
3. Common culprits:
   - Runaway DAG task
   - Memory leak in custom code
   - Too many concurrent tasks
   - Large log files

**Immediate actions**:
- Reduce `max_active_tasks` or `max_active_runs` in DAG
- Kill problematic processes
- Add more resources or nodes

### Problem 6: Large Log Directories

**What you'll see** (in new v3 monitoring):
```
⚠️  celery-1: Large logs directory (7.52 GB) - consider cleanup
```

**Impact**: 
- Disk space exhaustion
- Slow log access
- Increased backup time

**Action**:
```bash
# Check log retention settings in airflow.cfg
[logging]
base_log_folder = /home/rocky/airflow/logs
log_retention_days = 30  # Adjust this

# Manual cleanup (be careful!)
airflow db clean --clean-before-timestamp "2025-10-01" --dry-run
airflow db clean --clean-before-timestamp "2025-10-01" --yes
```

---

## Best Practices

### 1. Regular Monitoring

**Use your new DAG**:
- It runs every 2 minutes
- Check failures immediately
- Review system resources weekly

**Set up alerts**:
```python
# In your DAG default_args
'email_on_failure': True,
'email': ['your-team@example.com'],
'sla': timedelta(minutes=5),  # Alert if task takes >5min
```

### 2. Log Retention

**Configure in `airflow.cfg`**:
```ini
[logging]
base_log_folder = /home/rocky/airflow/logs
log_retention_days = 30
```

**Automated cleanup**:
```bash
# Add to cron (daily at 2am)
0 2 * * * /path/to/venv/bin/airflow db clean --clean-before-timestamp $(date -d '30 days ago' +\%Y-\%m-\%d) --yes
```

### 3. Reading Task Logs in UI

**In Airflow UI**:
1. Go to DAGs → Click your DAG
2. Click on a DAG run (execution date)
3. Click on a task (colored square)
4. Click "Log" button

**What to look for**:
- ✅ Green = Success → Look for your expected output
- 🔴 Red = Failed → Look for error stack trace
- 🔵 Blue = Running → Check progress
- ⚪ White = Queued → Waiting to run

### 4. Understanding Task Dependencies

**Your DAG structure**:
```
detect_nfs_active_node
    ↓
nfs_service_checks ───┐
                       ├→ health_summary → final_status_check
service_checks ────────┤
pg/rabbitmq/etc ───────┘
system_resources ──────┤
logs_size ─────────────┘
```

**If a task fails**:
- Tasks downstream (to the right) won't run
- Parallel tasks continue
- `health_summary` uses `trigger_rule="all_done"` so it always runs

### 5. XCom for Communication

**Your DAG uses XCom to pass data**:
```python
# Task A stores data
ti.xcom_push(key='failure_type', value='CRITICAL_NFS_FAILURE')

# Task B retrieves it
failure_type = ti.xcom_pull(task_ids='task_a', key='failure_type')
```

**View XComs in UI**:
1. Task Instance Details → XCom tab
2. See what data tasks shared

### 6. Interpreting Your Health Summary

```
🏥  HEALTH CHECK SUMMARY
════════════════════════════════════════════════════════════════════════
✅ Successful: 35
❌ Total Failed: 1
   ├─ Critical Failures: 0        ← THIS IS WHAT MATTERS
   └─ Expected Passive Failures: 1
```

**Key metric**: Critical Failures

- **0 critical failures** = System is healthy ✅
- **1+ critical failures** = Action needed 🚨

**Expected failures**: 
- Always 1: `check_nfs_2_airflow_dag_processor` (passive node)
- This is normal and expected!

### 7. Using the New Resource Monitoring

**CPU/RAM/Disk Report**:
```
📊 SYSTEM RESOURCES MONITORING REPORT
════════════════════════════════════════════════════════════════════════

🖥️  HAPROXY-1
────────────────────────────────────────────────────────────────────────
  💻 CPU:
     Usage: 45.20% | Available: 54.80%
     Top 5 CPU-consuming processes:
        1. /usr/bin/python3 /usr/bin/airflow scheduler    CPU:  15.2%  MEM:   4.5%
        2. postgres: airflow_db ...                        CPU:   8.7%  MEM:   2.1%
        ...
```

**What to monitor**:
- CPU >80% sustained = Add capacity
- RAM >90% = Risk of OOM kills
- Disk >85% = Clean up logs

**Top processes**:
- See what's consuming resources
- Correlate with task execution times
- Identify optimization opportunities

### 8. Understanding the Logs Size Report

```
📁 AIRFLOW LOGS DIRECTORY SIZE REPORT
════════════════════════════════════════════════════════════════════════

📂 haproxy-1            │ Path: /home/rocky/airflow/logs          │ Size:   1.2GB (1240.50 MB)
📂 celery-1             │ Path: /home/rocky/airflow/logs          │ Size:   2.8GB (2876.23 MB)
...

📊 TOTAL LOGS SIZE ACROSS ALL NODES: 8432.45 MB (8.24 GB)
```

**What to do**:
- If >5GB per node: Consider cleanup
- If growing fast: Check log verbosity settings
- Monitor weekly trend

---

## Cheat Sheet: Quick Log Analysis

### When a Task Fails:

1. **Look at the task log in UI** (primary source)
   - Click DAG → Run → Task → Log
   - Read the error message and stack trace

2. **Check service logs** (if service check task)
   - Your DAG automatically includes these
   - Look for the "📋 Recent logs from..." sections

3. **Check system resources** (if performance issue)
   - Look at the resource monitoring report
   - Check if node has high CPU/RAM/disk

4. **Verify dependencies** (if connection issue)
   - PostgreSQL VIP accessible?
   - RabbitMQ cluster healthy?
   - Network connectivity?

### Common Error Patterns:

| Error Message | Meaning | Action |
|--------------|---------|---------|
| `Connection refused` | Service not listening | Check service status |
| `Timeout` | Service slow or unreachable | Check network/resources |
| `Authentication failed` | Wrong credentials | Check credentials |
| `No space left on device` | Disk full | Clean up logs/data |
| `Cannot allocate memory` | RAM exhausted | Add RAM or reduce load |
| `ModuleNotFoundError` | Missing Python package | Install package |
| `Permission denied` | File/directory permissions | Check ownership/permissions |

### Quick Commands:

```bash
# Check service status
sudo systemctl status airflow-scheduler
sudo systemctl status airflow-worker

# View recent logs
sudo journalctl -u airflow-scheduler -n 100 --no-pager
sudo journalctl -u airflow-worker -f  # Follow mode

# Check Airflow processes
ps aux | grep airflow

# Check resources
top
htop
df -h
free -h

# Check connectivity
ping 10.101.20.210  # PostgreSQL VIP
telnet 10.101.20.205 5672  # RabbitMQ
psql -h 10.101.20.210 -p 5000 -U airflow_user -d airflow_db

# Clean old logs
cd /home/rocky/airflow/logs
find . -type f -mtime +30 -name "*.log" -delete
```

---

## Summary

### Key Takeaways:

1. **Airflow logs are multi-layered**:
   - Task logs (what your code prints)
   - Service logs (systemd journals)
   - System logs (resource usage)

2. **Your monitoring DAG automatically collects**:
   - Service status
   - Recent error logs
   - System resources (NEW in v3)
   - Log directory sizes (NEW in v3)

3. **Critical vs. Expected failures**:
   - Critical failures = Action required
   - Expected failures = Normal for passive nodes

4. **The v3 improvements fix**:
   - ✅ Duplicate log entries (deduplication)
   - ✅ [Invalid date] artifacts (better format)
   - ✅ Added comprehensive resource monitoring
   - ✅ Added logs size tracking

5. **Regular monitoring routine**:
   - Let DAG run every 2 minutes
   - Check critical failure count
   - Review resource usage weekly
   - Clean logs monthly

### Next Steps:

1. Deploy the new v3 DAG
2. Watch a few runs to understand the output
3. Set up email alerts for failures
4. Create a dashboard to track trends
5. Establish log retention and cleanup policies

---

## Need Help?

If you see something in your logs you don't understand:

1. **Copy the relevant log section**
2. **Note the task that failed**
3. **Check the service logs included in the task output**
4. **Look at the resource monitoring report**
5. **Check this guide for similar patterns**

Remember: Logs tell a story. Read them chronologically, understand what each component was trying to do, and the cause of issues will become clear!
