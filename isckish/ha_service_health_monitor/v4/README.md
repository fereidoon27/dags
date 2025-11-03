# Enhanced HA Health Monitor v3 - Complete Package

## 📦 What's Included

This package contains your enhanced Airflow HA Infrastructure Health Monitor with all issues fixed and new monitoring capabilities added.

### Files in This Package

1. **ha_service_health_monitor_enhanced_v3.py** (38 KB)
   - The complete, production-ready DAG
   - All issues fixed
   - New monitoring features included

2. **DEPLOYMENT_GUIDE.md** (19 KB)
   - Step-by-step deployment instructions
   - Detailed explanation of all changes
   - Troubleshooting guide
   - Comparison table: v2 vs v3

3. **AIRFLOW_LOGS_GUIDE.md** (24 KB)
   - Comprehensive guide to understanding Airflow logs
   - Architecture diagrams
   - Log analysis patterns
   - Troubleshooting workflows
   - Best practices

---

## 🎯 Quick Start

1. **Read DEPLOYMENT_GUIDE.md first** - It explains all changes and how to deploy
2. **Deploy ha_service_health_monitor_enhanced_v3.py** to your DAGs folder
3. **Keep AIRFLOW_LOGS_GUIDE.md handy** - Reference it when analyzing logs

---

## ✅ What Was Fixed

### 1. Duplicate Log Entries
- **Before**: Same lines appeared 2-4 times in logs
- **After**: Each log line appears only once
- **How**: Added deduplication logic using sets

### 2. [Invalid date] Artifacts
- **Before**: `[Invalid date]` appeared in journalctl output
- **After**: Proper timestamps in all logs
- **How**: Changed from `short-iso` to `short-precise` format

---

## 🆕 New Features

### 1. System Resource Monitoring (`check_system_resources` task)

Monitors all Airflow nodes every 2 minutes:

- **CPU**: Usage percentage, available percentage, top 5 processes
- **RAM**: Used/Total/Available, percentage, top 5 processes  
- **Disk**: Used/Total, percentage for root partition

**Automatic warnings** when resources exceed thresholds:
- CPU > 90%
- Memory > 90%
- Disk > 85%

### 2. Airflow Logs Size Monitoring (`check_airflow_logs_size` task)

Tracks log directory size on all nodes:

- Per-node log sizes (human-readable + MB/GB)
- Total logs size across all nodes
- Automatic warnings for large log directories (>5GB)

---

## 📊 Sample Output

### Healthy System
```
✅ All services active
📊 CPU: 45% | RAM: 39% | Disk: 45%
📁 Total logs: 8.2 GB across all nodes
🏥 HEALTH CHECK SUMMARY: 0 critical failures
```

### With Issues Detected
```
❌ celery-2 - airflow-worker is NOT ACTIVE
[Automatic log collection included]

⚠️ RESOURCE WARNINGS:
  ⚠️ celery-2: HIGH MEMORY usage (95.20%)

🚨 DAG FAILED: 1 critical service down
```

---

## 🎓 Learning Resources

### For Understanding Airflow

**Start here if you're new to Airflow logs**:
1. Read AIRFLOW_LOGS_GUIDE.md sections 1-3
   - Understand the architecture
   - Learn about log types
   - Know where logs are stored

2. Watch your DAG run once
   - Look at each task in the UI
   - See how logs are organized
   - Understand the flow

### For Analyzing Your Logs

**When you see a failure**:
1. Go to AIRFLOW_LOGS_GUIDE.md section 4
   - "Analyzing Your Health Monitor Logs"
   - Pattern recognition guide

2. Check section 5
   - "Common Patterns & What They Mean"
   - Real examples from your system

3. Use section 6
   - "Troubleshooting Guide"
   - Step-by-step problem solving

---

## 🔧 Deployment Checklist

- [ ] Read DEPLOYMENT_GUIDE.md completely
- [ ] Backup current DAG (ha_service_health_monitor_enhanced_v2.py)
- [ ] Copy new DAG to `/home/rocky/airflow/dags/`
- [ ] Verify DAG appears in UI without errors
- [ ] Pause old DAG, enable new DAG
- [ ] Trigger manual test run
- [ ] Verify no duplicates in logs
- [ ] Verify no [Invalid date] in logs
- [ ] Check resource monitoring report appears
- [ ] Check logs size report appears
- [ ] Monitor for 10 minutes (5 runs)
- [ ] Set up email alerts (optional)

---

## 📈 What to Monitor

### Daily
- Check DAG runs in UI
- Look for critical failures
- Review any resource warnings

### Weekly
- Review resource trends
- Check logs size growth
- Identify top resource-consuming processes

### Monthly
- Clean up old logs if needed
- Adjust resource thresholds if needed
- Review and optimize based on patterns

---

## 🆘 Need Help?

### First Steps
1. Check AIRFLOW_LOGS_GUIDE.md for your specific issue
2. Look at the task logs in Airflow UI
3. Review the automatic diagnostic logs included in failures

### Common Issues & Quick Fixes

**Issue**: Resource monitoring shows errors
- **Check**: SSH connectivity from scheduler to all nodes
- **Fix**: `ssh-copy-id rocky@<node-ip>` for each node

**Issue**: Logs size monitoring not working
- **Check**: Path exists: `/home/rocky/airflow/logs`
- **Fix**: Verify permissions and path on all nodes

**Issue**: Still seeing duplicates
- **Check**: Make sure you're running v3, not v2
- **Verify**: DAG ID should be `ha_service_health_monitor_enhanced_v3`

---

## 💡 Pro Tips

1. **Keep the Logs Guide Open**: Bookmark AIRFLOW_LOGS_GUIDE.md in your browser for quick reference

2. **Watch Resources Over Time**: After a week, you'll see patterns in resource usage

3. **Set Alert Thresholds**: Adjust the warning levels (90%, 85%) based on your normal usage

4. **Use the Top Processes**: They help identify which tasks consume the most resources

5. **Regular Log Cleanup**: Don't let logs grow indefinitely; clean them monthly

---

## 📚 File Descriptions

### ha_service_health_monitor_enhanced_v3.py

**Purpose**: Production DAG file
**Size**: 38 KB (807 lines)
**Key Functions**:
- Service health monitoring (all existing functionality)
- System resource monitoring (NEW)
- Logs size monitoring (NEW)
- Automatic log collection on failures
- Deduplication and date formatting fixes

**Configuration Constants**:
- `SERVERS`: All server nodes with their services
- `NFS_NODES`: NFS nodes with HA awareness
- `AIRFLOW_MONITORING_NODES`: Nodes for resource monitoring
- `AIRFLOW_LOGS_PATH`: Path to monitor for log sizes

### DEPLOYMENT_GUIDE.md

**Purpose**: Complete deployment documentation
**Sections**:
- Detailed changelog (what was fixed)
- New features explanation
- Step-by-step deployment
- Troubleshooting guide
- Performance considerations
- Maintenance schedule

**When to use**: Before and during deployment

### AIRFLOW_LOGS_GUIDE.md

**Purpose**: Educational resource for understanding Airflow
**Sections**:
- Airflow architecture explained
- Log types and locations
- Log analysis techniques
- Common patterns dictionary
- Troubleshooting workflows
- Best practices

**When to use**: 
- When learning Airflow (first time)
- When analyzing failures (reference)
- When training new team members

---

## 🎉 Summary

You now have:
- ✅ A production-ready, enhanced health monitoring DAG
- ✅ All issues fixed (duplicates, [Invalid date])
- ✅ New system resource monitoring
- ✅ New logs size monitoring  
- ✅ Comprehensive documentation
- ✅ Educational guide for Airflow logs

**Next Step**: Start with DEPLOYMENT_GUIDE.md and follow the checklist!

---

## 📞 Quick Reference

| Document | Use When |
|----------|----------|
| **DEPLOYMENT_GUIDE.md** | Deploying, understanding changes |
| **AIRFLOW_LOGS_GUIDE.md** | Analyzing logs, troubleshooting |
| **This README** | Quick overview, getting started |

**Most Important**: All three documents work together to give you complete coverage of your monitoring system!

---

Good luck with your deployment! 🚀
