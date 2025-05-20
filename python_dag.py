# python_dag.py
from datetime import datetime, timedelta  # Import time-related functions
from airflow import DAG  # Import the main Airflow DAG class
from airflow.operators.python import PythonOperator  # Import the operator that runs Python code

# --------- TASK FUNCTIONS ---------

# This simple function will be our first task
def say_hello():
    """
    This function simply prints a greeting message.
    In Airflow, print statements appear in the task logs.
    """
    print("Hello from Python operator!")
    # The return value will be stored in XCom automatically
    # Example: Return value "Task completed successfully" will be stored
    return "Task completed successfully"  

# This function simulates processing some data
def process_data(**context):
    """
    This function demonstrates how to:
    1. Access the Airflow context (execution information)
    2. Process some data (simulated here)
    3. Store results for other tasks using XCom
    
    The **context parameter receives all the information Airflow provides:
    - task_instance: The running task instance
    - logical_date: When this DAG run was scheduled for (previously called execution_date)
    - dag: The DAG object
    - etc.
    """
    # Get the execution date from context
    # Example: If DAG was scheduled for May 20, 2025, execution_date will be 2025-05-20T00:00:00
    execution_date = context['logical_date']
    print(f"Processing data for {execution_date}")
    
    # Simulate some data processing with a dictionary
    # In a real scenario, this might be the result of processing files, API calls, etc.
    data = {
        'processed_records': 100,  # Example: Processed 100 records
        'success': True,           # Example: Processing was successful
        'execution_date': str(execution_date)  # Convert datetime to string for storage
    }
    
    # Store results using XCom (Cross-Communication)
    # XCom allows tasks to exchange small amounts of data
    # Example: Store the dictionary above with the key 'results'
    task_instance = context['task_instance']
    task_instance.xcom_push(key='results', value=data)
    
    print(f"Stored results in XCom: {data}")
    return "Data processing completed"

# This function retrieves and checks the results from the previous task
def check_results(**context):
    """
    This function demonstrates how to:
    1. Retrieve data from a previous task using XCom
    2. Process that data
    
    The **context works the same as in the process_data function
    """
    # Get the task instance from context
    task_instance = context['task_instance']
    
    # Retrieve data stored by the process_data task
    # Example: Retrieves the dictionary {'processed_records': 100, 'success': True, ...}
    results = task_instance.xcom_pull(
        task_ids='process_data_task',  # From which task to get data
        key='results'                  # Which data to get (by key)
    )
    
    print(f"Retrieved results: {results}")
    
    # Access specific values from the dictionary
    # Example: Gets the value 100 from the 'processed_records' key
    record_count = results['processed_records']
    print(f"Processed {record_count} records")
    
    # Conditional logic based on the results
    if results['success']:
        print("Data processing was successful!")
    else:
        print("Data processing failed!")
        # In a real scenario, you might want to raise an exception here
        # raise ValueError("Data processing failed")
    
    return f"Checked {record_count} records"

# --------- DAG DEFINITION ---------

# Create the DAG object that will contain our tasks
with DAG(
    'python_functions_dag',  # Unique identifier for this DAG
    # Default settings that apply to all tasks in this DAG
    default_args={
        'owner': 'your_name',  # Who owns this DAG
        'retries': 1,          # How many times to retry failed tasks
        'retry_delay': timedelta(minutes=5),  # How long to wait between retries
                                              # Example: Wait 5 minutes before retrying
    },
    description='DAG using Python functions',  # Description shown in the UI
    schedule_interval='@daily',  # When to run: @daily = once per day at midnight
                                # Other options: @hourly, @weekly, @monthly, 
                                # or cron expressions like '0 0 * * *' (midnight every day)
    start_date=datetime(2024, 5, 1),  # Start scheduling from this date
                                      # Example: Start scheduling from May 1, 2024
    catchup=False,  # If True, Airflow will run all missed DAG runs since start_date
                    # False means only run for the current schedule
) as dag:

    # --------- TASK DEFINITIONS ---------
    
    # Task 1: Say Hello
    # This creates our first task using the say_hello function
    hello_task = PythonOperator(
        task_id='hello_task',  # Unique identifier for this task within the DAG
        python_callable=say_hello,  # The function this task will execute
        # No provide_context=True needed since this function doesn't use context
    )

    # Task 2: Process Data
    # This task will run the process_data function
    process_data_task = PythonOperator(
        task_id='process_data_task',  # Unique identifier for this task
        python_callable=process_data,  # The function to run
        provide_context=True,  # Pass the Airflow context to the function
                               # This is how the function gets access to task_instance, etc.
    )

    # Task 3: Check Results
    # This task will retrieve and check the results from the process_data task
    check_results_task = PythonOperator(
        task_id='check_results_task',  # Unique identifier for this task
        python_callable=check_results,  # The function to run
        provide_context=True,  # Pass the Airflow context to the function
    )

    # --------- TASK DEPENDENCIES ---------
    
    # Set the order in which tasks should run
    # This means: run hello_task first, then process_data_task, then check_results_task
    hello_task >> process_data_task >> check_results_task
    
    # Equivalent ways to write the same dependencies:
    # Option 1: hello_task.set_downstream(process_data_task)
    #           process_data_task.set_downstream(check_results_task)
    # Option 2: check_results_task << process_data_task << hello_task
