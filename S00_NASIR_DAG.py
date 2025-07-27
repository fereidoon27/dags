# S00_NASIR_DAG.py
from datetime import datetime, timedelta
from airflow.decorators import dag, task


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

    @task(queue='default')
    def sum_1(nums: list):
        print("=== sum of numbers in a list ===")
        if not nums:
            print("No numbers provided, returning 0")
            return 0
        total = sum(nums)
        print(f"Total sum: {total}")
        return total

    @task(queue='default')
    def combine(a: int, b: int):
        return a + b

    @task(queue='default')
    def add_const(value: int, const: int = 2):
        return value + const

    # Step-by-step execution
    r1 = sum_1([2, 2])
    r2 = sum_1([3, 3])
    result_1 = combine(r1, r2)

    result_2 = sum_1([4, 4])
    result_3 = combine(result_2, result_1)
    result_4 = add_const(result_3)

    # Optional: log the result
    @task
    def print_final(result: int):
        print(f"Final result: {result}")

    print_final(result_4)


# DAG instance
dag_instance = sum_flow()
