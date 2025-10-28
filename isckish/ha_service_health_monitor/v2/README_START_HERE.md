# Solutions for Airflow HA Monitoring & Timezone Issues

## 📦 What You've Received

This package contains complete solutions for both issues you raised:

### Issue 1: Enhanced Logging for Failed Services ✅
**Problem**: When services fail, manually SSH-ing and checking journalctl was tedious.
**Solution**: Automatic diagnostic log fetching built into the health monitor DAG.

### Issue 2: Timezone Inconsistency ✅
**Problem**: Timestamps differ between UI (UTC) and logs (Asia/Tehran).
**Solution**: Complete configuration guide to properly set up timezone handling.

---

## 📁 Files Included

### 1. **ha_service_health_monitor_enhanced.py** (32 KB)
The enhanced health monitoring DAG with automatic log fetching.

**Key Features:**
- ✅ Automatically fetches journalctl logs from failed services (last 60 minutes)
- ✅ Automatically fetches Airflow worker logs for failed tasks
- ✅ Automatically fetches scheduler logs related to failed tasks
- ✅ All diagnostic info appears directly in the task log
- ✅ No manual SSH required for root cause analysis

**Enhancement Over Original:**
- Added `fetch_journalctl_logs()` function
- Added `fetch_airflow_worker_logs()` function
- Added `fetch_scheduler_logs_for_task()` function
- Enhanced all service check functions to call these automatically on failure
- Added diagnostic log sections to PostgreSQL, RabbitMQ, Scheduler, and Worker checks

### 2. **DEPLOYMENT_GUIDE.md** (12 KB)
Complete step-by-step deployment instructions.

**Contents:**
- Prerequisites verification
- Deployment steps
- Testing procedures
- Troubleshooting common issues
- Performance considerations
- Customization options

### 3. **TIMEZONE_CONFIGURATION_GUIDE.md** (12 KB)
Comprehensive timezone configuration guide.

**Contents:**
- Understanding Airflow timezone behavior
- System timezone configuration (all nodes)
- airflow.cfg configuration
- DAG timezone-aware datetime examples
- Service restart procedures
- Verification scripts
- Common issues and solutions

### 4. **QUICK_REFERENCE.md** (13 KB)
Quick reference card for incident response.

**Contents:**
- 7 common failure scenarios with exact commands
- Quick command cheat sheet
- Priority matrix for incident response
- Copy-paste ready commands

---

## 🚀 Quick Start Guide

### For Issue 1 (Enhanced Logging):

1. **Deploy the Enhanced DAG**
   ```bash
   # Copy to your NFS active node
   scp ha_service_health_monitor_enhanced.py rocky@10.101.20.165:/srv/airflow/dags/
   ```

2. **Verify Prerequisites**
   ```bash
   # On celery-1 and celery-2
   pip install psycopg2-binary pika --break-system-packages
   ```

3. **Test It**
   - Wait for DAG to appear in UI (30 seconds)
   - Trigger manually or wait for scheduled run
   - Simulate a failure to see log fetching in action

**See DEPLOYMENT_GUIDE.md for detailed instructions**

### For Issue 2 (Timezone Configuration):

1. **Set System Timezone on ALL Nodes**
   ```bash
   # On each node: haproxy-1, haproxy-2, scheduler-2, celery-1, celery-2, nfs-1, nfs-2
   sudo timedatectl set-timezone Asia/Tehran
   ```

2. **Update airflow.cfg on ALL Airflow Nodes**
   ```bash
   # Add to [core] section:
   default_timezone = Asia/Tehran
   
   # Add to [webserver] section:
   default_ui_timezone = Asia/Tehran
   ```

3. **Restart All Services**
   ```bash
   sudo systemctl restart airflow-scheduler
   sudo systemctl restart airflow-webserver
   sudo systemctl restart airflow-worker
   sudo systemctl restart airflow-dag-processor
   ```

4. **Clear Browser Cache**
   - Clear cache or use incognito mode
   - Log back into Airflow UI

**See TIMEZONE_CONFIGURATION_GUIDE.md for complete instructions**

---

## 📊 What Will Change

### After Deploying Enhanced DAG

**Before:**
```
Task Log:
❌ vsftpd on ftp (10.101.20.164) is INACTIVE

[You had to SSH manually to check journalctl]
```

**After:**
```
Task Log:
❌ vsftpd on ftp (10.101.20.164) is INACTIVE

Service Status Output:
------------------------------------------------------------
● vsftpd.service - Vsftpd ftp daemon
   Active: inactive (dead)
------------------------------------------------------------

================================================================================
📋 JOURNALCTL LOGS (Last 60 minutes):
================================================================================
Oct 28 13:45:23 ftp systemd[1]: Stopping Vsftpd ftp daemon...
Oct 28 13:45:23 ftp systemd[1]: vsftpd.service: Succeeded.
[... full service logs ...]

================================================================================
📋 AIRFLOW WORKER LOGS:
================================================================================
[2025-10-28, 14:30:00 +0330] {taskinstance.py:1234} INFO - Starting attempt 1 of 1
[... worker execution logs ...]

================================================================================
📋 AIRFLOW SCHEDULER LOGS:
================================================================================
Oct 28 14:29:58 scheduler-2 airflow-scheduler[23456]: INFO - Checking task instance
[... scheduler logs from both schedulers ...]

================================================================================
```

### After Fixing Timezone Configuration

**Before:**
- UI shows: `2025-10-28T07:51:00` (UTC)
- Logs show: `11:22:49 +0330` (Tehran)
- Confusion when correlating events

**After:**
- UI shows: `2025-10-28T11:21:49+03:30` (Tehran)
- Logs show: `11:22:49 +0330` (Tehran)
- Everything aligned to Asia/Tehran timezone

---

## 🎯 Implementation Priority

### High Priority (Do First):

1. **Fix Timezone** (30 minutes effort)
   - Affects all future DAGs and logging
   - No downtime required (just service restarts)
   - Follow TIMEZONE_CONFIGURATION_GUIDE.md

2. **Deploy Enhanced DAG** (15 minutes effort)
   - Immediate benefit for troubleshooting
   - Can run alongside existing DAG
   - Follow DEPLOYMENT_GUIDE.md

### Medium Priority (Do Soon):

3. **Test Failure Scenarios** (1 hour)
   - Intentionally stop a service
   - Verify logs are fetched correctly
   - Practice using QUICK_REFERENCE.md

4. **Train Team** (ongoing)
   - Share QUICK_REFERENCE.md with ops team
   - Review common scenarios together
   - Practice incident response

---

## ⚠️ Important Notes

### For Enhanced DAG:

- **No Downtime Required**: Deploy alongside existing DAG
- **Performance Impact**: ~5-15 seconds overhead per failed service (acceptable)
- **Sudo Required**: Workers need sudo access for journalctl and systemctl
- **SSH Required**: Workers need passwordless SSH to all nodes

### For Timezone Configuration:

- **Service Restarts Required**: Brief interruption during restart
- **Database Stays UTC**: This is correct Airflow behavior
- **All Nodes Must Match**: Inconsistent timezones cause confusion
- **Browser Cache**: Must clear after configuration changes

---

## 🔍 Verification

### Verify Enhanced DAG Works:

```bash
# 1. Check DAG appears in UI
curl -s http://10.101.20.210:8081/api/v1/dags/ha_service_health_monitor_enhanced | grep dag_id

# 2. Trigger test run
airflow dags trigger ha_service_health_monitor_enhanced

# 3. Stop a test service
ssh rocky@10.101.20.164 'sudo systemctl stop vsftpd'

# 4. Check task log shows diagnostic logs
# (View in Airflow UI - check_ftp_vsftpd task log)

# 5. Restore service
ssh rocky@10.101.20.164 'sudo systemctl start vsftpd'
```

### Verify Timezone Configuration:

```bash
# 1. Check system timezone on all nodes
for host in haproxy-1 haproxy-2 scheduler-2 celery-1 celery-2; do
    echo "=== $host ==="
    ssh rocky@$host 'timedatectl | grep "Time zone"'
done

# 2. Check Airflow config
ssh rocky@10.101.20.202 'grep "default_timezone" /home/rocky/airflow/airflow.cfg'

# 3. Check in UI
# - Login to http://10.101.20.210:8081
# - Check any DAG run timestamp
# - Should show "+03:30" timezone offset
```

---

## 📞 Support & Troubleshooting

If you encounter issues:

1. **Check Prerequisites**
   - Review DEPLOYMENT_GUIDE.md Prerequisites section
   - Verify all dependencies installed
   - Test SSH and sudo access

2. **Review Logs**
   - Enhanced DAG task logs show detailed diagnostics
   - Check scheduler logs: `journalctl -u airflow-scheduler -n 100`
   - Check worker logs: `journalctl -u airflow-worker -n 100`

3. **Common Issues**
   - See "Troubleshooting" section in DEPLOYMENT_GUIDE.md
   - See "Common Issues" section in TIMEZONE_CONFIGURATION_GUIDE.md
   - See specific scenarios in QUICK_REFERENCE.md

4. **Test Environment**
   - If possible, test in non-production first
   - Run side-by-side with existing DAG for 1 week
   - Validate before removing original DAG

---

## ✅ Success Checklist

After implementation, you should have:

**Enhanced Monitoring:**
- [ ] Enhanced DAG running every 15 minutes
- [ ] Failed services automatically show journalctl logs
- [ ] Failed tasks automatically show worker and scheduler logs
- [ ] No need to SSH manually for troubleshooting
- [ ] health_summary correctly categorizes failures

**Timezone Configuration:**
- [ ] All nodes show Asia/Tehran timezone
- [ ] Airflow UI shows times with +03:30 offset
- [ ] Task logs show +0330 timezone
- [ ] DAG schedules run at expected local times
- [ ] No confusion when correlating logs and UI

---

## 📚 Additional Resources

### External Documentation:
- Airflow Logging: https://airflow.apache.org/docs/apache-airflow/stable/logging-monitoring/logging-tasks.html
- Airflow Timezone: https://airflow.apache.org/docs/apache-airflow/stable/timezone.html
- Patroni HA: https://patroni.readthedocs.io/
- RabbitMQ Clustering: https://www.rabbitmq.com/clustering.html

### Your Original Files:
- Original DAG: `ha_service_health_monitor.py`
- Original README: `ha_service_health_monitor.md`
- Architecture: (from your initial upload)

---

## 🎉 Summary

You now have:

1. **Enhanced Health Monitor DAG** with automatic diagnostic log fetching
2. **Complete Timezone Configuration Guide** for consistent timestamp handling
3. **Deployment Guide** with step-by-step instructions
4. **Quick Reference Card** for incident response

**Estimated Implementation Time:**
- Timezone fix: 30 minutes
- Enhanced DAG deployment: 15 minutes
- Testing and validation: 1 hour
- **Total: ~2 hours for complete implementation**

**Benefits:**
- 🚀 Faster incident response (no manual SSH required)
- 🎯 Better root cause analysis (all logs in one place)
- ⏰ Consistent timezone handling (no confusion)
- 📊 Better operational visibility

**Next Steps:**
1. Read DEPLOYMENT_GUIDE.md
2. Read TIMEZONE_CONFIGURATION_GUIDE.md
3. Deploy and test
4. Share QUICK_REFERENCE.md with your team

Good luck with your implementation! 🎊
