# Lesson 02: SSH Connection Management

## What You're Learning
How to create secure SSH connections to remote servers using Paramiko with proper error handling.

---

## The create_ssh_client Function

```python
def create_ssh_client(hostname: str) -> paramiko.SSHClient:
    """Create and return configured SSH client"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        private_key = paramiko.Ed25519Key.from_private_key_file(SSH_CONFIG['key_file'])
        client.connect(
            hostname=hostname,
            username=SSH_CONFIG['user'],
            pkey=private_key,
            timeout=30
        )
        return client
    except Exception as e:
        raise AirflowException(f"SSH connection to {hostname} failed: {str(e)}")
```

---

## Function Signature

```python
def create_ssh_client(hostname: str) -> paramiko.SSHClient:
```

**Type Hints Explained:**
- `hostname: str` - Input must be a string (server IP or domain)
- `-> paramiko.SSHClient` - Returns an SSH client object

**Example Call:**
```python
ssh = create_ssh_client('10.101.20.164')  # Connect to FTP server
```

---

## Creating the SSH Client Object

```python
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
```

**What's happening:**

**Line 1:** Creates an empty SSH client object
- Like opening a connection tool, but not connected yet

**Line 2:** Configures host key verification
- **The Problem:** SSH verifies server identity using "host keys"
- **AutoAddPolicy():** Automatically trusts new servers (adds to known_hosts)
- **Security Note:** Production environments should use stricter policies

**Real-World Analogy:**
When you SSH manually, you see: "Are you sure you want to connect (yes/no)?"
`AutoAddPolicy()` automatically answers "yes"

---

## Loading the Private Key

```python
private_key = paramiko.Ed25519Key.from_private_key_file(SSH_CONFIG['key_file'])
```

**What's happening:**
- Reads the SSH private key file from disk
- `Ed25519Key` - Modern, secure SSH key type (better than RSA)
- `from_private_key_file()` - Loads key from file path

**Key File Location:**
```python
SSH_CONFIG['key_file']  # Gets '/home/rocky/.ssh/id_ed25519'
```

**Example:**
If the file contains:
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAA...
-----END OPENSSH PRIVATE KEY-----
```
Paramiko parses this into a usable key object.

---

## Establishing the Connection

```python
client.connect(
    hostname=hostname,
    username=SSH_CONFIG['user'],
    pkey=private_key,
    timeout=30
)
```

**Parameters Explained:**

**hostname**: Server IP address
- Example: `'10.101.20.164'` (passed as function argument)

**username**: SSH user account
- Gets `'rocky'` from config

**pkey**: Private key for authentication
- Uses the loaded Ed25519 key (no password needed)

**timeout**: Connection timeout in seconds
- If server doesn't respond in 30 seconds, connection fails
- Prevents hanging indefinitely

**Example Connection:**
```
User: rocky
Server: 10.101.20.164
Auth: SSH key (no password)
Timeout: 30 seconds
```

---

## Error Handling

```python
try:
    private_key = paramiko.Ed25519Key.from_private_key_file(SSH_CONFIG['key_file'])
    client.connect(...)
    return client
except Exception as e:
    raise AirflowException(f"SSH connection to {hostname} failed: {str(e)}")
```

**The Pattern:**

**try block:** Attempt connection operations
**except block:** Catch ANY error that occurs
**raise AirflowException:** Convert to Airflow-specific error

**Why AirflowException?**
- Airflow recognizes this error type
- Triggers retry logic (remember `retries: 2` from default_args)
- Logs properly in Airflow UI

**Error Message Example:**
```
SSH connection to 10.101.20.164 failed: [Errno 111] Connection refused
```

**Common Errors:**
- File not found: Key file path wrong
- Permission denied: Key file permissions incorrect (should be 600)
- Connection refused: Server not running SSH service
- Timeout: Server unreachable or firewall blocking

---

## TIP: SSH Key Authentication

### What is it?

Authentication using cryptographic key pairs instead of passwords. More secure and automated-friendly.

### Most Common Use Cases

**Automated Scripts:**
```python
# No password prompts - perfect for DAGs
client.connect(hostname='server', pkey=private_key)
```

**Server-to-Server Communication:**
```python
# Production servers talking to each other
ftp_client = create_ssh_client('10.101.20.164')
target_client = create_ssh_client('10.101.20.201')
```

### Key Types Comparison

| Key Type | Security | Speed | Modern? |
|----------|----------|-------|---------|
| RSA 2048 | Good | Slower | Legacy |
| Ed25519 | Excellent | Fastest | ✓ Modern |

### Booklet Summary
SSH keys enable passwordless authentication. Ed25519 is the modern standard (fast + secure). Use `pkey` parameter for key-based auth, perfect for automation.

---

## Complete Flow Visualization

```
1. Call: create_ssh_client('10.101.20.164')
         ↓
2. Create empty SSH client object
         ↓
3. Set host key policy (auto-trust)
         ↓
4. Load private key from file
         ↓
5. Connect with: IP + username + key + timeout
         ↓
6. Return connected client (or raise error)
```

---

## Key Takeaways

✅ **paramiko.SSHClient()** creates SSH connection objects  
✅ **AutoAddPolicy()** auto-trusts new servers (convenience vs security trade-off)  
✅ **Ed25519Key** is modern SSH key format (fast and secure)  
✅ **pkey parameter** enables passwordless authentication  
✅ **timeout=30** prevents infinite hanging  
✅ **AirflowException** makes errors retry-friendly  
✅ **try/except** catches connection failures gracefully  

---

## What's Next

**Lesson 03:** File Detection with Sensors - The `check_for_card_files()` function and how sensors work in Airflow
