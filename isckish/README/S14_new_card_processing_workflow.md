# Card Batch Processing Workflow

> **Secure SSH-based file processing pipeline for Apache Airflow 2.9+**

Automated detection, transfer, and processing of card batch files between Linux servers using SSH key authentication and modern TaskFlow API.

[![Airflow](https://img.shields.io/badge/Airflow-2.9+-blue.svg)](https://airflow.apache.org/)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Overview

This workflow automates the secure transfer and processing of card batch files between two Linux servers in a high-availability Airflow environment. It uses SSH key-based authentication (no passwords, no FTP) and implements a sensor-based detection pattern for reliable file processing.

### Key Features

- ✅ **Modern TaskFlow API** - Uses `@dag`, `@task`, and `@task.sensor` decorators
- ✅ **Secure SSH** - Ed25519 key-based authentication only
- ✅ **High Availability** - Compatible with Celery executor and multi-worker setups
- ✅ **Sensor-Based Detection** - Automatic file discovery with configurable polling
- ✅ **No Cleanup Required** - Source files remain intact for audit purposes
- ✅ **Production Ready** - Error handling, retries, and comprehensive logging

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Airflow HA Environment                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Scheduler   │  │   Workers    │  │   Webserver  │          │
│  │   (Multi)    │  │ (Celery x2)  │  │  (HAProxy)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                    │                │
│         └─────────────────┴────────────────────┘                │
│                           │                                     │
│         ┌─────────────────┴─────────────────┐                  │
│         │                                   │                  │
│    RabbitMQ (3-node)              PostgreSQL (3-node)          │
│         Cluster                          + Patroni             │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ SSH Connection
                           ▼
        ┌──────────────────────────────────────────┐
        │           External Servers                │
        │                                           │
        │  ┌─────────────┐      ┌─────────────┐   │
        │  │  ftp (src)  │ SSH  │ target-1    │   │
        │  │ 10.101.20.164├─────→│ 10.101.20.201│  │
        │  └─────────────┘      └─────────────┘   │
        └──────────────────────────────────────────┘
```

### Workflow Steps

```mermaid
graph LR
    A[Sensor: Detect Files] -->|Files Found| B[Get File List]
    B --> C[Transfer Files via SSH]
    C --> D[Process Files]
    D --> E[Generate Reports]
```

---

## 📋 Prerequisites

### Infrastructure Requirements

- **Airflow**: Version 2.9 or higher
- **Python**: 3.9+
- **Executor**: CeleryExecutor (recommended for HA)
- **Message Broker**: RabbitMQ cluster (3 nodes)
- **Database**: PostgreSQL with Patroni (3 nodes)

### Server Configuration

| Server | IP | Role | Required Access |
|--------|---------|------|----------------|
| `ftp` | `10.101.20.164` | Source | SSH with Ed25519 key |
| `target-1` | `10.101.20.201` | Destination | SSH with Ed25519 key |

### Dependencies

```bash
pip install paramiko>=2.8.0
```

---

## 🚀 Installation

### 1. Deploy DAG File

```bash
# Copy to Airflow DAGs folder (NFS-mounted in HA setup)
cp S14_new_card_processing_workflow.py /home/rocky/airflow/dags/

# Verify no import errors
airflow dags list-import-errors
```

### 2. Deploy Processing Script

On **target-1** server:

```bash
# Create scripts directory
ssh rocky@10.101.20.201
mkdir -p /home/rocky/scripts

# Deploy processor script
vi /home/rocky/scripts/card_processor.py
# (See card_processor.py in repository)

# Make executable
chmod +x /home/rocky/scripts/card_processor.py
```

### 3. Setup SSH Keys

Ensure SSH key exists on **all Celery workers**:

```bash
# On celery-1 and celery-2
ls -la /home/rocky/.ssh/id_ed25519

# Test connectivity
ssh -i /home/rocky/.ssh/id_ed25519 rocky@10.101.20.164 "echo 'OK'"
ssh -i /home/rocky/.ssh/id_ed25519 rocky@10.101.20.201 "echo 'OK'"
```

### 4. Create Directories

```bash
# On ftp server
ssh rocky@10.101.20.164 "mkdir -p /home/rocky/card/in"

# On target-1 server
ssh rocky@10.101.20.201 "mkdir -p /home/rocky/card/in"
```

### 5. Install Dependencies on Workers

```bash
# On all Celery workers
ssh rocky@10.101.20.199 "pip3 install paramiko"  # celery-1
ssh rocky@10.101.20.200 "pip3 install paramiko"  # celery-2
```

---

## ⚙️ Configuration

### DAG Settings

```python
SSH_CONFIG = {
    'user': 'rocky',
    'key_file': '/home/rocky/.ssh/id_ed25519',
    'ftp_host': '10.101.20.164',           # Source server
    'target_host': '10.101.20.201',        # Destination server
    'card_dir': '/home/rocky/card/in/',    # Working directory
    'processor_script': '/home/rocky/scripts/card_processor.py'
}

# DAG Configuration
dag_id = 'S14_new_card_processing_workflow'
schedule_interval = None  # Manual trigger or use cron
queue = 'card_processing_queue'
```

### Sensor Configuration

```python
poke_interval = 30      # Check every 30 seconds
timeout = 3600          # 1 hour timeout
mode = 'poke'           # Blocking mode (recommended for HA)
```

---

## 📝 Usage

### File Naming Convention

Card batch files must follow this pattern:
- **Prefix**: `card_batch`
- **Extension**: `.txt`
- **Examples**: `card_batch_001.txt`, `card_batch_20250110.txt`

### Sample Input File

```text
1234567890123456,John Doe,2025-12-31,GOLD
9876543210987654,Jane Smith,2026-01-15,PLATINUM
5555666677778888,Bob Johnson,2025-11-20,SILVER
```

### Trigger Workflow

**Method 1: Airflow UI**
1. Navigate to `http://10.101.20.210:8081`
2. Find `S14_new_card_processing_workflow`
3. Click **▶ Trigger DAG**

**Method 2: CLI**
```bash
airflow dags trigger S14_new_card_processing_workflow
```

**Method 3: Schedule**
```python
# Modify DAG to run daily at 2 AM
schedule_interval = '0 2 * * *'
```

### Monitor Execution

```bash
# View DAG runs
airflow dags list-runs -d S14_new_card_processing_workflow

# Check task logs
airflow tasks logs S14_new_card_processing_workflow detect_card_files <run_id>
```

---

## 📊 Workflow Details

### Task 1: Sensor - Detect Card Files
- **Function**: Polls `/home/rocky/card/in/` on ftp server
- **Pattern**: `card_batch*.txt`
- **Interval**: 30 seconds
- **Output**: List of detected file paths

### Task 2: Get File List
- **Function**: Retrieves current list of card files
- **Validation**: Ensures files still exist
- **Output**: XCom passes list to next task

### Task 3: Transfer Files
- **Protocol**: SSH/SFTP (Paramiko)
- **Source**: `ftp:/home/rocky/card/in/`
- **Destination**: `target-1:/home/rocky/card/in/`
- **Behavior**: Overwrites existing files
- **Output**: List of successfully transferred files

### Task 4: Process Files
- **Script**: `/home/rocky/scripts/card_processor.py`
- **Execution**: Remote SSH command on target-1
- **Per File Generates**:
  - `{filename}.processed` - Records with `PROCESSED:` prefix
  - `{filename}.report` - Summary with timestamp and count

---

## 🔍 Output Examples

### Processed File
```
# Card Batch Processing Report
# File: card_batch_001.txt
# Processed: 2025-10-11 14:30:45
# Records: 3
============================================================

PROCESSED: 1234567890123456,John Doe,2025-12-31,GOLD
PROCESSED: 9876543210987654,Jane Smith,2026-01-15,PLATINUM
PROCESSED: 5555666677778888,Bob Johnson,2025-11-20,SILVER
```

### Report File
```
Card Batch Processing Report
============================================================
Input File:     card_batch_001.txt
Processed:      2025-10-11 14:30:45
Total Records:  3
Output Files:
  - card_batch_001.txt.processed
  - card_batch_001.txt.report
============================================================
Status:         SUCCESS
```

---

## 🐛 Troubleshooting

### DAG Import Errors

```bash
# Check for import errors
airflow dags list-import-errors

# Test DAG file directly
python3 /home/rocky/airflow/dags/S14_new_card_processing_workflow.py
```

### SSH Connection Issues

```bash
# Test SSH from worker
ssh -i /home/rocky/.ssh/id_ed25519 rocky@10.101.20.164 "ls /home/rocky/card/in/"

# Verify key permissions
chmod 600 /home/rocky/.ssh/id_ed25519
```

### Paramiko Not Found

```bash
# Install on all workers
pip3 install paramiko

# Verify installation
python3 -c "import paramiko; print(paramiko.__version__)"
```

### Sensor Timeout

```bash
# Check if files exist
ssh rocky@10.101.20.164 "ls -lh /home/rocky/card/in/card_batch*.txt"

# Increase timeout in DAG
timeout = 7200  # 2 hours
```

### Worker Connection Issues

If workers lose RabbitMQ/PostgreSQL connections, deploy the health check DAG:
```bash
# See S15_worker_health_check.py
# Keeps workers active every 15 minutes
```



---

## 📈 Performance Considerations

### High Availability Setup
- **Scheduler**: Multi-scheduler (2 instances) prevents single point of failure
- **Workers**: Celery workers (2+) for parallel task execution
- **Database**: PostgreSQL + Patroni for automatic failover
- **Message Queue**: RabbitMQ cluster with mirrored queues
- **Storage**: NFS HA with active/passive failover

### Scalability
- **Horizontal**: Add more Celery workers for higher throughput
- **File Size**: Tested with files up to 10MB (adjust timeouts for larger)
- **Concurrency**: Process multiple batches in parallel with dynamic DAG runs

---


## 📄 License

This project is licensed under the ISC COrporation License - 

---

## 👥 Authors

- **Initial Development** - Mohammadamin Fereidoon


---

## 📞 Support

For issues and questions:

- **Email**: fereidoon.info@gmail.com


---
