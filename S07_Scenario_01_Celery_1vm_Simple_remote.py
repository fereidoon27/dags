# simple_remote_dag.py - Fixed: Direct SSH execution (no nested Celery)

from datetime import datetime, timedelta
from airflow.decorators import dag, task
import sys
import os

# Add airflow directory to Python path
sys.path.insert(0, '/home/rocky/airflow')

@dag(
    dag_id='S07_Scenario_01_Celery_1vm_Simple_remote',
    schedule_interval=None,
    start_date=datetime(2024, 5, 1),
    catchup=False,
    default_args={'owner': 'rocky', 'retries': 0}
)
def simple_remote_workflow_fixed():
    
    @task
    def get_hostname():
        """Get hostname from VM1 - Direct SSH execution"""
        
        # Import our SSH utility directly
        from utils.simple_ssh import execute_ssh_command
        
        # Execute SSH command directly (no nested Celery call)
        result = execute_ssh_command('vm1', 'hostname')
        print(f"Hostname result: {result}")
        
        return result
    
    @task
    def make_directory():
        """Create a directory on VM1 - Direct SSH execution"""
        
        from utils.simple_ssh import execute_ssh_command
        
        result = execute_ssh_command('vm1', 'mkdir -p /tmp/airflow_test && echo "Directory created"')
        print(f"Directory creation result: {result}")
        
        return result
    
    @task
    def check_directory():
        """Check if directory exists on VM1 - Direct SSH execution"""
        
        from utils.simple_ssh import execute_ssh_command
        
        result = execute_ssh_command('vm1', 'ls -la /tmp/airflow_test')
        print(f"Directory check result: {result}")
        
        return result
    
    @task
    def get_vm_status():
        """Get comprehensive VM status - Direct SSH execution"""
        
        from utils.simple_ssh import execute_ssh_command
        
        # Execute multiple commands and collect results
        commands = {
            'hostname': 'hostname',
            'uptime': 'uptime', 
            'disk': 'df -h /',
            'date': 'date'
        }
        
        results = {}
        
        for check_name, command in commands.items():
            try:
                result = execute_ssh_command('vm1', command)
                results[check_name] = result['output']
                print(f"{check_name}: {result['output']}")
            except Exception as e:
                results[check_name] = f"ERROR: {str(e)}"
                print(f"{check_name} failed: {e}")
        
        return {
            'vm': 'vm1',
            'checks': results
        }
    
    @task
    def cleanup():
        """Clean up test directory - Direct SSH execution"""
        
        from utils.simple_ssh import execute_ssh_command
        
        result = execute_ssh_command('vm1', 'rm -rf /tmp/airflow_test && echo "Cleanup done"')
        print(f"Cleanup result: {result}")
        
        return result
    
    # Define workflow - tasks execute directly on Airflow workers
    # Each task makes its own SSH connection to VM1
    hostname = get_hostname()
    directory = make_directory()
    check_dir = check_directory() 
    status = get_vm_status()
    clean = cleanup()
    
    # Sequential execution
    hostname >> directory >> check_dir >> status >> clean

# Create DAG
dag_instance = simple_remote_workflow_fixed()
