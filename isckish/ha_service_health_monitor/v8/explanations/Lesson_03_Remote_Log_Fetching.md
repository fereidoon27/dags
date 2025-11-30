# Lesson 03: Remote Log Fetching with SSH & Subprocess

## Plain-English Overview

This function fetches system service logs from servers - either locally (if we're on that server) or remotely (using SSH). It's like having a remote control that can grab log files from any server in your infrastructure.

**Real-world analogy:**
Imagine you manage multiple warehouse security cameras. This function is like asking "show me the last 100 events from Camera #5" - whether that camera is in your current building or across town.

---

## Structure Overview

**Function:** `fetch_service_logs()`

**What it does:**
1. Determines if target server is local or remote
2. Builds appropriate command (local or SSH)
3. Executes command using subprocess
4. Handles output and errors
5. Returns logs or error message

**Key concepts:**
- Type hints (`: str`, `-> str`)
- subprocess module (running shell commands)
- SSH (remote server access)
- journalctl (Linux log viewing)
- String operations

---

## Line-by-Line Walkthrough

### Line 177: Function Signature with Type Hints

```python
def fetch_service_logs(ip: str, service: str, hostname: str, lines: int = 100) -> str:
```

**Breaking it down:**

**`ip: str`**
- Parameter `ip` expects a string
- The `: str` is a **type hint** (tells other developers what type to pass)
- Example: `'10.101.20.202'`

**`service: str`**
- Service name to check (e.g., `'airflow-scheduler'`)

**`hostname: str`**
- Server name (e.g., `'haproxy-1'`)

**`lines: int = 100`**
- How many log lines to fetch
- Default value = 100 (optional parameter)
- The `: int` indicates it should be an integer

**`-> str:`**
- **Return type hint**
- The `->` means "returns"
- This function returns a string (the logs)

**Why type hints?**
- Helps IDEs give you better autocomplete
- Makes code self-documenting
- Helps catch bugs early
- NOT enforced by Python (just helpful hints)

---

### 🎓 TIP: Type Hints in Python

**What are type hints?**
Optional annotations that document what types your function expects and returns.

**Basic syntax:**
```python
def function_name(param: type) -> return_type:
    pass
```

**Common types:**
- `str` - String
- `int` - Integer
- `float` - Decimal number
- `bool` - True/False
- `list` - List
- `dict` - Dictionary
- `None` - No return value

**Common use cases:**
1. Documenting function interfaces
2. Helping IDEs with autocomplete
3. Using with type checkers (mypy)
4. Making code more readable

**Copy-ready examples:**
```python
# Example 1: Basic type hints
def greet(name: str, age: int) -> str:
    return f"Hello {name}, you are {age} years old"

# Example 2: Optional parameters with type hints
def connect(host: str, port: int = 5432, timeout: int = 10) -> bool:
    # connection logic
    return True

# Example 3: Multiple types (using Union)
from typing import Union

def process_id(id_value: Union[str, int]) -> str:
    return str(id_value)

# Example 4: List and Dict types
from typing import List, Dict

def get_users() -> List[str]:
    return ['alice', 'bob', 'charlie']

def get_config() -> Dict[str, str]:
    return {'host': 'localhost', 'port': '5432'}

# Example 5: Optional return (might be None)
from typing import Optional

def find_user(user_id: int) -> Optional[str]:
    # Might return a name or None
    if user_id == 1:
        return "Alice"
    return None

# Example 6: No return value
def log_message(msg: str) -> None:
    print(msg)
    # No return statement
```

**Booklet summary:**
Type hints document expected types: `param: type` for parameters, `-> type` for return values. Common types: `str`, `int`, `bool`, `list`, `dict`. Use `Optional[type]` when might return None. Type hints are optional and not enforced at runtime.

---

### Lines 178-180: Initial Setup

```python
"""Fetch service logs from journalctl"""
current_host = get_current_hostname()
is_local_check = (current_host == hostname)
```

**Line 178**: Docstring explaining function purpose

**Line 179**: `current_host = get_current_hostname()`
- Calls our helper function from Lesson 02
- Gets name of the server we're currently running on
- Stores it in `current_host` variable

**Line 180**: `is_local_check = (current_host == hostname)`
- Compares current server with target server
- `==` checks if they're equal
- Result is `True` or `False`
- Example: If we're on 'haproxy-1' and checking 'haproxy-1' → `True` (local)
- Example: If we're on 'haproxy-1' and checking 'celery-1' → `False` (remote)

**Why check if local?**
- Local commands are faster (no SSH overhead)
- Different command syntax for local vs remote
- More reliable (no network issues)

---

### Lines 182-186: Building the Command

```python
try:
    if is_local_check:
        cmd = f"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso"
    else:
        cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso\""
```

**Line 182**: Start try block

**Line 183-184: Local command**
```python
if is_local_check:
    cmd = f"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso"
```

**Breaking down the command:**
- `sudo` - Run with admin privileges
- `journalctl` - Linux log viewing tool
- `-u {service}` - Filter by service unit (e.g., `-u airflow-scheduler`)
- `--no-pager` - Don't use interactive pager (output all at once)
- `-n {lines}` - Show last N lines (e.g., `-n 100`)
- `-o short-iso` - Output format with ISO timestamps

**Example result:**
```bash
sudo journalctl -u airflow-scheduler --no-pager -n 100 -o short-iso
```

**Line 185-186: Remote command (SSH)**
```python
else:
    cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@{ip} \"sudo journalctl -u {service} --no-pager -n {lines} -o short-iso\""
```

**SSH command structure:**
- `ssh` - Secure shell (remote connection)
- `-o ConnectTimeout=5` - Wait max 5 seconds to connect
- `-o StrictHostKeyChecking=no` - Don't ask about unknown hosts (automation-friendly)
- `rocky@{ip}` - Connect as user 'rocky' to IP address
- `\"...\"` - The command to run on remote server (escaped quotes)

**Example result:**
```bash
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no rocky@10.101.20.202 "sudo journalctl -u airflow-scheduler --no-pager -n 100 -o short-iso"
```

**Why the escaping `\"`?**
- The outer f-string uses double quotes
- The SSH command also needs quotes
- `\"` escapes the inner quotes so they're literal characters
- Without escaping, Python would end the string early

---

### 🎓 TIP: The subprocess Module

**What is subprocess?**
A Python module that lets you run shell commands and capture their output.

**Why use it?**
- Execute system commands from Python
- Run external programs
- Capture command output
- Handle errors from commands

**Basic usage:**
```python
import subprocess

result = subprocess.run(
    'ls -l',           # Command to run
    shell=True,        # Use shell to interpret
    capture_output=True,  # Capture stdout/stderr
    text=True          # Return strings (not bytes)
)

print(result.stdout)   # Command output
print(result.stderr)   # Error messages
print(result.returncode)  # Exit code (0 = success)
```

**Common use cases:**
1. Running system commands
2. Executing scripts
3. File operations
4. Network diagnostics
5. System administration tasks

**Copy-ready examples:**
```python
# Example 1: Simple command
import subprocess

result = subprocess.run(['ls', '-l'], capture_output=True, text=True)
if result.returncode == 0:
    print(result.stdout)

# Example 2: With shell (allows pipes, wildcards)
result = subprocess.run(
    'ps aux | grep python',
    shell=True,
    capture_output=True,
    text=True
)

# Example 3: With timeout
try:
    result = subprocess.run(
        'long_running_command',
        shell=True,
        timeout=10  # Kill if takes > 10 seconds
    )
except subprocess.TimeoutExpired:
    print("Command timed out!")

# Example 4: Check for errors
result = subprocess.run(
    'some_command',
    shell=True,
    capture_output=True,
    text=True
)
if result.returncode != 0:
    print(f"Error: {result.stderr}")

# Example 5: SSH command (like our code)
cmd = f'ssh user@{ip} "ls -l /home"'
result = subprocess.run(
    cmd,
    shell=True,
    capture_output=True,
    text=True,
    timeout=30
)
```

**Key parameters:**
- `shell=True` - Use system shell (needed for pipes, variables)
- `capture_output=True` - Save stdout and stderr
- `text=True` - Return strings instead of bytes
- `timeout=N` - Kill command after N seconds
- `check=True` - Raise exception if command fails

**Booklet summary:**
`subprocess.run()` executes shell commands from Python. Use `shell=True` for complex commands, `capture_output=True` to get output, `text=True` for strings. Check `returncode` (0=success) and use `timeout` to prevent hanging. Access output via `result.stdout` and errors via `result.stderr`.

---

### 🎓 TIP: SSH (Secure Shell)

**What is SSH?**
Secure Shell - a protocol for securely connecting to remote servers and executing commands.

**Basic SSH syntax:**
```bash
ssh username@hostname "command to run"
```

**Common SSH options:**
- `-o ConnectTimeout=N` - Connection timeout in seconds
- `-o StrictHostKeyChecking=no` - Skip host key verification (automation)
- `-i key_file` - Use specific private key
- `-p PORT` - Connect to non-standard port

**Common use cases:**
1. Remote server administration
2. Running commands on multiple servers
3. File transfers (with scp/sftp)
4. Automated monitoring
5. Deployment scripts

**Copy-ready examples:**
```python
# Example 1: Basic SSH command
import subprocess

cmd = 'ssh user@server.com "hostname"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(result.stdout)  # Remote server's hostname

# Example 2: SSH with timeout
cmd = 'ssh -o ConnectTimeout=5 user@10.0.0.1 "uptime"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

# Example 3: Multiple commands
cmd = 'ssh user@server "cd /var/log && tail -n 50 syslog"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

# Example 4: SSH in Python function (like our code)
def run_remote_command(ip: str, command: str) -> str:
    ssh_cmd = f'ssh -o ConnectTimeout=5 rocky@{ip} "{command}"'
    result = subprocess.run(
        ssh_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=15
    )
    if result.returncode == 0:
        return result.stdout
    return f"Error: {result.stderr}"

# Example 5: Check if server is reachable
def check_server(ip: str) -> bool:
    cmd = f'ssh -o ConnectTimeout=3 rocky@{ip} "echo ok"'
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
    return result.returncode == 0
```

**Security notes:**
- Use key-based authentication (not passwords)
- `StrictHostKeyChecking=no` is convenient but less secure
- Only disable in trusted networks
- Set appropriate timeouts

**Booklet summary:**
SSH connects to remote servers: `ssh user@host "command"`. Use `-o ConnectTimeout=N` for timeout, `-o StrictHostKeyChecking=no` for automation. In Python, wrap in `subprocess.run()` with `shell=True`. Always set timeouts to prevent hanging.

---

### Line 188: Progress Message

```python
print(f"🔍 Fetching last {lines} lines of journalctl for {service} on {hostname}...")
```

**What it does:**
- Prints status message to console
- Uses emoji for visual clarity (🔍 = search/investigation)
- Shows exactly what we're doing and where

**Why print status messages?**
- User knows what's happening
- Helpful for debugging
- Shows progress in long-running operations
- Appears in Airflow task logs

---

### Lines 190-196: Execute the Command

```python
result = subprocess.run(
    cmd,
    shell=True,
    capture_output=True,
    text=True,
    timeout=15
)
```

**Line 190**: `result = subprocess.run(`
- Execute the command we built
- Returns a `CompletedProcess` object

**Line 191**: `cmd,`
- The command to run (either local or SSH)

**Line 192**: `shell=True,`
- Use system shell to interpret command
- Needed for pipes, variables, etc.
- Allows complex commands

**Line 193**: `capture_output=True,`
- Capture both stdout (normal output) and stderr (error output)
- Equivalent to `stdout=PIPE, stderr=PIPE`

**Line 194**: `text=True,`
- Return strings instead of bytes
- Makes output easier to work with
- Also called `universal_newlines=True` in older Python

**Line 195**: `timeout=15`
- Kill command if it takes longer than 15 seconds
- Prevents hanging indefinitely
- Raises `subprocess.TimeoutExpired` if timeout occurs

**Result object has:**
- `result.returncode` - Exit code (0 = success)
- `result.stdout` - Normal output
- `result.stderr` - Error output

---

### Lines 198-204: Handle the Result

```python
if result.returncode == 0 and result.stdout.strip():
    output = result.stdout
    if '[Invalid date]' in output:
        output = output.replace('[Invalid date]', '')
    return output
else:
    return f"⚠️ Could not fetch journalctl logs (returncode: {result.returncode})\nStderr: {result.stderr}"
```

**Line 198**: `if result.returncode == 0 and result.stdout.strip():`
- **Two conditions** (both must be true):
  1. `result.returncode == 0` → Command succeeded
  2. `result.stdout.strip()` → Output is not empty
- `.strip()` removes whitespace; empty string = False

**Line 199**: `output = result.stdout`
- Store the output in a variable

**Lines 200-201**: Clean up output
```python
if '[Invalid date]' in output:
    output = output.replace('[Invalid date]', '')
```
- Check if string contains `'[Invalid date]'`
- Remove it if present (journalctl sometimes adds this for corrupted timestamps)
- `.replace(old, new)` replaces all occurrences

**Line 202**: `return output`
- Return cleaned log output

**Lines 203-204**: Error handling
```python
else:
    return f"⚠️ Could not fetch journalctl logs (returncode: {result.returncode})\nStderr: {result.stderr}"
```
- If command failed or no output
- Return descriptive error message
- Includes return code and error details
- `\n` adds newline between lines

---

### Lines 206-209: Exception Handling

```python
except subprocess.TimeoutExpired:
    return "⚠️ Timeout while fetching journalctl logs"
except Exception as e:
    return f"⚠️ Error fetching journalctl logs: {str(e)}"
```

**Line 206-207: Timeout handling**
- Catches `subprocess.TimeoutExpired` specifically
- Happens when command takes > 15 seconds
- Returns clear timeout message

**Line 208-209: General error handling**
- Catches any other exception
- `Exception as e` captures the error
- Returns error message with details

**Why two except blocks?**
- Different handling for different errors
- Timeout is expected (network issues)
- Other exceptions might be bugs

---

## 🎓 TIP: String Methods

**Common string operations used in this function:**

**`.strip()` - Remove whitespace**
```python
text = "  hello  "
text.strip()  # "hello"
```

**`.replace(old, new)` - Replace substrings**
```python
text = "Hello World"
text.replace("World", "Python")  # "Hello Python"
```

**`in` operator - Check if substring exists**
```python
if "error" in log_message:
    print("Found error!")
```

**Copy-ready examples:**
```python
# Example 1: Cleaning input
user_input = "  john@example.com  \n"
clean = user_input.strip()  # "john@example.com"

# Example 2: Multiple replacements
text = "Error: something failed. Error occurred."
text = text.replace("Error", "Warning")

# Example 3: Check and replace pattern
def clean_output(output: str) -> str:
    if '[Invalid' in output:
        output = output.replace('[Invalid date]', '')
    if 'WARNING' in output:
        output = output.replace('WARNING', 'INFO')
    return output

# Example 4: Substring checking
log = "2024-01-15 ERROR: Database connection failed"
if "ERROR" in log:
    print("Error found!")
if "Database" in log:
    print("Database issue detected")
```

**Booklet summary:**
String methods: `.strip()` removes whitespace, `.replace(old, new)` substitutes text, `'x' in string` checks presence. All return new strings (strings are immutable). Chain methods: `text.strip().lower().replace('a', 'b')`.

---

## Key Takeaways

✅ **Type hints** document expected types: `param: type` and `-> return_type`

✅ **subprocess.run()** executes shell commands from Python

✅ **SSH** enables remote command execution: `ssh user@host "command"`

✅ **journalctl** is Linux's log viewing tool

✅ **Local vs remote** - different approaches for better efficiency

✅ **Timeouts** prevent hanging - always set them for network operations

✅ **Return codes** - 0 means success, non-zero means failure

✅ **String cleaning** - .strip(), .replace(), and 'in' operator

---

## What's Next?

In Lesson 04, we'll continue with:
- `fetch_task_specific_logs()` - Complex log searching
- Working with multiple servers
- Set operations for deduplication
- More advanced string patterns

**Ready to continue?** 🚀
