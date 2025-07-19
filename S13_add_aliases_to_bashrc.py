# S13_add_aliases_to_bashrc.py
from datetime import datetime, timedelta
from airflow.decorators import dag, task
import paramiko
import time

# =============================================================================
# CONFIGURATION SECTION
# =============================================================================

# SSH Configuration
SSH_KEY_PATH = '/home/rocky/.ssh/id_ed25519'  # Change to None if using password
SSH_PASSWORD = '111'  # Used if SSH_KEY_PATH is None
SSH_USERNAME = 'rocky'
SSH_PORT = 22
SSH_TIMEOUT = 30

# Target VMs configuration
TARGET_VMS = [
    {'ip': '192.168.83.150', 'hostname': 'nfs2'},
    {'ip': '192.168.83.141', 'hostname': 'mq1'},

]

# Aliases to add (each line will be added to .bashrc)
ALIASES_TO_ADD = [
    "# --- HAProxy Aliases ---",
    "alias jha='sudo journalctl -u haproxy.service -f'",
    "alias sha='sudo systemctl status haproxy.service'",
    "alias stha='sudo systemctl start haproxy.service'",
    "alias spha='sudo systemctl stop haproxy.service'",
    "alias rha='sudo systemctl restart haproxy.service'",
    "",
    "# --- Airflow Webserver Aliases ---",
    "alias jw='sudo journalctl -u airflow-webserver.service -f'",
    "alias sw='sudo systemctl status airflow-webserver.service'",
    "alias stw='sudo systemctl start airflow-webserver.service'",
    "alias spw='sudo systemctl stop airflow-webserver.service'",
    "alias rw='sudo systemctl restart airflow-webserver.service'",
    "",
    "# --- Airflow Scheduler Aliases ---",
    "alias js='sudo journalctl -u airflow-scheduler.service -f'",
    "alias ss='sudo systemctl status airflow-scheduler.service'",
    "alias sts='sudo systemctl start airflow-scheduler.service'",
    "alias sps='sudo systemctl stop airflow-scheduler.service'",
    "alias rs='sudo systemctl restart airflow-scheduler.service'",
    "",
    "# --- Airflow DAG Processor Aliases ---",
    "alias jd='sudo journalctl -u airflow-dag-processor.service -f'",
    "alias sd='sudo systemctl status airflow-dag-processor.service'",
    "alias std='sudo systemctl start airflow-dag-processor.service'",
    "alias spd='sudo systemctl stop airflow-dag-processor.service'",
    "alias rd='sudo systemctl restart airflow-dag-processor.service'",
    "",
    "# --- Airflow Worker Aliases ---",
    "alias jwork='sudo journalctl -u airflow-worker.service -f'",
    "alias swork='sudo systemctl status airflow-worker.service'",
    "alias stwork='sudo systemctl start airflow-worker.service'",
    "alias spwork='sudo systemctl stop airflow-worker.service'",
    "alias rwork='sudo systemctl restart airflow-worker.service'",
    "",
    "# --- RabbitMQ Server Aliases ---",
    "alias jmq='sudo journalctl -u rabbitmq-server.service -f'",
    "alias smq='sudo systemctl status rabbitmq-server.service'",
    "alias stmq='sudo systemctl start rabbitmq-server.service'",
    "alias spmq='sudo systemctl stop rabbitmq-server.service'",
    "alias rmq='sudo systemctl restart rabbitmq-server.service'",
    "",
    "# --- Patroni Aliases ---",
    "alias jpat='sudo journalctl -u patroni.service -f'",
    "alias spat='sudo systemctl status patroni.service'",
    "alias stpat='sudo systemctl start patroni.service'",
    "alias sppat='sudo systemctl stop patroni.service'",
    "alias rpat='sudo systemctl restart patroni.service'",
    "",
    "# --- ETCD Aliases ---",
    "alias jet='sudo journalctl -u etcd.service -f'",
    "alias set='sudo systemctl status etcd.service'",
    "alias stet='sudo systemctl start etcd.service'"
]

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ssh_connect(vm_ip):
    """Create SSH connection to a VM"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        if SSH_KEY_PATH:
            # Use SSH key authentication
            ssh.connect(
                hostname=vm_ip,
                username=SSH_USERNAME,
                key_filename=SSH_KEY_PATH,
                port=SSH_PORT,
                timeout=SSH_TIMEOUT
            )
        else:
            # Use password authentication
            ssh.connect(
                hostname=vm_ip,
                username=SSH_USERNAME,
                password=SSH_PASSWORD,
                port=SSH_PORT,
                timeout=SSH_TIMEOUT
            )
        return ssh
    except Exception as e:
        raise Exception(f"Failed to connect to {vm_ip}: {str(e)}")

def execute_ssh_command(ssh, command):
    """Execute a command via SSH and return output"""
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    
    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()
    
    if exit_code != 0:
        raise Exception(f"Command failed (exit code {exit_code}): {error}")
    
    return output

def extract_alias_name(alias_line):
    """Extract alias name from alias line (e.g., 'alias jha=' -> 'jha')"""
    if alias_line.strip().startswith('alias ') and '=' in alias_line:
        # Extract text between 'alias ' and '='
        alias_part = alias_line.strip()[6:]  # Remove 'alias '
        alias_name = alias_part.split('=')[0]
        return alias_name
    return None

# =============================================================================
# DAG DEFINITION
# =============================================================================

@dag(
    dag_id='S13_add_aliases_to_bashrc',
    description='Add system aliases to .bashrc on target VMs',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_tasks=3,  # DAG-level concurrency limit
    default_args={
        'owner': 'rocky',
        'retries': 0,  # No retries as requested
    },
    tags=['bashrc', 'aliases', 'system-management']
)
def add_aliases_workflow():
    
    @task
    def add_aliases_to_vm(vm_config: dict):
        """Add aliases to .bashrc on a single VM"""
        vm_ip = vm_config['ip']
        vm_hostname = vm_config['hostname']
        
        print(f"=== Processing VM: {vm_hostname} ({vm_ip}) ===")
        
        ssh = None
        try:
            # Connect to VM
            print(f"Connecting to {vm_ip}...")
            ssh = ssh_connect(vm_ip)
            print("✓ SSH connection established")
            
            # Read current .bashrc content
            print("Reading current .bashrc content...")
            try:
                current_bashrc = execute_ssh_command(ssh, "cat ~/.bashrc")
            except:
                # If .bashrc doesn't exist, create it
                current_bashrc = ""
                print("⚠ .bashrc not found, will create new one")
            
            # Find existing alias names in .bashrc
            existing_aliases = set()
            for line in current_bashrc.split('\n'):
                alias_name = extract_alias_name(line)
                if alias_name:
                    existing_aliases.add(alias_name)
            
            print(f"Found {len(existing_aliases)} existing aliases: {sorted(existing_aliases)}")
            
            # Determine which aliases to add
            aliases_to_add = []
            skipped_count = 0
            
            for alias_line in ALIASES_TO_ADD:
                alias_name = extract_alias_name(alias_line)
                
                if alias_name and alias_name in existing_aliases:
                    print(f"⚠ Skipping existing alias: {alias_name}")
                    skipped_count += 1
                else:
                    aliases_to_add.append(alias_line)
            
            print(f"Will add {len(aliases_to_add)} new lines, skipped {skipped_count} existing aliases")
            
            if not aliases_to_add:
                print("✓ All aliases already exist, no changes needed")
                return {
                    'vm': vm_hostname,
                    'ip': vm_ip,
                    'status': 'success',
                    'action': 'no_changes',
                    'added': 0,
                    'skipped': skipped_count
                }
            
            # Create backup of .bashrc
            backup_cmd = f"cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S)"
            execute_ssh_command(ssh, backup_cmd)
            print("✓ Created .bashrc backup")
            
            # Prepare new aliases content
            new_aliases_content = '\n\n# === Airflow Management Aliases (Added by DAG) ===\n'
            new_aliases_content += '\n'.join(aliases_to_add)
            new_aliases_content += '\n# === End of Airflow Management Aliases ===\n'
            
            # Append new aliases to .bashrc using echo commands
            # This approach avoids issues with special characters
            print("Adding new aliases to .bashrc...")
            
            # Add separator comment first
            execute_ssh_command(ssh, f"echo '' >> ~/.bashrc")
            execute_ssh_command(ssh, f"echo '# === Airflow Management Aliases (Added by DAG) ===' >> ~/.bashrc")
            
            added_count = 0
            for alias_line in aliases_to_add:
                if alias_line.strip():  # Skip empty lines in echo
                    # Escape single quotes in the alias line
                    escaped_line = alias_line.replace("'", "'\"'\"'")
                    execute_ssh_command(ssh, f"echo '{escaped_line}' >> ~/.bashrc")
                    added_count += 1
                else:
                    execute_ssh_command(ssh, f"echo '' >> ~/.bashrc")
            
            # Add closing comment
            execute_ssh_command(ssh, f"echo '# === End of Airflow Management Aliases ===' >> ~/.bashrc")
            
            print(f"✓ Added {added_count} alias lines to .bashrc")
            
            # Source .bashrc to apply changes
            print("Sourcing .bashrc to apply changes...")
            execute_ssh_command(ssh, "source ~/.bashrc")
            print("✓ .bashrc sourced successfully")
            
            # Verify aliases were added
            print("Verifying aliases were added...")
            new_bashrc = execute_ssh_command(ssh, "cat ~/.bashrc")
            
            # Count how many of our aliases are now present
            verified_count = 0
            for alias_line in aliases_to_add:
                alias_name = extract_alias_name(alias_line)
                if alias_name:
                    for line in new_bashrc.split('\n'):
                        if extract_alias_name(line) == alias_name:
                            verified_count += 1
                            break
            
            print(f"✓ Verified {verified_count} aliases in updated .bashrc")
            
            return {
                'vm': vm_hostname,
                'ip': vm_ip,
                'status': 'success',
                'action': 'added_aliases',
                'added': added_count,
                'skipped': skipped_count,
                'verified': verified_count
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"✗ ERROR processing {vm_hostname} ({vm_ip}): {error_msg}")
            
            return {
                'vm': vm_hostname,
                'ip': vm_ip,
                'status': 'failed',
                'error': error_msg,
                'added': 0,
                'skipped': 0
            }
        
        finally:
            # Always close SSH connection
            if ssh:
                ssh.close()
                print(f"✓ SSH connection to {vm_ip} closed")
    
    @task
    def generate_summary_report(results: list):
        """Generate a summary report of all operations"""
        print("\n" + "="*60)
        print("           ALIASES DEPLOYMENT SUMMARY REPORT")
        print("="*60)
        
        successful_vms = [r for r in results if r['status'] == 'success']
        failed_vms = [r for r in results if r['status'] == 'failed']
        
        print(f"\nTotal VMs processed: {len(results)}")
        print(f"Successful: {len(successful_vms)}")
        print(f"Failed: {len(failed_vms)}")
        
        if successful_vms:
            print(f"\n--- SUCCESSFUL DEPLOYMENTS ---")
            for result in successful_vms:
                action_desc = "No changes needed" if result['action'] == 'no_changes' else f"Added {result['added']} aliases"
                print(f"✓ {result['vm']:12} ({result['ip']:15}) - {action_desc}")
                if result.get('skipped', 0) > 0:
                    print(f"    Skipped {result['skipped']} existing aliases")
        
        if failed_vms:
            print(f"\n--- FAILED DEPLOYMENTS ---")
            for result in failed_vms:
                print(f"✗ {result['vm']:12} ({result['ip']:15}) - {result['error']}")
        
        # Calculate totals
        total_added = sum(r.get('added', 0) for r in successful_vms)
        total_skipped = sum(r.get('skipped', 0) for r in successful_vms)
        
        print(f"\n--- STATISTICS ---")
        print(f"Total aliases added: {total_added}")
        print(f"Total aliases skipped (already existed): {total_skipped}")
        print(f"Success rate: {len(successful_vms)}/{len(results)} ({100*len(successful_vms)/len(results):.1f}%)")
        
        print("\n" + "="*60)
        
        return {
            'total_vms': len(results),
            'successful': len(successful_vms),
            'failed': len(failed_vms),
            'total_added': total_added,
            'total_skipped': total_skipped,
            'success_rate': len(successful_vms)/len(results) if results else 0
        }
    
    # Create tasks for each VM (will run concurrently up to max_active_tasks limit)
    vm_results = []
    for vm_config in TARGET_VMS:
        result = add_aliases_to_vm(vm_config)
        vm_results.append(result)
    
    # Generate summary report after all VM tasks complete
    summary = generate_summary_report(vm_results)
    
    return summary

# Create DAG instance
dag_instance = add_aliases_workflow()
