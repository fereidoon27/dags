# simple_file_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import paramiko

# Simple configuration
VM2_HOST = '192.168.83.132'
VM3_HOST = '192.168.83.133'  
USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'  # PRIVATE key, not .pub

def run_ssh_command(host, command):
    """Run command on remote host"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect with private key
        ssh.connect(hostname=host, username=USERNAME, key_filename=SSH_KEY)
        
        # Run command
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            print(f"Error: {error}")
            return None
        
        return output
    
    except Exception as e:
        print(f"SSH Error: {e}")
        return None
    
    finally:
        ssh.close()

def find_files(**context):
    """Find txt files on VM2"""
    command = f"find /home/{USERNAME} -name '*.txt' -path '*/in/*'"
    result = run_ssh_command(VM2_HOST, command)
    
    if result:
        files = result.split('\n')
        print(f"Found files: {files}")
        return files
    else:
        print("No files found")
        return []

def copy_and_process(**context):
    """Copy files from VM2 to VM3 and process them"""
    # Get file list from previous task
    files = context['task_instance'].xcom_pull(task_ids='find_files')
    
    if not files:
        print("No files to process")
        return
    
    for file_path in files:
        print(f"Processing: {file_path}")
        
        # Step 1: Copy file from VM2 to VM3
        copy_cmd = f"scp -i {SSH_KEY} {USERNAME}@{VM2_HOST}:{file_path} {USERNAME}@{VM3_HOST}:{file_path}"
        copy_result = os.system(copy_cmd)
        
        if copy_result == 0:
            print(f"File copied successfully: {file_path}")
            
            # Step 2: Process file on VM3
            process_cmd = f"python3 /home/{USERNAME}/scripts/simple_file_manager.py {file_path}"
            process_result = run_ssh_command(VM3_HOST, process_cmd)
            
            if process_result:
                print(f"Processing result: {process_result}")
            else:
                print(f"Processing failed for: {file_path}")
        else:
            print(f"Copy failed for: {file_path}")

# Simple DAG
with DAG(
    'simple_file_processing',
    default_args={
        'owner': 'rocky',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='Simple file processing workflow',
    schedule_interval='@hourly',
    start_date=datetime(2024, 5, 1),
    catchup=False,
) as dag:

    # Task 1: Find files on VM2
    find_task = PythonOperator(
        task_id='find_files',
        python_callable=find_files,
    )

    # Task 2: Copy and process files
    process_task = PythonOperator(
        task_id='copy_and_process',
        python_callable=copy_and_process,
        provide_context=True,
    )

    # Set dependency
    find_task >> process_task
