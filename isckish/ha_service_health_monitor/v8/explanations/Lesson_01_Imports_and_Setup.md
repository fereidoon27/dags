# Lesson 01: Understanding Imports and Basic Setup

## Plain-English Overview

This code monitors the health of a complex Airflow High Availability (HA) system. Think of it like a hospital monitoring system that checks if all vital organs (servers, databases, message queues) are working properly.

The first part imports necessary tools and sets up configuration for all the servers it needs to monitor.

---

## Structure Overview

**What we're learning:**
- Python imports (bringing in tools we need)
- Configuration dictionaries (organizing server information)
- Module docstring (describing what the code does)

**Key Components:**
1. **Imports**: Loading 11 different Python modules
2. **Server Configuration**: 3 dictionaries defining servers to monitor
3. **Path Configuration**: Where to find log files

---

## Line-by-Line Walkthrough

### Lines 1-7: Module Documentation
```python
"""
Airflow HA Infrastructure Health Monitor - Enhanced V8
CHANGES IN V8:
- Added comprehensive log collection (service logs + task-specific logs + worker logs)
- Added VM Resource Inventory Report task
- Fixed top 5 process display in system resources
"""
```

**What this means:**
- Triple quotes (`"""`) create a **docstring** - documentation for the whole file
- Explains this is version 8 of a health monitoring system
- Lists recent changes (like a version changelog)
- Good practice: Always document what your code does!

---

### Lines 8-21: Importing Required Modules

```python
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from airflow.operators.python import get_current_context
import psycopg2
import pika
import subprocess
import socket
import platform
import os
import glob
import json
import re
from collections import OrderedDict
```

**Understanding imports:**
- `from X import Y` → Get specific tool Y from package X
- `import X` → Get entire package X

Let me explain each import:

**Line 8**: `from datetime import datetime, timedelta`
- Gets date/time tools for scheduling and timestamps

**Line 9**: `from airflow.decorators import dag, task`
- Gets special Airflow decorators (we'll learn about these later!)
- These turn regular Python functions into Airflow tasks

**Line 10**: `from airflow.exceptions import AirflowException`
- Gets Airflow's error-raising tool
- Used when something goes wrong and we need to report it

**Line 11**: `from airflow.operators.python import get_current_context`
- Gets function to access current task's information
- Like asking "What task am I running right now?"

**Line 12**: `import psycopg2`
- PostgreSQL database connector
- Used to check database health

**Line 13**: `import pika`
- RabbitMQ (message queue) connector
- Used to check if message system is working

**Line 14**: `import subprocess`
- Runs shell commands from Python
- Used to execute SSH commands and system checks

**Line 15**: `import socket`
- Network communication tool
- Used to check server connectivity

**Line 16**: `import platform`
- Gets system information (OS, hostname, etc.)
- Used to identify which server we're running on

**Line 17**: `import os`
- Operating system interface
- Used for file paths, process IDs, environment variables

**Line 18**: `import glob`
- File pattern matching
- Used to find log files

**Line 19**: `import json`
- JSON data format handler
- Used for structured data exchange

**Line 20**: `import re`
- Regular expressions (pattern matching in text)
- Used to search logs

**Line 21**: `from collections import OrderedDict`
- Dictionary that remembers insertion order
- Used for organized data structures

---

### Lines 24-74: Server Configuration Dictionary

```python
SERVERS = {
    'haproxy-1': {
        'ip': '10.101.20.202',
        'services': ['airflow-scheduler', 'airflow-webserver', 'haproxy', 'keepalived']
    },
    'haproxy-2': {
        'ip': '10.101.20.146',
        'services': ['airflow-webserver', 'haproxy', 'keepalived']
    },
    # ... more servers ...
}
```

**What this is:**
- A **dictionary** (key-value pairs) storing all servers to monitor
- Written in UPPERCASE = Python convention for **constants** (values that don't change)

**Structure:**
```
SERVERS = {
    'server_name': {                    ← Server nickname
        'ip': 'IP_ADDRESS',             ← How to reach it
        'services': ['service1', ...]   ← What to check on it
    }
}
```

**Example breakdown:**
- `'haproxy-1'` → Server name (the key)
- `'ip': '10.101.20.202'` → Server's network address
- `'services': [...]` → List of services running on this server

---

### Lines 76-86: NFS Configuration

```python
NFS_NODES = {
    'nfs-1': {
        'ip': '10.101.20.165',
        'services': ['airflow-dag-processor', 'nfs-server', 'lsyncd', 'keepalived']
    },
    'nfs-2': {
        'ip': '10.101.20.203',
        'services': ['airflow-dag-processor', 'nfs-server', 'lsyncd', 'keepalived']
    },
}
```

**Why separate from SERVERS?**
- NFS nodes need special handling (they share files)
- Kept separate for clarity and different monitoring logic

---

### Lines 88-106: All Nodes Mapping

```python
ALL_NODES = {
    'haproxy-1': '10.101.20.202',
    'haproxy-2': '10.101.20.146',
    'scheduler-2': '10.101.20.132',
    # ... all servers ...
}
```

**Purpose:**
- Simpler dictionary: just hostname → IP mapping
- Used for system resource checks (CPU, memory, disk)
- Notice: no 'services' list here, just IPs

---

### Lines 108-116: Airflow-Specific Configuration

```python
AIRFLOW_NODES_WITH_LOGS = [
    'haproxy-1', 'haproxy-2', 'scheduler-2',
    'nfs-1', 'nfs-2', 'celery-1', 'celery-2'
]

AIRFLOW_HOME = '/home/rocky/airflow'
AIRFLOW_LOGS_BASE = f'{AIRFLOW_HOME}/logs'
```

**Line 109-112**: `AIRFLOW_NODES_WITH_LOGS`
- A **list** of servers that have Airflow log files
- Not all servers run Airflow, so not all have these logs

**Line 114**: `AIRFLOW_HOME = '/home/rocky/airflow'`
- Base directory where Airflow is installed
- Fixed path on all Airflow nodes

**Line 115**: `AIRFLOW_LOGS_BASE = f'{AIRFLOW_HOME}/logs'`
- Uses **f-string** (formatted string) to build path
- Result: `/home/rocky/airflow/logs`
- The `f` before the quote lets us use `{variable}` inside

---

## Key Takeaways

✅ **Imports bring tools into your code** - like getting supplies before starting work

✅ **Dictionaries organize related data** - perfect for server configurations

✅ **UPPERCASE names = constants** - values that shouldn't change

✅ **Separation of concerns** - different dictionaries for different purposes (SERVERS, NFS_NODES, ALL_NODES)

✅ **F-strings make string building easy** - `f'{variable}/path'`

---

## What's Next?

In the next lesson, we'll learn about:
- Helper functions (`get_current_hostname()`, `get_task_identifiers()`)
- How to interact with the system
- Error handling basics

**Ready to continue? Let me know!**
