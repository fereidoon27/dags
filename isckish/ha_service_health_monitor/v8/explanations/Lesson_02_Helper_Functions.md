# Lesson 02: Helper Functions - Hostname & Task Identifiers

## Plain-English Overview

These helper functions answer two important questions:
1. **"Which server am I running on?"** → `get_current_hostname()`
2. **"What task am I executing right now?"** → `get_task_identifiers()`

Think of it like a delivery driver who needs to know (1) their current location and (2) which package they're delivering.

---

## Structure Overview

**Functions we'll learn:**
1. `get_current_hostname()` - Returns the current server's name
2. `get_task_identifiers()` - Extracts task execution details
3. `format_identifiers_for_grep()` - Creates search patterns for logs

**New concepts:**
- Try/except error handling
- Function parameters with defaults
- Dictionary operations
- Conditional logic

---

## Line-by-Line Walkthrough

### Lines 118-124: Getting the Current Hostname

```python
def get_current_hostname():
    """Get the current hostname"""
    try:
        return platform.node()
    except:
        return socket.gethostname()
```

**Line 118**: `def get_current_hostname():`
- `def` = **define** a function
- `get_current_hostname` = function name (descriptive!)
- `()` = no parameters needed (empty parentheses)
- `:` = start of function body

**Line 119**: `"""Get the current hostname"""`
- Function **docstring** - describes what the function does
- Always write these! Helps others (and future you) understand the code

**Line 120**: `try:`
- Starts a **try block** - "try to run this code"
- Used when code might fail

**Line 121**: `return platform.node()`
- **First attempt**: Use `platform.node()` to get hostname
- `return` = send this value back to whoever called the function
- `platform.node()` is the preferred method (more reliable)

**Line 122**: `except:`
- **Fallback**: If `platform.node()` fails, do this instead
- Catches ANY error (not specific)

**Line 123**: `return socket.gethostname()`
- **Second attempt**: Use `socket.gethostname()` as backup
- Different method, might work when platform.node() doesn't

**Why two methods?**
- Belt-and-suspenders approach
- Ensures we ALWAYS get a hostname, even in weird environments
- Better to have a backup than crash!

---

### 🎓 TIP: Try/Except Error Handling

**What is it?**
Error handling lets your code gracefully handle problems instead of crashing.

**Basic syntax:**
```python
try:
    # Code that might fail
    risky_operation()
except:
    # What to do if it fails
    safe_fallback()
```

**Common use cases:**
1. File operations (file might not exist)
2. Network operations (server might be down)
3. User input (might be invalid)
4. External API calls (might timeout)

**Better practice (specific exceptions):**
```python
try:
    file = open('data.txt')
except FileNotFoundError:
    print("File doesn't exist!")
except PermissionError:
    print("No permission to read file!")
```

**Copy-ready example:**
```python
# Example 1: Safe file reading
def read_config(filename):
    try:
        with open(filename, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "default config"
    except Exception as e:
        print(f"Error: {e}")
        return None

# Example 2: Safe number conversion
def safe_int(value):
    try:
        return int(value)
    except ValueError:
        return 0  # Default value

# Example 3: Multiple fallbacks (like our hostname function)
def get_data():
    try:
        return method1()
    except:
        try:
            return method2()
        except:
            return "default"
```

**Booklet summary:**
`try/except` prevents crashes. Use `try:` for risky code, `except:` for fallback. Catch specific exceptions when possible (`FileNotFoundError`, `ValueError`). Always have a safe fallback plan.

---

### Lines 126-159: Getting Task Identifiers

```python
def get_task_identifiers(context=None):
    """Extract unique identifiers for task instance tracing"""
    if context is None:
        try:
            context = get_current_context()
        except:
            return {}
    
    identifiers = {}
    
    try:
        ti = context.get('ti')
        if ti:
            identifiers['dag_id'] = ti.dag_id
            identifiers['task_id'] = ti.task_id
            identifiers['run_id'] = ti.run_id
            identifiers['execution_date'] = str(ti.execution_date)
            identifiers['try_number'] = ti.try_number
            identifiers['job_id'] = ti.job_id if hasattr(ti, 'job_id') else None
            
            if hasattr(ti, 'external_executor_id'):
                identifiers['external_executor_id'] = ti.external_executor_id
            
            identifiers['ti_key'] = f"{ti.dag_id}__{ti.task_id}__{ti.execution_date}"
            identifiers['pid'] = os.getpid()
            
            if hasattr(ti, 'map_index'):
                identifiers['map_index'] = ti.map_index
    
    except Exception as e:
        identifiers['error'] = str(e)
    
    return identifiers
```

**Line 126**: `def get_task_identifiers(context=None):`
- Function with **optional parameter**
- `context=None` means: "If caller doesn't provide context, use None"
- This is a **default parameter value**

**Line 127**: `"""Extract unique identifiers for task instance tracing"""`
- Explains function purpose: get info about current running task

**Lines 128-132**: Context handling
```python
if context is None:
    try:
        context = get_current_context()
    except:
        return {}
```
- **Line 128**: Check if context was provided
- **Line 130**: If not, try to get it ourselves using Airflow's function
- **Line 132**: If that fails too, return empty dictionary `{}`
- This makes the function flexible - works with or without context parameter

**Line 134**: `identifiers = {}`
- Create empty dictionary to store all identifiers
- We'll fill this up with task information

**Line 136**: `try:`
- Start try block - extracting identifiers might fail

**Line 137**: `ti = context.get('ti')`
- Get **task instance** (ti) from context dictionary
- `.get()` is safe - returns `None` if 'ti' key doesn't exist
- `ti` contains all information about the current task

**Line 138**: `if ti:`
- Only proceed if we successfully got the task instance
- `if ti:` checks if ti is not None/empty

**Lines 139-143**: Basic identifiers
```python
identifiers['dag_id'] = ti.dag_id
identifiers['task_id'] = ti.task_id
identifiers['run_id'] = ti.run_id
identifiers['execution_date'] = str(ti.execution_date)
identifiers['try_number'] = ti.try_number
```
- **dag_id**: Which DAG (workflow) is this?
- **task_id**: Which specific task?
- **run_id**: Which run of the DAG?
- **execution_date**: When was it scheduled? (converted to string)
- **try_number**: How many times has this task tried to run?

**Line 144**: `identifiers['job_id'] = ti.job_id if hasattr(ti, 'job_id') else None`
- **Conditional expression** (ternary operator)
- Format: `value_if_true if condition else value_if_false`
- `hasattr(ti, 'job_id')` checks if ti has a job_id attribute
- If yes, use it; if no, use None
- Safe way to access attributes that might not exist

**Lines 146-147**: Optional external executor ID
```python
if hasattr(ti, 'external_executor_id'):
    identifiers['external_executor_id'] = ti.external_executor_id
```
- Only add this if it exists
- Used when tasks run on external systems (like Celery workers)

**Line 149**: `identifiers['ti_key'] = f"{ti.dag_id}__{ti.task_id}__{ti.execution_date}"`
- Create unique identifier by combining three values
- Double underscores `__` separate the parts
- Example result: `"my_dag__check_db__2024-01-15"`

**Line 150**: `identifiers['pid'] = os.getpid()`
- Get **process ID** - the operating system's ID for this running process
- Useful for debugging and finding logs

**Lines 152-153**: Optional map index
```python
if hasattr(ti, 'map_index'):
    identifiers['map_index'] = ti.map_index
```
- For mapped tasks (tasks that run multiple times in parallel)
- Only present in dynamic task mapping scenarios

**Lines 155-156**: Error handling
```python
except Exception as e:
    identifiers['error'] = str(e)
```
- If anything fails, save the error message
- `Exception as e` captures the error object
- `str(e)` converts error to readable string

**Line 158**: `return identifiers`
- Return the dictionary with all collected information
- Will be empty `{}` if everything failed

---

### 🎓 TIP: Function Parameters and Default Values

**What are function parameters?**
Variables that functions receive as input.

**Syntax:**
```python
def function_name(parameter1, parameter2):
    # Use parameters here
    return result
```

**Default parameters:**
```python
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"

greet("Alice")              # "Hello, Alice!"
greet("Bob", "Hi")          # "Hi, Bob!"
```

**Common use cases:**
1. Optional configuration
2. Fallback values
3. Making functions flexible

**Copy-ready examples:**
```python
# Example 1: Function with defaults
def connect_database(host, port=5432, timeout=10):
    """Connect to database with optional port and timeout"""
    print(f"Connecting to {host}:{port} (timeout: {timeout}s)")
    # connection logic here

connect_database("localhost")              # Uses defaults
connect_database("localhost", 5433)        # Custom port
connect_database("localhost", 5433, 30)    # Custom port and timeout

# Example 2: Optional parameter pattern (like our code)
def process_data(data, config=None):
    if config is None:
        config = get_default_config()
    # Use config here

# Example 3: Multiple defaults
def send_email(to, subject, body="", cc=None, priority="normal"):
    print(f"To: {to}, Subject: {subject}, Priority: {priority}")
    if cc:
        print(f"CC: {cc}")
```

**Booklet summary:**
Default parameters make functions flexible. Format: `def func(required, optional=default):`. Parameters with defaults must come after required ones. Use `None` as default for mutable types (lists, dicts).

---

### 🎓 TIP: Dictionary Operations

**What we're doing:**
Building and accessing dictionaries dynamically.

**Basic operations:**
```python
# Create empty dict
data = {}

# Add items
data['key'] = 'value'
data['name'] = 'Alice'

# Access items
name = data['name']              # Direct access (fails if missing)
age = data.get('age')            # Safe access (returns None if missing)
age = data.get('age', 0)         # With default value

# Check if key exists
if 'name' in data:
    print(data['name'])

# Get from nested dict
config = context.get('settings', {})  # Returns {} if 'settings' missing
```

**Copy-ready examples:**
```python
# Example 1: Building a dictionary dynamically
user_info = {}
user_info['username'] = 'alice'
user_info['email'] = 'alice@example.com'
user_info['age'] = 30

# Example 2: Safe dictionary access
def get_user_name(user_dict):
    # Method 1: Using get() with default
    return user_dict.get('name', 'Anonymous')
    
    # Method 2: Check before accessing
    if 'name' in user_dict:
        return user_dict['name']
    return 'Anonymous'

# Example 3: Conditional dictionary building (like our code)
config = {}
config['required_field'] = 'value'

if some_condition:
    config['optional_field'] = 'optional_value'

# Only add if attribute exists
if hasattr(object, 'property'):
    config['property'] = object.property
```

**Booklet summary:**
Use `.get(key, default)` for safe access. Build dicts dynamically with `dict[key] = value`. Check existence with `if key in dict:` or `hasattr()` for object attributes. Empty dict `{}` is a safe default.

---

### Lines 161-175: Format Identifiers for Grep

```python
def format_identifiers_for_grep(identifiers):
    """Create grep pattern from identifiers"""
    patterns = []
    
    if identifiers.get('task_id'):
        patterns.append(identifiers['task_id'])
    if identifiers.get('run_id'):
        patterns.append(identifiers['run_id'])
    if identifiers.get('job_id'):
        patterns.append(str(identifiers['job_id']))
    if identifiers.get('external_executor_id'):
        patterns.append(identifiers['external_executor_id'])
    
    return '|'.join(patterns) if patterns else identifiers.get('task_id', 'taskinstance')
```

**Purpose:**
Creates a search pattern for finding task-related log entries.

**Line 161**: `def format_identifiers_for_grep(identifiers):`
- Takes the identifiers dictionary from previous function
- Will create a grep search pattern

**Line 163**: `patterns = []`
- Empty list to collect search terms
- We'll add relevant identifiers to this

**Lines 165-173**: Conditional pattern building
```python
if identifiers.get('task_id'):
    patterns.append(identifiers['task_id'])
```
- **Pattern**: Check if identifier exists, then add to list
- `.get('task_id')` returns None if missing, which is "falsy"
- `.append()` adds item to end of list
- We do this for: task_id, run_id, job_id, external_executor_id

**Line 170**: `patterns.append(str(identifiers['job_id']))`
- `str()` converts job_id to string (it might be a number)
- Grep needs text to search for

**Line 174**: `return '|'.join(patterns) if patterns else identifiers.get('task_id', 'taskinstance')`
- **Complex line** - let's break it down:
  - `'|'.join(patterns)` → Join list items with `|` (pipe symbol)
  - In grep, `|` means "OR"
  - Example: `['task1', 'run1']` → `'task1|run1'` → searches for "task1 OR run1"
  - `if patterns` → Only if patterns list has items
  - `else identifiers.get('task_id', 'taskinstance')` → Fallback if no patterns
  - Final fallback: the string `'taskinstance'`

**Example result:**
```python
identifiers = {'task_id': 'check_db', 'run_id': 'manual_2024', 'job_id': 12345}
result = format_identifiers_for_grep(identifiers)
# result = "check_db|manual_2024|12345"
# This searches logs for any of these three patterns
```

---

### 🎓 TIP: String Join Method

**What is `.join()`?**
Combines a list of strings into one string with a separator.

**Syntax:**
```python
separator.join(list_of_strings)
```

**Common use cases:**
1. Creating CSV data
2. Building file paths
3. Formatting output
4. Creating search patterns

**Copy-ready examples:**
```python
# Example 1: Basic join
words = ['Hello', 'World', 'Python']
sentence = ' '.join(words)  # "Hello World Python"
csv = ','.join(words)       # "Hello,World,Python"

# Example 2: Join with different separators
items = ['apple', 'banana', 'orange']
comma_list = ', '.join(items)      # "apple, banana, orange"
pipe_list = '|'.join(items)        # "apple|banana|orange"
path = '/'.join(['home', 'user'])  # "home/user"

# Example 3: Building grep patterns (like our code)
search_terms = ['error', 'warning', 'critical']
grep_pattern = '|'.join(search_terms)  # "error|warning|critical"
# Use in command: grep "error|warning|critical" logfile

# Example 4: Join with newlines
lines = ['Line 1', 'Line 2', 'Line 3']
text = '\n'.join(lines)
# Result:
# Line 1
# Line 2
# Line 3

# Example 5: Safe join (convert to strings first)
numbers = [1, 2, 3, 4, 5]
result = ','.join(str(n) for n in numbers)  # "1,2,3,4,5"
```

**Booklet summary:**
`.join()` combines list items into a string. Format: `separator.join(list)`. Use `' '` for spaces, `','` for CSV, `'|'` for OR patterns, `'\n'` for newlines. All items must be strings (use `str()` if needed).

---

## Key Takeaways

✅ **Try/except** prevents crashes - always have a fallback plan

✅ **Default parameters** make functions flexible - `def func(param=default)`

✅ **Safe dictionary access** - use `.get(key, default)` instead of `dict[key]`

✅ **hasattr()** checks if object has an attribute before accessing it

✅ **`.join()`** combines list items into a string with separator

✅ **Conditional expressions** - `value_if_true if condition else value_if_false`

---

## What's Next?

In Lesson 03, we'll learn about:
- SSH commands with subprocess
- Log fetching from remote servers
- More complex error handling
- Working with journalctl logs

**Ready to continue?** 🚀
