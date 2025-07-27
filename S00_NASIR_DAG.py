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
    def sum_two_numbers(a: int, b: int) -> int:
        print(f"=== sum_two_numbers: {a} + {b} ===")
        result = a + b
        print(f"Result: {result}")
        return result

    # Step-by-step dependency logic
    r1 = sum_two_numbers(2, 2)
    r2 = sum_two_numbers(3, 3)
    result_1 = sum_two_numbers.partial().expand(a=[r1], b=[r2])  # result_1 = r1 + r2

    result_2 = sum_two_numbers(4, 4)
    result_3 = sum_two_numbers.partial().expand(a=[result_2], b=result_1)  # result_3 = result_2 + result_1

    result_4 = sum_two_numbers.partial().expand(a=result_3, b=[2])  # result_4 = result_3 + 2

    @task
    def print_result(value: int):
        print(f"Final result: {value}")

    print_result(result_4)


dag_instance = sum_flow()
