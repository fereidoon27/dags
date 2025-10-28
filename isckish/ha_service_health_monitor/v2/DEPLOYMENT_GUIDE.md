# Enhanced HA Service Health Monitor - Deployment Guide

## 🎯 What's New in the Enhanced Version

### Issue 1 Solution: Automatic Log Fetching

The enhanced DAG now **automatically fetches diagnostic logs** when any service fails:

1. **Journalctl logs** from the affected server (last 60 minutes)
2. **Airflow worker logs** for the failed task
3. **Airflow scheduler logs** related to the failed task

This means you no longer need to manually SSH into servers to investigate failures!

## 📋 Prerequisites

### 1. Verify Python Packages on Workers

On **celery-1** and **celery-2**:

```bash
pip list | grep -E "(psycopg2|pika)"

# If not installed:
pip install psycopg2-binary pika --break-system-packages
```

### 2. Verify Sudo Permissions

The DAG needs sudo access for `systemctl` and `journalctl`. On **all nodes**:

```bash
# Test sudo without password
sudo systemctl status airflow-scheduler
sudo journalctl -u airflow-scheduler --since '10 minutes ago' -n 5

# If prompted for password, add to sudoers:
sudo visudo

# Add these lines (replace 'rocky' with your user):
rocky ALL=(ALL) NOPASSWD: /usr/bin/systemctl
rocky ALL=(ALL) NOPASSWD: /usr/bin/journalctl
```

### 3. Verify SSH Access from Workers

On **celery-1** and **celery-2**:

```bash
# Test SSH to all nodes (should work without password)
for ip in 10.101.20.202 10.101.20.146 10.101.20.132 \
          10.101.20.165 10.101.20.203 \
          10.101.20.205 10.101.20.147 10.101.20.206 \
          10.101.20.204 10.101.20.166 10.101.20.137 \
          10.101.20.164; do
    echo "Testing $ip..."
    ssh -o ConnectTimeout=3 rocky@$ip 'echo OK'
done
```

## 🚀 Deployment Steps

### Step 1: Backup Current DAG (Optional)

On the **active NFS node** (nfs-1 or nfs-2):

```bash
cd /srv/airflow/dags
cp ha_service_health_monitor.py ha_service_health_monitor.py.backup
```

### Step 2: Deploy Enhanced DAG

**Option A: Replace existing DAG**

```bash
# On active NFS node
cd /srv/airflow/dags
# Upload the new file as ha_service_health_monitor.py
```

**Option B: Deploy alongside existing DAG (Recommended for testing)**

```bash
# On active NFS node
cd /srv/airflow/dags
# Upload as ha_service_health_monitor_enhanced.py
# Both DAGs will run independently
```

### Step 3: Verify Deployment

```bash
# Check file is visible on all Airflow nodes
for host in haproxy-1 haproxy-2 scheduler-2 celery-1 celery-2; do
    echo "=== $host ==="
    ssh rocky@$host 'ls -lh /airflow/dags/ha_service_health_monitor*.py'
done
```

### Step 4: Wait for DAG to Appear

The DAG will automatically appear in the Airflow UI within 30 seconds (DAG parsing interval).

Navigate to: `http://10.101.20.210:8081/dags`

You should see:
- `ha_service_health_monitor` (original) - if kept
- `ha_service_health_monitor_enhanced` (new)

### Step 5: Test the Enhanced DAG

#### Manual Test Run

1. In Airflow UI, find `ha_service_health_monitor_enhanced`
2. Click the "Trigger DAG" button (play icon)
3. Wait for execution to complete
4. Check the Graph view - all tasks should be green (or expected red for passive NFS)

#### Simulate a Failure for Testing

To test the log fetching feature:

```bash
# SSH to a test node (e.g., ftp server)
ssh rocky@10.101.20.164

# Stop a service temporarily
sudo systemctl stop vsftpd

# Wait for the next DAG run (or trigger manually)
# The DAG will fail, and the task log will show:
# - Service status
# - Journalctl logs
# - Worker logs
# - Scheduler logs

# Restore the service
sudo systemctl start vsftpd
```

## 📊 Understanding the Enhanced Logs

### Example: Service Failure with Automatic Logs

When a service fails, you'll see something like this in the task log:

```
[2025-10-28, 14:30:00 +0330] {taskinstance.py:1234} INFO - ❌ vsftpd on ftp (10.101.20.164) is INACTIVE

Service Status Output:
------------------------------------------------------------
● vsftpd.service - Vsftpd ftp daemon
   Loaded: loaded (/usr/lib/systemd/system/vsftpd.service)
   Active: inactive (dead)
------------------------------------------------------------

================================================================================
📋 FETCHING DIAGNOSTIC LOGS FOR FAILED SERVICE
================================================================================

🔍 Fetching journalctl logs for vsftpd on ftp (last 60 minutes)...

================================================================================
📋 JOURNALCTL LOGS (Last 60 minutes):
================================================================================
Oct 28 13:45:23 ftp systemd[1]: Stopping Vsftpd ftp daemon...
Oct 28 13:45:23 ftp systemd[1]: vsftpd.service: Succeeded.
Oct 28 13:45:23 ftp systemd[1]: Stopped Vsftpd ftp daemon.
Oct 28 14:20:15 ftp systemd[1]: Started Vsftpd ftp daemon.
Oct 28 14:25:30 ftp systemd[1]: Stopping Vsftpd ftp daemon...
Oct 28 14:25:30 ftp systemd[1]: vsftpd.service: Succeeded.

================================================================================
📋 AIRFLOW WORKER LOGS:
================================================================================
[2025-10-28, 14:30:00 +0330] {taskinstance.py:1234} INFO - Dependencies all met for <TaskInstance: ...>
[2025-10-28, 14:30:00 +0330] {taskinstance.py:1456} INFO - Starting attempt 1 of 1
[2025-10-28, 14:30:00 +0330] {taskinstance.py:1678} INFO - Executing <Task(PythonOperator): check_ftp_vsftpd>
[2025-10-28, 14:30:00 +0330] {python.py:177} INFO - Done. Returned value was: None

================================================================================
📋 AIRFLOW SCHEDULER LOGS:
================================================================================
Oct 28 14:29:55 haproxy-1 airflow-scheduler[12345]: [2025-10-28, 14:29:55 +0330] {dag.py:2456} INFO - Sync 1 DAGs
Oct 28 14:29:58 scheduler-2 airflow-scheduler[23456]: [2025-10-28, 14:29:58 +0330] {scheduler_job.py:789} INFO - Checking task instance <TaskInstance: ha_service_health_monitor_enhanced.check_ftp_vsftpd>
Oct 28 14:30:00 haproxy-1 airflow-scheduler[12345]: [2025-10-28, 14:30:00 +0330] {scheduler_job.py:1234} INFO - Sending task to executor: check_ftp_vsftpd

================================================================================
```

### Key Sections Explained

1. **Service Status Output**: Shows the current systemd status
2. **Journalctl Logs**: Last 60 minutes of service logs from the affected server
3. **Worker Logs**: Airflow task execution logs from the worker
4. **Scheduler Logs**: Scheduler activity related to this task (from both schedulers)

## 🔍 Troubleshooting

### Issue 1: "Permission denied" when fetching journalctl

**Symptom**: Logs show `sudo: no tty present and no askpass program specified`

**Solution**: Update sudoers file:
```bash
sudo visudo
# Add:
rocky ALL=(ALL) NOPASSWD: /usr/bin/journalctl
```

### Issue 2: "Could not fetch worker logs"

**Symptom**: Worker logs section shows "Worker log file not found"

**Cause**: Log path mismatch or logs not yet written

**Solution**: 
1. Verify `AIRFLOW_LOGS_BASE` in the DAG matches your actual log path:
   ```bash
   # Check your actual log path
   ls -la /home/rocky/airflow/logs/
   ```

2. Update the DAG if needed:
   ```python
   AIRFLOW_LOGS_BASE = '/home/rocky/airflow/logs'  # Update this
   ```

### Issue 3: Scheduler logs empty

**Symptom**: Scheduler logs section shows "No relevant scheduler logs found"

**Cause**: grep pattern not matching or logs rotated

**Solution**: This is usually not critical. The service and worker logs are more important.

### Issue 4: SSH timeouts

**Symptom**: Errors like "ssh: connect to host X.X.X.X port 22: Connection timed out"

**Solution**:
```bash
# From worker node, test SSH to all hosts
for ip in $(grep -oP '\d+\.\d+\.\d+\.\d+' /home/rocky/airflow/dags/ha_service_health_monitor_enhanced.py | sort -u); do
    echo -n "$ip: "
    ssh -o ConnectTimeout=3 rocky@$ip 'hostname' || echo "FAILED"
done
```

## 📈 Performance Considerations

### Log Fetching Overhead

- **Journalctl fetch**: ~2-5 seconds per service
- **Worker log read**: ~1-2 seconds
- **Scheduler log fetch**: ~3-7 seconds (queries 2 schedulers)

**Total overhead per failed service**: ~5-15 seconds

This is acceptable because:
1. Logs are only fetched when a service actually fails
2. The diagnostic value far outweighs the time cost
3. Failed services need immediate attention anyway

### Adjusting Log Fetch Duration

If you want to fetch more or less history, edit the DAG:

```python
# Default: 60 minutes
journalctl_logs = fetch_journalctl_logs(ip, service, hostname, minutes_back=60)

# For more history:
journalctl_logs = fetch_journalctl_logs(ip, service, hostname, minutes_back=180)  # 3 hours

# For less (faster):
journalctl_logs = fetch_journalctl_logs(ip, service, hostname, minutes_back=30)  # 30 minutes
```

## 🔄 Migration from Original DAG

### Side-by-Side Operation (Recommended)

1. Keep both DAGs running for 1 week
2. Monitor both for consistency
3. After validation, disable the original:
   ```bash
   # In Airflow UI, toggle off ha_service_health_monitor
   # Or delete the old file from NFS
   ```

### Direct Replacement

1. Stop the original DAG in UI
2. Wait for current run to complete
3. Delete old file:
   ```bash
   rm /srv/airflow/dags/ha_service_health_monitor.py
   ```
4. Deploy new file with same name
5. Clear DAG runs if needed:
   ```bash
   airflow dags delete ha_service_health_monitor
   ```

## 📝 Customization Options

### 1. Adjust Log Retention

```python
# In fetch_journalctl_logs function
def fetch_journalctl_logs(ip, service, hostname, minutes_back=60):
    # Change minutes_back default
```

### 2. Add More Services to Monitor

```python
SERVERS = {
    # Add new server
    'my-new-server': {
        'ip': '10.101.20.XXX',
        'services': ['my-service', 'another-service']
    },
}
```

### 3. Change DAG Schedule

```python
@dag(
    # Change from every 15 minutes to every 5 minutes
    schedule='*/5 * * * *',
    # Or every hour
    schedule='0 * * * *',
)
```

### 4. Email Alerts on Failure

```python
default_args={
    'owner': 'airflow',
    'retries': 0,
    'email': ['ops@yourdomain.com', 'oncall@yourdomain.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}
```

### 5. Custom Log Paths

```python
# If your logs are in a different location
AIRFLOW_LOGS_BASE = '/custom/path/to/logs'
```

## 🎓 Best Practices

1. **Test in non-production first**: If possible, test on a dev cluster
2. **Monitor DAG performance**: Check execution times don't exceed 5 minutes
3. **Review logs regularly**: Even when all services are healthy
4. **Keep historical runs**: Useful for incident analysis
5. **Document custom changes**: If you modify the DAG

## 🆘 Support Checklist

Before asking for help, verify:

```
□ All workers have psycopg2-binary and pika installed
□ SSH works from workers to all nodes (passwordless)
□ Sudo works without password for systemctl and journalctl
□ DAG file is visible on all Airflow nodes via NFS
□ DAG appears in Airflow UI
□ Test run completes successfully
□ Logs are being fetched (check a failed task)
```

## 📚 Additional Resources

- Original README: `ha_service_health_monitor.md`
- Timezone Guide: `TIMEZONE_CONFIGURATION_GUIDE.md`
- Airflow Logging: https://airflow.apache.org/docs/apache-airflow/stable/logging-monitoring/logging-tasks.html

## 🎉 Success Indicators

You'll know it's working when:

✅ DAG runs every 15 minutes without errors (except expected passive NFS)
✅ When you manually stop a service, the task log shows:
   - Service status
   - Journalctl logs
   - Worker logs
   - Scheduler logs
✅ health_summary shows correct count of critical vs expected failures
✅ No need to SSH manually to investigate failures anymore!

---

**Questions or Issues?**

Check the troubleshooting section above or review the logs in:
- Failed task logs (for detailed diagnostic info)
- health_summary task (for overall status)
- Scheduler logs on haproxy-1 and scheduler-2
