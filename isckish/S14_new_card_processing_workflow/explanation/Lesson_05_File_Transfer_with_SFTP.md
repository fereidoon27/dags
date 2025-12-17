# Lesson 05: File Transfer with SFTP

## What You're Learning
How to transfer files between remote servers using SFTP (SSH File Transfer Protocol) through Paramiko.

---

## The transfer_card_files Task

```python
@task
def transfer_card_files(file_list: List[str]) -> List[str]:
    """Transfer files from ftp to target-1 via SSH/SCP"""
    
    # Validate input
    if not file_list or file_list is None:
        raise AirflowException("No files to transfer - received empty or None file list")
    
    ssh_source = None
    ssh_target = None
    transferred = []
    
    try:
        ssh_source = create_ssh_client(SSH_CONFIG['ftp_host'])
        ssh_target = create_ssh_client(SSH_CONFIG['target_host'])
        
        for file_path in file_list:
            filename = Path(file_path).name
            print(f"📤 Transferring: {filename}")
            
            # Read file from source
            sftp_source = ssh_source.open_sftp()
            with sftp_source.file(file_path, 'r') as remote_file:
                file_content = remote_file.read()
            sftp_source.close()
            
            # Write file to target (overwrite if exists)
            sftp_target = ssh_target.open_sftp()
            with sftp_target.file(file_path, 'w') as remote_file:
                remote_file.write(file_content)
            sftp_target.close()
            
            transferred.append(file_path)
            print(f"✓ Transferred: {filename} ({len(file_content)} bytes)")
        
        print(f"✓ All {len(transferred)} files transferred successfully")
        return transferred
        
    except Exception as e:
        raise AirflowException(f"File transfer failed: {str(e)}")
    finally:
        if ssh_source:
            ssh_source.close()
        if ssh_target:
            ssh_target.close()
```

---

## Input Validation

```python
if not file_list or file_list is None:
    raise AirflowException("No files to transfer - received empty or None file list")
```

**Why Two Conditions?**

**not file_list:** Catches empty list
- `[]` evaluates to `False`
- `not []` becomes `True`

**file_list is None:** Catches None explicitly
- Different from empty list
- Could happen if upstream task fails

**Example Scenarios:**
```python
file_list = []        # not file_list = True → Fails
file_list = None      # file_list is None = True → Fails
file_list = ['/path'] # Both False → Continues
```

**Why Fail Fast?**
Better to fail immediately with clear message than attempt transfer with no files.

---

## Managing Two SSH Connections

```python
ssh_source = None
ssh_target = None
transferred = []

try:
    ssh_source = create_ssh_client(SSH_CONFIG['ftp_host'])
    ssh_target = create_ssh_client(SSH_CONFIG['target_host'])
    # ... transfer logic ...
finally:
    if ssh_source:
        ssh_source.close()
    if ssh_target:
        ssh_target.close()
```

**Why Two Connections?**

**Source Server (FTP):** Where files currently are
- `10.101.20.164` - read files from here

**Target Server (Processing):** Where files need to go
- `10.101.20.201` - write files here

**transferred List:** Tracks successfully transferred files
- Starts empty
- Appends each successful transfer
- Returned to caller (stored in XCom)

**Cleanup Pattern:**
Both connections closed in `finally` block, even if transfer fails.

---

## Extracting Filename from Path

```python
filename = Path(file_path).name
```

**Using pathlib.Path:**

**Input:** `/home/rocky/card/in/card_batch_001.txt`
**Output:** `card_batch_001.txt`

**Why Path?**
Modern, cross-platform way to handle file paths.

**Alternative (old way):**
```python
import os
filename = os.path.basename(file_path)  # Same result
```

**Example:**
```python
from pathlib import Path

file_path = '/home/rocky/card/in/card_batch_001.txt'
filename = Path(file_path).name  # 'card_batch_001.txt'

# More Path features
Path(file_path).parent    # '/home/rocky/card/in'
Path(file_path).stem      # 'card_batch_001'
Path(file_path).suffix    # '.txt'
```

---

## Reading File from Source Server

```python
sftp_source = ssh_source.open_sftp()
with sftp_source.file(file_path, 'r') as remote_file:
    file_content = remote_file.read()
sftp_source.close()
```

**Step-by-Step:**

**1. Open SFTP Session:**
```python
sftp_source = ssh_source.open_sftp()
```
- Creates SFTP client from existing SSH connection
- SFTP = SSH File Transfer Protocol (secure file operations)

**2. Open Remote File:**
```python
with sftp_source.file(file_path, 'r') as remote_file:
```
- `file_path` - full path on remote server
- `'r'` - read mode
- `with` statement - auto-closes file

**3. Read File Content:**
```python
file_content = remote_file.read()
```
- Reads entire file into memory as bytes
- Example result: `b'card_data_here\n'`

**4. Close SFTP Session:**
```python
sftp_source.close()
```
- Releases SFTP resources
- SSH connection remains open

**Example:**
```python
# File on source: /home/rocky/card/in/card_batch_001.txt
# Content: "12345,John,Active\n67890,Jane,Active\n"
file_content = b'12345,John,Active\n67890,Jane,Active\n'
```

---

## Writing File to Target Server

```python
sftp_target = ssh_target.open_sftp()
with sftp_target.file(file_path, 'w') as remote_file:
    remote_file.write(file_content)
sftp_target.close()
```

**Step-by-Step:**

**1. Open SFTP Session:** (same as source)

**2. Open Remote File for Writing:**
```python
with sftp_target.file(file_path, 'w') as remote_file:
```
- `'w'` - write mode (overwrites if exists)
- Creates same path on target server
- Example: `/home/rocky/card/in/card_batch_001.txt`

**3. Write Content:**
```python
remote_file.write(file_content)
```
- Writes the bytes read from source
- Exact copy of source file

**4. Close SFTP Session**

**Important:** Same path on both servers
- Source: `/home/rocky/card/in/card_batch_001.txt`
- Target: `/home/rocky/card/in/card_batch_001.txt`
- Directory structure must exist on target

---

## TIP: SFTP vs SCP

### What are they?

Both transfer files over SSH, but different protocols and use cases.

### SFTP (SSH File Transfer Protocol)

**How it works:**
```python
sftp = ssh.open_sftp()
sftp.get('/remote/file.txt', '/local/file.txt')  # Download
sftp.put('/local/file.txt', '/remote/file.txt')  # Upload
sftp.close()
```

**Features:**
- List directories
- Check file existence
- Resume interrupted transfers
- More control over operations

**Best for:**
- Interactive file operations
- When you need to check files first
- Complex workflows

### SCP (Secure Copy Protocol)

**How it works:**
```python
# Simpler but less flexible
scp_client = SCPClient(ssh.get_transport())
scp_client.get('/remote/file.txt', '/local/file.txt')
scp_client.close()
```

**Features:**
- Simple copy only
- Faster for bulk transfers
- Less overhead

**Best for:**
- Simple file copies
- Performance-critical transfers
- One-off operations

### Your Code Uses SFTP

**Why SFTP here?**
- Need to read file into memory (not save locally)
- Write to different server
- Control over file handles

**Memory Transfer Pattern:**
```python
# Read from source → memory → write to target
file_content = source.file(path, 'r').read()
target.file(path, 'w').write(file_content)
```

### Booklet Summary
SFTP: Full featured, allows listing/checking files, better for complex operations. SCP: Simple copy only, faster for bulk transfers. Use SFTP when you need control; SCP when you just want to copy.

---

## Tracking Progress

```python
transferred.append(file_path)
print(f"✓ Transferred: {filename} ({len(file_content)} bytes)")
```

**Building Success List:**
- `transferred` starts as `[]`
- Each successful transfer appends file_path
- Final list returned to caller

**Logging Information:**
```python
len(file_content)  # Size in bytes
```
- Useful for debugging and monitoring
- Confirms file was actually transferred

**Example Output:**
```
📤 Transferring: card_batch_001.txt
✓ Transferred: card_batch_001.txt (2048 bytes)
📤 Transferring: card_batch_002.txt
✓ Transferred: card_batch_002.txt (1536 bytes)
✓ All 2 files transferred successfully
```

---

## Complete Transfer Flow

```
1. Receive file_list from previous task via XCom
         ↓
2. Validate list is not empty/None
         ↓
3. Connect to BOTH servers (source + target)
         ↓
4. For each file:
   a. Extract filename
   b. Open SFTP on source
   c. Read file content to memory
   d. Close source SFTP
   e. Open SFTP on target
   f. Write content from memory
   g. Close target SFTP
   h. Track successful transfer
         ↓
5. Close both SSH connections
         ↓
6. Return list of transferred files
```

---

## Key Takeaways

✅ **Validate inputs** before processing (empty list, None)  
✅ **Two SSH connections** for source and target servers  
✅ **open_sftp()** creates SFTP session from SSH connection  
✅ **file(path, 'r')** reads remote file  
✅ **file(path, 'w')** writes remote file (overwrites)  
✅ **Path().name** extracts filename from full path  
✅ **Memory transfer** pattern (read → memory → write)  
✅ **Track progress** with list of transferred files  
✅ **Always close** SFTP sessions and SSH connections  

---

## What's Next

**Lesson 06:** File Processing Task - Executing scripts on remote servers and handling results
