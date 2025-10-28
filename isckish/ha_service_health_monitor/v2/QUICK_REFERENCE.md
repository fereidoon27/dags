# Quick Reference Card - Enhanced HA Health Monitor

## 🚨 Common Failure Scenarios & Solutions

### Scenario 1: Service Down on Active Node

**What you see in logs:**
```
🚨 CRITICAL: airflow-scheduler on ACTIVE node haproxy-1 is inactive (should be ACTIVE)!

📋 JOURNALCTL LOGS:
Oct 28 14:25:30 haproxy-1 systemd[1]: airflow-scheduler.service failed
Oct 28 14:25:30 haproxy-1 systemd[1]: airflow-scheduler.service: Main process exited, code=killed, status=9/KILL
```

**What to do:**
```bash
# SSH to the affected node
ssh rocky@10.101.20.202

# Check detailed status
sudo systemctl status airflow-scheduler

# View full logs
sudo journalctl -u airflow-scheduler -n 100 --no-pager

# Common fixes:
# 1. Restart the service
sudo systemctl restart airflow-scheduler

# 2. Check disk space
df -h

# 3. Check memory
free -h

# 4. Check if process is stuck
ps aux | grep airflow-scheduler
# If stuck, kill and restart:
sudo pkill -9 -f airflow-scheduler
sudo systemctl start airflow-scheduler
```

---

### Scenario 2: Database Connection Issues

**What you see in logs:**
```
❌ PostgreSQL VIP FAILED: could not connect to server: Connection refused

📋 Patroni logs from postgresql-1:
Oct 28 14:30:00 postgresql-1 patroni[1234]: ERROR: Connection to database failed
Oct 28 14:30:00 postgresql-1 patroni[1234]: FATAL: no pg_hba.conf entry for host
```

**What to do:**
```bash
# Check Patroni cluster status
ssh rocky@10.101.20.204
patronictl -c /etc/patroni/patroni.yml list

# Expected output:
#  Cluster  |  Member  |  Role   | State  | TL | Lag in MB
# ----------+----------+---------+--------+----+-----------
#  airflow  | pg-1     | Leader  | running| 5  |
#  airflow  | pg-2     | Replica | running| 5  | 0
#  airflow  | pg-3     | Replica | running| 5  | 0

# If no leader, check patroni logs:
sudo journalctl -u patroni -n 50

# Check PostgreSQL is listening on VIP:
sudo ss -tlnp | grep 5000

# Test connection manually:
export PGPASSWORD=airflow_pass
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db -c "SELECT 1;"

# Common fixes:
# 1. Restart patroni on all nodes
for ip in 10.101.20.204 10.101.20.166 10.101.20.137; do
    ssh rocky@$ip 'sudo systemctl restart patroni'
done

# 2. Check etcd cluster
ssh rocky@10.101.20.204
etcdctl member list
```

---

### Scenario 3: RabbitMQ Quorum Lost

**What you see in logs:**
```
❌ RabbitMQ QUORUM LOST: Only 1/3 nodes healthy

📋 RabbitMQ logs from rabbit-2:
Oct 28 14:30:00 rabbit-2 rabbitmq[5678]: Connection failed: authentication error
Oct 28 14:30:00 rabbit-2 rabbitmq[5678]: Node rabbit@rabbit-3 not reachable
```

**What to do:**
```bash
# Check cluster status from any RabbitMQ node
ssh rocky@10.101.20.205
sudo rabbitmqctl cluster_status

# Check if nodes can communicate
sudo rabbitmqctl eval 'net_adm:ping("rabbit@rabbit-2").'
sudo rabbitmqctl eval 'net_adm:ping("rabbit@rabbit-3").'

# Check RabbitMQ service on each node
for ip in 10.101.20.205 10.101.20.147 10.101.20.206; do
    echo "=== Node $ip ==="
    ssh rocky@$ip 'sudo systemctl status rabbitmq-server | head -5'
done

# Common fixes:
# 1. Restart failed nodes
ssh rocky@10.101.20.147 'sudo systemctl restart rabbitmq-server'

# 2. If node is permanently down, remove from cluster:
ssh rocky@10.101.20.205
sudo rabbitmqctl forget_cluster_node rabbit@rabbit-2

# 3. Re-add node to cluster:
ssh rocky@10.101.20.147
sudo systemctl stop rabbitmq-server
sudo rm -rf /var/lib/rabbitmq/mnesia/*
sudo systemctl start rabbitmq-server
sudo rabbitmqctl stop_app
sudo rabbitmqctl join_cluster rabbit@rabbit-1
sudo rabbitmqctl start_app
```

---

### Scenario 4: No Active Schedulers

**What you see in logs:**
```
❌ NO ACTIVE SCHEDULERS FOUND

📋 Scheduler logs from haproxy-1:
Oct 28 14:25:30 haproxy-1 airflow-scheduler[1234]: Scheduler heartbeat failed
Oct 28 14:25:35 haproxy-1 systemd[1]: airflow-scheduler.service: Main process exited

📋 Scheduler logs from scheduler-2:
Oct 28 14:26:00 scheduler-2 airflow-scheduler[5678]: Database connection lost
```

**What to do:**
```bash
# Check scheduler status on both nodes
ssh rocky@10.101.20.202 'sudo systemctl status airflow-scheduler'
ssh rocky@10.101.20.132 'sudo systemctl status airflow-scheduler'

# Check database connectivity from scheduler nodes
for ip in 10.101.20.202 10.101.20.132; do
    echo "=== Testing from $ip ==="
    ssh rocky@$ip 'export PGPASSWORD=airflow_pass; psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db -c "SELECT 1;"'
done

# Check for zombie processes
ssh rocky@10.101.20.202 'ps aux | grep airflow-scheduler | grep -v grep'

# Common fixes:
# 1. Restart both schedulers
ssh rocky@10.101.20.202 'sudo systemctl restart airflow-scheduler'
ssh rocky@10.101.20.132 'sudo systemctl restart airflow-scheduler'

# 2. Clear stale scheduler entries in DB
export PGPASSWORD=airflow_pass
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db <<EOF
DELETE FROM job WHERE job_type = 'SchedulerJob' AND state = 'running' 
AND latest_heartbeat < NOW() - INTERVAL '5 minutes';
EOF

# 3. Check for file permission issues
ssh rocky@10.101.20.202 'ls -la /home/rocky/airflow/airflow.cfg'
ssh rocky@10.101.20.202 'ls -la /airflow/dags/'
```

---

### Scenario 5: Celery Workers Not Available

**What you see in logs:**
```
❌ NO CELERY WORKERS AVAILABLE

📋 Worker logs from celery-1:
Oct 28 14:30:00 celery-1 airflow-worker[9012]: Connection to broker lost
Oct 28 14:30:05 celery-1 airflow-worker[9012]: Failed to connect to amqp://...
```

**What to do:**
```bash
# Check worker status
ssh rocky@10.101.20.199 'sudo systemctl status airflow-worker'
ssh rocky@10.101.20.200 'sudo systemctl status airflow-worker'

# Test RabbitMQ connectivity from workers
for ip in 10.101.20.199 10.101.20.200; do
    echo "=== Testing from worker $ip ==="
    ssh rocky@$ip 'python3 -c "
import pika
try:
    credentials = pika.PlainCredentials(\"airflow_user\", \"airflow_pass\")
    conn = pika.BlockingConnection(pika.ConnectionParameters(
        host=\"10.101.20.205\", port=5672, virtual_host=\"airflow_host\",
        credentials=credentials, socket_timeout=5))
    conn.close()
    print(\"✅ RabbitMQ connection OK\")
except Exception as e:
    print(f\"❌ Connection failed: {e}\")
"'
done

# Check Celery queue
ssh rocky@10.101.20.199
celery -A airflow.executors.celery_executor.app inspect active
celery -A airflow.executors.celery_executor.app inspect stats

# Common fixes:
# 1. Restart workers
for ip in 10.101.20.199 10.101.20.200; do
    ssh rocky@$ip 'sudo systemctl restart airflow-worker'
done

# 2. Clear stuck tasks in RabbitMQ
ssh rocky@10.101.20.205
sudo rabbitmqctl list_queues -p airflow_host
# If queue is full:
sudo rabbitmqctl purge_queue celery -p airflow_host

# 3. Check worker concurrency
ssh rocky@10.101.20.199 'grep worker_concurrency /home/rocky/airflow/airflow.cfg'
```

---

### Scenario 6: NFS Failover Issues (Split-Brain)

**What you see in logs:**
```
🚨 CRITICAL: nfs-server on PASSIVE node nfs-2 is ACTIVE (should be NOT ACTIVE)! Possible split-brain!
```

**What to do:**
```bash
# Check which node has the VIP
ssh rocky@10.101.20.165 'ip addr show | grep 10.101.20.220'
ssh rocky@10.101.20.203 'ip addr show | grep 10.101.20.220'

# Only ONE should have the VIP. If both have it = SPLIT BRAIN!

# Check keepalived status
ssh rocky@10.101.20.165 'sudo systemctl status keepalived'
ssh rocky@10.101.20.203 'sudo systemctl status keepalived'

# Check keepalived logs
ssh rocky@10.101.20.165 'sudo journalctl -u keepalived -n 50 --no-pager'

# Common fixes:
# 1. Determine which should be active (the one with VIP)
# 2. Stop services on passive node:
ssh rocky@10.101.20.203 'sudo systemctl stop nfs-server lsyncd airflow-dag-processor'

# 3. If split-brain, restart keepalived on both:
for ip in 10.101.20.165 10.101.20.203; do
    ssh rocky@$ip 'sudo systemctl restart keepalived'
done
sleep 10

# 4. Verify only one has VIP
ssh rocky@10.101.20.165 'ip addr show | grep 10.101.20.220'
ssh rocky@10.101.20.203 'ip addr show | grep 10.101.20.220'
```

---

### Scenario 7: HAProxy Load Balancer Issues

**What you see in logs:**
```
❌ haproxy on haproxy-1 (10.101.20.202) is inactive

📋 JOURNALCTL LOGS:
Oct 28 14:30:00 haproxy-1 haproxy[3456]: Configuration error detected
Oct 28 14:30:00 haproxy-1 systemd[1]: haproxy.service: Main process exited
```

**What to do:**
```bash
# Check HAProxy configuration
ssh rocky@10.101.20.202 'sudo haproxy -c -f /etc/haproxy/haproxy.cfg'

# If config is OK, check what's blocking:
ssh rocky@10.101.20.202 'sudo ss -tlnp | grep :8081'

# Check HAProxy logs
ssh rocky@10.101.20.202 'sudo journalctl -u haproxy -n 100 --no-pager'

# Test backend servers from HAProxy node
ssh rocky@10.101.20.202
for ip in 10.101.20.202 10.101.20.146; do
    echo "Testing webserver on $ip..."
    curl -I http://$ip:8080
done

# Common fixes:
# 1. Fix configuration and restart
ssh rocky@10.101.20.202 'sudo systemctl restart haproxy'

# 2. Check if VIP is accessible
ping 10.101.20.210

# 3. Test direct access to webserver
curl http://10.101.20.202:8080
curl http://10.101.20.146:8080

# 4. Check keepalived is managing VIP
ssh rocky@10.101.20.202 'ip addr show | grep 10.101.20.210'
```

---

## ⚡ Quick Commands Cheat Sheet

### Service Management
```bash
# Restart scheduler
sudo systemctl restart airflow-scheduler

# Restart webserver
sudo systemctl restart airflow-webserver

# Restart worker
sudo systemctl restart airflow-worker

# Restart all Airflow services
for svc in scheduler webserver worker dag-processor; do
    sudo systemctl restart airflow-$svc 2>/dev/null || true
done
```

### Log Viewing
```bash
# Last 50 lines of service logs
sudo journalctl -u SERVICE_NAME -n 50 --no-pager

# Follow logs in real-time
sudo journalctl -u SERVICE_NAME -f

# Logs from last hour
sudo journalctl -u SERVICE_NAME --since '1 hour ago'

# Logs with timestamp
sudo journalctl -u SERVICE_NAME --since '2025-10-28 14:00:00'
```

### Database Queries
```bash
# Connect to database
export PGPASSWORD=airflow_pass
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db

# Check active schedulers
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db -c \
  "SELECT hostname, latest_heartbeat FROM job WHERE job_type = 'SchedulerJob' AND state = 'running';"

# Check running tasks
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db -c \
  "SELECT dag_id, task_id, state FROM task_instance WHERE state = 'running';"
```

### Cluster Status
```bash
# PostgreSQL cluster
ssh rocky@10.101.20.204 'patronictl -c /etc/patroni/patroni.yml list'

# RabbitMQ cluster
ssh rocky@10.101.20.205 'sudo rabbitmqctl cluster_status'

# Celery workers
ssh rocky@10.101.20.199 'celery -A airflow.executors.celery_executor.app inspect active'

# NFS VIP location
for ip in 10.101.20.165 10.101.20.203; do
    echo -n "$ip: "
    ssh rocky@$ip 'ip addr show | grep 10.101.20.220 > /dev/null && echo "HAS VIP" || echo "no vip"'
done
```

### Health Checks
```bash
# Check all services on a node
ssh rocky@NODE_IP 'sudo systemctl status airflow-* haproxy keepalived nfs-server patroni etcd rabbitmq-server lsyncd 2>/dev/null | grep "Active:"'

# Test database connectivity
export PGPASSWORD=airflow_pass
psql -h 10.101.20.210 -U airflow_user -p 5000 -d airflow_db -c "SELECT 1;"

# Test RabbitMQ connectivity
python3 -c "import pika; credentials = pika.PlainCredentials('airflow_user', 'airflow_pass'); conn = pika.BlockingConnection(pika.ConnectionParameters(host='10.101.20.205', port=5672, virtual_host='airflow_host', credentials=credentials)); conn.close(); print('OK')"

# Check Airflow UI access
curl -I http://10.101.20.210:8081

# Trigger health check DAG manually
airflow dags trigger ha_service_health_monitor_enhanced
```

---

## 🎯 Priority Matrix

| Issue                    | Severity | MTTR Target | First Action                        |
|--------------------------|----------|-------------|-------------------------------------|
| Database down            | P0       | < 5 min     | Check Patroni cluster, restart DB   |
| No active schedulers     | P0       | < 5 min     | Restart schedulers                  |
| RabbitMQ quorum lost     | P0       | < 10 min    | Identify failed node, restart       |
| NFS split-brain          | P1       | < 15 min    | Stop passive services, check VIP    |
| Worker down              | P1       | < 10 min    | Restart worker, check RabbitMQ      |
| Single HAProxy down      | P2       | < 30 min    | Check config, restart service       |
| Webserver down           | P2       | < 20 min    | Restart webserver                   |
| FTP server down          | P3       | < 1 hour    | Check vsftpd, restart               |

---

**Keep this card handy for quick incident response!**
