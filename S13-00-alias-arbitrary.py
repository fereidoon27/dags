#!/usr/bin/env python3
"""
Simple Airflow DAG to add bash aliases to multiple VMs
Easy to understand and debug for beginners
"""

from datetime import datetime, timedelta
import paramiko
from airflow.decorators import dag, task

# Configuration - Change these values for your setup
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

# SSH settings
USERNAME = 'rocky'
SSH_KEY = '/home/rocky/.ssh/id_ed25519'

# Aliases to add
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

def run_ssh_command(vm_ip, command):
    """
    Simple function to run SSH command on a VM
    Returns the output if successful, None if failed
    """
    try:
        # Connect to VM
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vm_ip, username=USERNAME, key_filename=SSH_KEY, timeout=10)
        
        # Run command
        stdin, stdout, stderr = ssh.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        
        ssh.close()
        
        # Return output if command worked, None if failed
        if exit_code == 0:
            return output
        else:
            return None
        
    except Exception as e:
        print(f"Error connecting to {vm_ip}: {e}")
        return None

def get_alias_name(alias_string):
    """
    Extract alias name from alias string
    Example: "alias bb='clear'" returns "bb"
    """
    # Find text between "alias " and "="
    start = alias_string.find("alias ") + 6
    end = alias_string.find("=")
    return alias_string[start:end].strip()

@dag(
    dag_id='S13-00-simple-aliass-add',
    description='Add bash aliases to multiple VMs - Simple version',
    schedule_interval=None,  # Run manually
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['aliases', 'simple', 'S13']
)
def simple_alias_workflow():
    
    @task
    def test_connections():
        """Test if we can connect to all VMs"""
        print("Testing connections to all VMs...")
        
        working_vms = []
        failed_vms = []
        
        for vm in TARGET_VMS:
            print(f"Testing {vm['hostname']} ({vm['ip']})...")
            
            # Try to run simple command
            result = run_ssh_command(vm['ip'], 'echo "test"')
            if result is not None:
                print(f"✓ {vm['hostname']} - OK")
                working_vms.append(vm)
            else:
                print(f"✗ {vm['hostname']} - FAILED")
                failed_vms.append(vm)
        
        print(f"\nConnection Results: {len(working_vms)} working, {len(failed_vms)} failed")
        
        return {
            'working_vms': working_vms,
            'failed_vms': failed_vms
        }
    
    @task
    def add_aliases(connection_results):
        """Add aliases to all working VMs"""
        working_vms = connection_results['working_vms']
        print("Adding aliases to working VMs...")
        
        success_vms = []
        failed_vms = []
        
        for vm in working_vms:
            print(f"\nProcessing {vm['hostname']} ({vm['ip']})...")
            
            # Create backup first
            backup_cmd = "cp ~/.bashrc ~/.bashrc.backup 2>/dev/null || touch ~/.bashrc"
            run_ssh_command(vm['ip'], backup_cmd)
            
            # Get current .bashrc content to check existing aliases
            current_bashrc = run_ssh_command(vm['ip'], 'cat ~/.bashrc 2>/dev/null || echo ""')
            if current_bashrc is None:
                current_bashrc = ""
            
            # Check each alias and add if not exists
            vm_success = True
            added_count = 0
            skipped_count = 0
            
            for alias in DEFAULT_ALIASES:
                alias_name = get_alias_name(alias)
                
                # Check if alias already exists
                if f"alias {alias_name}=" in current_bashrc:
                    print(f"  ○ Skipped: {alias_name} (already exists)")
                    skipped_count += 1
                else:
                    # Add alias to .bashrc
                    add_cmd = f'echo "{alias}" >> ~/.bashrc'
                    if run_ssh_command(vm['ip'], add_cmd) is not None:
                        print(f"  ✓ Added: {alias}")
                        added_count += 1
                    else:
                        print(f"  ✗ Failed: {alias}")
                        vm_success = False
            
            if vm_success:
                print(f"✓ {vm['hostname']} - {added_count} added, {skipped_count} skipped")
                success_vms.append(vm)
            else:
                print(f"✗ {vm['hostname']} - Some aliases failed")
                failed_vms.append(vm)
        
        return {
            'success_vms': success_vms,
            'failed_vms': failed_vms
        }
    
    @task
    def show_summary(connection_results, alias_results):
        """Show final summary with VM names"""
        # Connection results
        connection_working = [vm['hostname'] for vm in connection_results['working_vms']]
        connection_failed = [vm['hostname'] for vm in connection_results['failed_vms']]
        
        # Alias addition results
        alias_success = [vm['hostname'] for vm in alias_results['success_vms']]
        alias_failed = [vm['hostname'] for vm in alias_results['failed_vms']]
        
        print("\n" + "="*50)
        print("ALIAS ADDITION SUMMARY")
        print("="*50)
        
        print(f"\n📡 CONNECTION TEST:")
        print(f"  Total target VMs: {len(TARGET_VMS)}")
        print(f"  Successful connections: {len(connection_working)}")
        print(f"  Failed connections: {len(connection_failed)}")
        
        if connection_working:
            print(f"  ✓ Working VMs: {', '.join(connection_working)}")
        
        if connection_failed:
            print(f"  ✗ Failed VMs: {', '.join(connection_failed)}")
        
        print(f"\n🔧 ALIAS ADDITION:")
        print(f"  VMs processed: {len(connection_working)}")
        print(f"  Successful updates: {len(alias_success)}")
        print(f"  Failed updates: {len(alias_failed)}")
        
        if alias_success:
            print(f"  ✓ Success VMs: {', '.join(alias_success)}")
        
        if alias_failed:
            print(f"  ✗ Failed VMs: {', '.join(alias_failed)}")
        
        if len(alias_success) == len(connection_working):
            print("\n🎉 All accessible VMs updated successfully!")
        elif len(alias_success) > 0:
            print("\n⚠️  Some VMs updated successfully")
        else:
            print("\n❌ No VMs were updated")
        
        print("="*50)
        
        return {
            'connection_working': connection_working,
            'connection_failed': connection_failed,
            'alias_success': alias_success,
            'alias_failed': alias_failed
        }
    
    # Run the tasks in order
    connection_results = test_connections()
    alias_results = add_aliases(connection_results)
    summary = show_summary(connection_results, alias_results)

# Create the DAG
dag_instance = simple_alias_workflow()
