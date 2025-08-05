#!/usr/bin/env python3
"""
Airflow DAG for managing bash aliases across multiple VMs
Adds arbitrary aliases to .bashrc files on target virtual machines
"""

from datetime import datetime, timedelta
import paramiko
import re
from airflow.decorators import dag, task
from airflow.models import Variable

# Target VMs Configuration
TARGET_VMS = [
    {'ip': '192.168.83.129', 'hostname': 'airflow'},
    {'ip': '192.168.83.152', 'hostname': 'airflow2'},
    {'ip': '192.168.83.132', 'hostname': 'ftp'},
    {'ip': '192.168.83.150', 'hostname': 'nfs2'},
    {'ip': '192.168.83.200', 'hostname': 'nfs-cluster'},
    {'ip': '192.168.83.133', 'hostname': 'card1'},
    {'ip': '192.168.83.131', 'hostname': 'worker1'},
    {'ip': '192.168.83.153', 'hostname': 'worker2'},
    {'ip': '192.168.83.141', 'hostname': 'mq1'},
    {'ip': '192.168.83.142', 'hostname': 'mq2'},
    {'ip': '192.168.83.138', 'hostname': 'mq3'},
    {'ip': '192.168.83.148', 'hostname': 'sql1'},
    {'ip': '192.168.83.147', 'hostname': 'sql2'},
    {'ip': '192.168.83.149', 'hostname': 'sql3'},
    {'ip': '192.168.83.151', 'hostname': 'scheduler2'},
    {'ip': '192.168.83.154', 'hostname': 'haproxy2'},
]

# SSH Configuration
SSH_USERNAME = 'rocky'  # Change this to your username
SSH_KEY_PATH = '/home/rocky/.ssh/id_ed25519'  # Change to your SSH key path
SSH_TIMEOUT = 30

# Aliases to be added (can be overridden via Airflow Variables)
DEFAULT_ALIASES = [
    "alias bb='clear'",
    "alias ll='ls -la'",
    "alias la='ls -A'",
    "alias l='ls -CF'",
    "alias ..='cd ..'",
    "alias ...='cd ../..'",
    "alias grep='grep --color=auto'",
    "alias fgrep='fgrep --color=auto'",
    "alias egrep='egrep --color=auto'",
    "alias h='history'",
    "alias j='jobs -l'",
    "alias path='echo -e ${PATH//:/\\n}'",
    "alias now='date +\"%T\"'",
    "alias nowtime=now",
    "alias nowdate='date +\"%d-%m-%Y\"'"
]

class SSHConnectionError(Exception):
    """Custom exception for SSH connection errors"""
    pass

class AliasManagementError(Exception):
    """Custom exception for alias management errors"""
    pass

def ssh_execute(host, username, command, key_path=SSH_KEY_PATH, timeout=SSH_TIMEOUT):
    """
    Execute command via SSH and return output
    
    Args:
        host (str): Target host IP or hostname
        username (str): SSH username
        command (str): Command to execute
        key_path (str): Path to SSH private key
        timeout (int): SSH timeout in seconds
    
    Returns:
        tuple: (output, error, exit_code)
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {host} as {username}...")
        ssh.connect(
            hostname=host,
            username=username,
            key_filename=key_path,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False
        )
        
        print(f"Executing: {command}")
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        exit_code = stdout.channel.recv_exit_status()
        
        return output, error, exit_code
        
    except Exception as e:
        raise SSHConnectionError(f"SSH connection failed to {host}: {str(e)}")
    finally:
        ssh.close()

def parse_alias(alias_string):
    """
    Parse alias string to extract name and command
    
    Args:
        alias_string (str): Alias definition like "alias bb='clear'"
    
    Returns:
        tuple: (alias_name, alias_command)
    """
    # Match pattern: alias name='command' or alias name="command"
    match = re.match(r"alias\s+(\w+)=(['\"])(.+?)\2", alias_string)
    if match:
        return match.group(1), match.group(3)
    else:
        raise ValueError(f"Invalid alias format: {alias_string}")

@dag(
    dag_id='alias_management_workflow',
    description='Manage bash aliases across multiple VMs',
    schedule_interval=None,  # Manual trigger
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_tasks=8,  # Control parallelism
    default_args={
        'owner': 'rocky',
        'retries': 2,
        'retry_delay': timedelta(minutes=2),
        'queue': 'default'
    },
    tags=['alias-management', 'ssh', 'configuration']
)
def alias_management_workflow():
    
    @task
    def get_aliases_to_add():
        """
        Get list of aliases to add from Airflow Variables or use defaults
        
        Returns:
            list: List of alias strings to add
        """
        try:
            # Try to get aliases from Airflow Variable (JSON format)
            aliases_json = Variable.get("bash_aliases", default_var=None)
            if aliases_json:
                import json
                aliases = json.loads(aliases_json)
                print(f"Using aliases from Airflow Variable: {len(aliases)} aliases")
                return aliases
        except Exception as e:
            print(f"Failed to get aliases from Variable: {e}")
        
        print(f"Using default aliases: {len(DEFAULT_ALIASES)} aliases")
        return DEFAULT_ALIASES
    
    @task
    def validate_target_vms():
        """
        Validate target VMs configuration and connectivity
        
        Returns:
            list: List of validated VM configurations
        """
        print("=== VALIDATING TARGET VMS ===")
        validated_vms = []
        
        for vm in TARGET_VMS:
            print(f"\n--- Checking {vm['hostname']} ({vm['ip']}) ---")
            
            try:
                # Test basic SSH connectivity
                output, error, exit_code = ssh_execute(
                    vm['ip'], 
                    SSH_USERNAME, 
                    'echo "SSH test successful"'
                )
                
                if exit_code == 0:
                    print(f"✓ SSH connectivity OK")
                    validated_vms.append(vm)
                else:
                    print(f"✗ SSH test failed: {error}")
                    
            except Exception as e:
                print(f"✗ Connection failed: {str(e)}")
        
        print(f"\n=== VALIDATION COMPLETED: {len(validated_vms)}/{len(TARGET_VMS)} VMs accessible ===")
        return validated_vms
    
    @task
    def backup_bashrc_files(validated_vms: list):
        """
        Create backup of .bashrc files on all target VMs
        
        Args:
            validated_vms (list): List of validated VM configurations
            
        Returns:
            dict: Backup results for each VM
        """
        print("=== BACKING UP .BASHRC FILES ===")
        backup_results = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for vm in validated_vms:
            hostname = vm['hostname']
            ip = vm['ip']
            print(f"\n--- Backing up .bashrc on {hostname} ({ip}) ---")
            
            try:
                # Check if .bashrc exists
                output, error, exit_code = ssh_execute(
                    ip, SSH_USERNAME, 'test -f ~/.bashrc && echo "exists" || echo "not_found"'
                )
                
                if output.strip() == "not_found":
                    print("  ✓ .bashrc doesn't exist, will be created")
                    backup_results[hostname] = {
                        'status': 'no_file',
                        'backup_path': None,
                        'message': '.bashrc file does not exist, will be created'
                    }
                    continue
                
                # Create backup
                backup_path = f"~/.bashrc.backup_{timestamp}"
                cmd = f"cp ~/.bashrc {backup_path}"
                
                output, error, exit_code = ssh_execute(ip, SSH_USERNAME, cmd)
                
                if exit_code == 0:
                    print(f"  ✓ Backup created: {backup_path}")
                    backup_results[hostname] = {
                        'status': 'success',
                        'backup_path': backup_path,
                        'message': 'Backup created successfully'
                    }
                else:
                    raise Exception(f"Backup failed: {error}")
                    
            except Exception as e:
                print(f"  ✗ Backup failed: {str(e)}")
                backup_results[hostname] = {
                    'status': 'failed',
                    'backup_path': None,
                    'message': str(e)
                }
        
        print(f"\n=== BACKUP COMPLETED ===")
        return backup_results
    
    @task
    def check_existing_aliases(validated_vms: list, aliases_to_add: list):
        """
        Check which aliases already exist in .bashrc files
        
        Args:
            validated_vms (list): List of validated VM configurations
            aliases_to_add (list): List of aliases to add
            
        Returns:
            dict: Existing aliases status for each VM
        """
        print("=== CHECKING EXISTING ALIASES ===")
        existing_status = {}
        
        for vm in validated_vms:
            hostname = vm['hostname']
            ip = vm['ip']
            print(f"\n--- Checking aliases on {hostname} ({ip}) ---")
            
            vm_status = {
                'existing_aliases': [],
                'new_aliases': [],
                'conflicts': []
            }
            
            try:
                # Get current .bashrc content
                output, error, exit_code = ssh_execute(
                    ip, SSH_USERNAME, 'cat ~/.bashrc 2>/dev/null || echo ""'
                )
                
                current_bashrc = output
                
                for alias_string in aliases_to_add:
                    try:
                        alias_name, alias_command = parse_alias(alias_string)
                        
                        # Check if alias already exists
                        if f"alias {alias_name}=" in current_bashrc:
                            # Extract existing alias command
                            existing_match = re.search(
                                rf"alias\s+{re.escape(alias_name)}=(['\"])(.+?)\1", 
                                current_bashrc
                            )
                            
                            if existing_match:
                                existing_command = existing_match.group(2)
                                if existing_command == alias_command:
                                    print(f"  ✓ {alias_name}: already exists with same command")
                                    vm_status['existing_aliases'].append(alias_string)
                                else:
                                    print(f"  ⚠ {alias_name}: exists with different command")
                                    vm_status['conflicts'].append({
                                        'alias': alias_string,
                                        'existing': f"alias {alias_name}='{existing_command}'"
                                    })
                            else:
                                print(f"  ○ {alias_name}: will be added")
                                vm_status['new_aliases'].append(alias_string)
                        else:
                            print(f"  ○ {alias_name}: will be added")
                            vm_status['new_aliases'].append(alias_string)
                            
                    except ValueError as e:
                        print(f"  ✗ Invalid alias format: {alias_string}")
                        continue
                
                existing_status[hostname] = vm_status
                
            except Exception as e:
                print(f"  ✗ Failed to check aliases: {str(e)}")
                existing_status[hostname] = {
                    'error': str(e),
                    'existing_aliases': [],
                    'new_aliases': aliases_to_add,  # Assume all are new if check fails
                    'conflicts': []
                }
        
        print(f"\n=== ALIAS CHECK COMPLETED ===")
        return existing_status
    
    @task
    def add_aliases_to_vms(validated_vms: list, existing_status: dict, backup_results: dict):
        """
        Add new aliases to .bashrc files on target VMs
        
        Args:
            validated_vms (list): List of validated VM configurations
            existing_status (dict): Status of existing aliases
            backup_results (dict): Backup operation results
            
        Returns:
            dict: Results of alias addition for each VM
        """
        print("=== ADDING ALIASES TO VMS ===")
        addition_results = {}
        
        for vm in validated_vms:
            hostname = vm['hostname']
            ip = vm['ip']
            print(f"\n--- Adding aliases to {hostname} ({ip}) ---")
            
            # Skip if backup failed
            if backup_results.get(hostname, {}).get('status') == 'failed':
                print(f"  ✗ Skipping due to backup failure")
                addition_results[hostname] = {
                    'status': 'skipped',
                    'reason': 'backup_failed',
                    'added_count': 0,
                    'aliases': []
                }
                continue
            
            vm_status = existing_status.get(hostname, {})
            new_aliases = vm_status.get('new_aliases', [])
            conflicts = vm_status.get('conflicts', [])
            
            if not new_aliases and not conflicts:
                print("  ✓ No aliases to add")
                addition_results[hostname] = {
                    'status': 'success',
                    'reason': 'no_new_aliases',
                    'added_count': 0,
                    'aliases': []
                }
                continue
            
            try:
                # Prepare aliases to add
                aliases_to_append = []
                
                # Add new aliases
                aliases_to_append.extend(new_aliases)
                
                # Handle conflicts (overwrite existing)
                for conflict in conflicts:
                    aliases_to_append.append(conflict['alias'])
                    print(f"  ⚠ Will overwrite: {conflict['alias']}")
                
                if aliases_to_append:
                    # Create alias section in .bashrc
                    alias_section = [
                        "",
                        "# Custom aliases added by Airflow",
                        f"# Added on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        ""
                    ]
                    alias_section.extend(aliases_to_append)
                    alias_section.append("")
                    
                    # Remove existing conflicting aliases first
                    if conflicts:
                        for conflict in conflicts:
                            alias_name, _ = parse_alias(conflict['alias'])
                            remove_cmd = f"sed -i '/^alias {alias_name}=/d' ~/.bashrc"
                            ssh_execute(ip, SSH_USERNAME, remove_cmd)
                    
                    # Append new aliases
                    alias_content = '\n'.join(alias_section)
                    append_cmd = f"echo {repr(alias_content)} >> ~/.bashrc"
                    
                    output, error, exit_code = ssh_execute(ip, SSH_USERNAME, append_cmd)
                    
                    if exit_code == 0:
                        print(f"  ✓ Added {len(aliases_to_append)} aliases")
                        addition_results[hostname] = {
                            'status': 'success',
                            'added_count': len(aliases_to_append),
                            'aliases': aliases_to_append,
                            'conflicts_resolved': len(conflicts)
                        }
                    else:
                        raise Exception(f"Failed to append aliases: {error}")
                
            except Exception as e:
                print(f"  ✗ Failed to add aliases: {str(e)}")
                addition_results[hostname] = {
                    'status': 'failed',
                    'error': str(e),
                    'added_count': 0,
                    'aliases': []
                }
        
        print(f"\n=== ALIAS ADDITION COMPLETED ===")
        return addition_results
    
    @task
    def verify_aliases(validated_vms: list, addition_results: dict):
        """
        Verify that aliases were added correctly by testing them
        
        Args:
            validated_vms (list): List of validated VM configurations
            addition_results (dict): Results from alias addition
            
        Returns:
            dict: Verification results for each VM
        """
        print("=== VERIFYING ALIASES ===")
        verification_results = {}
        
        for vm in validated_vms:
            hostname = vm['hostname']
            ip = vm['ip']
            print(f"\n--- Verifying aliases on {hostname} ({ip}) ---")
            
            addition_result = addition_results.get(hostname, {})
            
            if addition_result.get('status') != 'success':
                print("  ○ Skipping verification (no aliases added)")
                verification_results[hostname] = {
                    'status': 'skipped',
                    'reason': 'no_aliases_added'
                }
                continue
            
            added_aliases = addition_result.get('aliases', [])
            
            try:
                verified_aliases = []
                failed_aliases = []
                
                for alias_string in added_aliases:
                    try:
                        alias_name, _ = parse_alias(alias_string)
                        
                        # Test if alias exists and works
                        test_cmd = f"bash -c 'source ~/.bashrc && type {alias_name}'"
                        output, error, exit_code = ssh_execute(ip, SSH_USERNAME, test_cmd)
                        
                        if exit_code == 0 and "is aliased to" in output:
                            print(f"  ✓ {alias_name}: verified")
                            verified_aliases.append(alias_name)
                        else:
                            print(f"  ✗ {alias_name}: verification failed")
                            failed_aliases.append(alias_name)
                            
                    except ValueError:
                        continue
                
                verification_results[hostname] = {
                    'status': 'completed',
                    'verified_count': len(verified_aliases),
                    'failed_count': len(failed_aliases),
                    'verified_aliases': verified_aliases,
                    'failed_aliases': failed_aliases
                }
                
                print(f"  Summary: {len(verified_aliases)} verified, {len(failed_aliases)} failed")
                
            except Exception as e:
                print(f"  ✗ Verification failed: {str(e)}")
                verification_results[hostname] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        print(f"\n=== VERIFICATION COMPLETED ===")
        return verification_results
    
    @task
    def generate_summary_report(
        validated_vms: list, 
        backup_results: dict, 
        addition_results: dict, 
        verification_results: dict
    ):
        """
        Generate a comprehensive summary report
        
        Args:
            validated_vms (list): List of validated VMs
            backup_results (dict): Backup operation results
            addition_results (dict): Alias addition results
            verification_results (dict): Verification results
            
        Returns:
            dict: Complete summary report
        """
        print("=== GENERATING SUMMARY REPORT ===")
        
        total_vms = len(TARGET_VMS)
        accessible_vms = len(validated_vms)
        successful_additions = 0
        total_aliases_added = 0
        total_verified = 0
        
        vm_reports = {}
        
        for vm in validated_vms:
            hostname = vm['hostname']
            
            addition_result = addition_results.get(hostname, {})
            verification_result = verification_results.get(hostname, {})
            backup_result = backup_results.get(hostname, {})
            
            if addition_result.get('status') == 'success':
                successful_additions += 1
                total_aliases_added += addition_result.get('added_count', 0)
            
            total_verified += verification_result.get('verified_count', 0)
            
            vm_reports[hostname] = {
                'ip': vm['ip'],
                'backup_status': backup_result.get('status', 'unknown'),
                'aliases_added': addition_result.get('added_count', 0),
                'aliases_verified': verification_result.get('verified_count', 0),
                'overall_status': 'success' if addition_result.get('status') == 'success' else 'failed'
            }
        
        summary = {
            'execution_time': datetime.now().isoformat(),
            'statistics': {
                'total_target_vms': total_vms,
                'accessible_vms': accessible_vms,
                'successful_vm_updates': successful_additions,
                'total_aliases_added': total_aliases_added,
                'total_aliases_verified': total_verified
            },
            'vm_details': vm_reports,
            'success_rate': f"{(successful_additions/accessible_vms*100):.1f}%" if accessible_vms > 0 else "0%"
        }
        
        print("\n" + "="*50)
        print("ALIAS MANAGEMENT SUMMARY")
        print("="*50)
        print(f"Target VMs: {total_vms}")
        print(f"Accessible VMs: {accessible_vms}")
        print(f"Successful Updates: {successful_additions}")
        print(f"Total Aliases Added: {total_aliases_added}")
        print(f"Total Aliases Verified: {total_verified}")
        print(f"Success Rate: {summary['success_rate']}")
        print("="*50)
        
        return summary
    
    # Define workflow
    aliases = get_aliases_to_add()
    vms = validate_target_vms()
    backups = backup_bashrc_files(vms)
    status = check_existing_aliases(vms, aliases)
    results = add_aliases_to_vms(vms, status, backups)
    verification = verify_aliases(vms, results)
    summary = generate_summary_report(vms, backups, results, verification)
    
    # Set task dependencies
    aliases >> vms >> backups
    [vms, aliases] >> status
    [status, backups] >> results
    results >> verification
    [vms, backups, results, verification] >> summary

# Create DAG instance
dag_instance = alias_management_workflow()
