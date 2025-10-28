"""
Airflow HA Infrastructure Health Monitor - Individual Service Tasks
Each service gets its own task that FAILS if unhealthy
Supports NFS active/passive HA configuration
DAG fails if any critical service fails
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


def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except:
        return socket.gethostname()


def check_service_status(ip: str, service: str, hostname: str) -> dict:
    """Check systemd service status via SSH or local - FAILS if not active"""
    
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        if is_local_check:
            # Local check - use direct systemctl without SSH
            print(f"🔍 Checking {service} locally on {hostname}")
            
            status_cmd = f"sudo systemctl status {service} 2>&1 | head -20"
            is_active_cmd = f"sudo systemctl is-active {service} 2>&1"
        else:
            # Remote check - use SSH
            print(f"🔍 Checking {service} remotely on {hostname} ({ip})")
            
            status_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl status {service} 2>&1 | head -20'"
            is_active_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
        
        # Get full status output
        result = subprocess.run(
            status_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        full_output = result.stdout.strip()
        
        # Check if service is active
        is_active_result = subprocess.run(
            is_active_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        status = is_active_result.stdout.strip()
        
        # Debug output for empty status
        if not status or status == '':
            print(f"⚠️ Empty status from {hostname}. Full status output:")
            print(full_output)
            print(f"Return code: {is_active_result.returncode}")
            print(f"Stderr: {is_active_result.stderr}")
            status = 'unknown'
        
        if status != 'active':
            error_msg = f"❌ {service} on {hostname} ({ip}) is {status.upper()}\n"
            error_msg += f"\nService Status Output:\n{'-'*60}\n{full_output}\n{'-'*60}"
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
        # Check which node has the NFS VIP (10.101.20.220)
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
    dag_id='ha_service_health_monitor',
    description='Monitor all HA services - each service is a separate task',
    schedule='*/15 * * * *',
    start_date=datetime(2025, 10, 12),
    catchup=False,
    default_args={
        'owner': 'airflow',
        'retries': 0,  # No retries - we want immediate failure visibility
    },
    tags=['monitoring', 'health-check'],
)
def ha_service_health_monitor():
    
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
            def check_nfs_service(ip_addr=ip, svc=service, host=hostname):
                # Get the active node from upstream task
                context = get_current_context()
                active = context['task_instance'].xcom_pull(task_ids='detect_nfs_active_node')
                ti = context['task_instance']
                
                # If this is the passive node
                if host != active:
                    # Keepalived should ALWAYS be active (on both nodes)
                    if svc == 'keepalived':
                        return check_service_status(ip_addr, svc, host)
                    
                    # For other services on passive node, check if they are INACTIVE
                    print(f"🔍 Checking {svc} on PASSIVE node {host} (should be INACTIVE)")
                    
                    current_host = get_current_hostname()
                    is_local = (current_host == host)
                    
                    try:
                        if is_local:
                            is_active_cmd = f"sudo systemctl is-active {svc} 2>&1"
                        else:
                            is_active_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip_addr} 'sudo systemctl is-active {svc} 2>&1'"
                        
                        result = subprocess.run(is_active_cmd, shell=True, capture_output=True, text=True, timeout=10)
                        status = result.stdout.strip()
                        
                        if status == 'active':
                            # CRITICAL ERROR - passive service should NOT be active
                            ti.xcom_push(key='failure_type', value='CRITICAL_PASSIVE_ACTIVE')
                            raise AirflowException(
                                f"🚨 CRITICAL: {svc} on PASSIVE node {host} is ACTIVE (should be NOT ACTIVE)! "
                                f"This indicates HA failover issue!"
                            )
                        else:
                            # EXPECTED - passive services can be inactive, failed, dead, etc. (anything except active)
                            ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE_INACTIVE')
                            raise AirflowException(
                                f"⏸️ EXPECTED: {svc} on PASSIVE node {host} is correctly NOT ACTIVE (status: {status})"
                            )
                    except subprocess.TimeoutExpired:
                        ti.xcom_push(key='failure_type', value='CRITICAL_TIMEOUT')
                        raise AirflowException(f"❌ {svc} on PASSIVE node {host} - TIMEOUT")
                    except AirflowException:
                        # Re-raise AirflowException (XCom already pushed above)
                        raise
                    except Exception as e:
                        ti.xcom_push(key='failure_type', value='CRITICAL_ERROR')
                        raise AirflowException(f"❌ {svc} on PASSIVE node {host} - ERROR: {str(e)}")
                
                # For active node, do normal check (all services should be active)
                return check_service_status(ip_addr, svc, host)
            
            task_instance = check_nfs_service()
            active_nfs >> task_instance
            nfs_tasks.append(task_instance)
    
    # Create tasks for all other servers (non-NFS)
    service_tasks = []
    
    for hostname, config in SERVERS.items():
        ip = config['ip']
        services = config['services']
        
        for service in services:
            # Create unique task for each service
            @task(task_id=f"check_{hostname.replace('-', '_')}_{service.replace('-', '_')}")
            def check_service(ip_addr=ip, svc=service, host=hostname):
                return check_service_status(ip_addr, svc, host)
            
            service_tasks.append(check_service())
    
    
    @task(task_id="check_postgresql_vip")
    def check_postgresql_vip():
        """Check PostgreSQL cluster via VIP - FAILS if unhealthy"""
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
            raise AirflowException(f"❌ PostgreSQL VIP FAILED: {str(e)}")
    
    
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
        
        # Require at least 2/3 nodes for quorum
        if healthy < 2:
            raise AirflowException(
                f"❌ RabbitMQ QUORUM LOST: Only {healthy}/3 nodes healthy"
            )
        
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
            
            # Airflow 2.9 uses 'job' table
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
                raise AirflowException("❌ NO ACTIVE SCHEDULERS FOUND")
            
            print(f"✅ {len(schedulers)} Active Scheduler(s):")
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
                raise AirflowException("❌ NO CELERY WORKERS AVAILABLE")
            
            print(f"✅ {len(stats)} Celery Worker(s) Active:")
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
        
        # Get all task instances for this dag run
        task_instances = dag_run.get_task_instances()
        
        failed_tasks = [task for task in task_instances if task.state == State.FAILED]
        success_tasks = [task for task in task_instances if task.state == State.SUCCESS]
        
        # Categorize failures
        expected_passive_failures = []
        critical_failures = []
        
        for failed_task in failed_tasks:
            # Try to get failure type from XCom
            failure_type = failed_task.xcom_pull(task_ids=failed_task.task_id, key='failure_type')
            
            if failure_type == 'EXPECTED_PASSIVE_INACTIVE':
                expected_passive_failures.append(failed_task)
            else:
                critical_failures.append(failed_task)
        
        # Store critical failures for final check
        ti.xcom_push(key='critical_failure_count', value=len(critical_failures))
        ti.xcom_push(key='critical_failure_tasks', value=[t.task_id for t in critical_failures])
        
        print("\n" + "=" * 80)
        print("🏥  HEALTH CHECK SUMMARY")
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
            print("\n⏸️  EXPECTED PASSIVE NODE FAILURES (inactive as expected):")
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
        
        # Get critical failure count from health_summary XCom
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
                f"Check the health_summary task for details."
            )
        
        print("✅ All critical services are healthy - DAG SUCCESS")
        print("ℹ️  Passive NFS node services are correctly inactive")
        return {'status': 'all_healthy'}
    
    
    # Build DAG dependencies
    pg_vip = check_postgresql_vip()
    rabbitmq = check_rabbitmq_cluster()
    scheduler = check_scheduler_heartbeat()
    celery = check_celery_workers()
    
    # Summary collects all results
    summary = health_summary()
    
    # Final check determines DAG success/failure
    final = final_status_check(summary)
    
    # Set dependencies
    service_tasks >> summary
    nfs_tasks >> summary
    [pg_vip, rabbitmq, scheduler, celery] >> summary
    summary >> final


# Instantiate the DAG
dag_instance = ha_service_health_monitor()
