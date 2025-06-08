# simple_remote_dag.py - Simple remote execution

from datetime import datetime, timedelta
from airflow.decorators import dag, task
from celery import Celery

# Initialize Celery app
celery_app = Celery('simple_remote_tasks')
celery_app.config_from_object('airflow.providers.celery.executors.default_celery')

@dag(
    dag_id='simple_remote_execution',
    schedule_interval=None,
    start_date=datetime(2024, 5, 1),
    catchup=False,
    default_args={'owner': 'rocky', 'retries': 0}
)
def simple_remote_workflow():
    
    @task
    def get_hostname():
        """Get hostname from VM1"""
        
        # Send task to any available worker
        task_result = celery_app.send_task(
            'simple_remote_tasks.run_command',
            args=['vm1', 'hostname'],
            queue='remote_tasks'
        )
        
        return task_result.get(timeout=60)
    
    @task
    def make_directory():
        """Create a directory on VM1"""
        
        task_result = celery_app.send_task(
            'simple_remote_tasks.run_command',
            args=['vm1', 'mkdir -p /tmp/airflow_test && echo "Directory created"'],
            queue='remote_tasks'
        )
        
        return task_result.get(timeout=60)
    
    @task
    def check_directory():
        """Check if directory exists on VM1"""
        
        task_result = celery_app.send_task(
            'simple_remote_tasks.run_command',
            args=['vm1', 'ls -la /tmp/airflow_test'],
            queue='remote_tasks'
        )
        
        return task_result.get(timeout=60)
    
    @task
    def get_vm_status():
        """Get comprehensive VM status"""
        
        task_result = celery_app.send_task(
            'simple_remote_tasks.check_vm_status',
            args=['vm1'],
            queue='remote_tasks'
        )
        
        return task_result.get(timeout=120)
    
    @task
    def cleanup():
        """Clean up test directory"""
        
        task_result = celery_app.send_task(
            'simple_remote_tasks.run_command',
            args=['vm1', 'rm -rf /tmp/airflow_test && echo "Cleanup done"'],
            queue='remote_tasks'
        )
        
        return task_result.get(timeout=60)
    
    # Simple workflow
    hostname = get_hostname()
    directory = make_directory()
    check_dir = check_directory()
    status = get_vm_status()
    clean = cleanup()
    
    # Sequential execution
    hostname >> directory >> check_dir >> status >> clean

# Create DAG
dag_instance = simple_remote_workflow()
