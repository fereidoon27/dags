# Lesson 02 Cheatsheet: SSH with Paramiko

## Basic SSH Connection Pattern
```python
import paramiko

def create_ssh_client(hostname: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        private_key = paramiko.Ed25519Key.from_private_key_file('/path/to/key')
        client.connect(
            hostname=hostname,
            username='user',
            pkey=private_key,
            timeout=30
        )
        return client
    except Exception as e:
        raise AirflowException(f"Connection failed: {str(e)}")
```

## Key Loading Methods
```python
# Ed25519 (modern, recommended)
key = paramiko.Ed25519Key.from_private_key_file('/path/to/id_ed25519')

# RSA (legacy)
key = paramiko.RSAKey.from_private_key_file('/path/to/id_rsa')

# With passphrase
key = paramiko.Ed25519Key.from_private_key_file('/path/to/key', password='pass')
```

## Connection Parameters
```python
client.connect(
    hostname='10.101.20.164',  # Server IP/domain
    username='rocky',           # SSH user
    pkey=private_key,          # Key object (no password)
    timeout=30,                # Connection timeout (seconds)
    port=22                    # Optional: SSH port (default 22)
)
```

## Host Key Policies
```python
# Auto-accept new hosts (convenient, less secure)
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Reject unknown hosts (secure, requires known_hosts)
client.set_missing_host_key_policy(paramiko.RejectPolicy())

# Warn but connect (middle ground)
client.set_missing_host_key_policy(paramiko.WarningPolicy())
```

## Common Error Patterns
```python
try:
    client.connect(...)
except paramiko.AuthenticationException:
    # Wrong key or username
except paramiko.SSHException:
    # SSH-specific errors
except socket.timeout:
    # Connection timeout
except Exception as e:
    # Catch-all
```

## Cleanup Pattern
```python
ssh = None
try:
    ssh = create_ssh_client('10.101.20.164')
    # Do work...
finally:
    if ssh:
        ssh.close()  # Always close connection
```

## Quick Reference
- **SSHClient()** - Creates SSH connection object
- **AutoAddPolicy()** - Auto-trust new servers
- **Ed25519Key** - Modern SSH key type
- **timeout** - Prevents infinite hanging
- **close()** - Always close connections in finally block
