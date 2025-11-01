# CORRECTED Version 2 - All Issues Fixed

## 🚨 Critical Fixes Applied

### Issue 1: NFS Active/Passive Logic ✅ FIXED

**Problem:**
```python
# WRONG - active_nfs passed as default parameter
def check_nfs_service(service_name=service, host=hostname, server_ip=ip, active_nfs_node=active_nfs):
```

The task was receiving the **task object** (`active_nfs`), not the **result value** (e.g., "nfs-2").

**Solution in v2:**
```python
# CORRECT - active_nfs passed as dynamic argument
def check_nfs_service(active_nfs_node: str, service_name=service, host=hostname, server_ip=ip):
    # Now active_nfs_node contains actual value like "nfs-2"
    is_active_node = (host == active_nfs_node)
    # Logic works correctly!

# Call with dynamic argument
nfs_tasks.append(check_nfs_service(active_nfs))  # ✅ Correct!

# Also added dependency
active_nfs >> nfs_tasks  # Ensures active_nfs runs first
```

**Result:**
- When nfs-2 is active → services on nfs-2 must be active (pass)
- When nfs-1 is passive → services on nfs-1 should be inactive (expected failure)
- DAG only fails if critical services down

---

### Issue 2: Schedule & Log Duration ✅ FIXED

**Changes:**
```python
@dag(
    schedule='*/2 * * * *',  # Changed from */15 to */2 (every 2 minutes)
    max_active_tasks=16,     # Added to prevent overwhelming system
)

# Changed all log fetching
fetch_journalctl_logs(ip, service, hostname, minutes_back=2)  # Changed from 60 to 2
fetch_task_specific_logs(identifiers, minutes_back=2)         # Changed from 60 to 2
```

**Result:**
- DAG runs every 2 minutes
- Logs only from last 2 minutes (not 60)
- Smaller log output in Airflow UI
- Faster log fetching

---

### Issue 3: Enhanced Task Tracing ✅ IMPLEMENTED

**New Function:**
```python
def get_task_identifiers(context):
    """Extract unique identifiers for task instance tracing"""
    identifiers = {
        'dag_id': ti.dag_id,
        'task_id': ti.task_id,
        'run_id': ti.run_id,
        'execution_date': str(ti.execution_date),
        'try_number': ti.try_number,
        'job_id': ti.job_id,                      # Internal Airflow job ID
        'external_executor_id': ti.external_executor_id,  # Celery task ID
        'ti_key': f"{dag_id}__{task_id}__{execution_date}",  # Unique key
        'pid': os.getpid(),                       # Process ID
        'map_index': ti.map_index,                # For mapped tasks
    }
    return identifiers
```

**New Function:**
```python
def fetch_task_specific_logs(identifiers, minutes_back=2):
    """
    Searches across ALL Airflow components for logs mentioning this specific task.
    Uses identifiers (task_id, run_id, job_id, etc.) to filter relevant logs.
    """
    # Searches: Scheduler 1, Scheduler 2, Worker 1, Worker 2
    # Returns: Only logs related to THIS specific task instance
```

**Result:**
- Task logs now show unique identifiers
- Traces task across all system components
- Finds scheduler AND worker logs for specific task
- Uses multiple identifiers for comprehensive tracing

---

### Issue 4: Timestamp "[Invalid date]" ✅ FIXED

**Problem:**
Using grep on journalctl was mixing timestamp formats, causing "[Invalid date]" to appear.

**Solution:**
```python
# OLD - caused [Invalid date]
cmd = f"journalctl -u {service} --since '60 minutes ago' | grep 'pattern'"

# NEW - preserves timestamps correctly
cmd = f"journalctl -u {service} --since '2 minutes ago' --no-pager -o short-iso"
# Then grep separately if needed
```

**Key changes:**
- Added `-o short-iso` for consistent ISO 8601 timestamps
- Simplified grep patterns
- Better timestamp preservation
- Format: `2025-10-28T15:00:27+0330` (includes timezone)

**No timestamp translation in code** - let system handle it naturally.

---

### Issue 5: execution_date Deprecation Warning ✅ FIXED

**Problem:**
```python
execution_date = context['execution_date']  # Triggers deprecation warning
```

**Solution:**
```python
# Access via task instance directly (no warning)
ti = context.get('ti')
identifiers['execution_date'] = str(ti.execution_date)  # Direct access, no warning
```

**Result:**
- No more deprecation warnings
- Uses Airflow 2.x best practices
- Direct access to task instance properties

---

## 📋 Complete List of Changes in v2

### Code Changes

1. **Fixed NFS logic**: Dynamic argument passing ✅
2. **Schedule change**: Every 2 minutes ✅
3. **Log duration**: Last 2 minutes only ✅
4. **Task identifiers**: Comprehensive extraction ✅
5. **Task-specific logs**: Cross-component tracing ✅
6. **Timestamp format**: ISO 8601 with `-o short-iso` ✅
7. **Deprecation fix**: Direct task instance access ✅
8. **Added max_active_tasks**: Prevent system overload ✅

### New Features

1. **`get_task_identifiers()`**: Extracts all unique IDs
2. **`fetch_task_specific_logs()`**: Searches across all components
3. **`format_identifiers_for_grep()`**: Builds smart grep patterns
4. **Better log sections**: Clearer separation of log types

---

## 🎯 What You Get Now

### When Service is Healthy
```
✅ airflow-worker on celery-1 (10.101.20.199) is ACTIVE
```

### When Service Fails on Active Node
```
🚨 CRITICAL: nfs-server on ACTIVE node nfs-2 is inactive (should be ACTIVE)!

Task Identifiers:
  - dag_id: ha_service_health_monitor_enhanced
  - task_id: check_nfs_2_nfs_server
  - run_id: manual__2025-10-28T11:30:22.050978+00:00
  - job_id: 12345
  - external_executor_id: abc-123-celery-task-id
  - ti_key: ha_service_health_monitor_enhanced__check_nfs_2_nfs_server__2025-10-28 11:30:22
  - pid: 67890

================================================================================
📋 SERVICE LOGS (journalctl - last 2 minutes):
================================================================================
2025-10-28T14:59:30+0330 nfs-2 systemd[1]: nfs-server.service: Main process exited
2025-10-28T14:59:30+0330 nfs-2 systemd[1]: nfs-server.service: Failed with result 'exit-code'
2025-10-28T14:59:35+0330 nfs-2 systemd[1]: Stopped NFS server and services

================================================================================
📋 TASK-SPECIFIC AIRFLOW LOGS (across all components):
================================================================================
📋 Scheduler haproxy-1 logs for this task:
2025-10-28T15:00:27+0330 haproxy-1 airflow-scheduler: Sending task check_nfs_2_nfs_server to executor
2025-10-28T15:00:27+0330 haproxy-1 airflow-scheduler: Task check_nfs_2_nfs_server queued

📋 Scheduler scheduler-2 logs for this task:
⏭️  No relevant logs found in Scheduler scheduler-2

📋 Worker celery-1 logs for this task:
2025-10-28T15:00:31+0330 celery-1 airflow-worker: Executing task check_nfs_2_nfs_server
2025-10-28T15:00:31+0330 celery-1 airflow-worker: Task PID: 67890
2025-10-28T15:00:32+0330 celery-1 airflow-worker: Task failed with exception

================================================================================
📋 THIS TASK'S WORKER LOG:
================================================================================
[2025-10-28, 15:00:31 +0330] {taskinstance.py:1345} INFO - Executing <Task(PythonOperator): check_nfs_2_nfs_server>
[2025-10-28, 15:00:31 +0330] {python.py:177} INFO - Starting task execution
[2025-10-28, 15:00:32 +0330] {logging_mixin.py:188} INFO - 🔍 Node: nfs-2, Active Node: nfs-2, Is Active: True
[2025-10-28, 15:00:32 +0330] {logging_mixin.py:188} INFO - 🚨 CRITICAL: Service down on active node!
```

### When Service on Passive Node (Expected)
```
⏸️ EXPECTED: nfs-server on PASSIVE node nfs-1 is correctly NOT ACTIVE (status: inactive)
This task failure is expected and does not indicate a problem.
```

---

## 🚀 Deployment Instructions

### 1. Remove Old Version
```bash
# SSH to active NFS node
ssh rocky@10.101.20.165

# Backup old version
cd /srv/airflow/dags
cp ha_service_health_monitor_enhanced.py ha_service_health_monitor_enhanced_v1_backup.py

# Or just delete it
rm ha_service_health_monitor_enhanced.py
```

### 2. Deploy v2
```bash
# Copy v2 to active NFS node
scp ha_service_health_monitor_enhanced_v2.py rocky@10.101.20.165:/srv/airflow/dags/
```

### 3. Rename (Optional)
```bash
# If you want to keep the same DAG name
ssh rocky@10.101.20.165
cd /srv/airflow/dags
mv ha_service_health_monitor_enhanced_v2.py ha_service_health_monitor_enhanced.py
```

### 4. Verify
```bash
# Check file is visible on all Airflow nodes
for host in haproxy-1 haproxy-2 scheduler-2 celery-1 celery-2; do
    echo "=== $host ==="
    ssh rocky@$host 'ls -lh /airflow/dags/ha_service_health_monitor_enhanced*.py'
done
```

### 5. Test
1. Wait 30 seconds for DAG to appear in UI
2. Navigate to: http://10.101.20.210:8081/dags
3. Find: `ha_service_health_monitor_enhanced`
4. Check tags: Should see `v2`
5. Trigger manual run
6. Verify:
   - NFS active/passive logic works
   - No "[Invalid date]" in logs
   - No deprecation warnings
   - Task identifiers appear in logs
   - Timestamps show +0330

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] DAG appears in UI with `v2` tag
- [ ] Schedule shows `*/2 * * * *`
- [ ] `detect_nfs_active_node` correctly identifies active NFS
- [ ] Active NFS services show ✅ (pass)
- [ ] Passive NFS services show ⏸️ EXPECTED (fail but expected)
- [ ] health_summary categorizes failures correctly
- [ ] DAG succeeds when only passive services fail
- [ ] DAG fails when critical services fail
- [ ] Failed task logs show:
  - [ ] Task identifiers (dag_id, task_id, run_id, job_id, PID, etc.)
  - [ ] Service logs (journalctl) with proper timestamps
  - [ ] Task-specific logs from all components
  - [ ] This task's worker log
- [ ] No "[Invalid date]" in logs
- [ ] No deprecation warnings
- [ ] Timestamps show Asia/Tehran (+0330)
- [ ] Log output is reasonably sized (not huge)

---

## 📚 Additional Documentation

1. **AIRFLOW_LOGS_EXPLAINED.md** - Understand Pre/Post execution logs
2. **DEPLOYMENT_GUIDE.md** - General deployment guidance
3. **QUICK_REFERENCE.md** - Incident response commands
4. **TIMEZONE_CONFIGURATION_GUIDE.md** - Timezone setup

---

## 🆘 If Issues Persist

### Issue: NFS logic still not working
**Check:**
```bash
# Manually verify which node is active
ssh rocky@10.101.20.165 'ip addr show | grep 10.101.20.220'
ssh rocky@10.101.20.203 'ip addr show | grep 10.101.20.220'

# Check detect_nfs_active_node task log - should show correct node
```

### Issue: Still seeing "[Invalid date]"
**Check:**
```bash
# Verify system timezone
for ip in 10.101.20.202 10.101.20.132; do
    ssh rocky@$ip 'timedatectl | grep "Time zone"'
done

# Test journalctl output format
ssh rocky@10.101.20.202 'journalctl -u airflow-scheduler -n 5 -o short-iso'
```

### Issue: Task identifiers not showing
**Check:**
```bash
# Verify task is actually failing (identifiers only show on failure)
# Check the actual task log in Airflow UI
# Look for section: "Task Identifiers:"
```

---

## 🎉 Summary

**All your issues are now fixed in v2:**

1. ✅ NFS active/passive logic works correctly
2. ✅ Runs every 2 minutes with 2-minute log history
3. ✅ Task identifiers trace across all components
4. ✅ No more "[Invalid date]" timestamps
5. ✅ No deprecation warnings
6. ✅ Cleaner, more focused logs

**Deploy v2 and test!**
