"""
Airflow 3.1.5 Health Monitoring DAG

Environment: Single VM deployment (RHEL 9)
- Airflow 3.1.5 with CeleryExecutor
- PostgreSQL 16, Redis 7
- All services on localhost

Assumptions:
1. Systemd service names: airflow-scheduler, airflow-api-server, airflow-dag-processor,
   airflow-triggerer, airflow-celery-worker, postgresql, redis
2. Airflow API server: http://localhost:8080
3. Auth credentials: airflow/airflow
4. AIRFLOW_HOME: ~/airflow (or from environment)
5. No HA setup - single VM monitoring only
"""

from airflow.sdk import dag, task
from datetime import datetime, timedelta
import subprocess
import json
import os
import requests
from requests.auth import HTTPBasicAuth
import psutil
import shutil
from typing import Dict, List, Any
from pathlib import Path


# Configuration
AIRFLOW_API_URL = "http://localhost:8080/api/v1"
AIRFLOW_USERNAME = "airflow"
AIRFLOW_PASSWORD = "airflow"
AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", os.path.expanduser("~/airflow"))

SYSTEMD_SERVICES = [
    "airflow-scheduler",
    "airflow-api-server",
    "airflow-dag-processor",
    "airflow-triggerer",
    "airflow-celery-worker",
    "postgresql",
    "redis",
]

# Thresholds
CPU_THRESHOLD_WARNING = 80.0  # %
CPU_THRESHOLD_CRITICAL = 95.0  # %
MEMORY_THRESHOLD_WARNING = 80.0  # %
MEMORY_THRESHOLD_CRITICAL = 95.0  # %
DISK_THRESHOLD_WARNING = 80.0  # %
DISK_THRESHOLD_CRITICAL = 90.0  # %
LOGS_SIZE_WARNING_GB = 10.0
LOGS_SIZE_CRITICAL_GB = 20.0


@dag(
    dag_id="airflow_health_monitor",
    schedule="*/15 * * * *",  # Every 15 minutes
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={
        "owner": "airflow",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["monitoring", "health", "diagnostics"],
    description="Comprehensive health monitoring for Airflow 3.1.5 single-VM deployment",
)
def airflow_health_monitor():
    
    @task
    def check_systemd_services() -> Dict[str, Any]:
        """
        Check all Airflow and dependency systemd services.
        Returns: dict with service statuses and diagnostics.
        """
        results = {
            "status": "HEALTHY",
            "services": {},
            "severity": "INFO",
            "diagnostics": []
        }
        
        failed_services = []
        
        for service in SYSTEMD_SERVICES:
            try:
                # Check if service is active
                check_cmd = ["systemctl", "is-active", service]
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                is_active = result.returncode == 0
                status = result.stdout.strip()
                
                results["services"][service] = {
                    "active": is_active,
                    "status": status
                }
                
                if not is_active:
                    failed_services.append(service)
                    
                    # Get journal logs for failed service
                    log_cmd = ["journalctl", "-u", service, "-n", "50", "--no-pager"]
                    log_result = subprocess.run(
                        log_cmd,
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    
                    results["diagnostics"].append({
                        "service": service,
                        "status": status,
                        "logs": log_result.stdout
                    })
                    
            except subprocess.TimeoutExpired:
                results["services"][service] = {
                    "active": False,
                    "status": "TIMEOUT"
                }
                failed_services.append(service)
                results["diagnostics"].append({
                    "service": service,
                    "error": "Command timeout"
                })
            except Exception as e:
                results["services"][service] = {
                    "active": False,
                    "status": "ERROR",
                    "error": str(e)
                }
                failed_services.append(service)
                results["diagnostics"].append({
                    "service": service,
                    "error": str(e)
                })
        
        if failed_services:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["failed_services"] = failed_services
        
        return results

    @task
    def check_scheduler_heartbeat() -> Dict[str, Any]:
        """
        Check Airflow scheduler heartbeat via REST API.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "diagnostics": []
        }
        
        try:
            # Check scheduler via health endpoint
            response = requests.get(
                f"{AIRFLOW_API_URL}/health",
                auth=HTTPBasicAuth(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
                timeout=10
            )
            
            if response.status_code == 200:
                health_data = response.json()
                scheduler_status = health_data.get("scheduler", {}).get("status")
                
                if scheduler_status != "healthy":
                    results["status"] = "UNHEALTHY"
                    results["severity"] = "CRITICAL"
                    results["scheduler_status"] = scheduler_status
                    results["diagnostics"].append({
                        "message": f"Scheduler status: {scheduler_status}",
                        "health_data": health_data
                    })
                else:
                    results["scheduler_status"] = scheduler_status
                    results["latest_scheduler_heartbeat"] = health_data.get("scheduler", {}).get("latest_scheduler_heartbeat")
            else:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": "Failed to get health status",
                    "status_code": response.status_code,
                    "response": response.text
                })
                
        except requests.exceptions.RequestException as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "API request failed",
                "error": str(e)
            })
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Unexpected error",
                "error": str(e)
            })
        
        return results

    @task
    def check_celery_workers() -> Dict[str, Any]:
        """
        Check Celery workers availability using Celery inspect API.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "workers": [],
            "diagnostics": []
        }
        
        try:
            from airflow.providers.celery.executors.celery_executor import app as celery_app
            
            # Inspect active workers
            inspect = celery_app.control.inspect(timeout=5)
            
            # Get active workers
            active_workers = inspect.active()
            stats = inspect.stats()
            
            if not active_workers:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": "No active Celery workers found"
                })
            else:
                results["workers"] = list(active_workers.keys())
                results["worker_count"] = len(active_workers)
                results["worker_stats"] = stats
                
        except ImportError as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Failed to import Celery app",
                "error": str(e)
            })
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Failed to inspect Celery workers",
                "error": str(e)
            })
        
        return results

    @task
    def check_api_server() -> Dict[str, Any]:
        """
        Check Airflow API server responsiveness.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "diagnostics": []
        }
        
        try:
            # Test API server with version endpoint
            response = requests.get(
                f"{AIRFLOW_API_URL}/version",
                auth=HTTPBasicAuth(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
                timeout=10
            )
            
            if response.status_code == 200:
                version_data = response.json()
                results["airflow_version"] = version_data.get("version")
                results["response_time_ms"] = response.elapsed.total_seconds() * 1000
                
                # Check response time
                if results["response_time_ms"] > 5000:
                    results["status"] = "DEGRADED"
                    results["severity"] = "WARNING"
                    results["diagnostics"].append({
                        "message": "API server response time is slow",
                        "response_time_ms": results["response_time_ms"]
                    })
            else:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": "API server returned error",
                    "status_code": response.status_code,
                    "response": response.text
                })
                
        except requests.exceptions.Timeout:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "API server request timeout"
            })
        except requests.exceptions.RequestException as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Failed to connect to API server",
                "error": str(e)
            })
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Unexpected error",
                "error": str(e)
            })
        
        return results

    @task
    def check_system_resources() -> Dict[str, Any]:
        """
        Monitor system resources: CPU, RAM, disk.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "diagnostics": []
        }
        
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=1)
            results["cpu_percent"] = cpu_percent
            
            if cpu_percent >= CPU_THRESHOLD_CRITICAL:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": f"CPU usage critical: {cpu_percent}%",
                    "threshold": CPU_THRESHOLD_CRITICAL
                })
            elif cpu_percent >= CPU_THRESHOLD_WARNING:
                if results["severity"] == "INFO":
                    results["severity"] = "WARNING"
                results["diagnostics"].append({
                    "message": f"CPU usage warning: {cpu_percent}%",
                    "threshold": CPU_THRESHOLD_WARNING
                })
            
            # Memory Usage
            memory = psutil.virtual_memory()
            results["memory_percent"] = memory.percent
            results["memory_available_gb"] = memory.available / (1024**3)
            results["memory_total_gb"] = memory.total / (1024**3)
            
            if memory.percent >= MEMORY_THRESHOLD_CRITICAL:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": f"Memory usage critical: {memory.percent}%",
                    "threshold": MEMORY_THRESHOLD_CRITICAL,
                    "available_gb": results["memory_available_gb"]
                })
            elif memory.percent >= MEMORY_THRESHOLD_WARNING:
                if results["severity"] == "INFO":
                    results["severity"] = "WARNING"
                results["diagnostics"].append({
                    "message": f"Memory usage warning: {memory.percent}%",
                    "threshold": MEMORY_THRESHOLD_WARNING,
                    "available_gb": results["memory_available_gb"]
                })
            
            # Disk Usage
            disk = psutil.disk_usage('/')
            results["disk_percent"] = disk.percent
            results["disk_free_gb"] = disk.free / (1024**3)
            results["disk_total_gb"] = disk.total / (1024**3)
            
            if disk.percent >= DISK_THRESHOLD_CRITICAL:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": f"Disk usage critical: {disk.percent}%",
                    "threshold": DISK_THRESHOLD_CRITICAL,
                    "free_gb": results["disk_free_gb"]
                })
            elif disk.percent >= DISK_THRESHOLD_WARNING:
                if results["severity"] == "INFO":
                    results["severity"] = "WARNING"
                results["diagnostics"].append({
                    "message": f"Disk usage warning: {disk.percent}%",
                    "threshold": DISK_THRESHOLD_WARNING,
                    "free_gb": results["disk_free_gb"]
                })
            
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "CRITICAL"
            results["diagnostics"].append({
                "message": "Failed to collect system resources",
                "error": str(e)
            })
        
        return results

    @task
    def check_top_processes() -> Dict[str, Any]:
        """
        Get top 5 CPU and memory consuming processes.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "diagnostics": []
        }
        
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Top 5 by CPU
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
            results["top_cpu_processes"] = [
                {
                    "pid": p['pid'],
                    "name": p['name'],
                    "cpu_percent": p['cpu_percent'],
                    "username": p['username']
                }
                for p in top_cpu
            ]
            
            # Top 5 by Memory
            top_memory = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:5]
            results["top_memory_processes"] = [
                {
                    "pid": p['pid'],
                    "name": p['name'],
                    "memory_percent": p['memory_percent'],
                    "username": p['username']
                }
                for p in top_memory
            ]
            
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "WARNING"
            results["diagnostics"].append({
                "message": "Failed to collect process information",
                "error": str(e)
            })
        
        return results

    @task
    def check_logs_directory() -> Dict[str, Any]:
        """
        Check Airflow logs directory size.
        """
        results = {
            "status": "HEALTHY",
            "severity": "INFO",
            "diagnostics": []
        }
        
        try:
            logs_dir = Path(AIRFLOW_HOME) / "logs"
            
            if not logs_dir.exists():
                results["status"] = "UNHEALTHY"
                results["severity"] = "WARNING"
                results["diagnostics"].append({
                    "message": f"Logs directory not found: {logs_dir}"
                })
                return results
            
            # Calculate directory size
            total_size = 0
            file_count = 0
            
            for item in logs_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            
            size_gb = total_size / (1024**3)
            results["logs_size_gb"] = size_gb
            results["logs_file_count"] = file_count
            results["logs_directory"] = str(logs_dir)
            
            if size_gb >= LOGS_SIZE_CRITICAL_GB:
                results["status"] = "UNHEALTHY"
                results["severity"] = "CRITICAL"
                results["diagnostics"].append({
                    "message": f"Logs directory size critical: {size_gb:.2f} GB",
                    "threshold": LOGS_SIZE_CRITICAL_GB,
                    "recommendation": "Consider log rotation or cleanup"
                })
            elif size_gb >= LOGS_SIZE_WARNING_GB:
                if results["severity"] == "INFO":
                    results["severity"] = "WARNING"
                results["diagnostics"].append({
                    "message": f"Logs directory size warning: {size_gb:.2f} GB",
                    "threshold": LOGS_SIZE_WARNING_GB,
                    "recommendation": "Monitor log growth"
                })
            
        except Exception as e:
            results["status"] = "UNHEALTHY"
            results["severity"] = "WARNING"
            results["diagnostics"].append({
                "message": "Failed to check logs directory",
                "error": str(e)
            })
        
        return results

    @task
    def aggregate_health_summary(
        systemd_check: Dict,
        scheduler_check: Dict,
        celery_check: Dict,
        api_check: Dict,
        resources_check: Dict,
        processes_check: Dict,
        logs_check: Dict
    ) -> Dict[str, Any]:
        """
        Aggregate all health check results and generate summary.
        """
        all_checks = {
            "systemd_services": systemd_check,
            "scheduler_heartbeat": scheduler_check,
            "celery_workers": celery_check,
            "api_server": api_check,
            "system_resources": resources_check,
            "top_processes": processes_check,
            "logs_directory": logs_check
        }
        
        # Determine overall status
        critical_issues = []
        warnings = []
        
        for check_name, check_result in all_checks.items():
            if check_result.get("severity") == "CRITICAL":
                critical_issues.append({
                    "check": check_name,
                    "status": check_result.get("status"),
                    "diagnostics": check_result.get("diagnostics", [])
                })
            elif check_result.get("severity") == "WARNING":
                warnings.append({
                    "check": check_name,
                    "status": check_result.get("status"),
                    "diagnostics": check_result.get("diagnostics", [])
                })
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "HEALTHY",
            "overall_severity": "INFO",
            "critical_count": len(critical_issues),
            "warning_count": len(warnings),
            "critical_issues": critical_issues,
            "warnings": warnings,
            "all_checks": all_checks
        }
        
        if critical_issues:
            summary["overall_status"] = "CRITICAL"
            summary["overall_severity"] = "CRITICAL"
        elif warnings:
            summary["overall_status"] = "DEGRADED"
            summary["overall_severity"] = "WARNING"
        
        # Print summary
        print("=" * 80)
        print("AIRFLOW HEALTH MONITORING SUMMARY")
        print("=" * 80)
        print(f"Timestamp: {summary['timestamp']}")
        print(f"Overall Status: {summary['overall_status']}")
        print(f"Overall Severity: {summary['overall_severity']}")
        print(f"Critical Issues: {summary['critical_count']}")
        print(f"Warnings: {summary['warning_count']}")
        print("=" * 80)
        
        if critical_issues:
            print("\n🔴 CRITICAL ISSUES:")
            for issue in critical_issues:
                print(f"\n  Check: {issue['check']}")
                print(f"  Status: {issue['status']}")
                for diag in issue.get('diagnostics', []):
                    print(f"  - {diag}")
        
        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"\n  Check: {warning['check']}")
                print(f"  Status: {warning['status']}")
                for diag in warning.get('diagnostics', []):
                    print(f"  - {diag}")
        
        if not critical_issues and not warnings:
            print("\n✅ ALL SYSTEMS HEALTHY")
        
        print("\n" + "=" * 80)
        print("DETAILED METRICS:")
        print("=" * 80)
        
        # Systemd Services
        if "systemd_services" in all_checks:
            print("\nSystemd Services:")
            for service, status in all_checks["systemd_services"].get("services", {}).items():
                icon = "✅" if status.get("active") else "❌"
                print(f"  {icon} {service}: {status.get('status')}")
        
        # System Resources
        if "system_resources" in all_checks:
            res = all_checks["system_resources"]
            print("\nSystem Resources:")
            print(f"  CPU: {res.get('cpu_percent', 0):.1f}%")
            print(f"  Memory: {res.get('memory_percent', 0):.1f}% ({res.get('memory_available_gb', 0):.2f} GB available)")
            print(f"  Disk: {res.get('disk_percent', 0):.1f}% ({res.get('disk_free_gb', 0):.2f} GB free)")
        
        # Logs
        if "logs_directory" in all_checks:
            logs = all_checks["logs_directory"]
            print(f"\nLogs Directory: {logs.get('logs_size_gb', 0):.2f} GB ({logs.get('logs_file_count', 0)} files)")
        
        # Celery Workers
        if "celery_workers" in all_checks:
            celery = all_checks["celery_workers"]
            print(f"\nCelery Workers: {celery.get('worker_count', 0)} active")
            for worker in celery.get('workers', []):
                print(f"  - {worker}")
        
        print("=" * 80)
        
        return summary

    @task
    def health_gate(summary: Dict[str, Any]) -> str:
        """
        Final gate: fail DAG if any critical issues exist.
        """
        if summary["overall_severity"] == "CRITICAL":
            critical_count = summary["critical_count"]
            critical_checks = [issue["check"] for issue in summary["critical_issues"]]
            
            error_message = (
                f"Health check FAILED with {critical_count} critical issue(s): "
                f"{', '.join(critical_checks)}"
            )
            
            print("=" * 80)
            print("❌ HEALTH CHECK FAILED")
            print("=" * 80)
            print(error_message)
            print("=" * 80)
            
            raise Exception(error_message)
        
        status_message = "ALL_HEALTHY"
        if summary["overall_severity"] == "WARNING":
            status_message = f"HEALTHY_WITH_WARNINGS ({summary['warning_count']})"
        
        print("=" * 80)
        print(f"✅ HEALTH CHECK PASSED: {status_message}")
        print("=" * 80)
        
        return status_message

    # Define task dependencies
    systemd_results = check_systemd_services()
    scheduler_results = check_scheduler_heartbeat()
    celery_results = check_celery_workers()
    api_results = check_api_server()
    resources_results = check_system_resources()
    processes_results = check_top_processes()
    logs_results = check_logs_directory()
    
    summary = aggregate_health_summary(
        systemd_results,
        scheduler_results,
        celery_results,
        api_results,
        resources_results,
        processes_results,
        logs_results
    )
    
    gate_result = health_gate(summary)


# Instantiate the DAG
dag_instance = airflow_health_monitor()
