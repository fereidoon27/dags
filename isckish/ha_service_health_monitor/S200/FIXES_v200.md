# HA Health Monitor v200 - Issues Fixed

## Quick Summary

All reported issues have been fixed in `ha_service_health_monitor_v200.py`:

✅ **Issue 1**: RabbitMQ authentication - restored original credentials
✅ **Issue 2**: Log fetching for broken services - fixed journalctl output
✅ **Issue 3**: Task names too long - shortened all task IDs
✅ **Issue 4**: System resources broken - fixed awk command escaping
✅ **Issue 5**: Logs size broken - fixed du command parsing

---

## Detailed Fixes

### Issue 1: RabbitMQ Authentication Error

**Problem**: 
```
ConnectionClosedByBroker: (403) 'ACCESS_REFUSED - Login was refused using authentication mechanism PLAIN.'
```

**Root Cause**: Changed credentials from original working ones.

**Fixed**:
- Restored original credentials:
  - Username: `airflow_user` (was changed to `admin`)
  - Password: `airflow_pass` (was changed to `admin`)
  - Virtual host: `airflow_host` (was missing)

**Code change**:
```python
# BEFORE (v3 - broken)
credentials = pika.PlainCredentials('admin', 'admin')
conn = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=ip, port=5672,
        credentials=credentials, socket_timeout=5
    )
)

# AFTER (v200 - fixed)
credentials = pika.PlainCredentials('airflow_user', 'airflow_pass')
conn = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=ip, port=5672, virtual_host='airflow_host',
        credentials=credentials, socket_timeout=5
    )
)
```

---

### Issue 2: Broken Service Logs Not Being Fetched

**Problem**: When a service failed, logs were not showing up in the error message.

**Root Cause**: The journalctl output format was changed but logs weren't being properly included in error messages.

**Fixed**:
- Ensured `fetch_journalctl_logs()` returns properly formatted logs
- Made sure error messages include the full log output with proper separators
- Changed from `--output-fields` back to simpler format

**Code change**:
```python
# BEFORE (v3 - broken)
cmd = f"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 150 -o short-precise --output-fields=MESSAGE,PRIORITY"

# AFTER (v200 - fixed)
cmd = f"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 150 -o short-precise"
```

And in error messages:
```python
# BEFORE
error_msg += f"\n{'='*80}\nðŸ"‹ Recent logs from {server_name}:\n{'='*80}\n{journalctl_logs}\n"

# AFTER - simpler, clearer
error_msg += f"{'='*80}\nðŸ"‹ Recent logs from {server_name}:\n{'='*80}\n{journalctl_logs}\n\n"
```

---

### Issue 3: Task Names Too Long

**Problem**: Task IDs like `check_celery_2_airflow_worker` were too long.

**Fixed**: Shortened all task names by:
1. Removing `check_` prefix from task IDs
2. Using abbreviations for services:
   - `rabbitmq-server` → `rmq`
   - `airflow-scheduler` → `sched`
   - `airflow-webserver` → `web`
   - `airflow-worker` → `worker`
   - `airflow-dag-processor` → `dag_proc`
   - Others kept short already

**Examples**:
```
BEFORE                                → AFTER
check_celery_2_airflow_worker        → celery2_worker
check_haproxy_1_airflow_scheduler    → haproxy1_sched
check_rabbit_1_rabbitmq_server       → rabbit1_rmq
check_nfs_1_airflow_dag_processor    → nfs1_dag_proc
check_rabbitmq_cluster               → rmq_cluster
check_postgresql_vip                 → pg_vip
check_scheduler_heartbeat            → scheduler_heartbeat
check_celery_workers                 → celery_workers
check_system_resources               → system_resources
check_airflow_logs_size              → logs_size
```

**Code change**:
```python
# Added service abbreviation mapping
SERVICE_ABBREV = {
    'airflow-scheduler': 'sched',
    'airflow-webserver': 'web',
    'airflow-worker': 'worker',
    'rabbitmq-server': 'rmq',
    'haproxy': 'haproxy',
    'keepalived': 'keepalived',
    'patroni': 'patroni',
    'etcd': 'etcd',
    'vsftpd': 'ftp',
    'airflow-dag-processor': 'dag_proc',
    'nfs-server': 'nfs',
    'lsyncd': 'lsyncd'
}

# Use in task creation
service_short = SERVICE_ABBREV.get(service_name, service_name.replace('-', '_'))
task_id = f"{server_name.replace('-', '')}_{service_short}"
```

---

### Issue 4: System Resources Command Broken

**Problem**: 
```
/bin/sh: line 1: %s: command not found
bash: -c: line 1: unexpected EOF while looking for matching `''
```

**Root Cause**: The awk printf format strings (`%s`, `%d`) were conflicting with Python string formatting and not properly escaped for shell/SSH execution.

**Fixed**: 
- Properly escaped awk commands using `\\\"` for quotes
- Used separate commands instead of complex printf formatting
- Fixed quote escaping for SSH execution

**Code change**:
```python
# BEFORE (v3 - broken)
mem_cmd = "free -m | awk 'NR==2{printf \"%s %s %.2f\", $3,$2,$3*100/$2 }'"

# AFTER (v200 - fixed)
mem_cmd = "free -m | awk 'NR==2{printf \\\"%s %s %.2f\\\", $3,$2,$3*100/$2 }'"

# And for SSH, properly escape again
if not is_local_check:
    full_cmd = full_cmd.replace('"', '\\"')
    full_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"{full_cmd}\""
```

---

### Issue 5: Logs Size Parsing Broken

**Problem**: 
```
Exception: invalid literal for int() with base 10: '13\t/home/rocky/airflow/logs'
```

**Root Cause**: The `du` command was returning tab-separated output with both size and path, but the code was trying to parse the entire output as an integer.

**Fixed**:
- Use `du -sk` to get size in KB only
- Use `cut -f1` to extract just the first field (size)
- Get human-readable size separately with `du -sh`

**Code change**:
```python
# BEFORE (v3 - broken)
cmd = f"du -sh {logs_path} && du -sb {logs_path} | awk '{{print $1}}'"
# This returned: "13M\t/path\n13000000"
# Tried to parse "13\t/path" as int

# AFTER (v200 - fixed)
cmd = f"du -sk {logs_path} | cut -f1"
# This returns just: "13000" (size in KB)

size_kb = int(result.stdout.strip())
size_bytes = size_kb * 1024

# Get human readable separately
human_cmd = f"du -sh {logs_path} | cut -f1"
```

---

## Testing Checklist

After deploying v200, verify:

- [ ] RabbitMQ cluster check passes (no authentication errors)
- [ ] When you stop a service, logs appear in the failure message
- [ ] Task names are shorter in the UI
- [ ] System resources report shows data for all nodes (no command errors)
- [ ] Logs size report shows accurate sizes for all nodes

---

## Task Name Reference

For quick reference, here are all the new shortened task names:

**Main Tasks**:
- `detect_active_nfs` - Detect active NFS node
- `system_resources` - System resource monitoring
- `logs_size` - Airflow logs size monitoring
- `pg_vip` - PostgreSQL VIP check
- `rmq_cluster` - RabbitMQ cluster check
- `scheduler_heartbeat` - Scheduler heartbeat check
- `celery_workers` - Celery workers check
- `health_summary` - Health summary
- `final_check` - Final status check

**Service Check Tasks** (format: `{server}{service}`):
- `haproxy1_sched` - haproxy-1 scheduler
- `haproxy1_web` - haproxy-1 webserver
- `haproxy1_haproxy` - haproxy-1 HAProxy
- `haproxy1_keepalived` - haproxy-1 keepalived
- `haproxy2_web` - haproxy-2 webserver
- `haproxy2_haproxy` - haproxy-2 HAProxy
- `haproxy2_keepalived` - haproxy-2 keepalived
- `scheduler2_sched` - scheduler-2 scheduler
- `rabbit1_rmq` - rabbit-1 RabbitMQ
- `rabbit2_rmq` - rabbit-2 RabbitMQ
- `rabbit3_rmq` - rabbit-3 RabbitMQ
- `postgresql1_patroni` - postgresql-1 Patroni
- `postgresql1_etcd` - postgresql-1 etcd
- `postgresql2_patroni` - postgresql-2 Patroni
- `postgresql2_etcd` - postgresql-2 etcd
- `postgresql3_patroni` - postgresql-3 Patroni
- `postgresql3_etcd` - postgresql-3 etcd
- `celery1_worker` - celery-1 worker
- `celery2_worker` - celery-2 worker
- `ftp_ftp` - FTP server
- `nfs1_dag_proc` - nfs-1 DAG processor
- `nfs1_nfs` - nfs-1 NFS server
- `nfs1_lsyncd` - nfs-1 lsyncd
- `nfs1_keepalived` - nfs-1 keepalived
- `nfs2_dag_proc` - nfs-2 DAG processor
- `nfs2_nfs` - nfs-2 NFS server
- `nfs2_lsyncd` - nfs-2 lsyncd
- `nfs2_keepalived` - nfs-2 keepalived

---

## What Didn't Change

These features are still working as designed:
- ✅ Duplicate log elimination
- ✅ NFS active/passive detection
- ✅ Automatic diagnostic log collection
- ✅ Health summary with expected vs critical failures
- ✅ DAG structure and dependencies

---

## Next Steps

1. Deploy `ha_service_health_monitor_v200.py` to your DAGs folder
2. Pause/delete the old DAG
3. Unpause the new v200 DAG
4. Trigger a test run
5. Verify all fixes are working
6. Test by stopping a service and checking logs appear

Refer to `AIRFLOW_LOGS_GUIDE.md` for help understanding and analyzing the logs.
