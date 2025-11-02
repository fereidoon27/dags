"""
Airflow HA Infrastructure Health Monitor - v3 IMPROVED
Key improvements:
- Fixed duplicate log entries
- Better timestamp handling
- Deduplicated output
- Cleaner log formatting
- Reduced verbosity
- Better error handling
"""
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from airflow.operators.python import get_current_context
import psycopg2
import pika
import subprocess
import socket
import platform
import os
import glob
import re


# Server and service configuration
SERVERS = {
    'haproxy-1': {
        'ip': '10.101.20.202',
        'services': ['airflow-scheduler', 'airflow-webserver', 'haproxy', 'keepalived']
    },
    'haproxy-2': {
        'ip': '10.101.20.146',
        'services': ['airflow-webserver', 'haproxy', 'keepalived']
    },
    'scheduler-2': {
        'ip': '10.101.20.132',
        'services': ['airflow-scheduler']
    },
    'rabbit-1': {
        'ip': '10.101.20.205',
        'services': ['rabbitmq-server']
    },
    'rabbit-2': {
        'ip': '10.101.20.147',
        'services': ['rabbitmq-server']
    },
    'rabbit-3': {
        'ip': '10.101.20.206',
        'services': ['rabbitmq-server']
    },
    'postgresql-1': {
        'ip': '10.101.20.204',
        'services': ['patroni', 'etcd']
    },
    'postgresql-2': {
        'ip': '10.101.20.166',
        'services': ['patroni', 'etcd']
    },
    'postgresql-3': {
        'ip': '10.101.20.137',
        'services': ['patroni', 'etcd']
    },
    'celery-1': {
        'ip': '10.101.20.199',
        'services': ['airflow-worker']
    },
    'celery-2': {
        'ip': '10.101.20.200',
        'services': ['airflow-worker']
    },
    'ftp': {
        'ip': '10.101.20.164',
        'services': ['vsftpd']
    },
}

# NFS nodes handled separately due to active/passive HA
NFS_NODES = {
    'nfs-1': {
        'ip': '10.101.20.165',
        'services': ['airflow-dag-processor', 'nfs-server', 'lsyncd', 'keepalived']
    },
    'nfs-2': {
        'ip': '10.101.20.203',
        'services': ['airflow-dag-processor', 'nfs-server', 'lsyncd', 'keepalived']
    },
}

# Airflow log paths
AIRFLOW_HOME = '/home/rocky/airflow'
AIRFLOW_LOGS_BASE = f'{AIRFLOW_HOME}/logs'


def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except:
        return socket.gethostname()


def deduplicate_lines(text: str) -> str:
    """
    Remove duplicate consecutive lines from log output.
    Keeps only unique lines while maintaining order.
    """
    if not text:
        return text
    
    lines = text.split('\n')
    seen = set()
    result = []
    
    for line in lines:
        # Strip whitespace for comparison but keep original formatting
        line_key = line.strip()
        if line_key and line_key not in seen:
            seen.add(line_key)
            result.append(line)
        elif not line_key:  # Keep empty lines for readability
            result.append(line)
    
    return '\n'.join(result)


def clean_timestamp_artifacts(text: str) -> str:
    """
    Remove [Invalid date] and other timestamp artifacts from logs.
    Replace with proper timestamp format or remove entirely.
    """
    if not text:
        return text
    
    # Remove [Invalid date] artifacts
    text = re.sub(r'\[Invalid date\]\s*', '', text)
    
    # Remove duplicate timestamps on same line
    text = re.sub(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{4})\s+\1', r'\1', text)
    
    return text


def get_task_identifiers(context=None):
    """
    Extract unique identifiers for task instance tracing across system logs.
    Returns dict with all available identifiers.
    """
    if context is None:
        try:
            context = get_current_context()
        except:
            return {}
    
    identifiers = {}
    
    try:
        ti = context.get('ti')
        if ti:
            identifiers['dag_id'] = ti.dag_id
            identifiers['task_id'] = ti.task_id
            identifiers['run_id'] = ti.run_id
            identifiers['execution_date'] = str(ti.execution_date)
            identifiers['try_number'] = ti.try_number
            identifiers['job_id'] = ti.job_id if hasattr(ti, 'job_id') else None
            
            # Get Celery/external executor ID if available
            if hasattr(ti, 'external_executor_id'):
                identifiers['external_executor_id'] = ti.external_executor_id
            
            # Build TaskInstance key
            identifiers['ti_key'] = f"{ti.dag_id}__{ti.task_id}__{ti.execution_date}"
            
            # Get current process PID
            identifiers['pid'] = os.getpid()
            
            # Get map_index if this is a mapped task
            if hasattr(ti, 'map_index'):
                identifiers['map_index'] = ti.map_index
    
    except Exception as e:
        identifiers['error'] = str(e)
    
    return identifiers


def format_identifiers_for_grep(identifiers):
    """
    Create grep pattern from identifiers for searching logs.
    Returns a pattern that can match any of the identifiers.
    """
    patterns = []
    
    # Add key patterns that are likely to appear in logs
    if identifiers.get('task_id'):
        patterns.append(identifiers['task_id'])
    if identifiers.get('run_id'):
        patterns.append(identifiers['run_id'])
    if identifiers.get('job_id'):
        patterns.append(str(identifiers['job_id']))
    if identifiers.get('external_executor_id'):
        patterns.append(identifiers['external_executor_id'])
    
    # Return grep-compatible pattern (OR pattern)
    return '|'.join(patterns) if patterns else identifiers.get('task_id', 'taskinstance')


def fetch_journalctl_logs(ip: str, service: str, hostname: str, minutes_back: int = 2) -> str:
    """
    Fetch journalctl logs for a failed service from the remote server.
    Goes back 'minutes_back' minutes from current time.
    Returns cleaned and deduplicated logs.
    """
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        # Use short-precise format and get unique lines only
        if is_local_check:
            cmd = f"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 100 -o short-precise | sort -u"
        else:
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 100 -o short-precise | sort -u\""
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Clean and deduplicate the output
            cleaned_output = clean_timestamp_artifacts(result.stdout)
            return deduplicate_lines(cleaned_output)
        else:
            return f"⚠️ Could not fetch journalctl logs (returncode: {result.returncode})"
    
    except subprocess.TimeoutExpired:
        return "⚠️ Timeout while fetching journalctl logs"
    except Exception as e:
        return f"⚠️ Error fetching journalctl logs: {str(e)}"


def fetch_task_specific_logs(identifiers: dict, minutes_back: int = 2) -> str:
    """
    Fetch logs across all Airflow components (scheduler, worker) that mention this specific task instance.
    Uses task identifiers to find relevant log entries.
    Returns cleaned and deduplicated logs.
    """
    grep_pattern = format_identifiers_for_grep(identifiers)
    
    all_logs = []
    
    # Define components to search
    components = [
        ('Scheduler haproxy-1', '10.101.20.202', 'airflow-scheduler'),
        ('Scheduler scheduler-2', '10.101.20.132', 'airflow-scheduler'),
        ('Worker celery-1', '10.101.20.199', 'airflow-worker'),
        ('Worker celery-2', '10.101.20.200', 'airflow-worker'),
    ]
    
    for component_name, ip, service in components:
        try:
            current_host = get_current_hostname()
            hostname = component_name.split()[1]
            is_local_check = (current_host == hostname)
            
            # Use journalctl with short-precise format, grep, and get unique lines
            if is_local_check:
                cmd = f"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -o short-precise | grep -E '({grep_pattern})' | sort -u | tail -30"
            else:
                cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -o short-precise | grep -E '({grep_pattern})' | sort -u | tail -30\""
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and result.stdout.strip():
                cleaned_output = clean_timestamp_artifacts(result.stdout)
                deduplicated = deduplicate_lines(cleaned_output)
                all_logs.append(f"\n{'='*80}\n📋 {component_name} logs:\n{'='*80}\n{deduplicated}")
        
        except Exception as e:
            all_logs.append(f"\n⚠️ Error fetching logs from {component_name}: {str(e)}")
    
    return '\n'.join(all_logs) if all_logs else "⚠️ No task-specific logs found"


def fetch_airflow_worker_logs() -> str:
    """
    Fetch Airflow worker logs for the current task.
    Returns last 100 lines (reduced from 200 for cleaner output).
    """
    try:
        context = get_current_context()
        dag_id = context['dag'].dag_id
        task_id = context['task'].task_id
        run_id = context['run_id']
        try_number = context['ti'].try_number
        
        # Airflow 2.x log path structure
        log_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/attempt={try_number}.log"
        
        if os.path.exists(log_pattern):
            with open(log_pattern, 'r') as f:
                lines = f.readlines()
                return ''.join(lines[-100:]) if len(lines) > 100 else ''.join(lines)
        else:
            # Try glob pattern as fallback
            glob_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/*.log"
            matching_files = glob.glob(glob_pattern)
            
            if matching_files:
                latest_file = max(matching_files, key=os.path.getctime)
                with open(latest_file, 'r') as f:
                    lines = f.readlines()
                    return ''.join(lines[-100:]) if len(lines) > 100 else ''.join(lines)
            
            return f"⚠️ Worker log file not found"
    
    except Exception as e:
        return f"⚠️ Error fetching worker logs: {str(e)}"


def check_service_status(ip: str, service: str, hostname: str) -> dict:
    """Check systemd service status via SSH or local - FAILS if not active"""
    
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        if is_local_check:
            print(f"🔍 Checking {service} locally on {hostname}")
            status_cmd = f"sudo systemctl status {service} 2>&1 | head -20"
            is_active_cmd = f"sudo systemctl is-active {service} 2>&1"
        else:
            print(f"🔍 Checking {service} remotely on {hostname} ({ip})")
            status_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl status {service} 2>&1 | head -20'"
            is_active_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
        
        # Get full status output
        result = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=10)
        full_output = result.stdout.strip()
        
        # Check if service is active
        is_active_result = subprocess.run(is_active_cmd, shell=True, capture_output=True, text=True, timeout=10)
        status = is_active_result.stdout.strip()
        
        if not status or status == '':
            status = 'unknown'
        
        if status != 'active':
            # SERVICE IS DOWN - FETCH ALL DIAGNOSTIC LOGS
            error_msg = f"❌ {service} on {hostname} ({ip}) is {status.upper()}\n"
            error_msg += f"\n{'='*80}\n📋 Service Status:\n{'='*80}\n{full_output}\n"
            
            # Get task identifiers
            identifiers = get_task_identifiers()
            
            # Print task identifiers (only once, concise)
            print(f"\n🔍 Task ID: {identifiers.get('task_id')}, Job ID: {identifiers.get('job_id')}, PID: {identifiers.get('pid')}")
            
            # Fetch journalctl logs
            journalctl_logs = fetch_journalctl_logs(ip, service, hostname, minutes_back=2)
            error_msg += f"\n{'='*80}\n📋 Service Logs (last 2 min):\n{'='*80}\n{journalctl_logs}\n"
            
            # Fetch task-specific logs from Airflow components
            try:
                task_specific_logs = fetch_task_specific_logs(identifiers, minutes_back=2)
                if "No task-specific logs" not in task_specific_logs:
                    error_msg += f"\n{'='*80}\n📋 Airflow Component Logs:\n{'='*80}\n{task_specific_logs}\n"
                
                # Also fetch this task's own worker log
                worker_logs = fetch_airflow_worker_logs()
                if "not found" not in worker_logs and "Error" not in worker_logs:
                    error_msg += f"\n{'='*80}\n📋 This Task's Worker Log:\n{'='*80}\n{worker_logs}\n"
            
            except Exception as log_error:
                error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
            
            error_msg += f"\n{'='*80}\n"
            
            raise AirflowException(error_msg)
        
        # Special handling for patroni - check role
        role_info = ""
        if service == 'patroni':
            last_octet = ip.split(".")[-1]
            if is_local_check:
                role_cmd = f"patronictl -c /etc/patroni/patroni.yml list 2>/dev/null | grep {last_octet}"
            else:
                role_cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no rocky@{ip} 'patronictl -c /etc/patroni/patroni.yml list 2>/dev/null | grep {last_octet}'"
            
            role_result = subprocess.run(role_cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if 'Leader' in role_result.stdout:
                role_info = " [LEADER]"
            elif 'Replica' in role_result.stdout:
                role_info = " [REPLICA]"
        
        print(f"✅ {service} on {hostname} ({ip}) is ACTIVE{role_info}")
        return {'status': 'active', 'hostname': hostname, 'ip': ip, 'service': service}
        
    except subprocess.TimeoutExpired:
        raise AirflowException(f"❌ {service} on {hostname} ({ip}) - TIMEOUT")
    except AirflowException:
        raise
    except Exception as e:
        raise AirflowException(f"❌ {service} on {hostname} ({ip}) - ERROR: {str(e)}")


def detect_active_nfs_node() -> str:
    """Detect which NFS node is currently active by checking keepalived VIP"""
    try:
        for node in ['nfs-1', 'nfs-2']:
            ip = '10.101.20.165' if node == 'nfs-1' else '10.101.20.203'
            cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no rocky@{ip} 'ip addr show | grep 10.101.20.220'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if '10.101.20.220' in result.stdout:
                return node
        
        return 'unknown'
    except:
        return 'unknown'


@dag(
    dag_id='ha_service_health_monitor_enhanced_v3',
    description='Monitor all HA services - v3 with improved logging',
    schedule='*/2 * * * *',  # Every 2 minutes
    start_date=datetime(2025, 10, 12),
    catchup=False,
    max_active_tasks=16,
    default_args={
        'owner': 'airflow',
        'retries': 0,
    },
    tags=['monitoring', 'health-check', 'v3-improved'],
)
def ha_service_health_monitor_enhanced():
    
    # Detect active NFS node first
    @task(task_id="detect_nfs_active_node")
    def detect_nfs_node():
        active = detect_active_nfs_node()
        print(f"🔍 Active NFS Node: {active}")
        return active
    
    active_nfs = detect_nfs_node()
    
    # Create NFS service check tasks with active/passive logic
    nfs_tasks = []
    for hostname, config in NFS_NODES.items():
        ip = config['ip']
        services = config['services']
        
        for service in services:
            @task(task_id=f"check_{hostname.replace('-', '_')}_{service.replace('-', '_')}")
            def check_nfs_service(active_nfs_node: str, service_name=service, host=hostname, server_ip=ip):
                """Check NFS service with active/passive logic"""
                context = get_current_context()
                ti = context['task_instance']
                
                current_host = get_current_hostname()
                is_local_check = (current_host == host)
                
                # Determine if this node is active
                is_active_node = (host == active_nfs_node)
                
                print(f"🔍 Node: {host}, Active: {active_nfs_node}, Is Active: {is_active_node}")
                
                # Services that should only run on active node
                active_only_services = ['nfs-server', 'lsyncd', 'airflow-dag-processor']
                
                # Check service status
                if is_local_check:
                    status_check = f"sudo systemctl is-active {service_name} 2>&1"
                else:
                    status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{server_ip} 'sudo systemctl is-active {service_name} 2>&1'"
                
                result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
                service_status = result.stdout.strip()
                
                # Logic for active/passive HA
                if service_name in active_only_services:
                    if is_active_node:
                        # ACTIVE NODE: Service MUST be active
                        if service_status != 'active':
                            # CRITICAL FAILURE - fetch diagnostic logs
                            error_msg = f"🚨 CRITICAL: {service_name} on ACTIVE node {host} is {service_status.upper()}!\n"
                            
                            # Get task identifiers
                            identifiers = get_task_identifiers(context)
                            print(f"🔍 Task ID: {identifiers.get('task_id')}, Job ID: {identifiers.get('job_id')}")
                            
                            # Fetch diagnostic logs
                            journalctl_logs = fetch_journalctl_logs(server_ip, service_name, host, minutes_back=2)
                            error_msg += f"\n{'='*80}\n📋 Service Logs:\n{'='*80}\n{journalctl_logs}\n"
                            
                            task_specific_logs = fetch_task_specific_logs(identifiers, minutes_back=2)
                            if "No task-specific logs" not in task_specific_logs:
                                error_msg += f"\n{'='*80}\n📋 Airflow Logs:\n{'='*80}\n{task_specific_logs}\n"
                            
                            ti.xcom_push(key='failure_type', value='CRITICAL_ACTIVE_DOWN')
                            raise AirflowException(error_msg)
                        else:
                            print(f"✅ {service_name} on ACTIVE node {host} is correctly ACTIVE")
                    else:
                        # PASSIVE NODE: Service should NOT be active
                        if service_status == 'active':
                            # SPLIT-BRAIN - both nodes active!
                            error_msg = f"🚨 CRITICAL: {service_name} on PASSIVE node {host} is ACTIVE! Possible split-brain!\n"
                            
                            journalctl_logs = fetch_journalctl_logs(server_ip, service_name, host, minutes_back=2)
                            error_msg += f"\n{'='*80}\n📋 Service Logs:\n{'='*80}\n{journalctl_logs}\n"
                            
                            ti.xcom_push(key='failure_type', value='CRITICAL_PASSIVE_ACTIVE')
                            raise AirflowException(error_msg)
                        else:
                            # EXPECTED - passive node service is not active
                            print(f"⏸️ EXPECTED: {service_name} on PASSIVE node {host} is correctly NOT ACTIVE")
                            ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE_INACTIVE')
                            raise AirflowException(
                                f"⏸️ EXPECTED: {service_name} on PASSIVE node {host} is correctly NOT ACTIVE\n"
                                "This task failure is expected and does not indicate a problem."
                            )
                else:
                    # keepalived should always be active on both nodes
                    if service_status != 'active':
                        error_msg = f"❌ {service_name} on {host} is {service_status.upper()}\n"
                        
                        journalctl_logs = fetch_journalctl_logs(server_ip, service_name, host, minutes_back=2)
                        error_msg += f"\n{'='*80}\n📋 Service Logs:\n{'='*80}\n{journalctl_logs}\n"
                        
                        ti.xcom_push(key='failure_type', value='CRITICAL_SERVICE_DOWN')
                        raise AirflowException(error_msg)
                    print(f"✅ {service_name} on {host} is ACTIVE")
            
            nfs_tasks.append(check_nfs_service(active_nfs))
    
    # Create regular service check tasks (non-NFS)
    service_tasks = []
    for hostname, config in SERVERS.items():
        ip = config['ip']
        services = config['services']
        
        for service in services:
            @task(task_id=f"check_{hostname.replace('-', '_')}_{service.replace('-', '_')}")
            def check_service(service_name=service, host=hostname, server_ip=ip):
                """Check regular service - FAILS if not active"""
                return check_service_status(server_ip, service_name, host)
            
            service_tasks.append(check_service())
    
    # Cluster-level checks
    @task(task_id="check_postgresql_vip")
    def check_postgresql_vip():
        """Check PostgreSQL via VIP - FAILS if unreachable"""
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
            
            print(f"✅ PostgreSQL VIP (10.101.20.210:5000) is HEALTHY - {dag_count} DAGs")
            return {'status': 'healthy', 'dags': dag_count}
        except Exception as e:
            error_msg = f"❌ PostgreSQL VIP FAILED: {str(e)}\n"
            
            # Fetch PostgreSQL logs from all nodes
            pg_nodes = [
                ('postgresql-1', '10.101.20.204'),
                ('postgresql-2', '10.101.20.166'),
                ('postgresql-3', '10.101.20.137')
            ]
            
            for hostname, ip in pg_nodes:
                try:
                    journalctl_logs = fetch_journalctl_logs(ip, 'patroni', hostname, minutes_back=2)
                    error_msg += f"\n{'='*80}\n📋 Patroni logs from {hostname}:\n{'='*80}\n{journalctl_logs}\n"
                except:
                    pass
            
            raise AirflowException(error_msg)
    
    
    @task(task_id="check_rabbitmq_cluster")
    def check_rabbitmq_cluster():
        """Check RabbitMQ cluster - FAILS if quorum lost"""
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
            
            for name, ip in nodes:
                try:
                    journalctl_logs = fetch_journalctl_logs(ip, 'rabbitmq-server', name, minutes_back=2)
                    error_msg += f"\n{'='*80}\n📋 RabbitMQ logs from {name}:\n{'='*80}\n{journalctl_logs}\n"
                except:
                    pass
            
            raise AirflowException(error_msg)
        
        print(f"✅ RabbitMQ Cluster: {healthy}/3 nodes healthy")
        return {'healthy_nodes': healthy, 'total': 3, 'nodes': results}
    
    
    @task(task_id="check_scheduler_heartbeat")
    def check_scheduler_heartbeat():
        """Check active schedulers - FAILS if none active"""
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
            
            cur.execute("""
                SELECT hostname, latest_heartbeat 
                FROM job 
                WHERE job_type = 'SchedulerJob' 
                AND state = 'running'
                ORDER BY latest_heartbeat DESC;
            """)
            
            schedulers = cur.fetchall()
            cur.close()
            conn.close()
            
            if not schedulers:
                error_msg = "❌ NO ACTIVE SCHEDULERS FOUND\n"
                
                scheduler_nodes = [
                    ('haproxy-1', '10.101.20.202'),
                    ('scheduler-2', '10.101.20.132')
                ]
                
                for hostname, ip in scheduler_nodes:
                    try:
                        journalctl_logs = fetch_journalctl_logs(ip, 'airflow-scheduler', hostname, minutes_back=2)
                        error_msg += f"\n{'='*80}\n📋 Scheduler logs from {hostname}:\n{'='*80}\n{journalctl_logs}\n"
                    except:
                        pass
                
                raise AirflowException(error_msg)
            
            print(f"✅ {len(schedulers)} Active Scheduler(s)")
            for sched in schedulers:
                print(f"   - {sched[0]} (heartbeat: {sched[1]})")
            
            return {'status': 'healthy', 'count': len(schedulers)}
            
        except AirflowException:
            raise
        except Exception as e:
            raise AirflowException(f"❌ Scheduler check FAILED: {str(e)}")
    
    
    @task(task_id="check_celery_workers")
    def check_celery_workers():
        """Check Celery workers - FAILS if none available"""
        try:
            from airflow.providers.celery.executors.celery_executor import app
            stats = app.control.inspect().stats()
            
            if not stats:
                error_msg = "❌ NO CELERY WORKERS AVAILABLE\n"
                
                worker_nodes = [
                    ('celery-1', '10.101.20.199'),
                    ('celery-2', '10.101.20.200')
                ]
                
                for hostname, ip in worker_nodes:
                    try:
                        journalctl_logs = fetch_journalctl_logs(ip, 'airflow-worker', hostname, minutes_back=2)
                        error_msg += f"\n{'='*80}\n📋 Worker logs from {hostname}:\n{'='*80}\n{journalctl_logs}\n"
                    except:
                        pass
                
                raise AirflowException(error_msg)
            
            print(f"✅ {len(stats)} Celery Worker(s) Active")
            for worker in stats.keys():
                print(f"   - {worker}")
            
            return {'status': 'healthy', 'count': len(stats)}
            
        except AirflowException:
            raise
        except Exception as e:
            raise AirflowException(f"❌ Celery worker check FAILED: {str(e)}")
    
    
    @task(task_id="health_summary", trigger_rule="all_done")
    def health_summary():
        """Generate summary - runs even if some tasks fail"""
        from airflow.models import TaskInstance
        from airflow.utils.state import State
        
        context = get_current_context()
        dag_run = context['dag_run']
        ti = context['task_instance']
        
        task_instances = dag_run.get_task_instances()
        
        failed_tasks = [task for task in task_instances if task.state == State.FAILED]
        success_tasks = [task for task in task_instances if task.state == State.SUCCESS]
        
        # Categorize failures
        expected_passive_failures = []
        critical_failures = []
        
        for failed_task in failed_tasks:
            failure_type = failed_task.xcom_pull(task_ids=failed_task.task_id, key='failure_type')
            
            if failure_type == 'EXPECTED_PASSIVE_INACTIVE':
                expected_passive_failures.append(failed_task)
            else:
                critical_failures.append(failed_task)
        
        # Store critical failures for final check
        ti.xcom_push(key='critical_failure_count', value=len(critical_failures))
        ti.xcom_push(key='critical_failure_tasks', value=[t.task_id for t in critical_failures])
        
        print("\n" + "=" * 80)
        print("🏥 HEALTH CHECK SUMMARY")
        print("=" * 80)
        print(f"✅ Successful: {len(success_tasks)}")
        print(f"❌ Total Failed: {len(failed_tasks)}")
        print(f"   ├─ Critical Failures: {len(critical_failures)}")
        print(f"   └─ Expected Passive Failures: {len(expected_passive_failures)}")
        
        if critical_failures:
            print("\n🚨 CRITICAL FAILURES:")
            for task in critical_failures:
                print(f"   - {task.task_id}")
        
        if expected_passive_failures:
            print("\n⏸️  EXPECTED PASSIVE NODE FAILURES:")
            for task in expected_passive_failures:
                print(f"   - {task.task_id}")
        
        print("=" * 80 + "\n")
        
        return {
            'total': len(task_instances),
            'success': len(success_tasks),
            'total_failed': len(failed_tasks),
            'critical_failures': len(critical_failures),
            'expected_failures': len(expected_passive_failures)
        }
    
    
    @task(task_id="final_status_check")
    def final_status_check(summary_result):
        """Final check - FAILS the DAG if any critical services failed"""
        context = get_current_context()
        
        critical_count = context['task_instance'].xcom_pull(
            task_ids='health_summary', 
            key='critical_failure_count'
        )
        critical_tasks = context['task_instance'].xcom_pull(
            task_ids='health_summary', 
            key='critical_failure_tasks'
        )
        
        if critical_count and critical_count > 0:
            raise AirflowException(
                f"🚨 DAG FAILED: {critical_count} critical service(s) are down!\n"
                f"Failed services: {', '.join(critical_tasks)}\n"
                f"Check individual task logs for detailed diagnostic information."
            )
        
        print("✅ All critical services are healthy - DAG SUCCESS")
        print("ℹ️  Passive NFS node services are correctly inactive")
        return {'status': 'all_healthy'}
    
    
    # Build DAG dependencies
    pg_vip = check_postgresql_vip()
    rabbitmq = check_rabbitmq_cluster()
    scheduler = check_scheduler_heartbeat()
    celery = check_celery_workers()
    
    summary = health_summary()
    final = final_status_check(summary)
    
    # Set dependencies
    active_nfs >> nfs_tasks
    service_tasks >> summary
    nfs_tasks >> summary
    [pg_vip, rabbitmq, scheduler, celery] >> summary
    summary >> final


# Instantiate the DAG
dag_instance = ha_service_health_monitor_enhanced()
