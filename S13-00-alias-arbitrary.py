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

# Aliases to add - Add your own here!
ALIASES = [
    "alias bb='clear'",
    "alias ll='ls -la'",
    "alias ..='cd ..'",
    "alias h='history'",
]

def run_ssh_command(vm_ip, command):
    """
    Simple function to run SSH command on a VM
    Returns True if successful, False if failed
    """
    try:
        # Connect to VM
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vm_ip, username=USERNAME, key_filename=SSH_KEY, timeout=10)
        
        # Run command
        stdin, stdout, stderr = ssh.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        
        ssh.close()
        
        # Return True if command worked
        return exit_code == 0
        
    except Exception as e:
        print(f"Error connecting to {vm_ip}: {e}")
        return False

@dag(
    dag_id='simple_alias_manager',
    description='Add bash aliases to multiple VMs - Simple version',
    schedule_interval=None,  # Run manually
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['aliases', 'simple']
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
            if run_ssh_command(vm['ip'], 'echo "test"'):
                print(f"✓ {vm['hostname']} - OK")
                working_vms.append(vm)
            else:
                print(f"✗ {vm['hostname']} - FAILED")
                failed_vms.append(vm)
        
        print(f"\nResults: {len(working_vms)} working, {len(failed_vms)} failed")
        return working_vms
    
    @task
    def add_aliases(working_vms):
        """Add aliases to all working VMs"""
        print("Adding aliases to VMs...")
        
        success_count = 0
        
        for vm in working_vms:
            print(f"\nAdding aliases to {vm['hostname']} ({vm['ip']})...")
            
            # Create backup first
            backup_cmd = "cp ~/.bashrc ~/.bashrc.backup 2>/dev/null || touch ~/.bashrc"
            if not run_ssh_command(vm['ip'], backup_cmd):
                print(f"Warning: Could not backup .bashrc on {vm['hostname']}")
            
            # Add each alias
            vm_success = True
            for alias in ALIASES:
                # Command to add alias to .bashrc
                add_cmd = f'echo "{alias}" >> ~/.bashrc'
                
                if run_ssh_command(vm['ip'], add_cmd):
                    print(f"  ✓ Added: {alias}")
                else:
                    print(f"  ✗ Failed: {alias}")
                    vm_success = False
            
            if vm_success:
                print(f"✓ {vm['hostname']} - All aliases added successfully")
                success_count += 1
            else:
                print(f"✗ {vm['hostname']} - Some aliases failed")
        
        print(f"\nFinal result: {success_count}/{len(working_vms)} VMs updated successfully")
        return {"success": success_count, "total": len(working_vms)}
    
    @task
    def show_summary(results):
        """Show final summary"""
        success = results['success']
        total = results['total']
        
        print("\n" + "="*40)
        print("ALIAS ADDITION SUMMARY")
        print("="*40)
        print(f"VMs processed: {total}")
        print(f"Successful: {success}")
        print(f"Failed: {total - success}")
        
        if success == total:
            print("🎉 All VMs updated successfully!")
        elif success > 0:
            print("⚠️  Some VMs updated successfully")
        else:
            print("❌ No VMs were updated")
        
        print("="*40)
        return results
    
    # Run the tasks in order
    working_vms = test_connections()
    results = add_aliases(working_vms)
    summary = show_summary(results)
    
    # Set dependencies
    working_vms >> results >> summary

# Create the DAG
dag_instance = simple_alias_workflow()
