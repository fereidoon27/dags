"""
Apache Airflow DAG: Secure SSH-based Card File Processing Workflow
DAG ID: S14_new_card_processing_workflow
Description: Detects, transfers, and processes card batch files between Linux servers using SSH
"""

from datetime import datetime
from pathlib import Path
import paramiko
from typing import List

from airflow.decorators import dag, task
from airflow.sensors.python import PythonSensor
from airflow.exceptions import AirflowException


# Configuration
SSH_CONFIG = {
    'user': 'rocky',
    'key_file': '/home/rocky/.ssh/id_ed25519',
    'ftp_host': '10.101.20.164',
    'target_host': '10.101.20.201',
    'card_dir': '/home/rocky/card/in/',
    'processor_script': '/home/rocky/scripts/card_processor.py'
}


def create_ssh_client(hostname: str) -> paramiko.SSHClient:
    """Create and return configured SSH client"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        private_key = paramiko.Ed25519Key.from_private_key_file(SSH_CONFIG['key_file'])
        client.connect(
            hostname=hostname,
            username=SSH_CONFIG['user'],
            pkey=private_key,
            timeout=30
        )
        return client
    except Exception as e:
        raise AirflowException(f"SSH connection to {hostname} failed: {str(e)}")


def check_for_card_files() -> bool:
    """Sensor function to detect card files on ftp server"""
    ssh = None
    try:
        ssh = create_ssh_client(SSH_CONFIG['ftp_host'])
        
        # List files matching pattern
        cmd = f"ls {SSH_CONFIG['card_dir']}card_batch*.txt 2>/dev/null || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files = stdout.read().decode().strip().split('\n')
        files = [f for f in files if f and f.strip()]  # Remove empty strings
        
        if files:
            print(f"✓ Detected {len(files)} card file(s): {files}")
            return True
        else:
            print("⏳ No card files detected yet, waiting...")
            return False
            
    except Exception as e:
        print(f"⚠️  Sensor check failed: {str(e)}")
        return False
    finally:
        if ssh:
            ssh.close()


def get_card_files() -> List[str]:
    """Get list of card files from ftp server"""
    ssh = None
    try:
        ssh = create_ssh_client(SSH_CONFIG['ftp_host'])
        
        cmd = f"ls {SSH_CONFIG['card_dir']}card_batch*.txt 2>/dev/null || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files = stdout.read().decode().strip().split('\n')
        files = [f for f in files if f and f.strip()]
        
        print(f"Retrieved {len(files)} card file(s)")
        return files
        
    except Exception as e:
        raise AirflowException(f"Failed to get card files: {str(e)}")
    finally:
        if ssh:
            ssh.close()


@dag(
    dag_id='S14_new_card_processing_workflow',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['card-processing'],
    default_args={
        'owner': 'airflow',
        'queue': 'card_processing_queue',
        'retries': 2
    },
    description='Secure SSH-based card file processing workflow'
)
def card_processing_workflow():
    
    # Use traditional PythonSensor (more stable in Airflow 2.9)
    detect_files = PythonSensor(
        task_id='detect_card_files',
        python_callable=check_for_card_files,
        poke_interval=30,
        timeout=3600,
        mode='poke',
        queue='card_processing_queue'
    )
    
    
    @task
    def get_file_list() -> List[str]:
        """Get the list of detected card files"""
        files = get_card_files()
        if not files:
            raise AirflowException("No card files found - sensor passed but files disappeared")
        return files
    
    
    @task
    def transfer_card_files(file_list: List[str]) -> List[str]:
        """Transfer files from ftp to target-1 via SSH/SCP"""
        
        # Validate input
        if not file_list or file_list is None:
            raise AirflowException("No files to transfer - received empty or None file list")
        
        ssh_source = None
        ssh_target = None
        transferred = []
        
        try:
            ssh_source = create_ssh_client(SSH_CONFIG['ftp_host'])
            ssh_target = create_ssh_client(SSH_CONFIG['target_host'])
            
            for file_path in file_list:
                filename = Path(file_path).name
                print(f"📤 Transferring: {filename}")
                
                # Read file from source
                sftp_source = ssh_source.open_sftp()
                with sftp_source.file(file_path, 'r') as remote_file:
                    file_content = remote_file.read()
                sftp_source.close()
                
                # Write file to target (overwrite if exists)
                sftp_target = ssh_target.open_sftp()
                with sftp_target.file(file_path, 'w') as remote_file:
                    remote_file.write(file_content)
                sftp_target.close()
                
                transferred.append(file_path)
                print(f"✓ Transferred: {filename} ({len(file_content)} bytes)")
            
            print(f"✓ All {len(transferred)} files transferred successfully")
            return transferred
            
        except Exception as e:
            raise AirflowException(f"File transfer failed: {str(e)}")
        finally:
            if ssh_source:
                ssh_source.close()
            if ssh_target:
                ssh_target.close()
    
    
    @task
    def process_card_files(file_list: List[str]) -> dict:
        """Execute card_processor.py on target-1 for each file"""
        ssh = None
        results = {'success': [], 'failed': []}
        
        try:
            ssh = create_ssh_client(SSH_CONFIG['target_host'])
            
            for file_path in file_list:
                filename = Path(file_path).name
                print(f"⚙️  Processing: {filename}")
                
                cmd = f"python3 {SSH_CONFIG['processor_script']} {file_path}"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                
                exit_code = stdout.channel.recv_exit_status()
                output = stdout.read().decode()
                error = stderr.read().decode()
                
                if exit_code == 0:
                    results['success'].append(filename)
                    print(f"✓ {filename} processed successfully")
                    if output:
                        print(f"   Output: {output.strip()}")
                else:
                    results['failed'].append(filename)
                    print(f"✗ {filename} processing failed (exit code: {exit_code})")
                    if error:
                        print(f"   Error: {error.strip()}")
            
            print(f"\n📊 Processing Summary:")
            print(f"   Success: {len(results['success'])}")
            print(f"   Failed: {len(results['failed'])}")
            
            if results['failed']:
                raise AirflowException(f"Processing failed for: {results['failed']}")
            
            return results
            
        except Exception as e:
            raise AirflowException(f"File processing failed: {str(e)}")
        finally:
            if ssh:
                ssh.close()
    
    
    # Define task dependencies
    file_list = get_file_list()
    transferred_files = transfer_card_files(file_list)
    
    detect_files >> file_list
    process_card_files(transferred_files)


# Instantiate the DAG
card_dag = card_processing_workflow()
