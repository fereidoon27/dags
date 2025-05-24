# file_processing_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import paramiko
import os

# Configuration - Change these values for your setup
CONFIG = {
    'vm2_host': '192.168.83.132',  # FTP server
    'vm3_host': '192.168.83.133',  # Processing server
    'username': 'your_username',   # Same username on both VMs
    'ssh_key_path': '/home/rocky/.ssh/id_rsa',  # SSH key path on VM1
    'base_dirs': ['in', 'bon/in', 'card/in'],   # Directories to scan for files
}

def ssh_execute_command(host, username, key_path, command):
    """Execute command on remote host via SSH"""
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to remote host
        ssh_client.connect(hostname=host, username=username, key_filename=key_path)
        
        # Execute command
        stdin, stdout, stderr = ssh_client.exec_command(command)
        
        # Get results
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0 and error:
            raise Exception(f"Command failed: {error}")
        
        return output
    
    finally:
        ssh_client.close()

def discover_files(**context):
    """Discover all .txt files in the specified directories on VM2"""
    files_found = []
    
    # Command to find all .txt files in the specified directories
    find_command = f"find /home/{CONFIG['username']} -name '*.txt' -path '*/in/*' -type f"
    
    try:
        # Execute find command on VM2
        output = ssh_execute_command(
            CONFIG['vm2_host'], 
            CONFIG['username'], 
            CONFIG['ssh_key_path'], 
            find_command
        )
        
        # Parse output to get list of files
        if output:
            files_found = output.split('\n')
            files_found = [f.strip() for f in files_found if f.strip()]
        
        print(f"Found {len(files_found)} files to process:")
        for file_path in files_found:
            print(f"  - {file_path}")
        
        # Store file list in XCom for other tasks
        return files_found
    
    except Exception as e:
        print(f"Error discovering files: {e}")
        return []

def transfer_file(source_file, **context):
    """Transfer a single file from VM2 to VM3"""
    try:
        # Use SCP command to transfer file
        scp_command = f"scp -i {CONFIG['ssh_key_path']} {CONFIG['username']}@{CONFIG['vm2_host']}:{source_file} {CONFIG['username']}@{CONFIG['vm3_host']}:{source_file}"
        
        # Execute SCP from VM1 (this machine)
        result = os.system(scp_command)
        
        if result == 0:
            print(f"Successfully transferred: {source_file}")
            return True
        else:
            raise Exception(f"SCP command failed with exit code {result}")
    
    except Exception as e:
        print(f"Error transferring {source_file}: {e}")
        return False

def process_file_on_vm3(file_path, **context):
    """Process the transferred file using file_manager.py on VM3"""
    try:
        # Command to run file_manager.py on VM3
        process_command = f"python3 /home/{CONFIG['username']}/scripts/file_manager.py {file_path}"
        
        # Execute processing command on VM3
        result = ssh_execute_command(
            CONFIG['vm3_host'],
            CONFIG['username'], 
            CONFIG['ssh_key_path'],
            process_command
        )
        
        print(f"Processing result for {file_path}:")
        print(result)
        
        return True
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

# Define the DAG
with DAG(
    'file_processing_workflow',
    default_args={
        'owner': 'your_name',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='Hourly file processing from VM2 to VM3',
    schedule_interval='@hourly',  # Run every hour
    start_date=datetime(2024, 5, 1),
    catchup=False,
) as dag:

    # Task 1: Discover files on VM2
    discover_task = PythonOperator(
        task_id='discover_files',
        python_callable=discover_files,
    )

    # Task 2: Create dynamic tasks for each file found
    # This will be created dynamically based on discovered files
    def create_file_processing_tasks(**context):
        """Create processing tasks for each discovered file"""
        # Get file list from discover task
        files = context['task_instance'].xcom_pull(task_ids='discover_files')
        
        if not files:
            print("No files found to process")
            return
        
        # Process each file (in this simplified version, we'll process them sequentially)
        for file_path in files:
            print(f"\n--- Processing {file_path} ---")
            
            # Step 1: Transfer file
            if transfer_file(file_path, **context):
                # Step 2: Process file on VM3
                process_file_on_vm3(file_path, **context)
            else:
                print(f"Skipping processing of {file_path} due to transfer failure")

    # Combined task for transfer and processing
    process_files_task = PythonOperator(
        task_id='process_all_files',
        python_callable=create_file_processing_tasks,
        provide_context=True,
    )

    # Set task dependencies
    discover_task >> process_files_task
