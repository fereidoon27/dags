# Lesson 08 Cheatsheet: Task Implementation Patterns

## Service Health Check
```python
# Check with systemctl
cmd = f"ssh user@{ip} 'sudo systemctl is-active {service}'"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
status = result.stdout.strip()

if status != 'active':
    raise AirflowException(f"{service} is {status}")
```

## AirflowException
```python
from airflow.exceptions import AirflowException

# Basic failure
if service_down:
    raise AirflowException("Service is down")

# With detailed message
error_msg = f"Critical failure\n"
error_msg += fetch_logs()
raise AirflowException(error_msg)

# Multiple failures
failures = []
for item in items:
    if item.failed:
        failures.append(f"{item} failed")

if failures:
    raise AirflowException('\n'.join(failures))
```

## Error Message Building
```python
# Start with header
error_msg = f"🚨 CRITICAL: {service} failed\n"

# Add logs
logs = fetch_service_logs(ip, service)
error_msg += f"\n{'='*80}\n📋 LOGS:\n{'='*80}\n{logs}\n"

# Nested try for optional logs
try:
    extra_logs = fetch_extra_logs()
    error_msg += f"\n{extra_logs}\n"
except Exception as e:
    error_msg += f"\n⚠️ Couldn't fetch extra logs: {e}\n"

# Raise with complete message
raise AirflowException(error_msg)
```

## PostgreSQL Connection
```python
import psycopg2

# Connect and test
try:
    conn = psycopg2.connect(
        host='10.0.0.1',
        port=5432,
        database='mydb',
        user='user',
        password='pass',
        connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM table")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"✅ DB healthy - {count} rows")
except Exception as e:
    raise AirflowException(f"DB failed: {e}")
```

## RabbitMQ Connection
```python
import pika

# Test connection
try:
    credentials = pika.PlainCredentials('user', 'pass')
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='10.0.0.1',
            port=5672,
            virtual_host='/',
            credentials=credentials,
            socket_timeout=5
        )
    )
    conn.close()
    print("✅ RabbitMQ healthy")
except Exception as e:
    raise AirflowException(f"RabbitMQ failed: {e}")
```

## Quorum Checking
```python
nodes = [('node1', 'ip1'), ('node2', 'ip2'), ('node3', 'ip3')]
results = []

for name, ip in nodes:
    try:
        test_connection(ip)
        results.append({'node': name, 'status': 'healthy'})
    except Exception as e:
        results.append({'node': name, 'status': 'failed'})

healthy = sum(1 for r in results if r['status'] == 'healthy')

if healthy < 2:  # Need 2/3 for quorum
    raise AirflowException(f"Quorum lost: {healthy}/3 healthy")
```

## Failure Classification
```python
from airflow.operators.python import get_current_context

context = get_current_context()
ti = context['task_instance']

# Mark failure type
if critical_failure:
    ti.xcom_push(key='failure_type', value='CRITICAL')
    raise AirflowException("Critical failure")
elif expected_failure:
    ti.xcom_push(key='failure_type', value='EXPECTED')
    raise AirflowException("Expected failure")
```

## Active/Passive Validation
```python
active_only_services = ['service1', 'service2']

for node in nodes:
    is_active = (node == active_node)
    
    for service in services:
        status = check_status(service)
        
        if service in active_only_services:
            if is_active:
                # Must be active
                if status != 'active':
                    raise AirflowException(f"{service} down on active")
            else:
                # Must NOT be active
                if status == 'active':
                    raise AirflowException(f"Split-brain: {service} on passive")
```

## Multiple Failure Tracking
```python
all_failures = []
has_critical = False

for item in items:
    if not check(item):
        error = f"{item} failed\n{get_logs(item)}"
        all_failures.append(error)
        has_critical = True

if has_critical:
    raise AirflowException('\n'.join(all_failures))
```

## Common Patterns

### Service Check with Logs
```python
@task
def check_service():
    status = check_systemctl('nginx')
    
    if status != 'active':
        error = f"nginx is {status}\n"
        error += fetch_service_logs('nginx')
        raise AirflowException(error)
    
    return {'status': 'healthy'}
```

### Cluster Health Check
```python
@task
def check_cluster():
    results = []
    
    for node in cluster_nodes:
        try:
            test_node(node)
            results.append({'node': node, 'ok': True})
        except:
            results.append({'node': node, 'ok': False})
    
    healthy = sum(1 for r in results if r['ok'])
    
    if healthy < required_quorum:
        raise AirflowException(f"Cluster unhealthy: {healthy}/{len(results)}")
    
    return {'healthy': healthy, 'total': len(results)}
```

### Network Connectivity Test
```python
@task
def test_database():
    try:
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_pass,
            connect_timeout=5
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {'status': 'healthy'}
    except Exception as e:
        raise AirflowException(f"DB unreachable: {e}")
```

## Quick Reference

| Pattern | Use Case |
|---------|----------|
| `systemctl is-active` | Service health |
| `psycopg2.connect()` | Database connectivity |
| `pika.BlockingConnection()` | RabbitMQ connectivity |
| `raise AirflowException()` | Fail task |
| `ti.xcom_push()` | Classify failure |
| Quorum check | Cluster health |
| Nested try/except | Optional log collection |

## systemctl Status Values

| Status | Meaning |
|--------|---------|
| `active` | Running |
| `inactive` | Stopped |
| `failed` | Crashed |
| `unknown` | Doesn't exist |

## Troubleshooting

### Task doesn't fail on error
```python
# ❌ Print error
if failed:
    print("Error!")  # Task still succeeds

# ✅ Raise exception
if failed:
    raise AirflowException("Error!")
```

### Lost error context
```python
# ❌ Generic error
raise AirflowException("Something failed")

# ✅ Include details
error = f"Service {name} failed\n"
error += f"Status: {status}\n"
error += f"Logs:\n{logs}"
raise AirflowException(error)
```

### Log fetch failure breaks task
```python
# ❌ Log failure stops task
logs = fetch_logs()  # Might fail
raise AirflowException(f"Failed\n{logs}")

# ✅ Handle log fetch errors
try:
    logs = fetch_logs()
except Exception as e:
    logs = f"Couldn't get logs: {e}"
raise AirflowException(f"Failed\n{logs}")
```

### Connection doesn't timeout
```python
# ❌ No timeout
conn = psycopg2.connect(host=host)  # Hangs forever

# ✅ With timeout
conn = psycopg2.connect(
    host=host,
    connect_timeout=5
)
```
