"""
Airflow 3.1.5 Health Monitor DAG - Version 1
Migrated from Airflow 2.9 to 3.1.5 with Python 3.12

MAJOR CHANGES:
- Updated for Airflow 3.1.5 compatibility
- Removed external server dependencies (uses local constants)
- Updated import paths for providers-standard package
- Changed schedule_interval to schedule parameter
- Updated TaskFlow API patterns
- Simplified for standalone operation
"""
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
import subprocess
import socket
import platform
import os
import json
from collections import OrderedDict


# Local configuration - no external dependencies
LOCAL_SERVICES = {
    'scheduler': {'name': 'airflow-scheduler', 'expected_status': 'active'},
    'api_server': {'name': 'airflow-api-server', 'expected_status': 'active'},
    'dag_processor': {'name': 'airflow-dag-processor', 'expected_status': 'active'},
    'triggerer': {'name': 'airflow-triggerer', 'expected_status': 'active'},
    'celery_worker': {'name': 'airflow-celery-worker', 'expected_status': 'active'},
}

# Expected resource thresholds
RESOURCE_THRESHOLDS = {
    'cpu_warning': 80.0,
    'cpu_critical': 95.0,
    'memory_warning': 80.0,
    'memory_critical': 90.0,
    'disk_warning': 80.0,
    'disk_critical': 90.0,
}

# Airflow home directory
AIRFLOW_HOME = os.getenv('AIRFLOW_HOME', '/home/airflow')


def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except Exception:
        return socket.gethostname()


def get_service_status(service_name: str) -> dict:
    """
    Check systemd service status locally
    Returns dict with status information
    """
    try:
        cmd = f"systemctl is-active {service_name}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        is_active = result.stdout.strip() == 'active'
        
        # Get detailed status
        cmd_status = f"systemctl status {service_name} --no-pager -l"
        status_result = subprocess.run(
            cmd_status,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return {
            'service': service_name,
            'status': 'active' if is_active else result.stdout.strip(),
            'is_healthy': is_active,
            'details': status_result.stdout[:500] if status_result.returncode == 0 else 'N/A'
        }
        
    except subprocess.TimeoutExpired:
        return {
            'service': service_name,
            'status': 'timeout',
            'is_healthy': False,
            'details': 'Service check timed out'
        }
    except Exception as e:
        return {
            'service': service_name,
            'status': 'error',
            'is_healthy': False,
            'details': f'Error: {str(e)}'
        }


def get_system_resources() -> dict:
    """
    Get local system resource usage
    Returns dict with CPU, memory, and disk metrics
    """
    resources = {
        'hostname': get_current_hostname(),
        'timestamp': datetime.now().isoformat(),
    }
    
    # CPU usage
    try:
        cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            resources['cpu_usage'] = float(result.stdout.strip())
    except Exception as e:
        resources['cpu_usage'] = None
        resources['cpu_error'] = str(e)
    
    # Memory usage
    try:
        cmd = "free | grep Mem | awk '{printf \"%.2f\", ($3/$2) * 100}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            resources['memory_usage'] = float(result.stdout.strip())
    except Exception as e:
        resources['memory_usage'] = None
        resources['memory_error'] = str(e)
    
    # Disk usage
    try:
        cmd = "df -h / | tail -1 | awk '{print $5}' | sed 's/%//'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            resources['disk_usage'] = float(result.stdout.strip())
    except Exception as e:
        resources['disk_usage'] = None
        resources['disk_error'] = str(e)
    
    # Airflow logs size
    try:
        logs_dir = f"{AIRFLOW_HOME}/logs"
        cmd = f"du -sh {logs_dir} 2>/dev/null | awk '{{print $1}}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            resources['logs_size'] = result.stdout.strip()
    except Exception:
        resources['logs_size'] = 'N/A'
    
    return resources


def fetch_service_logs(service_name: str, lines: int = 50) -> str:
    """Fetch recent logs from journalctl for a service"""
    try:
        cmd = f"sudo journalctl -u {service_name} --no-pager -n {lines} -o short-iso 2>/dev/null"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        else:
            return f"⚠️ Could not fetch logs (returncode: {result.returncode})"
    
    except subprocess.TimeoutExpired:
        return "⚠️ Timeout while fetching logs"
    except Exception as e:
        return f"⚠️ Error fetching logs: {str(e)}"


@dag(
    dag_id='d02-v01-health_monitor',
    description='Health monitoring DAG for Airflow 3.1.5 infrastructure',
    schedule=timedelta(minutes=5),  # Changed from schedule_interval in Airflow 3.x
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={
        'owner': 'airflow',
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
    },
    tags=['health-check', 'monitoring', 'v01'],
    max_active_runs=1,
)
def health_monitor_dag():
    """
    Main health monitoring DAG for Airflow 3.1.5
    Checks local services, system resources, and generates health reports
    """
    
    @task(task_id="check_scheduler_service")
    def check_scheduler_service():
        """Check Airflow Scheduler service status"""
        service = LOCAL_SERVICES['scheduler']['name']
        status = get_service_status(service)
        
        print(f"\n{'='*80}")
        print(f"📊 SCHEDULER SERVICE CHECK")
        print(f"{'='*80}")
        print(f"Service: {status['service']}")
        print(f"Status: {status['status']}")
        print(f"Healthy: {'✅' if status['is_healthy'] else '❌'}")
        print(f"{'='*80}\n")
        
        if not status['is_healthy']:
            # Fetch logs for troubleshooting
            logs = fetch_service_logs(service, lines=50)
            error_msg = (
                f"❌ SCHEDULER SERVICE DOWN\n"
                f"Status: {status['status']}\n"
                f"{'='*80}\n"
                f"Recent logs:\n{logs}\n"
                f"{'='*80}"
            )
            raise AirflowException(error_msg)
        
        return status
    
    
    @task(task_id="check_api_server_service")
    def check_api_server_service():
        """Check Airflow API Server (Web UI) service status"""
        service = LOCAL_SERVICES['api_server']['name']
        status = get_service_status(service)
        
        print(f"\n{'='*80}")
        print(f"🌐 API SERVER SERVICE CHECK")
        print(f"{'='*80}")
        print(f"Service: {status['service']}")
        print(f"Status: {status['status']}")
        print(f"Healthy: {'✅' if status['is_healthy'] else '❌'}")
        print(f"{'='*80}\n")
        
        if not status['is_healthy']:
            logs = fetch_service_logs(service, lines=50)
            error_msg = (
                f"❌ API SERVER SERVICE DOWN\n"
                f"Status: {status['status']}\n"
                f"{'='*80}\n"
                f"Recent logs:\n{logs}\n"
                f"{'='*80}"
            )
            raise AirflowException(error_msg)
        
        return status
    
    
    @task(task_id="check_dag_processor_service")
    def check_dag_processor_service():
        """Check Airflow DAG Processor service status"""
        service = LOCAL_SERVICES['dag_processor']['name']
        status = get_service_status(service)
        
        print(f"\n{'='*80}")
        print(f"📁 DAG PROCESSOR SERVICE CHECK")
        print(f"{'='*80}")
        print(f"Service: {status['service']}")
        print(f"Status: {status['status']}")
        print(f"Healthy: {'✅' if status['is_healthy'] else '❌'}")
        print(f"{'='*80}\n")
        
        if not status['is_healthy']:
            logs = fetch_service_logs(service, lines=50)
            error_msg = (
                f"❌ DAG PROCESSOR SERVICE DOWN\n"
                f"Status: {status['status']}\n"
                f"{'='*80}\n"
                f"Recent logs:\n{logs}\n"
                f"{'='*80}"
            )
            raise AirflowException(error_msg)
        
        return status
    
    
    @task(task_id="check_triggerer_service")
    def check_triggerer_service():
        """Check Airflow Triggerer service status"""
        service = LOCAL_SERVICES['triggerer']['name']
        status = get_service_status(service)
        
        print(f"\n{'='*80}")
        print(f"⚡ TRIGGERER SERVICE CHECK")
        print(f"{'='*80}")
        print(f"Service: {status['service']}")
        print(f"Status: {status['status']}")
        print(f"Healthy: {'✅' if status['is_healthy'] else '❌'}")
        print(f"{'='*80}\n")
        
        if not status['is_healthy']:
            logs = fetch_service_logs(service, lines=50)
            error_msg = (
                f"❌ TRIGGERER SERVICE DOWN\n"
                f"Status: {status['status']}\n"
                f"{'='*80}\n"
                f"Recent logs:\n{logs}\n"
                f"{'='*80}"
            )
            raise AirflowException(error_msg)
        
        return status
    
    
    @task(task_id="check_celery_worker_service")
    def check_celery_worker_service():
        """Check Airflow Celery Worker service status"""
        service = LOCAL_SERVICES['celery_worker']['name']
        status = get_service_status(service)
        
        print(f"\n{'='*80}")
        print(f"👷 CELERY WORKER SERVICE CHECK")
        print(f"{'='*80}")
        print(f"Service: {status['service']}")
        print(f"Status: {status['status']}")
        print(f"Healthy: {'✅' if status['is_healthy'] else '❌'}")
        print(f"{'='*80}\n")
        
        if not status['is_healthy']:
            logs = fetch_service_logs(service, lines=50)
            error_msg = (
                f"❌ CELERY WORKER SERVICE DOWN\n"
                f"Status: {status['status']}\n"
                f"{'='*80}\n"
                f"Recent logs:\n{logs}\n"
                f"{'='*80}"
            )
            raise AirflowException(error_msg)
        
        return status
    
    
    @task(task_id="check_system_resources")
    def check_system_resources():
        """Monitor system resources (CPU, Memory, Disk)"""
        resources = get_system_resources()
        
        print(f"\n{'='*80}")
        print(f"💻 SYSTEM RESOURCES CHECK")
        print(f"{'='*80}")
        print(f"Hostname: {resources['hostname']}")
        print(f"Timestamp: {resources['timestamp']}")
        print(f"CPU Usage: {resources.get('cpu_usage', 'N/A')}%")
        print(f"Memory Usage: {resources.get('memory_usage', 'N/A')}%")
        print(f"Disk Usage: {resources.get('disk_usage', 'N/A')}%")
        print(f"Logs Size: {resources.get('logs_size', 'N/A')}")
        print(f"{'='*80}\n")
        
        # Check thresholds
        warnings = []
        critical = []
        
        if resources.get('cpu_usage'):
            if resources['cpu_usage'] >= RESOURCE_THRESHOLDS['cpu_critical']:
                critical.append(f"CPU at {resources['cpu_usage']}%")
            elif resources['cpu_usage'] >= RESOURCE_THRESHOLDS['cpu_warning']:
                warnings.append(f"CPU at {resources['cpu_usage']}%")
        
        if resources.get('memory_usage'):
            if resources['memory_usage'] >= RESOURCE_THRESHOLDS['memory_critical']:
                critical.append(f"Memory at {resources['memory_usage']}%")
            elif resources['memory_usage'] >= RESOURCE_THRESHOLDS['memory_warning']:
                warnings.append(f"Memory at {resources['memory_usage']}%")
        
        if resources.get('disk_usage'):
            if resources['disk_usage'] >= RESOURCE_THRESHOLDS['disk_critical']:
                critical.append(f"Disk at {resources['disk_usage']}%")
            elif resources['disk_usage'] >= RESOURCE_THRESHOLDS['disk_warning']:
                warnings.append(f"Disk at {resources['disk_usage']}%")
        
        if warnings:
            print(f"⚠️ WARNINGS: {', '.join(warnings)}")
        
        if critical:
            error_msg = f"🚨 CRITICAL: {', '.join(critical)}"
            print(error_msg)
            raise AirflowException(error_msg)
        
        return resources
    
    
    @task(task_id="check_database_connectivity")
    def check_database_connectivity():
        """
        Check PostgreSQL database connectivity
        Note: In Airflow 3.x, direct database access from tasks is discouraged
        This is a simplified connectivity check
        """
        try:
            # Use airflow CLI to verify database connection
            cmd = "airflow db check 2>&1"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_healthy = result.returncode == 0
            
            print(f"\n{'='*80}")
            print(f"🗄️ DATABASE CONNECTIVITY CHECK")
            print(f"{'='*80}")
            print(f"Status: {'✅ Connected' if is_healthy else '❌ Connection Failed'}")
            print(f"Output: {result.stdout[:200]}")
            print(f"{'='*80}\n")
            
            if not is_healthy:
                raise AirflowException(
                    f"❌ DATABASE CONNECTION FAILED\n"
                    f"Error: {result.stderr[:500]}"
                )
            
            return {'status': 'connected', 'output': result.stdout}
            
        except Exception as e:
            raise AirflowException(f"❌ Database check failed: {str(e)}")
    
    
    @task(task_id="check_redis_connectivity")
    def check_redis_connectivity():
        """
        Check Redis connectivity (Celery broker)
        """
        try:
            cmd = "redis-cli ping 2>&1"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_healthy = result.stdout.strip().upper() == 'PONG'
            
            print(f"\n{'='*80}")
            print(f"🔴 REDIS CONNECTIVITY CHECK")
            print(f"{'='*80}")
            print(f"Status: {'✅ Connected' if is_healthy else '❌ Connection Failed'}")
            print(f"Response: {result.stdout.strip()}")
            print(f"{'='*80}\n")
            
            if not is_healthy:
                raise AirflowException(
                    f"❌ REDIS CONNECTION FAILED\n"
                    f"Response: {result.stdout}\n"
                    f"Error: {result.stderr}"
                )
            
            return {'status': 'connected', 'response': result.stdout.strip()}
            
        except Exception as e:
            raise AirflowException(f"❌ Redis check failed: {str(e)}")
    
    
    @task(task_id="health_summary", trigger_rule="all_done")
    def health_summary(**context):
        """
        Generate comprehensive health summary
        In Airflow 3.x, use context directly instead of get_current_context()
        """
        # Access task instance from context
        ti = context['ti']
        dag_run = context['dag_run']
        
        # Get all task instances for this DAG run
        task_instances = dag_run.get_task_instances()
        
        # Count task states
        from airflow.utils.state import TaskInstanceState
        
        success_tasks = [t for t in task_instances if t.state == TaskInstanceState.SUCCESS]
        failed_tasks = [t for t in task_instances if t.state == TaskInstanceState.FAILED]
        
        print("\n" + "="*80)
        print("🏥 HEALTH CHECK SUMMARY")
        print("="*80)
        print(f"✅ Successful Checks: {len(success_tasks)}")
        print(f"❌ Failed Checks: {len(failed_tasks)}")
        
        if failed_tasks:
            print("\n🚨 FAILED CHECKS:")
            for task in failed_tasks:
                print(f"   - {task.task_id}")
        
        print("="*80 + "\n")
        
        # Push summary to XCom for final status check
        summary_data = {
            'total': len(task_instances),
            'success': len(success_tasks),
            'failed': len(failed_tasks),
            'timestamp': datetime.now().isoformat()
        }
        
        # In Airflow 3.x, XCom push syntax remains similar
        ti.xcom_push(key='health_summary', value=summary_data)
        
        return summary_data
    
    
    @task(task_id="final_status_check")
    def final_status_check(**context):
        """
        Final status check - fail the DAG if any critical checks failed
        """
        ti = context['ti']
        
        # Pull summary from XCom
        summary = ti.xcom_pull(task_ids='health_summary', key='health_summary')
        
        if not summary:
            raise AirflowException("❌ Could not retrieve health summary")
        
        failed_count = summary.get('failed', 0)
        
        print("\n" + "="*80)
        print("🎯 FINAL STATUS CHECK")
        print("="*80)
        print(f"Total Checks: {summary['total']}")
        print(f"Successful: {summary['success']}")
        print(f"Failed: {failed_count}")
        print("="*80 + "\n")
        
        if failed_count > 0:
            raise AirflowException(
                f"🚨 HEALTH CHECK FAILED: {failed_count} check(s) failed\n"
                f"Review the logs above for details"
            )
        
        print("✅ ALL HEALTH CHECKS PASSED - SYSTEM HEALTHY")
        return {'status': 'all_healthy', 'timestamp': datetime.now().isoformat()}
    
    
    # Define task dependencies
    # In Airflow 3.x, task dependencies are defined the same way
    
    # Service checks (run in parallel)
    scheduler_check = check_scheduler_service()
    api_server_check = check_api_server_service()
    dag_processor_check = check_dag_processor_service()
    triggerer_check = check_triggerer_service()
    celery_worker_check = check_celery_worker_service()
    
    # Infrastructure checks (run in parallel)
    system_resources_check = check_system_resources()
    database_check = check_database_connectivity()
    redis_check = check_redis_connectivity()
    
    # Summary task (waits for all checks to complete)
    summary = health_summary()
    
    # Final status check
    final = final_status_check()
    
    # Set up dependencies
    # All service checks must complete before summary
    [
        scheduler_check,
        api_server_check,
        dag_processor_check,
        triggerer_check,
        celery_worker_check,
        system_resources_check,
        database_check,
        redis_check
    ] >> summary >> final


# Instantiate the DAG
dag_instance = health_monitor_dag()
