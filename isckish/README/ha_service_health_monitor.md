# Airflow HA Infrastructure Health Monitor

A comprehensive health monitoring DAG for Apache Airflow 2.9+ that validates all components in a highly-available (HA) infrastructure deployment.

## 📋 Overview

This DAG monitors a 13-VM Airflow cluster with zero single points of failure. It runs every 15 minutes and creates **individual tasks for each service** across all servers, making it easy to identify exactly which component is experiencing issues.

## 🏗️ Monitored Architecture

### Infrastructure Components

- **Load Balancers (HAProxy)**: 2 nodes with active/passive keepalived
- **Schedulers**: 2 nodes with multi-scheduler coordination
- **Web Servers**: 2 nodes load-balanced via HAProxy
- **Storage (NFS)**: 2 nodes with active/passive HA + real-time sync
- **Database (PostgreSQL)**: 3-node Patroni cluster with etcd
- **Message Queue (RabbitMQ)**: 3-node cluster with mirroring
- **Celery Workers**: 2 nodes for task execution
- **FTP Server**: 1 node for file transfers

### Virtual IPs
- **Main VIP** (`10.101.20.210`): Database, HAProxy, Webserver access
- **NFS VIP** (`10.101.20.220`): Shared storage access

## 🎯 What It Checks

### 1. **Service-Level Checks**
Each systemd service on every VM gets its own Airflow task:
- Schedulers (`airflow-scheduler`)
- Web servers (`airflow-webserver`)
- Workers (`airflow-worker`)
- DAG processors (`airflow-dag-processor`)
- HAProxy, Keepalived, NFS, lsyncd, vsftpd
- Patroni, etcd
- RabbitMQ

### 2. **Cluster-Level Checks**
- **PostgreSQL VIP**: Validates database connectivity and queries
- **RabbitMQ Cluster**: Ensures quorum (≥2/3 nodes healthy)
- **Scheduler Heartbeat**: Confirms active schedulers in metadata DB
- **Celery Workers**: Verifies worker availability via Celery inspect

### 3. **NFS Active/Passive HA Logic**
Special handling for storage high availability:

1. **Detects active NFS node** by checking which has the VIP (10.101.20.220)
2. **Active node**: All services must be ACTIVE
3. **Passive node**: 
   - `keepalived` must be ACTIVE (monitors VIP)
   - Other services (`nfs-server`, `airflow-dag-processor`, `lsyncd`) must be NOT ACTIVE

## 📊 Task Outcomes & Scenarios

### Success Scenarios ✅

| Scenario | Task Status | DAG Status |
|----------|-------------|------------|
| All services healthy | All tasks SUCCESS | **SUCCESS** |
| Passive NFS services inactive | Those tasks FAIL | **SUCCESS** ✓ |
| Passive NFS services failed/dead | Those tasks FAIL | **SUCCESS** ✓ |

### Failure Scenarios ❌

| Scenario | Task Status | DAG Status | Severity |
|----------|-------------|------------|----------|
| Active service down | Task FAILS | **FAILED** | Critical |
| RabbitMQ quorum lost (<2/3) | Task FAILS | **FAILED** | Critical |
| No active schedulers | Task FAILS | **FAILED** | Critical |
| Passive NFS service ACTIVE | Task FAILS | **FAILED** | Critical (HA issue) |
| PostgreSQL VIP unreachable | Task FAILS | **FAILED** | Critical |

## 🔍 Understanding Task Failures

Not all task failures are critical! The DAG intelligently categorizes failures:

### Expected Failures (DAG still succeeds)
```
⏸️ EXPECTED: nfs-server on PASSIVE node nfs-2 is correctly NOT ACTIVE (status: inactive)
```
These are **normal** - passive NFS services should be down.

### Critical Failures (DAG fails)
```
🚨 CRITICAL: nfs-server on PASSIVE node nfs-2 is ACTIVE (should be NOT ACTIVE)!
```
This indicates an **HA failover problem** - both nodes are active (split-brain).

## 🚀 How It Works

### DAG Execution Flow

```
detect_nfs_active_node
        ↓
    ┌───┴───┐
    │       │
NFS Tasks  Other Service Tasks  +  Cluster Checks
    │       │                           │
    └───┬───┴───────────────────────────┘
        ↓
  health_summary (trigger_rule: all_done)
        ↓
  final_status_check
        ↓
    DAG Result
```

### Smart Worker Self-Check
Workers check their own service status **locally** (not via SSH) to avoid connection issues when a worker checks itself.

### XCom-Based Failure Classification
Each failed task stores its failure type in XCom:
- `EXPECTED_PASSIVE_INACTIVE`: Normal passive node state
- `CRITICAL_PASSIVE_ACTIVE`: HA failover problem
- Other failures: Critical service issues

The `health_summary` task reads these XCom values and separates expected failures from critical ones.

## 📝 Reading the Logs

### Health Summary Output
```
================================================================================
🏥  HEALTH CHECK SUMMARY
================================================================================
✅ Successful: 35
❌ Total Failed: 3
   ├─ Critical Failures: 0
   └─ Expected Passive Failures: 3

⏸️  EXPECTED PASSIVE NODE FAILURES (inactive as expected):
   - check_nfs_2_lsyncd
   - check_nfs_2_airflow_dag_processor
   - check_nfs_2_nfs_server
================================================================================
```

### Service Failure Logs
When a service fails, the full `systemctl status` output is included:
```
❌ airflow-scheduler on scheduler-2 (10.101.20.132) is INACTIVE

Service Status Output:
------------------------------------------------------------
● airflow-scheduler.service - Airflow scheduler daemon
   Loaded: loaded (/usr/lib/systemd/system/airflow-scheduler.service)
   Active: inactive (dead)
------------------------------------------------------------
```

## 🛠️ Setup & Usage

### Prerequisites
```bash
# Install required Python packages on all workers
pip install psycopg2-binary pika
```

### Configuration
The DAG reads server configuration from dictionaries at the top of the file. Update IPs if needed:
```python
SERVERS = {
    'celery-1': {'ip': '10.101.20.199', 'services': ['airflow-worker']},
    # ...
}
```

### Deployment
1. Place `airflow_ha_health_check.py` in your DAGs folder (`/airflow/dags/`)
2. Wait for DAG to appear in Airflow UI (auto-refreshes every 30s)
3. Enable the DAG if not auto-enabled
4. First run will execute automatically (schedule: `*/15 * * * *`)

### Monitoring
- **Graph View**: See all service checks as individual tasks - red = failed
- **health_summary logs**: Get the overall summary
- **final_status_check**: DAG succeeds only if this task succeeds

## 🔔 Alerting Integration

The DAG is designed to work with Airflow's built-in alerting:

### Email Alerts
Configure in `airflow.cfg`:
```ini
[smtp]
smtp_host = localhost
smtp_port = 587
smtp_mail_from = airflow@yourdomain.com
```

Then set DAG-level alerts:
```python
default_args={
    'email': ['ops@yourdomain.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}
```

### Other Alert Options
- **Slack**: Use `SlackWebhookOperator` as a final task
- **PagerDuty**: Add PagerDuty API calls on failure
- **Custom webhooks**: HTTP callbacks in the `final_status_check` task

## ❓ Troubleshooting

### Issue: Worker self-check fails with "Empty status"
**Cause**: SSH to localhost returning empty output  
**Solution**: The DAG now detects local checks and uses direct `systemctl` commands

### Issue: All passive NFS tasks marked as failed
**Status**: This is **expected behavior**  
**Explanation**: Tasks fail for visibility, but DAG succeeds if services are NOT active

### Issue: DAG succeeds but some services are down
**Check**: Look at `health_summary` logs to see which services failed  
**Action**: If critical services failed, the DAG should have failed. Report a bug.

### Issue: SSH timeouts to servers
**Cause**: Network connectivity or SSH key issues  
**Solution**: Verify passwordless SSH from workers to all nodes:
```bash
ssh rocky@<server-ip> 'echo OK'
```

## 📚 Key Design Decisions

1. **Individual tasks per service**: Provides granular visibility - you know exactly which service on which VM failed
2. **No retries**: Immediate failure visibility without retry delays
3. **Expected failures**: Passive NFS tasks fail but don't fail the DAG
4. **Local vs SSH checks**: Workers check themselves locally to avoid self-SSH issues
5. **XCom for classification**: Failure types stored in XCom enable smart summary logic

## 📄 License & Support

This DAG is part of an Airflow HA deployment. For issues or questions, contact your infrastructure team.

**Version**: 1.0  
**Compatible with**: Apache Airflow 2.9+  
**Last Updated**: October 2025
