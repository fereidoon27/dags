# S00_NASIR_DAG.py
from datetime import datetime, timedelta
import os
import paramiko
from airflow.decorators import dag, task
from airflow.sensors.base import PokeReturnValue




@dag(
    dag_id='S00_NASIR_DAG',
    schedule_interval=None,  # Triggered by sensor
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_tasks=5,  # DAG-level concurrency limit
    default_args={
        'owner': 'rocky',
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
        'queue': 'default'  # Custom queue for all tasks
    },
    tags=['simple', 'nasir']
)
def sum_flow():
    
    @task(queue='default')
    def sum_1(nums: list):
        """sum of numbers in a list"""
        print("=== sum of numbers in a list ===")
        
        if not nums:
            print("No numbers provided, returning 0")
            return 0
        
        total = sum(nums)
        print(f"Total sum: {total}")
        return total


    result_1 = sum_1([2, 2]) + sum_1([3, 3])
    # Define workflow
    result_2 = sum_1([4, 4])

    result_3 = result_2 + result_1

    result_4 = result_3 + 2

    print(f"Final result: {result_4}")
    
    # Dependencies

# Create DAG instance
dag_instance = sum_flow()
