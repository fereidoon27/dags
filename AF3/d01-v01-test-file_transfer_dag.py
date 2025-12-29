from datetime import datetime, timedelta
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.ssh.operators.ssh import SSHOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'file_transfer_example',
    default_args=default_args,
    description='Transfer files between servers',
    schedule='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
) as dag:

    # Task 1: Check source file exists
    check_source = BashOperator(
        task_id='check_source_file',
        bash_command='echo "Checking source file..."',
    )

    # Task 2: Transfer file (example using scp)
    transfer_file = BashOperator(
        task_id='transfer_file',
        bash_command='echo "Transferring file..."',
        # Actual: 'scp user@vm1:/path/file user@vm2:/path/'
    )

    # Task 3: Verify transfer
    verify_transfer = BashOperator(
        task_id='verify_transfer',
        bash_command='echo "Verifying transfer..."',
    )

    check_source >> transfer_file >> verify_transfer
