# python_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Define Python functions that will become tasks
def say_hello():
    print("Hello from Python operator!")
    return "Task completed successfully"

def process_data(**context):
    # You can access task context and execution info
    execution_date = context['logical_date']
    print(f"Processing data for {execution_date}")
    
    # Simulate some data processing
    data = {'processed_records': 100, 'success': True}
    
    # Store results for the next task (using XCom)
    context['task_instance'].xcom_push(key='results', value=data)
    
    return "Data processing completed"

def check_results(**context):
    # Retrieve data from the previous task
    results = context['task_instance'].xcom_pull(task_ids='process_data_task', key='results')
    
    print(f"Retrieved results: {results}")
    print(f"Processed {results['processed_records']} records")
    
    if results['success']:
        print("Data processing was successful!")
    else:
        print("Data processing failed!")
    
    return f"Checked {results['processed_records']} records"

# Create the DAG
with DAG(
    'python_functions_dag',
    default_args={
        'owner': 'your_name',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='DAG using Python functions',
    schedule_interval='@daily',  # Run once per day
    start_date=datetime(2024, 5, 1),
    catchup=False,
) as dag:

    # Create tasks using Python functions
    hello_task = PythonOperator(
        task_id='hello_task',
        python_callable=say_hello,
    )

    process_data_task = PythonOperator(
        task_id='process_data_task',
        python_callable=process_data,
        provide_context=True,  # This passes context to the function
    )

    check_results_task = PythonOperator(
        task_id='check_results_task',
        python_callable=check_results,
        provide_context=True,
    )

    # Set dependencies
    hello_task >> process_data_task >> check_results_task