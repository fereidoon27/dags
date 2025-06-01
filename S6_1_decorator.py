# simple_taskflow_dag.py
from datetime import datetime, timedelta
import os
import paramiko
from airflow.decorators import dag, task

# Config
VM2_HOST = '192.168.83.132'
VM3_HOST = '192.168.83.133'
VM2_USERNAME = 'rocky'
VM3_USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'
FTP_PASSWORD = '111'

SOURCE_PATHS = ['/home/rocky/in/sample1.txt', '/home/rocky/bon/in/sample3.txt']
DEST_PATHS = ['/home/rocky/in/sample1.txt', '/home/rocky/bon/in/sample3.txt']

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
    dag_id='simple_ftp_dag',
    schedule_interval='@hourly',
    start_date=datetime(2024, 5, 1),
    catchup=False,
    default_args={'owner': 'rocky', 'retries': 1}
)
def simple_workflow():
    
    @task
    def transfer_files():
        """Transfer files via FTP"""
        transferred = []
        
        for i in range(len(SOURCE_PATHS)):
            src, dst = SOURCE_PATHS[i], DEST_PATHS[i]
            
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
    
    # Workflow
    files = transfer_files()
    checked = check_processing(files)
    result = process_files(checked)
    
    return result

# Create DAG
dag_instance = simple_workflow()
