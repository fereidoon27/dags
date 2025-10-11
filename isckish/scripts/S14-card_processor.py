#!/usr/bin/env python3
"""
Card Batch File Processor
Processes card batch files and generates .processed and .report outputs
Usage: python3 card_processor.py <file_path>
"""

import sys
from datetime import datetime
from pathlib import Path


def process_card_file(input_file_path: str) -> dict:
    """
    Process a card batch file and generate outputs

    Args:
        input_file_path: Path to the input .txt file

    Returns:
        dict: Processing results with counts and status
    """
    input_path = Path(input_file_path)

    # Validate input file
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file_path}")

    if not input_path.is_file():
        raise ValueError(f"Not a file: {input_file_path}")

    # Define output paths
    processed_path = input_path.with_suffix(input_path.suffix + '.processed')
    report_path = input_path.with_suffix(input_path.suffix + '.report')

    # Processing timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"Processing: {input_path.name}")
    print(f"Timestamp: {timestamp}")

    # Read and process input file
    with open(input_path, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    record_count = len(lines)
    print(f"Records found: {record_count}")

    # Write .processed file
    print(f"Writing: {processed_path.name}")
    with open(processed_path, 'w', encoding='utf-8') as outfile:
        outfile.write(f"# Card Batch Processing Report\n")
        outfile.write(f"# File: {input_path.name}\n")
        outfile.write(f"# Processed: {timestamp}\n")
        outfile.write(f"# Records: {record_count}\n")
        outfile.write(f"{'=' * 60}\n\n")

        for idx, line in enumerate(lines, 1):
            processed_line = f"PROCESSED: {line.rstrip()}\n"
            outfile.write(processed_line)

    # Write .report file
    print(f"Writing: {report_path.name}")
    with open(report_path, 'w', encoding='utf-8') as reportfile:
        reportfile.write(f"Card Batch Processing Report\n")
        reportfile.write(f"{'=' * 60}\n")
        reportfile.write(f"Input File:     {input_path.name}\n")
        reportfile.write(f"Processed:      {timestamp}\n")
        reportfile.write(f"Total Records:  {record_count}\n")
        reportfile.write(f"Output Files:\n")
        reportfile.write(f"  - {processed_path.name}\n")
        reportfile.write(f"  - {report_path.name}\n")
        reportfile.write(f"{'=' * 60}\n")
        reportfile.write(f"Status:         SUCCESS\n")

    results = {
        'input_file': str(input_path),
        'processed_file': str(processed_path),
        'report_file': str(report_path),
        'record_count': record_count,
        'timestamp': timestamp,
        'status': 'SUCCESS'
    }

    print(f"\n✓ Processing complete!")
    print(f"  - Processed: {record_count} records")
    print(f"  - Generated: {processed_path.name}")
    print(f"  - Generated: {report_path.name}")

    return results


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python3 card_processor.py <file_path>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]

    try:
        results = process_card_file(input_file)
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Processing failed: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
