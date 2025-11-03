"""
Airflow HA Infrastructure Health Monitor - Enhanced Version 3
Fixes:
- Eliminated duplicate log entries by using sets and proper deduplication
- Fixed [Invalid date] issues by using short-precise format
- Added system resource monitoring (CPU, RAM, Disk)
- Added top 5 process monitoring
- Added Airflow logs directory size monitoring
- Improved log collection and presentation
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
import json
from typing import Dict, List, Set


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

# Airflow nodes for resource monitoring
AIRFLOW_MONITORING_NODES = {
    'haproxy-1': {'ip': '10.101.20.202', 'roles': ['scheduler', 'webserver']},
    'haproxy-2': {'ip': '10.101.20.146', 'roles': ['webserver']},
    'scheduler-2': {'ip': '10.101.20.132', 'roles': ['scheduler']},
    'celery-1': {'ip': '10.101.20.199', 'roles': ['worker']},
    'celery-2': {'ip': '10.101.20.200', 'roles': ['worker']},
    'nfs-1': {'ip': '10.101.20.165', 'roles': ['nfs']},
    'nfs-2': {'ip': '10.101.20.203', 'roles': ['nfs']},
}

AIRFLOW_LOGS_PATH = '/home/rocky/airflow/logs'


def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except:
        return socket.gethostname()


def deduplicate_log_lines(logs: str) -> str:
    """
    Remove duplicate log lines while preserving order.
    This fixes the duplicate log entry issue.
    """
    if not logs:
        return logs
    
    lines = logs.split('\n')
    seen: Set[str] = set()
    unique_lines: List[str] = []
    
    for line in lines:
        # Use stripped line for comparison to handle whitespace differences
        line_key = line.strip()
        if line_key and line_key not in seen:
            seen.add(line_key)
            unique_lines.append(line)
        elif not line_key:  # Keep empty lines
            unique_lines.append(line)
    
    return '\n'.join(unique_lines)


def fetch_journalctl_logs(ip: str, service: str, hostname: str, minutes_back: int = 2) -> str:
    """
    Fetch journalctl logs for a failed service from the remote server.
    Uses short-precise format to avoid [Invalid date] issues.
    """
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        # Use short-precise format which includes microseconds and avoids [Invalid date]
        # Also added --output-fields to ensure we get consistent output
        if is_local_check:
            cmd = f"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 150 -o short-precise --output-fields=MESSAGE,PRIORITY"
        else:
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --since '{minutes_back} minutes ago' --no-pager -n 150 -o short-precise --output-fields=MESSAGE,PRIORITY\""
        
        print(f"📋 Fetching journalctl logs for {service} on {hostname} (last {minutes_back} minutes)...")
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Deduplicate the logs before returning
            return deduplicate_log_lines(result.stdout)
        else:
            return f"⚠️ Could not fetch journalctl logs (returncode: {result.returncode})\nStderr: {result.stderr}"
    
    except subprocess.TimeoutExpired:
        return "⚠️ Timeout while fetching journalctl logs"
    except Exception as e:
        return f"⚠️ Error fetching journalctl logs: {str(e)}"


def fetch_system_resources(ip: str, hostname: str) -> Dict:
    """
    Fetch system resource usage: CPU, RAM, and Disk.
    Returns dict with usage statistics.
    """
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        # Build comprehensive resource monitoring command
        cmd_parts = [
            # CPU usage (percentage)
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
            # Memory info (used, total, percentage)
            "free -m | awk 'NR==2{printf \"%s %s %.2f\", $3,$2,$3*100/$2 }'",
            # Disk usage for root partition
            "df -h / | awk 'NR==2{printf \"%s %s %s\", $3,$2,$5}'",
            # Top 5 CPU-consuming processes
            "ps aux --sort=-%cpu | head -6 | tail -5 | awk '{printf \"%s|%s|%s\\n\", $11, $3, $4}'",
            # Top 5 RAM-consuming processes  
            "ps aux --sort=-%mem | head -6 | tail -5 | awk '{printf \"%s|%s|%s\\n\", $11, $3, $4}'"
        ]
        
        full_cmd = " && echo '---' && ".join(cmd_parts)
        
        if not is_local_check:
            full_cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"{full_cmd}\""
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output_parts = result.stdout.strip().split('---')
            
            # Parse CPU
            cpu_usage = float(output_parts[0].strip()) if len(output_parts) > 0 else 0.0
            
            # Parse Memory
            mem_parts = output_parts[1].strip().split() if len(output_parts) > 1 else ['0', '0', '0']
            mem_used = int(mem_parts[0]) if len(mem_parts) > 0 else 0
            mem_total = int(mem_parts[1]) if len(mem_parts) > 1 else 0
            mem_percent = float(mem_parts[2]) if len(mem_parts) > 2 else 0.0
            
            # Parse Disk
            disk_parts = output_parts[2].strip().split() if len(output_parts) > 2 else ['0', '0', '0%']
            disk_used = disk_parts[0] if len(disk_parts) > 0 else '0'
            disk_total = disk_parts[1] if len(disk_parts) > 1 else '0'
            disk_percent = disk_parts[2] if len(disk_parts) > 2 else '0%'
            
            # Parse top CPU processes
            top_cpu = []
            if len(output_parts) > 3:
                cpu_lines = output_parts[3].strip().split('\n')
                for line in cpu_lines[:5]:
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 3:
                            top_cpu.append({
                                'process': parts[0],
                                'cpu': parts[1],
                                'mem': parts[2]
                            })
            
            # Parse top RAM processes
            top_mem = []
            if len(output_parts) > 4:
                mem_lines = output_parts[4].strip().split('\n')
                for line in mem_lines[:5]:
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 3:
                            top_mem.append({
                                'process': parts[0],
                                'cpu': parts[1],
                                'mem': parts[2]
                            })
            
            return {
                'hostname': hostname,
                'cpu': {
                    'usage_percent': cpu_usage,
                    'available_percent': 100.0 - cpu_usage,
                    'top_processes': top_cpu
                },
                'memory': {
                    'used_mb': mem_used,
                    'total_mb': mem_total,
                    'usage_percent': mem_percent,
                    'available_mb': mem_total - mem_used,
                    'top_processes': top_mem
                },
                'disk': {
                    'used': disk_used,
                    'total': disk_total,
                    'usage_percent': disk_percent
                }
            }
        else:
            return {
                'hostname': hostname,
                'error': f"Failed to fetch resources: {result.stderr}"
            }
    
    except Exception as e:
        return {
            'hostname': hostname,
            'error': f"Exception: {str(e)}"
        }


def fetch_airflow_logs_size(ip: str, hostname: str, logs_path: str = AIRFLOW_LOGS_PATH) -> Dict:
    """
    Get the size of Airflow logs directory on a node.
    """
    current_host = get_current_hostname()
    is_local_check = (current_host == hostname)
    
    try:
        # Command to get directory size in human readable and bytes
        cmd = f"du -sh {logs_path} && du -sb {logs_path} | awk '{{print $1}}'"
        
        if not is_local_check:
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"{cmd}\""
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            size_human = lines[0].split()[0] if len(lines) > 0 else 'Unknown'
            size_bytes = int(lines[1]) if len(lines) > 1 else 0
            
            return {
                'hostname': hostname,
                'path': logs_path,
                'size_human': size_human,
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / (1024 * 1024), 2),
                'size_gb': round(size_bytes / (1024 * 1024 * 1024), 2)
            }
        else:
            return {
                'hostname': hostname,
                'path': logs_path,
                'error': f"Could not get size: {result.stderr}"
            }
    
    except Exception as e:
        return {
            'hostname': hostname,
            'path': logs_path,
            'error': f"Exception: {str(e)}"
        }


def format_resource_report(resources: List[Dict]) -> str:
    """
    Format system resources into a readable report.
    """
    report = "\n" + "="*100 + "\n"
    report += "📊 SYSTEM RESOURCES MONITORING REPORT\n"
    report += "="*100 + "\n\n"
    
    for resource in resources:
        if 'error' in resource:
            report += f"❌ {resource['hostname']}: {resource['error']}\n\n"
            continue
        
        report += f"🖥️  {resource['hostname'].upper()}\n"
        report += "-" * 100 + "\n"
        
        # CPU Information
        cpu = resource.get('cpu', {})
        report += f"  💻 CPU:\n"
        report += f"     Usage: {cpu.get('usage_percent', 0):.2f}% | Available: {cpu.get('available_percent', 0):.2f}%\n"
        report += f"     Top 5 CPU-consuming processes:\n"
        for idx, proc in enumerate(cpu.get('top_processes', [])[:5], 1):
            report += f"        {idx}. {proc['process']:<40} CPU: {proc['cpu']:>6}%  MEM: {proc['mem']:>6}%\n"
        
        # Memory Information
        mem = resource.get('memory', {})
        report += f"\n  🧠 MEMORY:\n"
        report += f"     Used: {mem.get('used_mb', 0)} MB / {mem.get('total_mb', 0)} MB ({mem.get('usage_percent', 0):.2f}%)\n"
        report += f"     Available: {mem.get('available_mb', 0)} MB\n"
        report += f"     Top 5 Memory-consuming processes:\n"
        for idx, proc in enumerate(mem.get('top_processes', [])[:5], 1):
            report += f"        {idx}. {proc['process']:<40} CPU: {proc['cpu']:>6}%  MEM: {proc['mem']:>6}%\n"
        
        # Disk Information
        disk = resource.get('disk', {})
        report += f"\n  💾 DISK (/):\n"
        report += f"     Used: {disk.get('used', 'N/A')} / {disk.get('total', 'N/A')} ({disk.get('usage_percent', 'N/A')})\n"
        
        report += "\n"
    
    report += "="*100 + "\n"
    return report


def format_logs_size_report(log_sizes: List[Dict]) -> str:
    """
    Format Airflow logs size into a readable report.
    """
    report = "\n" + "="*100 + "\n"
    report += "📁 AIRFLOW LOGS DIRECTORY SIZE REPORT\n"
    report += "="*100 + "\n\n"
    
    total_bytes = 0
    
    for log_info in log_sizes:
        if 'error' in log_info:
            report += f"❌ {log_info['hostname']}: {log_info.get('error', 'Unknown error')}\n"
        else:
            report += f"📂 {log_info['hostname']:<20} │ Path: {log_info['path']:<35} │ Size: {log_info['size_human']:>8} ({log_info['size_mb']:.2f} MB)\n"
            total_bytes += log_info.get('size_bytes', 0)
    
    report += "\n" + "-"*100 + "\n"
    total_gb = total_bytes / (1024 * 1024 * 1024)
    total_mb = total_bytes / (1024 * 1024)
    report += f"📊 TOTAL LOGS SIZE ACROSS ALL NODES: {total_mb:.2f} MB ({total_gb:.2f} GB)\n"
    report += "="*100 + "\n"
    
    return report


@dag(
    dag_id='ha_service_health_monitor_enhanced_v3',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 0,
    },
    description='Enhanced HA Infrastructure Health Monitor with System Resource Monitoring',
    schedule='*/2 * * * *',  # Every 2 minutes
    start_date=datetime(2025, 11, 1),
    catchup=False,
    tags=['monitoring', 'ha', 'health-check', 'resources'],
    max_active_runs=1,
)
def ha_service_health_monitor_enhanced():
    
    @task(task_id="detect_nfs_active_node")
    def detect_nfs_active_node():
        """Detect which NFS node is active by checking keepalived MASTER state"""
        for name, config in NFS_NODES.items():
            ip = config['ip']
            try:
                current_host = get_current_hostname()
                is_local = (current_host == name)
                
                if is_local:
                    cmd = "sudo systemctl is-active keepalived && sudo ip addr show | grep '10.101.20.99' | wc -l"
                else:
                    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo systemctl is-active keepalived && sudo ip addr show | grep '10.101.20.99' | wc -l\""
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2 and lines[0] == 'active' and lines[1] == '1':
                        print(f"✅ {name} is the ACTIVE NFS node (has VIP 10.101.20.99)")
                        return name
            except:
                continue
        
        print("⚠️ Could not detect active NFS node, defaulting to nfs-1")
        return 'nfs-1'
    
    
    @task(task_id="check_system_resources")
    def check_system_resources():
        """
        NEW TASK: Monitor system resources (CPU, RAM, Disk) and top processes
        across all Airflow infrastructure nodes.
        """
        print("🔍 Collecting system resource metrics from all nodes...")
        
        resources = []
        for hostname, config in AIRFLOW_MONITORING_NODES.items():
            ip = config['ip']
            print(f"  Checking {hostname} ({ip})...")
            resource_data = fetch_system_resources(ip, hostname)
            resources.append(resource_data)
        
        # Generate and print report
        report = format_resource_report(resources)
        print(report)
        
        # Check for critical resource usage
        warnings = []
        for resource in resources:
            if 'error' in resource:
                continue
            
            hostname = resource['hostname']
            cpu_usage = resource.get('cpu', {}).get('usage_percent', 0)
            mem_usage = resource.get('memory', {}).get('usage_percent', 0)
            disk_usage_str = resource.get('disk', {}).get('usage_percent', '0%')
            disk_usage = float(disk_usage_str.rstrip('%'))
            
            if cpu_usage > 90:
                warnings.append(f"⚠️  {hostname}: HIGH CPU usage ({cpu_usage:.2f}%)")
            if mem_usage > 90:
                warnings.append(f"⚠️  {hostname}: HIGH MEMORY usage ({mem_usage:.2f}%)")
            if disk_usage > 85:
                warnings.append(f"⚠️  {hostname}: HIGH DISK usage ({disk_usage:.2f}%)")
        
        if warnings:
            print("\n" + "="*100)
            print("⚠️  RESOURCE WARNINGS:")
            for warning in warnings:
                print(f"   {warning}")
            print("="*100 + "\n")
        else:
            print("\n✅ All nodes have healthy resource levels\n")
        
        return {
            'resources': resources,
            'warnings': warnings,
            'warning_count': len(warnings)
        }
    
    
    @task(task_id="check_airflow_logs_size")
    def check_airflow_logs_size():
        """
        NEW TASK: Monitor the size of /home/rocky/airflow/logs directory
        on all Airflow nodes (schedulers, webservers, workers).
        """
        print(f"📁 Checking Airflow logs directory size on all nodes...")
        print(f"   Logs path: {AIRFLOW_LOGS_PATH}\n")
        
        log_sizes = []
        for hostname, config in AIRFLOW_MONITORING_NODES.items():
            ip = config['ip']
            print(f"  Checking {hostname} ({ip})...")
            log_size_data = fetch_airflow_logs_size(ip, hostname)
            log_sizes.append(log_size_data)
        
        # Generate and print report
        report = format_logs_size_report(log_sizes)
        print(report)
        
        # Check for large log directories (>5GB per node)
        warnings = []
        for log_info in log_sizes:
            if 'error' not in log_info:
                size_gb = log_info.get('size_gb', 0)
                if size_gb > 5:
                    warnings.append(
                        f"⚠️  {log_info['hostname']}: Large logs directory ({size_gb:.2f} GB) - consider cleanup"
                    )
        
        if warnings:
            print("\n" + "="*100)
            print("⚠️  LOG SIZE WARNINGS:")
            for warning in warnings:
                print(f"   {warning}")
            print("="*100 + "\n")
        
        return {
            'log_sizes': log_sizes,
            'warnings': warnings
        }
    
    
    # Original health check tasks (keeping the existing logic)
    def create_service_check_task(server_name: str, service_name: str):
        """Factory function to create service check tasks"""
        
        @task(task_id=f"check_{server_name}_{service_name.replace('-', '_')}")
        def check_service():
            server_config = SERVERS.get(server_name)
            if not server_config:
                raise AirflowException(f"Server {server_name} not found in configuration")
            
            ip = server_config['ip']
            current_host = get_current_hostname()
            is_local_check = (current_host == server_name)
            
            try:
                if is_local_check:
                    cmd = f"sudo systemctl is-active {service_name}"
                else:
                    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo systemctl is-active {service_name}\""
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip() == 'active':
                    print(f"✅ {server_name} - {service_name} is ACTIVE")
                    return {'status': 'active', 'server': server_name, 'service': service_name}
                else:
                    error_msg = f"❌ {server_name} - {service_name} is NOT ACTIVE\n\n"
                    
                    # Fetch diagnostic logs
                    journalctl_logs = fetch_journalctl_logs(ip, service_name, server_name, minutes_back=2)
                    error_msg += f"\n{'='*80}\n📋 Recent logs from {server_name}:\n{'='*80}\n{journalctl_logs}\n"
                    
                    context = get_current_context()
                    ti = context['task_instance']
                    ti.xcom_push(key='failure_type', value='SERVICE_INACTIVE')
                    
                    raise AirflowException(error_msg)
                    
            except AirflowException:
                raise
            except Exception as e:
                raise AirflowException(f"❌ Error checking {service_name} on {server_name}: {str(e)}")
        
        return check_service()
    
    
    def create_nfs_service_check_task(nfs_node_name: str, service_name: str, active_node_name: str):
        """Factory function to create NFS service check tasks with active/passive awareness"""
        
        @task(task_id=f"check_{nfs_node_name}_{service_name.replace('-', '_')}")
        def check_nfs_service():
            nfs_config = NFS_NODES.get(nfs_node_name)
            if not nfs_config:
                raise AirflowException(f"NFS node {nfs_node_name} not found in configuration")
            
            ip = nfs_config['ip']
            is_active_node = (nfs_node_name == active_node_name)
            current_host = get_current_hostname()
            is_local_check = (current_host == nfs_node_name)
            
            try:
                if is_local_check:
                    cmd = f"sudo systemctl is-active {service_name}"
                else:
                    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo systemctl is-active {service_name}\""
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                service_is_active = (result.returncode == 0 and result.stdout.strip() == 'active')
                
                # Active node: services should be running
                if is_active_node:
                    if service_is_active:
                        print(f"✅ {nfs_node_name} (ACTIVE) - {service_name} is ACTIVE")
                        return {'status': 'active', 'node': nfs_node_name, 'service': service_name}
                    else:
                        error_msg = f"❌ {nfs_node_name} (ACTIVE) - {service_name} is NOT ACTIVE\n"
                        journalctl_logs = fetch_journalctl_logs(ip, service_name, nfs_node_name, minutes_back=2)
                        error_msg += f"\n{'='*80}\n📋 Recent logs:\n{'='*80}\n{journalctl_logs}\n"
                        
                        context = get_current_context()
                        ti = context['task_instance']
                        ti.xcom_push(key='failure_type', value='CRITICAL_NFS_FAILURE')
                        raise AirflowException(error_msg)
                
                # Passive node: airflow-dag-processor should be inactive
                else:
                    if service_name == 'airflow-dag-processor':
                        if service_is_active:
                            print(f"⚠️  {nfs_node_name} (PASSIVE) - {service_name} is UNEXPECTEDLY ACTIVE")
                            return {'status': 'warning', 'node': nfs_node_name, 'service': service_name}
                        else:
                            print(f"✅ {nfs_node_name} (PASSIVE) - {service_name} is INACTIVE (expected)")
                            context = get_current_context()
                            ti = context['task_instance']
                            ti.xcom_push(key='failure_type', value='EXPECTED_PASSIVE_INACTIVE')
                            raise AirflowException(
                                f"ℹ️  {nfs_node_name} (PASSIVE) - {service_name} is inactive as expected"
                            )
                    else:
                        # Other services (nfs-server, lsyncd, keepalived) can be active on passive
                        if service_is_active:
                            print(f"✅ {nfs_node_name} (PASSIVE) - {service_name} is ACTIVE")
                            return {'status': 'active', 'node': nfs_node_name, 'service': service_name}
                        else:
                            error_msg = f"❌ {nfs_node_name} (PASSIVE) - {service_name} is NOT ACTIVE\n"
                            journalctl_logs = fetch_journalctl_logs(ip, service_name, nfs_node_name, minutes_back=2)
                            error_msg += f"\n{'='*80}\n📋 Recent logs:\n{'='*80}\n{journalctl_logs}\n"
                            
                            context = get_current_context()
                            ti = context['task_instance']
                            ti.xcom_push(key='failure_type', value='NFS_SUPPORT_SERVICE_FAILURE')
                            raise AirflowException(error_msg)
                    
            except AirflowException:
                raise
            except Exception as e:
                raise AirflowException(f"❌ Error checking {service_name} on {nfs_node_name}: {str(e)}")
        
        return check_nfs_service()
    
    
    # Build dynamic task list
    active_nfs = detect_nfs_active_node()
    
    service_tasks = []
    for server_name, config in SERVERS.items():
        for service in config['services']:
            task_instance = create_service_check_task(server_name, service)
            service_tasks.append(task_instance)
    
    nfs_tasks = []
    for nfs_node_name, config in NFS_NODES.items():
        for service in config['services']:
            task_instance = create_nfs_service_check_task(nfs_node_name, service, active_nfs)
            nfs_tasks.append(task_instance)
    
    
    @task(task_id="check_postgresql_vip")
    def check_postgresql_vip():
        """Check PostgreSQL VIP connectivity"""
        vip = '10.101.20.210'
        port = 5000
        
        try:
            conn = psycopg2.connect(
                host=vip,
                port=port,
                database='airflow_db',
                user='airflow_user',
                password='airflow_pass',
                connect_timeout=5
            )
            conn.close()
            print(f"✅ PostgreSQL VIP ({vip}:{port}) is ACCESSIBLE")
            return {'status': 'healthy', 'vip': vip}
            
        except Exception as e:
            error_msg = f"❌ PostgreSQL VIP ({vip}:{port}) CONNECTION FAILED\n\n"
            error_msg += f"Error: {str(e)}\n\n"
            
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
        """Check RabbitMQ cluster - FAILS if <2 nodes healthy"""
        nodes = [
            ('rabbit-1', '10.101.20.205'),
            ('rabbit-2', '10.101.20.147'),
            ('rabbit-3', '10.101.20.206')
        ]
        
        results = []
        
        for name, ip in nodes:
            try:
                credentials = pika.PlainCredentials('admin', 'admin')
                conn = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=ip, port=5672,
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
                print(f"     Check task logs for automatic diagnostic information")
        
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
    
    # NEW: System monitoring tasks
    system_resources = check_system_resources()
    logs_size = check_airflow_logs_size()
    
    summary = health_summary()
    final = final_status_check(summary)
    
    # Set dependencies
    active_nfs >> nfs_tasks
    service_tasks >> summary
    nfs_tasks >> summary
    [pg_vip, rabbitmq, scheduler, celery, system_resources, logs_size] >> summary
    summary >> final


# Instantiate the DAG
dag_instance = ha_service_health_monitor_enhanced()
