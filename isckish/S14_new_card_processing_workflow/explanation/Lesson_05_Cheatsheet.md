# Lesson 05 Cheatsheet: SFTP File Transfers

## Basic SFTP Pattern
```python
# Open SFTP session
sftp = ssh.open_sftp()

# Read remote file
with sftp.file('/remote/path/file.txt', 'r') as f:
    content = f.read()

# Write remote file
with sftp.file('/remote/path/file.txt', 'w') as f:
    f.write(content)

# Always close
sftp.close()
```

## Server-to-Server Transfer
```python
@task
def transfer_files(file_list: List[str]) -> List[str]:
    ssh_source = None
    ssh_target = None
    transferred = []
    
    try:
        # Connect to both servers
        ssh_source = create_ssh_client(source_host)
        ssh_target = create_ssh_client(target_host)
        
        for file_path in file_list:
            # Read from source
            sftp_src = ssh_source.open_sftp()
            with sftp_src.file(file_path, 'r') as f:
                content = f.read()
            sftp_src.close()
            
            # Write to target
            sftp_tgt = ssh_target.open_sftp()
            with sftp_tgt.file(file_path, 'w') as f:
                f.write(content)
            sftp_tgt.close()
            
            transferred.append(file_path)
        
        return transferred
    finally:
        if ssh_source: ssh_source.close()
        if ssh_target: ssh_target.close()
```

## Common SFTP Operations
```python
sftp = ssh.open_sftp()

# Read file
with sftp.file('/path/file.txt', 'r') as f:
    content = f.read()

# Write file
with sftp.file('/path/file.txt', 'w') as f:
    f.write(b'content')

# Append to file
with sftp.file('/path/file.txt', 'a') as f:
    f.write(b'more content')

# List directory
files = sftp.listdir('/path/')

# Get file info
info = sftp.stat('/path/file.txt')
size = info.st_size

# Check if file exists
try:
    sftp.stat('/path/file.txt')
    exists = True
except FileNotFoundError:
    exists = False

# Delete file
sftp.remove('/path/file.txt')

# Rename/move file
sftp.rename('/old/path.txt', '/new/path.txt')

# Create directory
sftp.mkdir('/new/dir')

sftp.close()
```

## Path Manipulation
```python
from pathlib import Path

file_path = '/home/rocky/card/in/card_batch_001.txt'

# Extract parts
filename = Path(file_path).name      # 'card_batch_001.txt'
parent = Path(file_path).parent      # '/home/rocky/card/in'
stem = Path(file_path).stem          # 'card_batch_001'
suffix = Path(file_path).suffix      # '.txt'

# Build paths
new_path = Path('/home/rocky') / 'card' / 'out' / 'result.txt'
# Result: '/home/rocky/card/out/result.txt'
```

## Input Validation Pattern
```python
@task
def process_files(file_list: List[str]) -> List[str]:
    # Validate input
    if not file_list or file_list is None:
        raise AirflowException("No files to process")
    
    # Process files
    results = []
    for file_path in file_list:
        # Do work
        results.append(file_path)
    
    return results
```

## Progress Tracking
```python
transferred = []

for file_path in file_list:
    filename = Path(file_path).name
    print(f"📤 Processing: {filename}")
    
    # Do transfer
    transfer_file(file_path)
    
    transferred.append(file_path)
    print(f"✓ Done: {filename}")

print(f"✓ All {len(transferred)} files processed")
return transferred
```

## SFTP vs SCP Quick Comparison

| Feature | SFTP | SCP |
|---------|------|-----|
| List files | ✓ | ✗ |
| Check existence | ✓ | ✗ |
| Resume transfers | ✓ | ✗ |
| Simple copy | ✓ | ✓ |
| Performance | Good | Better |
| Complexity | Higher | Lower |

## Error Handling
```python
try:
    sftp = ssh.open_sftp()
    with sftp.file('/path/file.txt', 'r') as f:
        content = f.read()
    sftp.close()
except FileNotFoundError:
    print("File not found")
except PermissionError:
    print("Permission denied")
except Exception as e:
    raise AirflowException(f"Transfer failed: {e}")
```

## Quick Reference
- **open_sftp()** - Create SFTP session from SSH
- **file(path, 'r')** - Read remote file
- **file(path, 'w')** - Write remote file (overwrite)
- **file(path, 'a')** - Append to remote file
- **Path().name** - Extract filename from path
- **with statement** - Auto-closes file handles
- **Always close** - SFTP sessions and SSH connections
