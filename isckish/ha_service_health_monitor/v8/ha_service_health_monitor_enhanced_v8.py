"""
Airflow HA Infrastructure Health Monitor - Enhanced V8
CHANGES IN V8:
- Added comprehensive log collection (service logs + task-specific logs + worker logs)
- Added VM Resource Inventory Report task
- Fixed top 5 process display in system resources
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
import json
import re
from collections import OrderedDict


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

# NFS nodes
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

# All nodes for system monitoring
ALL_NODES = {
    'haproxy-1': '10.101.20.202',
    'haproxy-2': '10.101.20.146',
    'scheduler-2': '10.101.20.132',
    'nfs-1': '10.101.20.165',
    'nfs-2': '10.101.20.203',
    'celery-1': '10.101.20.199',
    'celery-2': '10.101.20.200',
    'postgresql-1': '10.101.20.204',
    'postgresql-2': '10.101.20.166',
    'postgresql-3': '10.101.20.137',
    'rabbit-1': '10.101.20.205',
    'rabbit-2': '10.101.20.147',
    'rabbit-3': '10.101.20.206',
    'ftp': '10.101.20.164',
    'target-1': '10.101.20.201',
    'monitoring': '10.101.20.201',
}

# Only airflow nodes have logs directory
AIRFLOW_NODES_WITH_LOGS = [
    'haproxy-1', 'haproxy-2', 'scheduler-2',
    'nfs-1', 'nfs-2', 'celery-1', 'celery-2'
]

AIRFLOW_HOME = '/home/rocky/airflow'
AIRFLOW_LOGS_BASE = f'{AIRFLOW_HOME}/logs'


def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except:
        return socket.gethostname()


def get_task_identifiers(context=None):
    """Extract unique identifiers for task instance tracing"""
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
            
            if hasattr(ti, 'external_executor_id'):
                identifiers['external_executor_id'] = ti.external_executor_id
            
            identifiers['ti_key'] = f"{ti.dag_id}__{ti.task_id}__{ti.execution_date}"
            identifiers['pid'] = os.getpid()
            
            if hasattr(ti, 'map_index'):
                identifiers['map_index'] = ti.map_index
    
    except Exception as e:
        identifiers['error'] = str(e)
    
    return identifiers


def format_identifiers_for_grep(identifiers):
    """Create grep pattern from identifiers"""
    patterns = []
    
    if identifiers.get('task_id'):
        patterns.append(identifiers['task_id'])
    if identifiers.get('run_id'):
        patterns.append(identifiers['run_id'])
    if identifiers.get('job_id'):
        patterns.append(str(identifiers['job_id']))
    if identifiers.get('external_executor_id'):
        patterns.append(identifiers['external_executor_id'])
    
    return '|'.join(patterns) if patterns else identifiers.get('task_id', 'taskinstance')


def fetch_service_logs(ip: str, service: str, hostname: str, lines: int = 100) -> str:
    """Fetch service logs from journalctl"""
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        if is_local_check:
            cmd = f"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso"
        else:
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso\""
        
        print(f"🔍 Fetching last {lines} lines of journalctl for {service} on {hostname}...")
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout
            if '[Invalid date]' in output:
                output = output.replace('[Invalid date]', '')
            return output
        else:
            return f"⚠️ Could not fetch journalctl logs (returncode: {result.returncode})\nStderr: {result.stderr}"
    
    except subprocess.TimeoutExpired:
        return "⚠️ Timeout while fetching journalctl logs"
    except Exception as e:
        return f"⚠️ Error fetching journalctl logs: {str(e)}"


def fetch_task_specific_logs(identifiers: dict, lines: int = 100) -> str:
    """Fetch logs with grep pattern across Airflow components"""
    grep_pattern = format_identifiers_for_grep(identifiers)
    
    print(f"\n🔍 Searching for task-specific logs using pattern: {grep_pattern}")
    
    all_logs = []
    all_log_lines = set()
    
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
            
            if is_local_check:
                cmd = f"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso | grep -E '({grep_pattern})' | tail -50"
            else:
                cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso | grep -E '({grep_pattern})' | tail -50\""
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout
                if '[Invalid date]' in output:
                    output = output.replace('[Invalid date]', '')
                
                new_lines = []
                for line in output.split('\n'):
                    if line.strip() and line not in all_log_lines:
                        all_log_lines.add(line)
                        new_lines.append(line)
                
                if new_lines:
                    all_logs.append(f"\n{'='*80}\n📋 {component_name} logs for this task:\n{'='*80}\n" + '\n'.join(new_lines))
                else:
                    all_logs.append(f"\n⭕ No unique logs found in {component_name}")
            else:
                all_logs.append(f"\n⭕ No relevant logs found in {component_name}")
        
        except Exception as e:
            all_logs.append(f"\n⚠️ Error fetching logs from {component_name}: {str(e)}")
    
    return '\n'.join(all_logs) if all_logs else "⚠️ No task-specific logs fetched"


def fetch_airflow_worker_logs() -> str:
    """Fetch Airflow worker logs for the current task"""
    try:
        context = get_current_context()
        dag_id = context['dag'].dag_id
        task_id = context['task'].task_id
        run_id = context['run_id']
        try_number = context['ti'].try_number
        
        log_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/attempt={try_number}.log"
        
        print(f"🔍 Searching for worker log at: {log_pattern}")
        
        if os.path.exists(log_pattern):
            with open(log_pattern, 'r') as f:
                lines = f.readlines()
                return ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
        else:
            glob_pattern = f"{AIRFLOW_LOGS_BASE}/dag_id={dag_id}/run_id={run_id}/task_id={task_id}/*.log"
            matching_files = glob.glob(glob_pattern)
            
            if matching_files:
                latest_file = max(matching_files, key=os.path.getctime)
                with open(latest_file, 'r') as f:
                    lines = f.readlines()
                    return ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
            
            return f"⚠️ Worker log file not found"
    
    except Exception as e:
        return f"⚠️ Error fetching worker logs: {str(e)}"


def get_system_resources(ip: str, hostname: str) -> dict:
    """Collect system resources"""
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    should_calc_logs = hostname in AIRFLOW_NODES_WITH_LOGS
    
    if should_calc_logs:
        logs_calc = '''
if [ -d "/home/rocky/airflow/logs" ]; then
    cd /home/rocky/airflow/logs 2>/dev/null && logs_size=$(du -sh . 2>/dev/null | awk '{print $1}') || logs_size="N/A"
else
    logs_size="N/A"
fi
'''
    else:
        logs_calc = 'logs_size="N/A"'
    
    monitoring_script = f'''
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}' | cut -d'%' -f1)
cpu_cores=$(nproc)

mem_info=$(free -m | grep Mem)
mem_total=$(echo "$mem_info" | awk '{{print $2}}')
mem_used=$(echo "$mem_info" | awk '{{print $3}}')
mem_available=$(echo "$mem_info" | awk '{{print $7}}')
mem_percent=$(awk "BEGIN {{printf \\"%.2f\\", ($mem_used / $mem_total) * 100}}")

disk_info=$(df -h / | tail -1)
disk_total=$(echo "$disk_info" | awk '{{print $2}}')
disk_used=$(echo "$disk_info" | awk '{{print $3}}')
disk_available=$(echo "$disk_info" | awk '{{print $4}}')
disk_percent=$(echo "$disk_info" | awk '{{print $5}}' | sed 's/%//')

top_cpu=$(ps aux --sort=-%cpu | head -6 | tail -5 | awk '{{printf "%s|%s|%s\\n", $11, $3, $2}}')
top_mem=$(ps aux --sort=-%mem | head -6 | tail -5 | awk '{{printf "%s|%s|%s\\n", $11, $4, $2}}')

{logs_calc}

echo "CPU_USAGE=$cpu_usage"
echo "CPU_CORES=$cpu_cores"
echo "MEM_TOTAL=$mem_total"
echo "MEM_USED=$mem_used"
echo "MEM_AVAILABLE=$mem_available"
echo "MEM_PERCENT=$mem_percent"
echo "DISK_TOTAL=$disk_total"
echo "DISK_USED=$disk_used"
echo "DISK_AVAILABLE=$disk_available"
echo "DISK_PERCENT=$disk_percent"
echo "LOGS_SIZE=$logs_size"
echo "TOP_CPU_START"
echo "$top_cpu"
echo "TOP_CPU_END"
echo "TOP_MEM_START"
echo "$top_mem"
echo "TOP_MEM_END"
'''
    
    try:
        if is_local_check:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
                tf.write(monitoring_script)
                temp_script = tf.name
            
            try:
                cmd = f"bash {temp_script}"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=45
                )
            finally:
                os.unlink(temp_script)
        else:
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'bash -s' <<'ENDSCRIPT'\n{monitoring_script}\nENDSCRIPT"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=45
            )
        
        if result.returncode != 0:
            return {'status': 'error', 'error': f"Command failed: {result.stderr}"}
        
        output = result.stdout
        metrics = {'status': 'success', 'hostname': hostname, 'ip': ip}
        
        for line in output.split('\n'):
            if '=' in line and not line.startswith('TOP_'):
                key, value = line.split('=', 1)
                metrics[key.lower()] = value.strip()
        
        # Parse top CPU
        top_cpu_section = re.search(r'TOP_CPU_START\n(.*?)\nTOP_CPU_END', output, re.DOTALL)
        if top_cpu_section:
            metrics['top_cpu'] = []
            for line in top_cpu_section.group(1).strip().split('\n'):
                if line.strip():
                    parts = line.split('|')
                    if len(parts) == 3:
                        metrics['top_cpu'].append({
                            'process': parts[0],
                            'cpu_percent': parts[1],
                            'pid': parts[2]
                        })
        
        # Parse top memory
        top_mem_section = re.search(r'TOP_MEM_START\n(.*?)\nTOP_MEM_END', output, re.DOTALL)
        if top_mem_section:
            metrics['top_mem'] = []
            for line in top_mem_section.group(1).strip().split('\n'):
                if line.strip():
                    parts = line.split('|')
                    if len(parts) == 3:
                        metrics['top_mem'].append({
                            'process': parts[0],
                            'mem_percent': parts[1],
                            'pid': parts[2]
                        })
        
        return metrics
        
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'Timeout (45s) while collecting metrics'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def detect_active_nfs_node() -> str:
    """Detect active NFS node"""
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
    dag_id='ha_service_health_monitor_v8',
    description='Monitor all HA services - V8 with comprehensive logging and VM inventory',
    schedule='*/2 * * * *',
    start_date=datetime(2025, 10, 12),
    catchup=False,
    max_active_tasks=16,
    default_args={
        'owner': 'airflow',
        'retries': 0,
    },
    tags=['monitoring', 'health-check', 'v8'],
)
def ha_service_health_monitor_v8():
    
    @task(task_id="detect_nfs_active_node")
    def detect_nfs_node():
        active = detect_active_nfs_node()
        print(f"🔍 Active NFS Node: {active}")
        return active
    
    active_nfs = detect_nfs_node()
    
    @task(task_id="check_system_resources")
    def check_system_resources():
        """Monitor system resources across all nodes"""
        print("\n" + "="*80)
        print("💻 SYSTEM RESOURCES MONITORING")
        print("="*80 + "\n")
        
        all_metrics = {}
        
        for hostname, ip in ALL_NODES.items():
            print(f"📊 Collecting metrics from {hostname} ({ip})...")
            metrics = get_system_resources(ip, hostname)
            all_metrics[hostname] = metrics
            
            if metrics.get('status') == 'success':
                logs_info = metrics.get('logs_size', 'N/A')
                print(f"✅ {hostname}: CPU {metrics.get('cpu_usage', 'N/A')}% | "
                      f"RAM {metrics.get('mem_percent', 'N/A')}% | "
                      f"Disk {metrics.get('disk_percent', 'N/A')}% | "
                      f"Logs {logs_info}")
            else:
                print(f"❌ {hostname}: {metrics.get('error', 'Unknown error')}")
        
        # Generate detailed report
        report = "\n" + "="*80 + "\n"
        report += "📊 SYSTEM RESOURCES REPORT\n"
        report += "="*80 + "\n\n"
        
        for hostname in sorted(all_metrics.keys()):
            metrics = all_metrics[hostname]
            report += f"{'─'*80}\n"
            report += f"🖥️  {hostname.upper()} ({metrics.get('ip', 'N/A')})\n"
            report += f"{'─'*80}\n"
            
            if metrics.get('status') == 'success':
                report += f"\n💻 CPU:\n"
                report += f"   Usage: {metrics.get('cpu_usage', 'N/A')}%\n"
                report += f"   Cores: {metrics.get('cpu_cores', 'N/A')}\n"
                
                report += f"\n🧠 MEMORY:\n"
                report += f"   Used: {metrics.get('mem_used', 'N/A')} MB / {metrics.get('mem_total', 'N/A')} MB ({metrics.get('mem_percent', 'N/A')}%)\n"
                report += f"   Available: {metrics.get('mem_available', 'N/A')} MB\n"
                
                report += f"\n💾 DISK (/):\n"
                report += f"   Used: {metrics.get('disk_used', 'N/A')} / {metrics.get('disk_total', 'N/A')} ({metrics.get('disk_percent', 'N/A')}%)\n"
                report += f"   Available: {metrics.get('disk_available', 'N/A')}\n"
                
                if hostname in AIRFLOW_NODES_WITH_LOGS:
                    report += f"\n📁 AIRFLOW LOGS DIRECTORY:\n"
                    report += f"   Size: {metrics.get('logs_size', 'N/A')}\n"
                
                if metrics.get('top_cpu'):
                    report += f"\n🔥 TOP 5 CPU PROCESSES:\n"
                    for i, proc in enumerate(metrics['top_cpu'], 1):
                        report += f"   {i}. {proc['process'][:40]:40} | CPU: {proc['cpu_percent']:>6}% | PID: {proc['pid']}\n"
                
                if metrics.get('top_mem'):
                    report += f"\n🧠 TOP 5 MEMORY PROCESSES:\n"
                    for i, proc in enumerate(metrics['top_mem'], 1):
                        report += f"   {i}. {proc['process'][:40]:40} | MEM: {proc['mem_percent']:>6}% | PID: {proc['pid']}\n"
            else:
                report += f"\n❌ ERROR: {metrics.get('error', 'Failed to collect metrics')}\n"
            
            report += "\n"
        
        report += "="*80 + "\n"
        
        print(report)
        
        context = get_current_context()
        context['task_instance'].xcom_push(key='system_metrics', value=all_metrics)
        
        return all_metrics
    
    @task(task_id="vm_resource_inventory")
    def vm_resource_inventory():
        """Generate VM Resource Inventory Report"""
        print("\n" + "="*80)
        print("🖥️  VM RESOURCE INVENTORY")
        print("="*80 + "\n")
        
        inventory = []
        successful = 0
        failed = 0
        
        for hostname, ip in ALL_NODES.items():
            print(f"📊 Scanning {hostname} ({ip})...")
            metrics = get_system_resources(ip, hostname)
            
            if metrics.get('status') == 'success':
                cpu_cores = metrics.get('cpu_cores', 'N/A')
                mem_total_mb = metrics.get('mem_total', '0')
                
                # Convert MB to GB
                try:
                    mem_gb = float(mem_total_mb) / 1024
                    mem_gb_str = f"{mem_gb:.2f}"
                except:
                    mem_gb = 0
                    mem_gb_str = "N/A"
                
                inventory.append({
                    'hostname': hostname,
                    'ip': ip,
                    'cpu_cores': cpu_cores,
                    'ram_gb': mem_gb_str,
                    'ram_gb_num': mem_gb
                })
                successful += 1
                print(f"✅ {hostname}: {cpu_cores} cores, {mem_gb_str} GB RAM")
            else:
                inventory.append({
                    'hostname': hostname,
                    'ip': ip,
                    'cpu_cores': 'N/A',
                    'ram_gb': 'N/A',
                    'ram_gb_num': 0
                })
                failed += 1
                print(f"❌ {hostname}: Failed to collect")
        
        # Generate report
        report = "\n" + "="*80 + "\n"
        report += "Individual VM Resources\n"
        report += "="*80 + "\n"
        report += f"{'VM Name':<25} {'IP Address':<18} {'CPU Cores':<12} {'RAM (GB)'}\n"
        report += "-"*80 + "\n"
        
        # Calculate totals
        total_cpu = 0
        total_ram = 0.0
        
        for vm in sorted(inventory, key=lambda x: x['hostname']):
            report += f"{vm['hostname']:<25} {vm['ip']:<18} {str(vm['cpu_cores']):<12} {vm['ram_gb']}\n"
            
            # Add to totals
            try:
                if vm['cpu_cores'] != 'N/A':
                    total_cpu += int(vm['cpu_cores'])
            except:
                pass
            
            total_ram += vm['ram_gb_num']
        
        report += "\n" + "="*80 + "\n"
        report += "Summary\n"
        report += "="*80 + "\n"
        report += f"Total VMs scanned:        {len(inventory)}\n"
        report += f"Successful connections:   {successful}\n"
        report += f"Failed connections:       {failed}\n"
        report += f"\n"
        report += f"Total CPU Cores:          {total_cpu}\n"
        report += f"Total RAM (GB):           {total_ram:.2f}\n"
        report += "="*80 + "\n"
        
        print(report)
        
        return {
            'total_vms': len(inventory),
            'successful': successful,
            'failed': failed,
            'total_cpu_cores': total_cpu,
            'total_ram_gb': round(total_ram, 2),
            'inventory': inventory
        }
    
    @task(task_id="check_nfs_services")
    def check_nfs_services(active_nfs_node: str):
        """Check NFS cluster (both nodes with active/passive logic)"""
        print(f"🔍 Checking NFS cluster - Active node: {active_nfs_node}")
        
        context = get_current_context()
        ti = context['task_instance']
        
        active_only_services = ['nfs-server', 'lsyncd', 'airflow-dag-processor']
        
        all_failures = []
        has_critical_failure = False
        has_expected_passive_failure = False
        
        for hostname, config in NFS_NODES.items():
            ip = config['ip']
            services = config['services']
            is_active_node = (hostname == active_nfs_node)
            
            print(f"\n{'─'*60}")
            print(f"📍 {hostname} ({ip}) - {'ACTIVE' if is_active_node else 'PASSIVE'}")
            print(f"{'─'*60}")
            
            for service in services:
                status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
                result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
                service_status = result.stdout.strip()
                
                if service in active_only_services:
                    if is_active_node:
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
                                error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS (across all components):\n{'='*80}\n{task_specific_logs}\n"
                                
                                worker_logs = fetch_airflow_worker_logs()
                                error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                            except Exception as log_error:
                                error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                            
                            all_failures.append(error_msg)
                            has_critical_failure = True
                            print(f"❌ {service}: CRITICAL - {service_status}")
                        else:
                            print(f"✅ {service}: ACTIVE")
                    else:
                        if service_status == 'active':
                            error_msg = f"🚨 CRITICAL: {service} on PASSIVE node {hostname} is ACTIVE! Split-brain!\n"
                            
                            identifiers = get_task_identifiers(context)
                            logs = fetch_service_logs(ip, service, hostname, lines=100)
                            error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                            
                            try:
                                task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                                error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                                
                                worker_logs = fetch_airflow_worker_logs()
                                error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                            except Exception as log_error:
                                error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                            
                            all_failures.append(error_msg)
                            has_critical_failure = True
                            print(f"❌ {service}: CRITICAL - SPLIT BRAIN")
                        else:
                            print(f"⏸️ {service}: NOT ACTIVE (expected)")
                            has_expected_passive_failure = True
                else:
                    if service_status != 'active':
                        error_msg = f"❌ {service} on {hostname} is {service_status.upper()}\n"
                        
                        identifiers = get_task_identifiers(context)
                        logs = fetch_service_logs(ip, service, hostname, lines=100)
                        error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                        
                        try:
                            task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                            error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                            
                            worker_logs = fetch_airflow_worker_logs()
                            error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                        except Exception as log_error:
                            error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                        
                        all_failures.append(error_msg)
                        has_critical_failure = True
                        print(f"❌ {service}: CRITICAL - {service_status}")
                    else:
                        print(f"✅ {service}: ACTIVE")
        
        if has_critical_failure:
            ti.xcom_push(key='failure_type', value='CRITICAL_NFS_FAILURE')
            raise AirflowException('\n'.join(all_failures))
        elif has_expected_passive_failure:
            ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE_INACTIVE')
            raise AirflowException(f"⏸️ EXPECTED: Passive NFS node services are correctly NOT ACTIVE")
        
        print("\n✅ NFS cluster is healthy")
        return {'status': 'healthy', 'active_node': active_nfs_node}
    
    @task(task_id="check_haproxy_services")
    def check_haproxy_services():
        """Check HAProxy cluster (haproxy-1 and haproxy-2)"""
        print("🔍 Checking HAProxy cluster")
        
        context = get_current_context()
        
        haproxy_nodes = [
            ('haproxy-1', '10.101.20.202', ['haproxy', 'keepalived']),
            ('haproxy-2', '10.101.20.146', ['haproxy', 'keepalived'])
        ]
        
        all_failures = []
        
        for hostname, ip, services in haproxy_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            for service in services:
                status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
                result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
                service_status = result.stdout.strip()
                
                if service_status != 'active':
                    error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                    
                    identifiers = get_task_identifiers(context)
                    logs = fetch_service_logs(ip, service, hostname, lines=100)
                    error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                    
                    try:
                        task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                        error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                        
                        worker_logs = fetch_airflow_worker_logs()
                        error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                    except Exception as log_error:
                        error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                    
                    all_failures.append(error_msg)
                    print(f"❌ {service}: {service_status}")
                else:
                    print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ HAProxy cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_scheduler_services")
    def check_scheduler_services():
        """Check Scheduler cluster (haproxy-1 and scheduler-2)"""
        print("🔍 Checking Scheduler cluster")
        
        context = get_current_context()
        
        scheduler_nodes = [
            ('haproxy-1', '10.101.20.202'),
            ('scheduler-2', '10.101.20.132')
        ]
        
        all_failures = []
        
        for hostname, ip in scheduler_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            service = 'airflow-scheduler'
            status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
            result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
            service_status = result.stdout.strip()
            
            if service_status != 'active':
                error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                
                identifiers = get_task_identifiers(context)
                logs = fetch_service_logs(ip, service, hostname, lines=100)
                error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                
                try:
                    task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                    error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                    
                    worker_logs = fetch_airflow_worker_logs()
                    error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                except Exception as log_error:
                    error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                
                all_failures.append(error_msg)
                print(f"❌ {service}: {service_status}")
            else:
                print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ Scheduler cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_webserver_services")
    def check_webserver_services():
        """Check Webserver cluster (haproxy-1 and haproxy-2)"""
        print("🔍 Checking Webserver cluster")
        
        context = get_current_context()
        
        webserver_nodes = [
            ('haproxy-1', '10.101.20.202'),
            ('haproxy-2', '10.101.20.146')
        ]
        
        all_failures = []
        
        for hostname, ip in webserver_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            service = 'airflow-webserver'
            status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
            result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
            service_status = result.stdout.strip()
            
            if service_status != 'active':
                error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                
                identifiers = get_task_identifiers(context)
                logs = fetch_service_logs(ip, service, hostname, lines=100)
                error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                
                try:
                    task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                    error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                    
                    worker_logs = fetch_airflow_worker_logs()
                    error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                except Exception as log_error:
                    error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                
                all_failures.append(error_msg)
                print(f"❌ {service}: {service_status}")
            else:
                print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ Webserver cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_rabbitmq_services")
    def check_rabbitmq_services():
        """Check RabbitMQ cluster (all 3 nodes)"""
        print("🔍 Checking RabbitMQ cluster")
        
        context = get_current_context()
        
        rabbitmq_nodes = [
            ('rabbit-1', '10.101.20.205'),
            ('rabbit-2', '10.101.20.147'),
            ('rabbit-3', '10.101.20.206')
        ]
        
        all_failures = []
        
        for hostname, ip in rabbitmq_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            service = 'rabbitmq-server'
            status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
            result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
            service_status = result.stdout.strip()
            
            if service_status != 'active':
                error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                
                identifiers = get_task_identifiers(context)
                logs = fetch_service_logs(ip, service, hostname, lines=100)
                error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                
                try:
                    task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                    error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                    
                    worker_logs = fetch_airflow_worker_logs()
                    error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                except Exception as log_error:
                    error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                
                all_failures.append(error_msg)
                print(f"❌ {service}: {service_status}")
            else:
                print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ RabbitMQ cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_postgresql_services")
    def check_postgresql_services():
        """Check PostgreSQL cluster (all 3 nodes with patroni + etcd)"""
        print("🔍 Checking PostgreSQL cluster")
        
        context = get_current_context()
        
        postgresql_nodes = [
            ('postgresql-1', '10.101.20.204'),
            ('postgresql-2', '10.101.20.166'),
            ('postgresql-3', '10.101.20.137')
        ]
        
        all_failures = []
        
        for hostname, ip in postgresql_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            for service in ['patroni', 'etcd']:
                status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
                result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
                service_status = result.stdout.strip()
                
                if service_status != 'active':
                    error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                    
                    identifiers = get_task_identifiers(context)
                    logs = fetch_service_logs(ip, service, hostname, lines=100)
                    error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                    
                    try:
                        task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                        error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                        
                        worker_logs = fetch_airflow_worker_logs()
                        error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                    except Exception as log_error:
                        error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                    
                    all_failures.append(error_msg)
                    print(f"❌ {service}: {service_status}")
                else:
                    if service == 'patroni':
                        last_octet = ip.split(".")[-1]
                        role_cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no rocky@{ip} 'patronictl -c /etc/patroni/patroni.yml list 2>/dev/null | grep {last_octet}'"
                        role_result = subprocess.run(role_cmd, shell=True, capture_output=True, text=True, timeout=5)
                        
                        if 'Leader' in role_result.stdout:
                            print(f"✅ {service}: ACTIVE [LEADER]")
                        elif 'Replica' in role_result.stdout:
                            print(f"✅ {service}: ACTIVE [REPLICA]")
                        else:
                            print(f"✅ {service}: ACTIVE")
                    else:
                        print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ PostgreSQL cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_celery_services")
    def check_celery_services():
        """Check Celery worker cluster (celery-1 and celery-2)"""
        print("🔍 Checking Celery worker cluster")
        
        context = get_current_context()
        
        celery_nodes = [
            ('celery-1', '10.101.20.199'),
            ('celery-2', '10.101.20.200')
        ]
        
        all_failures = []
        
        for hostname, ip in celery_nodes:
            print(f"\n📍 Checking {hostname} ({ip})")
            
            service = 'airflow-worker'
            status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
            result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
            service_status = result.stdout.strip()
            
            if service_status != 'active':
                error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
                
                identifiers = get_task_identifiers(context)
                logs = fetch_service_logs(ip, service, hostname, lines=100)
                error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
                
                try:
                    task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                    error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                    
                    worker_logs = fetch_airflow_worker_logs()
                    error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
                except Exception as log_error:
                    error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
                
                all_failures.append(error_msg)
                print(f"❌ {service}: {service_status}")
            else:
                print(f"✅ {service}: ACTIVE")
        
        if all_failures:
            raise AirflowException('\n'.join(all_failures))
        
        print("\n✅ Celery worker cluster is healthy")
        return {'status': 'healthy'}
    
    @task(task_id="check_ftp_service")
    def check_ftp_service():
        """Check FTP service"""
        print("🔍 Checking FTP service")
        
        context = get_current_context()
        
        hostname = 'ftp'
        ip = '10.101.20.164'
        service = 'vsftpd'
        
        status_check = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} 'sudo systemctl is-active {service} 2>&1'"
        result = subprocess.run(status_check, shell=True, capture_output=True, text=True, timeout=10)
        service_status = result.stdout.strip()
        
        if service_status != 'active':
            error_msg = f"❌ {service} on {hostname} ({ip}) is {service_status.upper()}\n"
            
            identifiers = get_task_identifiers(context)
            logs = fetch_service_logs(ip, service, hostname, lines=100)
            error_msg += f"\n{'='*80}\n📋 SERVICE LOGS (last 100 lines):\n{'='*80}\n{logs}\n"
            
            try:
                task_specific_logs = fetch_task_specific_logs(identifiers, lines=100)
                error_msg += f"\n{'='*80}\n📋 TASK-SPECIFIC AIRFLOW LOGS:\n{'='*80}\n{task_specific_logs}\n"
                
                worker_logs = fetch_airflow_worker_logs()
                error_msg += f"\n{'='*80}\n📋 THIS TASK'S WORKER LOG:\n{'='*80}\n{worker_logs}\n"
            except Exception as log_error:
                error_msg += f"\n⚠️ Could not fetch some Airflow logs: {str(log_error)}"
            
            raise AirflowException(error_msg)
        
        print(f"✅ {service}: ACTIVE")
        return {'status': 'healthy'}
    
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
            
            print(f"✅ PostgreSQL VIP (10.101.20.210:5000) is HEALTHY - {dag_count} DAGs")
            return {'status': 'healthy', 'dags': dag_count}
        except Exception as e:
            error_msg = f"❌ PostgreSQL VIP FAILED: {str(e)}\n"
            
            for hostname, ip in [('postgresql-1', '10.101.20.204'), ('postgresql-2', '10.101.20.166'), ('postgresql-3', '10.101.20.137')]:
                try:
                    logs = fetch_service_logs(ip, 'patroni', hostname, lines=100)
                    error_msg += f"\n{'='*80}\n📋 Patroni logs from {hostname}:\n{'='*80}\n{logs}\n"
                except:
                    pass
            
            raise AirflowException(error_msg)
    
    
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
            
            for name, ip in nodes:
                try:
                    logs = fetch_service_logs(ip, 'rabbitmq-server', name, lines=100)
                    error_msg += f"\n{'='*80}\n📋 RabbitMQ logs from {name}:\n{'='*80}\n{logs}\n"
                except:
                    pass
            
            raise AirflowException(error_msg)
        
        print(f"✅ RabbitMQ Cluster: {healthy}/3 nodes healthy")
        return {'healthy_nodes': healthy, 'total': 3, 'nodes': results}
    
    
    @task(task_id="check_scheduler_heartbeat")
    def check_scheduler_heartbeat():
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
                
                for hostname, ip in [('haproxy-1', '10.101.20.202'), ('scheduler-2', '10.101.20.132')]:
                    try:
                        logs = fetch_service_logs(ip, 'airflow-scheduler', hostname, lines=100)
                        error_msg += f"\n{'='*80}\n📋 Scheduler logs from {hostname}:\n{'='*80}\n{logs}\n"
                    except:
                        pass
                
                raise AirflowException(error_msg)
            
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
        try:
            from airflow.providers.celery.executors.celery_executor import app
            stats = app.control.inspect().stats()
            
            if not stats:
                error_msg = "❌ NO CELERY WORKERS AVAILABLE\n"
                
                for hostname, ip in [('celery-1', '10.101.20.199'), ('celery-2', '10.101.20.200')]:
                    try:
                        logs = fetch_service_logs(ip, 'airflow-worker', hostname, lines=100)
                        error_msg += f"\n{'='*80}\n📋 Worker logs from {hostname}:\n{'='*80}\n{logs}\n"
                    except:
                        pass
                
                raise AirflowException(error_msg)
            
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
        """Generate health summary"""
        from airflow.models import TaskInstance
        from airflow.utils.state import State
        
        context = get_current_context()
        dag_run = context['dag_run']
        ti = context['task_instance']
        
        task_instances = dag_run.get_task_instances()
        
        failed_tasks = [task for task in task_instances if task.state == State.FAILED]
        success_tasks = [task for task in task_instances if task.state == State.SUCCESS]
        
        expected_passive_failures = []
        critical_failures = []
        
        for failed_task in failed_tasks:
            failure_type = failed_task.xcom_pull(task_ids=failed_task.task_id, key='failure_type')
            
            if failure_type == 'EXPECTED_PASSIVE_INACTIVE':
                expected_passive_failures.append(failed_task)
            else:
                critical_failures.append(failed_task)
        
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
        
        # System metrics summary
        system_metrics = ti.xcom_pull(task_ids='check_system_resources', key='system_metrics')
        if system_metrics:
            print("\n" + "=" * 80)
            print("💻 SYSTEM RESOURCES SUMMARY")
            print("=" * 80)
            for hostname in sorted(system_metrics.keys()):
                metrics = system_metrics[hostname]
                if metrics.get('status') == 'success':
                    if hostname in AIRFLOW_NODES_WITH_LOGS:
                        logs_display = metrics.get('logs_size', 'N/A')
                        print(f"{hostname:15} | CPU: {metrics.get('cpu_usage', 'N/A'):>6}% | "
                              f"RAM: {metrics.get('mem_percent', 'N/A'):>6}% | "
                              f"Disk: {metrics.get('disk_percent', 'N/A'):>4}% | "
                              f"Logs: {logs_display:>8}")
                    else:
                        print(f"{hostname:15} | CPU: {metrics.get('cpu_usage', 'N/A'):>6}% | "
                              f"RAM: {metrics.get('mem_percent', 'N/A'):>6}% | "
                              f"Disk: {metrics.get('disk_percent', 'N/A'):>4}%")
                else:
                    error_msg = metrics.get('error', 'N/A')
                    if len(error_msg) > 50:
                        error_msg = error_msg[:47] + "..."
                    print(f"{hostname:15} | ERROR: {error_msg}")
        
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
                f"Failed services: {', '.join(critical_tasks)}"
            )
        
        print("✅ All critical services are healthy - DAG SUCCESS")
        return {'status': 'all_healthy'}
    
    
    # Dependencies
    nfs = check_nfs_services(active_nfs)
    haproxy = check_haproxy_services()
    scheduler_svc = check_scheduler_services()
    webserver = check_webserver_services()
    rabbitmq_svc = check_rabbitmq_services()
    postgresql_svc = check_postgresql_services()
    celery_svc = check_celery_services()
    ftp = check_ftp_service()
    
    pg_vip = check_postgresql_vip()
    rabbitmq_cluster = check_rabbitmq_cluster()
    scheduler_hb = check_scheduler_heartbeat()
    celery_workers = check_celery_workers()
    sys_resources = check_system_resources()
    vm_inventory = vm_resource_inventory()
    
    summary = health_summary()
    final = final_status_check(summary)
    
    # Service checks
    [nfs, haproxy, scheduler_svc, webserver, rabbitmq_svc, postgresql_svc, celery_svc, ftp] >> summary
    
    # Cluster checks
    [pg_vip, rabbitmq_cluster, scheduler_hb, celery_workers, sys_resources, vm_inventory] >> summary
    
    summary >> final


dag_instance = ha_service_health_monitor_v8()