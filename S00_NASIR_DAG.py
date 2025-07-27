# S00_NASIR_DAG.py
from datetime import datetime, timedelta
from airflow.decorators import dag, task
import paramiko

# Configuration
VM2_HOST = '192.168.83.132'  # FTP server
VM2_USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'
FTP_PASSWORD = '111'

FTP_SOURCE_PATHS = {
    'num_001': '/home/rocky/card/num/num_001.txt',
    'num_002': '/home/rocky/card/num/num_002.txt',
    'num_003': '/home/rocky/card/num/num_003.txt'
}


def ssh_read_file(remote_path):
    """Read a file from the remote server using Paramiko."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname=VM2_HOST, username=VM2_USERNAME, password=FTP_PASSWORD, key_filename=SSH_KEY)
        sftp = client.open_sftp()
        with sftp.open(remote_path, 'r') as f:
            contents = f.read().decode('utf-8').strip()
            return contents
    finally:
        client.close()



@dag(
    dag_id='S00_NASIR_DAG',
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_tasks=5,
    default_args={
        'owner': 'rocky',
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
        'queue': 'default'
    },
    tags=['simple', 'nasir']
)
def sum_flow():

    @task
    def fetch_numbers(file_path: str) -> list:
        raw_data = ssh_read_file(file_path)
        print(f"Raw data from {file_path}: {raw_data}")
        # Split by comma or whitespace
        try:
            numbers = [int(x) for x in raw_data.replace(",", " ").split()]
            print(f"Parsed numbers: {numbers}")
        except Exception as e:
            print(f"Error parsing numbers: {e}")
            numbers = []
        return numbers

    @task
    def sum_1(nums: list):
        print("=== sum of numbers in a list ===")
        if not nums:
            print("No numbers provided, returning 0")
            return 0
        total = sum(nums)
        print(f"Total sum: {total}")
        return total

    @task
    def combine(a: int, b: int):
        return a + b

    @task
    def add_const(value: int, const: int = 2):
        return value + const

    @task
    def print_final(result: int):
        print(f"Final result: {result}")

    # Fetch and sum individual inputs
    nums_1 = fetch_numbers(FTP_SOURCE_PATHS['num_001'])
    nums_2 = fetch_numbers(FTP_SOURCE_PATHS['num_002'])
    nums_3 = fetch_numbers(FTP_SOURCE_PATHS['num_003'])

    r1 = sum_1(nums_1)
    r2 = sum_1(nums_2)
    result_1 = combine(r1, r2)

    result_2 = sum_1(nums_3)
    result_3 = combine(result_1, result_2)

    result_4 = add_const(result_3)
    print_final(result_4)


# DAG instance
dag_instance = sum_flow()
