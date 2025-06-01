# ftp_pr_1_with_sensor.py
from datetime import datetime, timedelta
import os
import paramiko
from airflow.decorators import dag, task
from airflow.sensors.base import BaseSensorOperator
from airflow.utils.context import Context

# Config (with your updates in mind)
VM2_HOST = '192.168.83.132'
VM3_HOST = '192.168.83.133'
VM2_USERNAME = 'rocky'
VM3_USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'
FTP_PASSWORD = '111'

# Source directories to monitor for new .txt files
SOURCE_DIRS = ['/home/rocky/in', '/home/rocky/bon/in', '/home/rocky/card/in']

def ssh_run(host, user, cmd):
    """Run SSH command"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, key_filename=SSH_KEY)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    output = stdout.read().decode().strip()
    if stdout.channel.recv_exit_status() != 0:
        raise Exception(stderr.read().decode())
    ssh.close()
    return output

def file_size(host, user, path):
    """Get file size or None"""
    try:
        result = ssh_run(host, user, f"stat -c%s {path} 2>/dev/null || echo 'NONE'")
        return None if result == 'NONE' else int(result)
    except:
        return None

@dag(
    dag_id='ftp_pr_1_with_sensor',
    schedule_interval=None,  # Sensor-driven, not time-based
    start_date=datetime(2024, 5, 1),
    catchup=False,
    default_args={'owner': 'rocky', 'retries': 0}
)
def sensor_workflow():
    
    @task.sensor(poke_interval=30, timeout=300, mode="poke")
    def file_sensor():
        """Check for new .txt files in source directories"""
        found_files = []
        
        for source_dir in SOURCE_DIRS:
            try:
                # Find all .txt files in this directory
                find_cmd = f"find {source_dir} -name '*.txt' -type f -newermt '1 minute ago' 2>/dev/null || true"
                result = ssh_run(VM2_HOST, VM2_USERNAME, find_cmd)
                
                if result:
                    new_files = [f.strip() for f in result.split('\n') if f.strip()]
                    found_files.extend(new_files)
            except:
                continue
        
        if found_files:
            print(f"Found new files: {found_files}")
            return found_files
        
        return False  # Keep sensor running
    
    @task
    def transfer_files(detected_files: list):
        """Transfer detected files via FTP"""
        transferred = []
        
        for src in detected_files:
            # Use same path on destination
            dst = src
            
            # Check sizes
            src_size = file_size(VM2_HOST, VM2_USERNAME, src)
            dst_size = file_size(VM3_HOST, VM3_USERNAME, dst)
            
            if dst_size == src_size:
                transferred.append(dst)
                continue
            elif dst_size is not None:
                raise Exception(f"Size mismatch: {src}")
            
            # Transfer
            ssh_run(VM3_HOST, VM3_USERNAME, f"mkdir -p {os.path.dirname(dst)}")
            ftp_cmd = f"lftp -u {VM2_USERNAME},{FTP_PASSWORD} {VM2_HOST} -e 'get {src} -o {dst}; quit'"
            ssh_run(VM3_HOST, VM3_USERNAME, ftp_cmd)
            transferred.append(dst)
        
        return transferred
    
    @task
    def check_processing(files: list):
        """Check if processing needed"""
        for f in files:
            base = f.replace('.txt', '')
            dat_exists = file_size(VM3_HOST, VM3_USERNAME, f"{base}.dat") is not None
            inv_exists = file_size(VM3_HOST, VM3_USERNAME, f"{base}.inv") is not None
            
            if dat_exists or inv_exists:
                raise Exception(f"Output files exist for {f}")
        
        return files
    
    @task
    def process_files(files: list):
        """Process files"""
        for f in files:
            cmd = f"python3 /home/{VM3_USERNAME}/scripts/simple_file_manager.py {f}"
            ssh_run(VM3_HOST, VM3_USERNAME, cmd)
        
        return len(files)
    
    # Workflow with sensor
    detected_files = file_sensor()
    files = transfer_files(detected_files)
    checked = check_processing(files)
    result = process_files(checked)
    
    return result

# Create DAG
dag_instance = sensor_workflow()
