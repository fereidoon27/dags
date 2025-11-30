# Lesson 01 Cheatsheet: Python Imports & Dictionaries

## Import Syntax
```python
import module_name              # Import entire module
from module import function     # Import specific function
from module import *            # Import everything (avoid this!)
```

## Common Modules Used
```python
# Date/Time
from datetime import datetime, timedelta

# System & OS
import os          # Files, paths, environment
import platform    # System info
import subprocess  # Run shell commands
import socket      # Network operations

# Data Formats
import json        # JSON handling
import re          # Regular expressions

# Files
import glob        # File pattern matching
```

## Dictionary Basics
```python
# Create dictionary
config = {
    'key1': 'value1',
    'key2': ['list', 'of', 'items'],
    'key3': {'nested': 'dict'}
}

# Access values
ip = config['key1']              # Get value
services = config.get('key2')    # Safe get (returns None if missing)

# Nested dictionaries
SERVERS = {
    'server1': {
        'ip': '10.0.0.1',
        'services': ['web', 'db']
    }
}
# Access: SERVERS['server1']['ip']
```

## String Formatting
```python
# F-strings (Python 3.6+)
name = "Alice"
age = 30
msg = f"Hello {name}, you are {age} years old"

# Build paths
base = "/home/user"
full_path = f"{base}/documents/file.txt"
```

## Naming Conventions
```python
CONSTANT_VALUE = "never changes"     # UPPERCASE
variable_name = "can change"          # lowercase_with_underscores
MyClass = "class name"                # PascalCase
```

## Quick Reference

| Concept | Syntax | Example |
|---------|--------|---------|
| Import module | `import x` | `import os` |
| Import from | `from x import y` | `from os import path` |
| Dictionary | `{key: value}` | `{'name': 'server1'}` |
| List | `[item1, item2]` | `['web', 'db']` |
| F-string | `f"{var}"` | `f"Hello {name}"` |

## Common Patterns in This Code
```python
# Configuration dictionary
SERVERS = {
    'hostname': {
        'ip': '10.0.0.1',
        'services': ['service1', 'service2']
    }
}

# Simple mapping
ALL_NODES = {
    'server1': '10.0.0.1',
    'server2': '10.0.0.2'
}

# Path building
BASE = '/home/user'
LOGS = f'{BASE}/logs'  # Result: /home/user/logs
```
