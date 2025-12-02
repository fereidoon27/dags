# Lesson 08: Task Implementation Patterns

## Overview

This lesson covers real-world task implementations: checking services, testing network connectivity, handling failures, and comprehensive error reporting with logs.

**Key learning:**
- Service health checking with systemctl
- Network connectivity testing (PostgreSQL, RabbitMQ)
- AirflowException for task failures
- Conditional error handling patterns
- XCom for failure classification

---

## Service Health Check Pattern (Lines 665-741)

### Basic Service Check

```python
for service in services:
    status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
    result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
    service_status = result.stdout.strip()
    
    if service_status != 'active':
        # Service is down - handle error
```

**systemctl is-active:**
- Returns: `active`, `inactive`, `failed`, `unknown`
- Exit code 0 = active, non-zero = not active
- We check the output string, not the exit code

**Example outputs:**
```bash
sudo systemctl is-active nginx
# active (service running)

sudo systemctl is-active postgresql
# inactive (service stopped)

sudo systemctl is-active nonexistent
# unknown (service doesn't exist)
```

---

## 🎓 AIRFLOW CONCEPT: Task Failure Strategy

**When to fail a task:**
Tasks should fail (raise exception) when critical conditions aren't met. This stops the DAG and alerts operators.

**Failure types:**

```python
# 1. Critical failure - raise immediately
if database_down:
    raise AirflowException("Database unreachable!")

# 2. Expected failure - classify and raise
if passive_node_inactive:
    ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE')
    raise AirflowException("Passive node inactive (expected)")

# 3. Partial failure - track and decide
failures = []
for service in services:
    if not check(service):
        failures.append(f"{service} down")

if failures:
    raise AirflowException('\n'.join(failures))
```

**Why raise exceptions?**
- Stops DAG execution
- Marks task as failed (red in UI)
- Triggers alerts/notifications
- Prevents dependent tasks from running

---

## Comprehensive Error Reporting (Lines 672-691)

### Building Rich Error Messages

```python
if service_status != 'active':
    error_msg = f"🚨 CRITICAL: {service} on ACTIVE node {hostname} is {service_status.upper()}\n"
    
    # Get task identifiers
    identifiers = get_task_identifiers(context)
    
    # Fetch service logs
    logs = fetch_service_logs(ip, service, hostname, lines=100)
    error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
    
    # Fetch task-specific logs
    try:
        task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
        error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
        
        worker_logs = fetch_airflow_worker_logs()
        error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
    except Exception as log_error:
        error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
    
    all_failures.append(error_msg)
    has_critical_failure = True
```

**Error message structure:**
1. **Header** - What failed
2. **Service logs** - System service output (journalctl)
3. **Task-specific logs** - Airflow logs related to this task
4. **Worker logs** - Execution logs from this worker

**Why comprehensive?**
- Debugging without SSH access
- All context in one place
- Airflow UI shows full error message
- Faster incident resolution

**Nested try/except:**
```python
# Outer try - main logic
try:
    result = check_service()
    
    if result.failed:
        # Inner try - log collection (don't fail task if logs unavailable)
        try:
            logs = fetch_logs()
        except Exception as log_error:
            logs = f"Couldn't fetch logs: {log_error}"
        
        raise AirflowException(f"Service failed\n{logs}")
except Exception as e:
    # Outer except - task failure
    raise
```

---

## Conditional Logic: Active vs Passive Nodes (Lines 670-719)

### HA Split-Brain Prevention

```python
active_only_services = ['nfs-server', 'lsyncd', 'airflow-dag-processor']

for hostname, config in NFS_NODES.items():
    is_active_node = (hostname == active_nfs_node)
    
    for service in services:
        if service in active_only_services:
            if is_active_node:
                # Active node - service MUST be active
                if service_status != 'active':
                    has_critical_failure = True
                    print(f"❌ {service}: CRITICAL - {service_status}")
                else:
                    print(f"✅ {service}: ACTIVE")
            else:
                # Passive node - service MUST NOT be active
                if service_status == 'active':
                    has_critical_failure = True
                    print(f"❌ {service}: CRITICAL - SPLIT BRAIN")
                else:
                    print(f"⏸️ {service}: NOT ACTIVE (expected)")
                    has_expected_passive_failure = True
```

**Split-brain scenario:**
Both nodes think they're active → data corruption risk

**Validation matrix:**

| Node | Service Status | Expected | Action |
|------|---------------|----------|--------|
| Active | active | ✅ Yes | Continue |
| Active | inactive | ❌ No | CRITICAL |
| Passive | active | ❌ No | CRITICAL (split-brain) |
| Passive | inactive | ✅ Yes | Expected |

**Multiple failure tracking:**
```python
all_failures = []
has_critical_failure = False
has_expected_passive_failure = False

# Collect all failures
for item in items:
    if item.failed_critically:
        all_failures.append(error_message)
        has_critical_failure = True
    elif item.expected_failure:
        has_expected_passive_failure = True

# Decide final action
if has_critical_failure:
    raise AirflowException('\n'.join(all_failures))
elif has_expected_passive_failure:
    # Still raise, but mark as expected
    ti.xcom_push(key='failure_type', value='EXPECTED')
    raise AirflowException("Expected failure")
```

---

## Database Connectivity Check (Lines 1098-1129)

### PostgreSQL Connection Test

```python
@task(task_id="check_postgresql_vip")
def check_postgresql_vip():
    try:
        conn = psycopg2.connect(
            host='10.101.20.210',
            port=5000,
            database='airflow_db',
            user='airflow_user',
            password='airflow_pass',
            connect_timeout=5
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dag;")
        dag_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"✅ PostgreSQL VIP is HEALTHY - {dag_count} DAGs")
        return {'status': 'healthy', 'dags': dag_count}
    except Exception as e:
        error_msg = f"❌ PostgreSQL VIP FAILED: {str(e)}\n"
        
        # Check individual nodes
        for hostname, ip in [('postgresql-1', '10.101.20.204'), ...]:
            try:
                logs = fetch_service_logs(ip, 'patroni', hostname, lines=100)
                error_msg += f"\n{'='*80}\n📋 Patroni logs from {hostname}:\n{'='*80}\n{logs}\n"
            except:
                pass
        
        raise AirflowException(error_msg)
```

**psycopg2 connection flow:**
1. Connect with timeout
2. Create cursor (execute queries)
3. Execute test query
4. Fetch results
5. Close cursor and connection

**Why test query?**
- Connection might succeed but DB is unhealthy
- Query confirms DB is actually working
- Using real table (dag) confirms schema exists

**Connection parameters:**
```python
psycopg2.connect(
    host='10.0.0.1',        # Server IP/hostname
    port=5432,              # PostgreSQL port
    database='mydb',         # Database name
    user='username',         # Auth user
    password='pass',         # Auth password
    connect_timeout=5        # Max seconds to wait
)
```

---

## 🎓 TIP: psycopg2 Basics

**Common operations:**

```python
import psycopg2

# Connect
conn = psycopg2.connect(
    host='localhost',
    database='mydb',
    user='user',
    password='pass'
)

# Execute query
cur = conn.cursor()
cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
rows = cur.fetchall()  # All rows
row = cur.fetchone()   # Single row

# Insert data
cur.execute("INSERT INTO logs (message) VALUES (%s)", (msg,))
conn.commit()  # Save changes

# Close
cur.close()
conn.close()
```

**Always use parameterized queries:**
```python
# ❌ SQL injection risk
cur.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

# ✅ Safe
cur.execute("SELECT * FROM users WHERE name = %s", (user_input,))
```

---

## RabbitMQ Connectivity Check (Lines 1130-1169)

### Message Queue Cluster Test

```python
@task(task_id="check_rabbitmq_cluster")
def check_rabbitmq_cluster():
    nodes = [
        ('rabbit-1', '10.101.20.205'),
        ('rabbit-2', '10.101.20.147'),
        ('rabbit-3', '10.101.20.206')
    ]
    
    results = []
    for name, ip in nodes:
        try:
            credentials = pika.PlainCredentials('airflow_user', 'airflow_pass')
            conn = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=ip, port=5672, virtual_host='airflow_host',
                    credentials=credentials, socket_timeout=5
                )
            )
            conn.close()
            results.append({'node': name, 'status': 'healthy'})
            print(f"✅ {name} ({ip}) RabbitMQ is HEALTHY")
        except Exception as e:
            results.append({'node': name, 'status': 'failed', 'error': str(e)})
            print(f"❌ {name} ({ip}) RabbitMQ FAILED: {str(e)}")
    
    healthy = sum(1 for r in results if r['status'] == 'healthy')
    
    if healthy < 2:
        error_msg = f"❌ RabbitMQ QUORUM LOST: Only {healthy}/3 nodes healthy\n"
        # Fetch logs...
        raise AirflowException(error_msg)
    
    print(f"✅ RabbitMQ Cluster: {healthy}/3 nodes healthy")
    return {'healthy_nodes': healthy, 'total': 3, 'nodes': results}
```

**pika connection flow:**
1. Create credentials object
2. Create connection parameters
3. Establish blocking connection
4. Close connection (test successful)

**Quorum logic:**
- 3-node cluster needs 2 healthy for quorum
- `if healthy < 2:` → not enough nodes
- Quorum = majority needed for cluster decisions

**Sum with generator:**
```python
healthy = sum(1 for r in results if r['status'] == 'healthy')

# Equivalent to:
healthy = 0
for r in results:
    if r['status'] == 'healthy':
        healthy += 1
```

---

## 🎓 TIP: pika RabbitMQ Client

**Basic usage:**

```python
import pika

# Connect
credentials = pika.PlainCredentials('user', 'pass')
params = pika.ConnectionParameters(
    host='localhost',
    port=5672,
    virtual_host='/',
    credentials=credentials,
    socket_timeout=5
)
conn = pika.BlockingConnection(params)
channel = conn.channel()

# Declare queue
channel.queue_declare(queue='tasks')

# Publish message
channel.basic_publish(
    exchange='',
    routing_key='tasks',
    body='Task data'
)

# Consume message
def callback(ch, method, properties, body):
    print(f"Received: {body}")

channel.basic_consume(
    queue='tasks',
    on_message_callback=callback,
    auto_ack=True
)

# Close
conn.close()
```

---

## Failure Classification with XCom (Lines 744-748)

### Marking Expected Failures

```python
if has_critical_failure:
    ti.xcom_push(key='failure_type', value='CRITICAL_NFS_FAILURE')
    raise AirflowException('\n'.join(all_failures))
elif has_expected_passive_failure:
    ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE_INACTIVE')
    raise AirflowException(f"⏸️ EXPECTED: Passive NFS node services are correctly NOT ACTIVE")
```

**Why classify failures?**
- Summary task can distinguish critical vs expected
- Reporting shows accurate health status
- Don't count expected failures as problems

**In summary task (Lines 1269-1276):**
```python
for failed_task in failed_tasks:
    failure_type = failed_task.xcom_pull(task_ids=failed_task.task_id, key='failure_type')
    
    if failure_type == 'EXPECTED_PASSIVE_INACTIVE':
        expected_passive_failures.append(failed_task)
    else:
        critical_failures.append(failed_task)
```

**Result:**
```
✅ Successful: 10
❌ Total Failed: 4
   ├─ Critical Failures: 1
   └─ Expected Passive Failures: 3
```

---

## Key Takeaways

✅ **systemctl is-active** - Standard service health check

✅ **AirflowException** - Fail tasks with detailed messages

✅ **Comprehensive errors** - Include all relevant logs

✅ **Nested try/except** - Don't fail on log collection errors

✅ **Network testing** - psycopg2 for DB, pika for RabbitMQ

✅ **Quorum logic** - Cluster health requires majority

✅ **Failure classification** - XCom to mark expected failures

✅ **Split-brain prevention** - Validate active/passive states

---

## What's Next?

Lesson 09 will cover:
- Summary task patterns
- Trigger rules (all_done)
- XCom pulling from multiple tasks
- Final status checks
- Task state inspection

**Ready to continue?** 🚀
