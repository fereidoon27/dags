# d04_v01_NASIR_DAG.py
from datetime import datetime, timedelta
from airflow.sdk import dag, task

# Local constant data (replacing remote file reads)
LOCAL_DATA = {
    'num_001': [10, 20, 30, 40],
    'num_002': [5, 15, 25],
    'num_003': [100, 200, 300]
}


@dag(
    dag_id='d04-v01-NASIR_DAG',
    schedule=None,  # Changed from schedule_interval to schedule
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_tasks=5,
    default_args={
        'owner': 'airflow',  # Changed from 'rocky' to 'airflow' for consistency
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
    },
    tags=['simple', 'nasir', 'v01']
)
def sum_flow():
    """
    DAG that fetches numbers from local constants, sums them,
    combines results, and adds a constant value.
    """

    @task
    def fetch_numbers(data_key: str) -> list:
        """Fetch numbers from local constant data."""
        numbers = LOCAL_DATA.get(data_key, [])
        print(f"Fetched numbers for {data_key}: {numbers}")
        return numbers

    @task
    def sum_numbers(nums: list) -> int:
        """Calculate sum of a list of numbers."""
        print("=== sum of numbers in a list ===")
        if not nums:
            print("No numbers provided, returning 0")
            return 0
        total = sum(nums)
        print(f"Total sum: {total}")
        return total

    @task
    def combine(a: int, b: int) -> int:
        """Combine two numbers by addition."""
        result = a + b
        print(f"Combining {a} + {b} = {result}")
        return result

    @task
    def add_const(value: int, const: int = 2) -> int:
        """Add a constant value to the input."""
        result = value + const
        print(f"Adding constant: {value} + {const} = {result}")
        return result

    @task
    def print_final(result: int):
        """Print the final result."""
        print(f"========================================")
        print(f"FINAL RESULT: {result}")
        print(f"========================================")

    # DAG workflow: Fetch and sum individual inputs
    nums_1 = fetch_numbers('num_001')
    nums_2 = fetch_numbers('num_002')
    nums_3 = fetch_numbers('num_003')

    # Sum first two datasets
    r1 = sum_numbers(nums_1)
    r2 = sum_numbers(nums_2)
    result_1 = combine(r1, r2)

    # Sum third dataset
    result_2 = sum_numbers(nums_3)
    
    # Combine all results
    result_3 = combine(result_1, result_2)

    # Add constant and print final result
    result_4 = add_const(result_3)
    print_final(result_4)


# DAG instance
dag_instance = sum_flow()
