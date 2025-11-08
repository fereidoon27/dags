"""
Apache Airflow DAG: Worker Health Check and Connection Monitor
DAG ID: S15_worker_health_check
Description: Runs every 15 minutes to keep workers active and test connections
"""

from datetime import datetime, timedelta
import socket
from airflow.decorators import dag, task
from airflow.exceptions import AirflowException


# Configuration
CONFIG = {
    'rabbitmq_hosts': [
        ('rabbit-1', '10.101.20.205', 5672),
        ('rabbit-2', '10.101.20.147', 5672),
        ('rabbit-3', '10.101.20.206', 5672)
    ],
    'postgresql_hosts': [
        ('postgresql-1', '10.101.20.204', 5432),
        ('postgresql-2', '10.101.20.166', 5432),
        ('postgresql-3', '10.101.20.137', 5432)
    ],
    'vip_main': ('airflow-vip', '10.101.20.210', 5000),
    'vip_nfs': ('nfs-vip', '10.101.20.220', 2049),
    'timeout': 5
}


def test_connection(host: str, ip: str, port: int, timeout: int = 5) -> dict:
    """Test TCP connection to a host"""
    result = {
        'host': host,
        'ip': ip,
        'port': port,
        'status': 'unknown',
        'latency_ms': None,
        'error': None
    }
    
    try:
        start = datetime.now()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        sock.close()
        end = datetime.now()
        
        latency = (end - start).total_seconds() * 1000
        result['status'] = 'OK'
        result['latency_ms'] = round(latency, 2)
        
    except socket.timeout:
        result['status'] = 'TIMEOUT'
        result['error'] = f"Connection timeout after {timeout}s"
    except socket.error as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)
    
    return result


@dag(
    dag_id='S15_worker_health_check',
    start_date=datetime(2025, 1, 1),
    schedule_interval='*/1 * * * *',  # Every 15 minutes
    catchup=False,
    tags=['monitoring', 'health-check'],
    default_args={
        'owner': 'airflow',
        'retries': 0,  # Don't retry health checks
        'execution_timeout': timedelta(minutes=5)
    },
    description='Keep workers active and monitor connections every 15 minutes'
)
def worker_health_check():
    
    @task(queue='card_processing_queue')
    def check_worker_health() -> dict:
        """Check basic worker health and system info"""
        import os
        import platform
        from datetime import datetime
        
        worker_info = {
            'timestamp': datetime.now().isoformat(),
            'hostname': socket.gethostname(),
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'worker_pid': os.getpid(),
            'status': 'HEALTHY'
        }
        
        print("="*60)
        print("🏥 WORKER HEALTH CHECK")
        print("="*60)
        print(f"Timestamp:  {worker_info['timestamp']}")
        print(f"Hostname:   {worker_info['hostname']}")
        print(f"Python:     {worker_info['python_version']}")
        print(f"Platform:   {worker_info['platform']}")
        print(f"PID:        {worker_info['worker_pid']}")
        print(f"Status:     ✓ {worker_info['status']}")
        print("="*60)
        
        return worker_info
    
    
    @task(queue='card_processing_queue')
    def check_rabbitmq_connections() -> dict:
        """Test connections to all RabbitMQ nodes"""
        results = []
        failed_count = 0
        
        print("\n" + "="*60)
        print("🐰 RABBITMQ CLUSTER CONNECTION CHECK")
        print("="*60)
        
        for host, ip, port in CONFIG['rabbitmq_hosts']:
            result = test_connection(host, ip, port, CONFIG['timeout'])
            results.append(result)
            
            status_icon = "✓" if result['status'] == 'OK' else "✗"
            latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "N/A"
            
            print(f"{status_icon} {host:15} ({ip:15}:{port}) - {result['status']:8} - {latency}")
            
            if result['status'] != 'OK':
                failed_count += 1
                if result['error']:
                    print(f"   Error: {result['error']}")
        
        summary = {
            'total': len(results),
            'ok': len(results) - failed_count,
            'failed': failed_count,
            'details': results
        }
        
        print("-"*60)
        print(f"Summary: {summary['ok']}/{summary['total']} nodes reachable")
        print("="*60)
        
        if failed_count == len(results):
            raise AirflowException("ALL RabbitMQ nodes unreachable!")
        
        return summary
    
    
    @task(queue='card_processing_queue')
    def check_postgresql_connections() -> dict:
        """Test connections to all PostgreSQL nodes"""
        results = []
        failed_count = 0
        
        print("\n" + "="*60)
        print("🐘 POSTGRESQL CLUSTER CONNECTION CHECK")
        print("="*60)
        
        for host, ip, port in CONFIG['postgresql_hosts']:
            result = test_connection(host, ip, port, CONFIG['timeout'])
            results.append(result)
            
            status_icon = "✓" if result['status'] == 'OK' else "✗"
            latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "N/A"
            
            print(f"{status_icon} {host:15} ({ip:15}:{port}) - {result['status']:8} - {latency}")
            
            if result['status'] != 'OK':
                failed_count += 1
                if result['error']:
                    print(f"   Error: {result['error']}")
        
        summary = {
            'total': len(results),
            'ok': len(results) - failed_count,
            'failed': failed_count,
            'details': results
        }
        
        print("-"*60)
        print(f"Summary: {summary['ok']}/{summary['total']} nodes reachable")
        print("="*60)
        
        if failed_count == len(results):
            raise AirflowException("ALL PostgreSQL nodes unreachable!")
        
        return summary
    
    
    @task(queue='card_processing_queue')
    def check_vip_connections() -> dict:
        """Test connections to VIPs"""
        results = []
        
        print("\n" + "="*60)
        print("🔗 VIRTUAL IP CONNECTION CHECK")
        print("="*60)
        
        # Check main VIP (HAProxy)
        result_main = test_connection(
            CONFIG['vip_main'][0],
            CONFIG['vip_main'][1],
            CONFIG['vip_main'][2],
            CONFIG['timeout']
        )
        results.append(result_main)
        
        status_icon = "✓" if result_main['status'] == 'OK' else "✗"
        latency = f"{result_main['latency_ms']}ms" if result_main['latency_ms'] else "N/A"
        print(f"{status_icon} {CONFIG['vip_main'][0]:15} ({CONFIG['vip_main'][1]:15}:{CONFIG['vip_main'][2]}) - {result_main['status']:8} - {latency}")
        
        if result_main['status'] != 'OK':
            print(f"   Error: {result_main['error']}")
        
        # Check NFS VIP
        result_nfs = test_connection(
            CONFIG['vip_nfs'][0],
            CONFIG['vip_nfs'][1],
            CONFIG['vip_nfs'][2],
            CONFIG['timeout']
        )
        results.append(result_nfs)
        
        status_icon = "✓" if result_nfs['status'] == 'OK' else "✗"
        latency = f"{result_nfs['latency_ms']}ms" if result_nfs['latency_ms'] else "N/A"
        print(f"{status_icon} {CONFIG['vip_nfs'][0]:15} ({CONFIG['vip_nfs'][1]:15}:{CONFIG['vip_nfs'][2]}) - {result_nfs['status']:8} - {latency}")
        
        if result_nfs['status'] != 'OK':
            print(f"   Error: {result_nfs['error']}")
        
        summary = {
            'main_vip': result_main,
            'nfs_vip': result_nfs,
            'all_details': results
        }
        
        print("="*60)
        
        return summary
    
    
    @task(queue='card_processing_queue')
    def check_database_query() -> dict:
        """Test actual database query using SQLAlchemy"""
        from airflow.settings import Session
        from sqlalchemy import text
        
        print("\n" + "="*60)
        print("💾 DATABASE QUERY TEST")
        print("="*60)
        
        result = {
            'status': 'UNKNOWN',
            'query_time_ms': None,
            'row_count': None,
            'error': None
        }
        
        try:
            session = Session()
            start = datetime.now()
            
            # Simple query to test connection
            query_result = session.execute(text("SELECT COUNT(*) FROM dag"))
            row_count = query_result.scalar()
            
            end = datetime.now()
            query_time = (end - start).total_seconds() * 1000
            
            session.close()
            
            result['status'] = 'OK'
            result['query_time_ms'] = round(query_time, 2)
            result['row_count'] = row_count
            
            print(f"✓ Database query successful")
            print(f"  Query time: {result['query_time_ms']}ms")
            print(f"  DAG count:  {result['row_count']}")
            
        except Exception as e:
            result['status'] = 'FAILED'
            result['error'] = str(e)
            print(f"✗ Database query failed: {e}")
        
        print("="*60)
        
        return result
    
    
    @task(queue='card_processing_queue')
    def generate_health_summary(
        worker_info: dict,
        rabbit_check: dict,
        postgres_check: dict,
        vip_check: dict,
        db_query: dict
    ) -> dict:
        """Generate overall health summary"""
        
        # Determine overall status
        critical_failures = []
        warnings = []
        
        if rabbit_check['failed'] == rabbit_check['total']:
            critical_failures.append("All RabbitMQ nodes unreachable")
        elif rabbit_check['failed'] > 0:
            warnings.append(f"{rabbit_check['failed']} RabbitMQ node(s) down")
        
        if postgres_check['failed'] == postgres_check['total']:
            critical_failures.append("All PostgreSQL nodes unreachable")
        elif postgres_check['failed'] > 0:
            warnings.append(f"{postgres_check['failed']} PostgreSQL node(s) down")
        
        if vip_check['main_vip']['status'] != 'OK':
            critical_failures.append("Main VIP unreachable")
        
        if db_query['status'] != 'OK':
            critical_failures.append("Database queries failing")
        
        overall_status = 'HEALTHY'
        if critical_failures:
            overall_status = 'CRITICAL'
        elif warnings:
            overall_status = 'WARNING'
        
        summary = {
            'timestamp': worker_info['timestamp'],
            'worker': worker_info['hostname'],
            'overall_status': overall_status,
            'critical_failures': critical_failures,
            'warnings': warnings,
            'rabbitmq': f"{rabbit_check['ok']}/{rabbit_check['total']} nodes OK",
            'postgresql': f"{postgres_check['ok']}/{postgres_check['total']} nodes OK",
            'main_vip': vip_check['main_vip']['status'],
            'database_query': db_query['status']
        }
        
        print("\n" + "="*60)
        print("📊 OVERALL HEALTH SUMMARY")
        print("="*60)
        print(f"Timestamp:       {summary['timestamp']}")
        print(f"Worker:          {summary['worker']}")
        print(f"Overall Status:  {summary['overall_status']}")
        print(f"RabbitMQ:        {summary['rabbitmq']}")
        print(f"PostgreSQL:      {summary['postgresql']}")
        print(f"Main VIP:        {summary['main_vip']}")
        print(f"DB Query:        {summary['database_query']}")
        
        if critical_failures:
            print(f"\n🚨 CRITICAL FAILURES:")
            for failure in critical_failures:
                print(f"  - {failure}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"  - {warning}")
        
        if overall_status == 'HEALTHY':
            print(f"\n✅ All systems operational!")
        
        print("="*60 + "\n")
        
        return summary
    
    
    # Define task dependencies - all checks run in parallel
    worker = check_worker_health()
    rabbit = check_rabbitmq_connections()
    postgres = check_postgresql_connections()
    vips = check_vip_connections()
    db_query = check_database_query()
    
    # Generate summary after all checks complete
    generate_health_summary(worker, rabbit, postgres, vips, db_query)


# Instantiate the DAG
health_dag = worker_health_check()
