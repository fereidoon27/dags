# Lesson 02 Cheatsheet: Error Handling & Dictionary Operations

## Try/Except Error Handling
```python
# Basic syntax
try:
    risky_code()
except:
    fallback_code()

# Specific exceptions
try:
    int('abc')
except ValueError:
    print("Not a number!")

# Multiple fallbacks
try:
    return method1()
except:
    return method2()

# Capture error
try:
    operation()
except Exception as e:
    print(f"Error: {e}")
```

## Function Parameters
```python
# No parameters
def greet():
    return "Hello"

# Required parameter
def greet(name):
    return f"Hello {name}"

# Default parameter
def greet(name, greeting="Hello"):
    return f"{greeting} {name}"

# Multiple defaults
def connect(host, port=5432, timeout=10):
    pass

# None as default
def process(data, config=None):
    if config is None:
        config = {}
```

## Dictionary Operations
```python
# Create and add
data = {}
data['key'] = 'value'

# Safe access
value = data.get('key')              # Returns None if missing
value = data.get('key', 'default')   # Returns 'default' if missing

# Check existence
if 'key' in data:
    print(data['key'])

# Get from object attribute
if hasattr(obj, 'attr'):
    value = obj.attr
```

## Conditional Expressions
```python
# Format: value_if_true if condition else value_if_false
result = x if x > 0 else 0
name = user.name if user else "Guest"
value = obj.attr if hasattr(obj, 'attr') else None
```

## String Join
```python
# Basic join
words = ['a', 'b', 'c']
result = ','.join(words)      # "a,b,c"
result = ' '.join(words)      # "a b c"
result = '|'.join(words)      # "a|b|c"

# Convert numbers first
nums = [1, 2, 3]
result = ','.join(str(n) for n in nums)  # "1,2,3"
```

## List Operations
```python
# Create empty list
items = []

# Add items
items.append('value')         # Add to end
items.extend(['a', 'b'])      # Add multiple

# Check if empty
if items:                     # True if has items
    print("Has items")
if not items:                 # True if empty
    print("Empty")
```

## Common Patterns
```python
# Pattern 1: Optional parameter with auto-fetch
def get_info(context=None):
    if context is None:
        context = fetch_context()
    return context

# Pattern 2: Safe attribute access
data = {}
if hasattr(obj, 'name'):
    data['name'] = obj.name

# Pattern 3: Build search pattern
patterns = []
if value1:
    patterns.append(value1)
if value2:
    patterns.append(value2)
result = '|'.join(patterns) if patterns else 'default'

# Pattern 4: Convert to string safely
str_value = str(value)  # Works for numbers, objects, etc.
```

## Quick Reference

| Operation | Syntax | Example |
|-----------|--------|---------|
| Try/except | `try: ... except: ...` | Error handling |
| Default param | `def f(x=default):` | Optional values |
| Safe dict get | `d.get(k, default)` | Avoid KeyError |
| Has attribute | `hasattr(obj, 'attr')` | Check before access |
| Ternary op | `x if cond else y` | Inline condition |
| Join list | `sep.join(list)` | Combine strings |
| Check empty | `if list:` | True if has items |

## Troubleshooting
```python
# KeyError → Use .get()
data['missing']           # ❌ Raises KeyError
data.get('missing')       # ✅ Returns None

# AttributeError → Use hasattr()
obj.missing_attr          # ❌ Raises AttributeError
if hasattr(obj, 'attr'):  # ✅ Check first
    val = obj.attr

# Type in join → Convert to str
'|'.join([1, 2, 3])       # ❌ TypeError
'|'.join(str(n) for n in [1,2,3])  # ✅ Works
```
