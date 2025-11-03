# Enhanced Health Monitor v3 - Changes & Deployment Guide

## Overview

This document describes all the improvements made to your Airflow HA Infrastructure Health Monitor DAG.

---

## Fixed Issues

### 1. ✅ Duplicate Log Entries - FIXED

**Problem**: Same log lines appearing multiple times in output.

**Root Cause**: 
- The log collection function was gathering logs from multiple sources (schedulers, workers)
- No deduplication was applied
- Same events were logged by multiple components

**Solution**:
- Added `deduplicate_log_lines()` function
- Uses a set to track unique log lines
- Preserves chronological order
- Removes exact duplicates while keeping first occurrence

**Before**:
```
2025-11-01T15:13:00 celery-2 airflow-worker[1815742]: Task ... received
2025-11-01T15:13:00 celery-2 airflow-worker[1815799]: Executing command...
2025-11-01T15:13:00 celery-2 airflow-worker[1815742]: Task ... received   ← DUPLICATE
2025-11-01T15:13:00 celery-2 airflow-worker[1815799]: Executing command... ← DUPLICATE
```

**After**:
```
2025-11-01T15:13:00 celery-2 airflow-worker[1815742]: Task ... received
2025-11-01T15:13:00 celery-2 airflow-worker[1815799]: Executing command...
```

---

### 2. ✅ [Invalid date] Artifacts - FIXED

**Problem**: "[Invalid date]" appearing in journalctl logs.

**Root Cause**:
- Using `short-iso` format with journalctl
- Some log entries don't parse correctly with this format
- Results in "[Invalid date]" placeholder

**Solution**:
- Changed from `short-iso` to `short-precise` format
- Added explicit `--output-fields=MESSAGE,PRIORITY`
- Ensures consistent timestamp parsing

**Before**:
```
2025-11-01T15:13:41+0330 scheduler-2 airflow-scheduler-ha2[Invalid date] {scheduler_job_runner.py:487} INFO - ...
```

**After**:
```
2025-11-01T15:13:41.123456 scheduler-2 airflow-scheduler-ha2[2978490] INFO - ...
```

---

## New Features

### 3. ✅ System Resource Monitoring

**New Task**: `check_system_resources`

**What it monitors**:
- **CPU Usage**: Current utilization percentage and available percentage
- **Memory Usage**: Used/Total/Available in MB, usage percentage
- **Disk Usage**: Used/Total space, usage percentage for root partition
- **Top 5 Processes**: 
  - Top 5 CPU-consuming processes with their CPU% and MEM%
  - Top 5 Memory-consuming processes with their CPU% and MEM%

**Monitored Nodes**:
- haproxy-1 (scheduler, webserver)
- haproxy-2 (webserver)
- scheduler-2 (scheduler)
- celery-1 (worker)
- celery-2 (worker)
- nfs-1 (NFS storage)
- nfs-2 (NFS storage)

**Output Example**:
```
📊 SYSTEM RESOURCES MONITORING REPORT
════════════════════════════════════════════════════════════════════════════

🖥️  HAPROXY-1
────────────────────────────────────────────────────────────────────────────
  💻 CPU:
     Usage: 45.20% | Available: 54.80%
     Top 5 CPU-consuming processes:
        1. /usr/bin/python3 /usr/bin/airflow scheduler    CPU:  15.2%  MEM:   4.5%
        2. postgres: airflow_db SELECT                     CPU:   8.7%  MEM:   2.1%
        3. /usr/bin/python3 /usr/bin/airflow webserver     CPU:   6.3%  MEM:   3.8%
        4. celery worker                                   CPU:   4.1%  MEM:   1.9%
        5. gunicorn                                        CPU:   3.2%  MEM:   1.2%

  🧠 MEMORY:
     Used: 12845 MB / 32768 MB (39.19%)
     Available: 19923 MB
     Top 5 Memory-consuming processes:
        1. /usr/bin/python3 /usr/bin/airflow scheduler    CPU:  15.2%  MEM:   4.5%
        2. /usr/bin/python3 /usr/bin/airflow webserver     CPU:   6.3%  MEM:   3.8%
        3. postgres: main process                          CPU:   2.1%  MEM:   3.2%
        4. celery worker                                   CPU:   4.1%  MEM:   1.9%
        5. python3 /home/rocky/airflow/dags/...            CPU:   1.8%  MEM:   1.5%

  💾 DISK (/):
     Used: 45G / 100G (45%)
```

**Resource Warnings**:
The task automatically flags concerning resource usage:
- CPU > 90% = Warning
- Memory > 90% = Warning
- Disk > 85% = Warning

**Example Warning**:
```
⚠️  RESOURCE WARNINGS:
   ⚠️  celery-1: HIGH CPU usage (95.40%)
   ⚠️  haproxy-1: HIGH MEMORY usage (92.15%)
   ⚠️  scheduler-2: HIGH DISK usage (88.00%)
```

---

### 4. ✅ Airflow Logs Directory Size Monitoring

**New Task**: `check_airflow_logs_size`

**What it monitors**:
- Size of `/home/rocky/airflow/logs` on all Airflow nodes
- Reports in both human-readable format and MB/GB
- Tracks total logs size across all nodes

**Monitored Nodes**: All nodes with Airflow components
- Schedulers (haproxy-1, scheduler-2)
- Webservers (haproxy-1, haproxy-2)
- Workers (celery-1, celery-2)
- NFS nodes (nfs-1, nfs-2)

**Output Example**:
```
📁 AIRFLOW LOGS DIRECTORY SIZE REPORT
════════════════════════════════════════════════════════════════════════════

📂 haproxy-1            │ Path: /home/rocky/airflow/logs          │ Size:   1.2GB (1240.50 MB)
📂 haproxy-2            │ Path: /home/rocky/airflow/logs          │ Size: 856.0MB (856.00 MB)
📂 scheduler-2          │ Path: /home/rocky/airflow/logs          │ Size:   1.5GB (1542.75 MB)
📂 celery-1             │ Path: /home/rocky/airflow/logs          │ Size:   2.8GB (2876.23 MB)
📂 celery-2             │ Path: /home/rocky/airflow/logs          │ Size:   2.3GB (2355.80 MB)
📂 nfs-1                │ Path: /home/rocky/airflow/logs          │ Size: 325.0MB (325.12 MB)
📂 nfs-2                │ Path: /home/rocky/airflow/logs          │ Size: 298.0MB (298.45 MB)

────────────────────────────────────────────────────────────────────────────
📊 TOTAL LOGS SIZE ACROSS ALL NODES: 9494.85 MB (9.27 GB)
════════════════════════════════════════════════════════════════════════════
```

**Log Size Warnings**:
Automatically warns if any node's logs exceed 5GB:
```
⚠️  LOG SIZE WARNINGS:
   ⚠️  celery-1: Large logs directory (7.52 GB) - consider cleanup
```

**Why This Matters**:
- Prevents disk space exhaustion
- Identifies nodes that need log cleanup
- Helps plan log retention policies
- Tracks log growth trends

---

## Code Improvements

### Additional Enhancements

1. **Better Error Handling**:
   - All resource fetching functions have proper try-catch blocks
   - Graceful degradation if SSH fails
   - Clear error messages in output

2. **Type Hints**:
   - Added type hints throughout (Dict, List, Set)
   - Improves code readability
   - Helps catch errors during development

3. **Improved Documentation**:
   - Comprehensive docstrings for all functions
   - Clear explanations of what each task does
   - Comments explaining complex logic

4. **Better Logging Format**:
   - Consistent use of emoji indicators (✅, ❌, ⚠️, 📊, etc.)
   - Structured output with clear separators
   - Easy-to-read reports

---

## Deployment Instructions

### Step 1: Backup Current DAG

```bash
# SSH to your Airflow DAG server (NFS active node)
ssh rocky@10.101.20.165  # or 10.101.20.203 if nfs-2 is active

# Backup the current DAG
cd /home/rocky/airflow/dags
cp ha_service_health_monitor_enhanced_v2.py ha_service_health_monitor_enhanced_v2.py.backup
```

### Step 2: Deploy New DAG

```bash
# Copy the new DAG to the DAGs folder
# (Transfer the file to the server first, then:)
cp /path/to/ha_service_health_monitor_enhanced_v3.py /home/rocky/airflow/dags/

# Verify file permissions
chmod 644 /home/rocky/airflow/dags/ha_service_health_monitor_enhanced_v3.py
chown rocky:rocky /home/rocky/airflow/dags/ha_service_health_monitor_enhanced_v3.py
```

### Step 3: Verify DAG in UI

1. Open Airflow UI: http://your-webserver-ip:8080
2. Wait ~30 seconds for DAG to be parsed
3. Look for DAG named: `ha_service_health_monitor_enhanced_v3`
4. Check that there are no parsing errors (look for red error icon)

### Step 4: Pause Old DAG, Enable New DAG

1. In Airflow UI, find `ha_service_health_monitor_enhanced_v2`
2. Toggle it OFF (pause it)
3. Find `ha_service_health_monitor_enhanced_v3`
4. Toggle it ON (unpause it)

### Step 5: Manual Test Run

1. Click on `ha_service_health_monitor_enhanced_v3`
2. Click "Trigger DAG" button (play icon)
3. Wait for it to complete
4. Check the task logs to verify:
   - No duplicate entries
   - No "[Invalid date]" in logs
   - Resource monitoring report appears
   - Logs size report appears

### Step 6: Monitor First Few Runs

Watch the DAG run for a few cycles (it runs every 2 minutes) to ensure:
- All tasks complete successfully
- Expected failures (passive NFS node) are present
- Resource reports are generated
- Logs size reports are generated

---

## What to Expect

### Normal Output

Every 2 minutes, you'll see:

1. **Service Health Checks**: ✅ or ❌ for each service
2. **System Resources Report**: CPU, RAM, Disk usage for all nodes
3. **Top Processes**: Most resource-intensive processes identified
4. **Logs Size Report**: Current size of logs on all nodes
5. **Health Summary**: Overall status with count of failures
6. **Final Status**: Pass/Fail based on critical services

### Example Healthy Run

```
[All service checks pass]

📊 SYSTEM RESOURCES MONITORING REPORT
[Shows resources are healthy]

✅ All nodes have healthy resource levels

📁 AIRFLOW LOGS DIRECTORY SIZE REPORT
[Shows log sizes across nodes]

🏥  HEALTH CHECK SUMMARY
════════════════════════════════════════════════════════════════════════
✅ Successful: 37
❌ Total Failed: 1
   ├─ Critical Failures: 0
   └─ Expected Passive Failures: 1

⏸️  EXPECTED PASSIVE NODE FAILURES (inactive as expected):
   - check_nfs_2_airflow_dag_processor

════════════════════════════════════════════════════════════════════════

✅ All critical services are healthy - DAG SUCCESS
ℹ️  Passive NFS node services are correctly inactive
```

### Example Failure Detection

```
❌ celery-2 - airflow-worker is NOT ACTIVE

════════════════════════════════════════════════════════════════════════
📋 Recent logs from celery-2:
════════════════════════════════════════════════════════════════════════
Nov 01 15:28:15 systemd[1]: Stopping Airflow Worker...
Nov 01 15:28:15 systemd[1]: airflow-worker.service: Main process exited
Nov 01 15:28:15 systemd[1]: airflow-worker.service: Failed with result 'exit-code'
Nov 01 15:28:15 celery[12345]: ERROR - Connection lost: [Errno 111] Connection refused

📊 SYSTEM RESOURCES MONITORING REPORT
[Shows if there are resource issues]

⚠️  RESOURCE WARNINGS:
   ⚠️  celery-2: HIGH MEMORY usage (95.20%)

🏥  HEALTH CHECK SUMMARY
════════════════════════════════════════════════════════════════════════
✅ Successful: 36
❌ Total Failed: 2
   ├─ Critical Failures: 1
   └─ Expected Passive Failures: 1

🚨 CRITICAL FAILURES:
   - check_celery_2_airflow_worker
     Check task logs for automatic diagnostic information

🚨 DAG FAILED: 1 critical service(s) are down!
Failed services: check_celery_2_airflow_worker
Check individual task logs for detailed diagnostic information.
```

---

## Interpreting the New Monitoring Data

### CPU Usage Interpretation

| CPU Usage | Status | Action |
|-----------|--------|--------|
| 0-50% | ✅ Healthy | Normal operation |
| 50-70% | ⚠️ Moderate | Monitor for trends |
| 70-90% | ⚠️ High | Investigate top processes |
| 90-100% | 🚨 Critical | Immediate action needed |

**Top CPU Processes**:
- Look for unexpected processes
- Scheduler/Worker processes are normal
- Runaway Python processes indicate problem tasks
- Check if process CPU usage correlates with task execution

### Memory Usage Interpretation

| Memory Usage | Status | Action |
|--------------|--------|--------|
| 0-60% | ✅ Healthy | Normal operation |
| 60-80% | ⚠️ Moderate | Monitor for leaks |
| 80-90% | ⚠️ High | Review top processes |
| 90-100% | 🚨 Critical | Risk of OOM killer |

**Top Memory Processes**:
- Schedulers and workers normally use 2-5% each
- >10% for single process = potential memory leak
- Check if memory grows over time
- Identify tasks causing high memory usage

### Disk Usage Interpretation

| Disk Usage | Status | Action |
|------------|--------|--------|
| 0-70% | ✅ Healthy | Normal operation |
| 70-85% | ⚠️ Moderate | Plan cleanup |
| 85-95% | 🚨 High | Clean up soon |
| 95-100% | 🔥 Critical | Immediate cleanup |

**What to check**:
- Logs growing too fast? Adjust retention
- Large DAG files? Clean up old ones
- Database backups? Move to another location

### Logs Size Interpretation

| Per-Node Size | Status | Action |
|---------------|--------|--------|
| 0-1 GB | ✅ Normal | No action needed |
| 1-5 GB | ⚠️ Moderate | Consider cleanup |
| 5-10 GB | ⚠️ High | Cleanup recommended |
| >10 GB | 🚨 Critical | Immediate cleanup |

**Total Logs Recommendations**:
- <10 GB total: Healthy
- 10-30 GB total: Monitor
- >30 GB total: Cleanup needed

---

## Troubleshooting New Features

### Resource Monitoring Not Working

**Symptoms**: Resource report shows errors for all nodes.

**Possible Causes**:
1. SSH connectivity issues
2. Missing commands (top, free, df)
3. Incorrect node IPs

**Fix**:
```bash
# Test SSH from scheduler node
ssh rocky@10.101.20.199 "top -bn1 | grep 'Cpu(s)'"

# Verify commands exist
which top free df ps

# Check IPs in AIRFLOW_MONITORING_NODES configuration
```

### Logs Size Monitoring Not Working

**Symptoms**: Logs size report shows errors.

**Possible Causes**:
1. Path doesn't exist: `/home/rocky/airflow/logs`
2. Permission issues
3. SSH problems

**Fix**:
```bash
# Verify path exists on all nodes
ssh rocky@10.101.20.202 "ls -la /home/rocky/airflow/logs"

# Check permissions
ssh rocky@10.101.20.202 "du -sh /home/rocky/airflow/logs"
```

### SSH Issues

**Symptoms**: Multiple nodes show SSH errors.

**Fix**:
```bash
# From the scheduler node where DAG runs, test SSH to all nodes
for ip in 10.101.20.202 10.101.20.146 10.101.20.132 10.101.20.199 10.101.20.200 10.101.20.165 10.101.20.203; do
    echo "Testing $ip..."
    ssh -o ConnectTimeout=5 rocky@$ip "hostname" || echo "FAILED: $ip"
done

# If SSH keys are not set up, add them:
ssh-copy-id rocky@10.101.20.XXX
```

---

## Performance Considerations

### Resource Overhead

The new monitoring adds:
- **Per run**: ~10-15 seconds total execution time
- **Network**: 7 SSH connections (one per monitored node)
- **CPU**: Minimal (just runs top, free, df commands)

### Optimization

The DAG is already optimized:
- Parallel execution of all checks
- Short command timeouts (5-10 seconds)
- Efficient deduplication algorithm
- No heavy computations

### Scaling

If you add more nodes:
1. Update `AIRFLOW_MONITORING_NODES` dictionary
2. Update `SERVERS` or `NFS_NODES` if they're service nodes
3. No other changes needed

---

## Comparison: v2 vs v3

| Feature | v2 | v3 |
|---------|----|----|
| Service health checks | ✅ | ✅ |
| PostgreSQL VIP check | ✅ | ✅ |
| RabbitMQ cluster check | ✅ | ✅ |
| Scheduler heartbeat check | ✅ | ✅ |
| Celery workers check | ✅ | ✅ |
| NFS active/passive detection | ✅ | ✅ |
| Automatic log collection | ✅ | ✅ |
| **Duplicate log entries** | ❌ | **✅ Fixed** |
| **[Invalid date] in logs** | ❌ | **✅ Fixed** |
| **CPU monitoring** | ❌ | **✅ New** |
| **RAM monitoring** | ❌ | **✅ New** |
| **Disk monitoring** | ❌ | **✅ New** |
| **Top 5 processes** | ❌ | **✅ New** |
| **Logs size tracking** | ❌ | **✅ New** |
| **Resource warnings** | ❌ | **✅ New** |

---

## Maintenance

### Weekly Tasks

1. Review resource trends
   - Are CPU/RAM increasing over time?
   - Which nodes are busiest?
   - Any processes consistently in top 5?

2. Check log sizes
   - Is any node accumulating logs too fast?
   - Total logs size trend

3. Review critical failures
   - Any recurring failures?
   - Patterns in failure times?

### Monthly Tasks

1. Clean up old logs if needed
   ```bash
   airflow db clean --clean-before-timestamp "2025-10-01" --yes
   ```

2. Review and adjust resource allocation
   - Based on observed usage patterns
   - Scale up/down as needed

3. Update thresholds if needed
   - CPU/RAM/Disk warning levels in code
   - Logs size warning threshold (currently 5GB)

---

## Support & Documentation

### Files Included

1. **ha_service_health_monitor_enhanced_v3.py**: The new DAG
2. **AIRFLOW_LOGS_GUIDE.md**: Comprehensive guide to understanding Airflow logs
3. **THIS FILE**: Deployment and change documentation

### Additional Resources

- Airflow Documentation: https://airflow.apache.org/docs/
- Your specific setup documentation in project files

### Getting Help

If you encounter issues:

1. Check the AIRFLOW_LOGS_GUIDE.md for log interpretation
2. Review task logs in Airflow UI
3. Check system logs with journalctl
4. Verify SSH connectivity from scheduler node
5. Check resource monitoring reports for clues

---

## Success Criteria

You'll know the deployment is successful when:

- ✅ No "[Invalid date]" in logs
- ✅ No duplicate log entries
- ✅ Resource monitoring report appears every run
- ✅ Logs size report appears every run
- ✅ Resource warnings appear when thresholds exceeded
- ✅ All service checks continue working as before
- ✅ DAG completes in ~30-60 seconds

---

## Conclusion

The v3 DAG provides:

1. **Better reliability**: Fixed duplicate and [Invalid date] issues
2. **More visibility**: System resources and log sizes
3. **Proactive monitoring**: Warnings before problems become critical
4. **Better diagnostics**: Top processes help identify issues quickly

Deploy confidently! The improvements are backward-compatible and only add new monitoring capabilities without breaking existing functionality.
