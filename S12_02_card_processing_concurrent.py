# S12_card_processing_concurrent.py
"""
Enhanced card processing workflow demonstrating concurrency concepts
This version shows how tasks can run in parallel on the same worker
"""
from datetime import datetime, timedelta
import os
import time
import paramiko
from airflow.decorators import dag, task
from airflow.sensors.base import PokeReturnValue

# Configuration (same as original)
VM2_HOST = '192.168.83.132'  # FTP server (source)
VM3_HOST = '192.168.83.133'  # Card1 server (destination/processing)
VM2_USERNAME = 'rocky'
VM3_USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'
FTP_PASSWORD = '111'

# Files to monitor - expanded for concurrency demo
CARD_SOURCE_PATHS = [
    '/home/rocky/card/in/card_batch_001.txt',
    '/home/rocky/card/in/card_batch_002.txt',
    '/home/rocky/card/in/card_batch_003.txt',
    '/home/rocky/card/in/card_batch_004.txt',
    '/home/rocky/card/in/card_batch_005.txt'
]

# Script paths on VM3
CARD_PROCESSOR_SCRIPT = '/home/rocky/scripts/S12_card_processor.py'
CARD_VALIDATOR_SCRIPT = '/home/rocky/scripts/S12_card_validator.py'
CARD_REPORTER_SCRIPT = '/home/rocky/scripts/S12_card_reporter.py'

def ssh_execute(host, user, cmd):
    """Execute command via SSH"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(hostname=host, username=user, key_filename=SSH_KEY, timeout=30)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            raise Exception(f"Command failed (exit {exit_code}): {error}")
        
        return output
    finally:
        ssh.close()

def get_file_info(host, user, path):
    """Get file size"""
    try:
        cmd = f"stat -c'%s' {path} 2>/dev/null || echo 'NOT_FOUND'"
        result = ssh_execute(host, user, cmd)
        return None if result == 'NOT_FOUND' else int(result)
    except:
        return None

@dag(
    dag_id='S12_card_processing_concurrent',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_tasks=10,  # Allow up to 10 concurrent tasks in this DAG
    default_args={
        'owner': 'rocky',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        'queue': 'card_processing_queue'
    },
    tags=['card-processing', 'concurrent', 'demo']
)
def card_processing_concurrent():
    
    @task.sensor(
        poke_interval=120,  # Check every 2 minutes
        timeout=3600,
        mode="poke",
        queue='card_processing_queue'
    )
    def detect_card_files():
        """Monitor for card files on VM2"""
        detected = []
        
        for src_path in CARD_SOURCE_PATHS:
            size = get_file_info(VM2_HOST, VM2_USERNAME, src_path)
            if size:
                detected.append({'path': src_path, 'size': size})
        
        if detected:
            print(f"Detected {len(detected)} files")
            return PokeReturnValue(is_done=True, xcom_value=detected)
        else:
            return PokeReturnValue(is_done=False)
    
    @task(queue='card_processing_queue')
    def parallel_transfer(file_info: dict):
        """Transfer a single file - runs in parallel for each file"""
        start_time = time.time()
        src_path = file_info['path']
        src_size = file_info['size']
        dst_path = src_path.replace('192.168.83.132', '192.168.83.133')
        
        print(f"[CONCURRENT] Starting transfer of {src_path}")
        print(f"[CONCURRENT] This task started at: {datetime.now()}")
        
        # Check destination
        dst_size = get_file_info(VM3_HOST, VM3_USERNAME, dst_path)
        if dst_size == src_size:
            print(f"[CONCURRENT] {src_path} already exists, skipping")
            return {'file': dst_path, 'transferred': False, 'duration': 0}
        
        # Create directory
        dst_dir = os.path.dirname(dst_path)
        ssh_execute(VM3_HOST, VM3_USERNAME, f"mkdir -p {dst_dir}")
        
        # Transfer file (simulate longer transfer for demo)
        print(f"[CONCURRENT] Transferring {src_path}...")
        time.sleep(3)  # Simulate network delay
        
        ftp_cmd = f"lftp -u {VM2_USERNAME},{FTP_PASSWORD} {VM2_HOST} -e 'get {src_path} -o {dst_path}; quit'"
        ssh_execute(VM3_HOST, VM3_USERNAME, ftp_cmd)
        
        duration = time.time() - start_time
        print(f"[CONCURRENT] Completed {src_path} in {duration:.2f} seconds")
        
        return {
            'file': dst_path,
            'transferred': True,
            'duration': duration,
            'size': src_size
        }
    
    @task(queue='card_processing_queue')
    def parallel_validate(file_result: dict):
        """Validate a single file - runs in parallel"""
        if not file_result['transferred']:
            return {'file': file_result['file'], 'valid': True, 'skipped': True}
        
        start_time = time.time()
        file_path = file_result['file']
        
        print(f"[CONCURRENT] Starting validation of {file_path}")
        print(f"[CONCURRENT] Validation started at: {datetime.now()}")
        
        # Simulate validation work
        time.sleep(2)  # Validation takes time
        
        # Run validation script
        cmd = f"python3 {CARD_VALIDATOR_SCRIPT} {file_path}"
        result = ssh_execute(VM3_HOST, VM3_USERNAME, cmd)
        
        duration = time.time() - start_time
        print(f"[CONCURRENT] Validated {file_path} in {duration:.2f} seconds")
        
        return {
            'file': file_path,
            'valid': 'VALID' in result,
            'duration': duration,
            'result': result
        }
    
    @task(queue='card_processing_queue')
    def parallel_process(validation_result: dict):
        """Process a single file - runs in parallel"""
        if not validation_result['valid']:
            return {'file': validation_result['file'], 'processed': False, 'error': 'Invalid file'}
        
        if validation_result.get('skipped'):
            return {'file': validation_result['file'], 'processed': False, 'skipped': True}
        
        start_time = time.time()
        file_path = validation_result['file']
        
        print(f"[CONCURRENT] Starting processing of {file_path}")
        print(f"[CONCURRENT] Processing started at: {datetime.now()}")
        
        # Simulate heavy processing
        time.sleep(5)  # Processing takes longer
        
        # Run processor script
        cmd = f"python3 {CARD_PROCESSOR_SCRIPT} {file_path}"
        result = ssh_execute(VM3_HOST, VM3_USERNAME, cmd)
        
        duration = time.time() - start_time
        print(f"[CONCURRENT] Processed {file_path} in {duration:.2f} seconds")
        
        return {
            'file': file_path,
            'processed': True,
            'duration': duration,
            'output': result
        }
    
    @task(queue='card_processing_queue')
    def generate_report(all_results: list):
        """Generate final report - waits for all parallel tasks"""
        print("\n=== CONCURRENCY ANALYSIS REPORT ===")
        print(f"Total files processed: {len(all_results)}")
        
        # Analyze timing
        total_serial_time = sum(r.get('duration', 0) for r in all_results)
        max_duration = max(r.get('duration', 0) for r in all_results)
        
        print(f"\nTiming Analysis:")
        print(f"- If run serially: {total_serial_time:.2f} seconds")
        print(f"- With parallel execution: ~{max_duration:.2f} seconds")
        print(f"- Time saved: {total_serial_time - max_duration:.2f} seconds")
        print(f"- Speedup factor: {total_serial_time / max_duration:.2f}x")
        
        # Create detailed report on VM3
        report_content = f"""S12 Card Processing Report
Generated: {datetime.now()}
Files Processed: {len(all_results)}
Concurrency Level: 5
Queue: card_processing_queue

File Details:
"""
        for r in all_results:
            report_content += f"- {r['file']}: {'SUCCESS' if r.get('processed') else 'SKIPPED'}\n"
        
        # Save report
        report_path = f"/tmp/S12_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        cmd = f"echo '{report_content}' > {report_path}"
        ssh_execute(VM3_HOST, VM3_USERNAME, cmd)
        
        return {
            'report_path': report_path,
            'files_processed': len(all_results),
            'time_saved': total_serial_time - max_duration
        }
    
    @task(queue='card_processing_queue')
    def demonstrate_concurrency_limit():
        """Show what happens when we exceed concurrency limit"""
        print("\n=== CONCURRENCY LIMIT DEMONSTRATION ===")
        print("Worker concurrency is set to 5")
        print("If we have 10 tasks but concurrency=5:")
        print("- First 5 tasks run immediately")
        print("- Next 5 tasks wait in queue")
        print("- As tasks complete, queued tasks start")
        print("\nCheck Flower UI to see tasks in different states:")
        print("- PENDING: Waiting in queue")
        print("- STARTED: Currently running")
        print("- SUCCESS: Completed")
        return "Demonstration complete"
    
    # Define workflow with parallel execution
    detected_files = detect_card_files()
    
    # Create parallel tasks for each file
    transfer_results = []
    for i in range(len(CARD_SOURCE_PATHS)):
        # Use .map() to create dynamic parallel tasks
        transfer_result = parallel_transfer.override(
            task_id=f'transfer_file_{i}'
        )(detected_files[i])
        transfer_results.append(transfer_result)
    
    # Parallel validation for each transferred file
    validation_results = []
    for i, transfer_result in enumerate(transfer_results):
        validation_result = parallel_validate.override(
            task_id=f'validate_file_{i}'
        )(transfer_result)
        validation_results.append(validation_result)
    
    # Parallel processing for each validated file
    process_results = []
    for i, validation_result in enumerate(validation_results):
        process_result = parallel_process.override(
            task_id=f'process_file_{i}'
        )(validation_result)
        process_results.append(process_result)
    
    # Generate report after all processing completes
    report = generate_report(process_results)
    
    # Demonstrate concurrency concepts
    demo = demonstrate_concurrency_limit()
    
    # Set dependencies
    detected_files >> transfer_results
    report >> demo

# Create DAG instance
dag_instance = card_processing_concurrent()
