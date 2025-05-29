#!/usr/bin/env python3
"""
Docker Compose Log Parser
A lightweight tool to fetch logs from the last X minutes from Docker Compose log files.

Usage:
    python log_parser.py --minutes 5
    python log_parser.py --minutes 10 --file /path/to/logs.txt --service web-app
    python log_parser.py --since "2025-05-26 14:30:00" --until "2025-05-26 14:35:00"
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple
import os

class DockerLogParser:
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        if not self.log_file.exists():
            raise FileNotFoundError(f"Log file not found: {log_file}")
    
    def extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from Docker Compose log line."""
        # Docker timestamp patterns
        patterns = [
            # Docker Compose: 2025-05-26T14:30:15.123456789Z
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z?',
            # Alternative: 2025-05-26 14:30:15
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            # Syslog format: May 26 14:30:15
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                timestamp_str = match.group(1)
                try:
                    if 'T' in timestamp_str:
                        # ISO format
                        return datetime.fromisoformat(timestamp_str.replace('Z', ''))
                    elif re.match(r'\d{4}-\d{2}-\d{2}\s', timestamp_str):
                        # Standard format
                        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Syslog format - add current year
                        current_year = datetime.now().year
                        return datetime.strptime(f"{current_year} {timestamp_str}", '%Y %b %d %H:%M:%S')
                except ValueError:
                    continue
        return None
    
    def extract_service_name(self, line: str) -> Optional[str]:
        """Extract service name from Docker Compose log line."""
        # Docker Compose format: service_1 | message  or  service-name_1 | message
        match = re.match(r'^([a-zA-Z0-9_-]+?)(?:_\d+)?\s*\|\s*', line)
        if match:
            return match.group(1)
        return None
    
    def get_logs_by_minutes(self, minutes: int, service_filter: Optional[str] = None, 
                           tail_lines: int = None) -> List[Tuple[datetime, str]]:
        """Get logs from the last X minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return self._get_logs_by_timerange(cutoff_time, datetime.now(), service_filter, tail_lines)
    
    def get_logs_by_timerange(self, since: str, until: str, 
                             service_filter: Optional[str] = None,
                             tail_lines: int = None) -> List[Tuple[datetime, str]]:
        """Get logs between two timestamps."""
        since_dt = datetime.fromisoformat(since.replace('Z', ''))
        until_dt = datetime.fromisoformat(until.replace('Z', ''))
        return self._get_logs_by_timerange(since_dt, until_dt, service_filter, tail_lines)
    
    def _get_logs_by_timerange(self, start_time: datetime, end_time: datetime,
                              service_filter: Optional[str] = None,
                              tail_lines: int = None) -> List[Tuple[datetime, str]]:
        """Internal method to get logs by time range."""
        matching_logs = []
        processed_lines = 0
        
        # Estimate tail lines if not provided
        if tail_lines is None:
            minutes_diff = (end_time - start_time).total_seconds() / 60
            tail_lines = max(1000, int(minutes_diff * 100))  # ~100 lines per minute estimate
        
        try:
            # Read from end of file for efficiency
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as file:
                # Get file size for progress indication
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                
                # Read last N lines efficiently
                lines = self._tail_file(file, tail_lines)
                
                for line in lines:
                    processed_lines += 1
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Extract timestamp
                    timestamp = self.extract_timestamp(line)
                    if not timestamp:
                        continue
                    
                    # Check time range
                    if not (start_time <= timestamp <= end_time):
                        continue
                    
                    # Apply service filter
                    if service_filter:
                        service_name = self.extract_service_name(line)
                        if not service_name or service_filter.lower() not in service_name.lower():
                            continue
                    
                    matching_logs.append((timestamp, line))
                    
        except Exception as e:
            print(f"Error reading log file: {e}", file=sys.stderr)
            return []
        
        # Sort by timestamp
        matching_logs.sort(key=lambda x: x[0])
        return matching_logs
    
    def _tail_file(self, file, num_lines: int) -> List[str]:
        """Efficiently read last N lines from file."""
        buffer_size = 8192
        file.seek(0, 2)  # Go to end of file
        file_size = file.tell()
        
        lines = []
        buffer = ""
        
        # Read file backwards in chunks
        pos = file_size
        
        while len(lines) < num_lines and pos > 0:
            # Calculate chunk size
            chunk_size = min(buffer_size, pos)
            pos -= chunk_size
            
            # Read chunk
            file.seek(pos)
            chunk = file.read(chunk_size)
            
            # Prepend to buffer
            buffer = chunk + buffer
            
            # Split into lines
            if '\n' in buffer:
                parts = buffer.split('\n')
                buffer = parts[0]  # Keep incomplete line
                lines = parts[1:] + lines
        
        # Add remaining buffer if it contains data
        if buffer:
            lines = [buffer] + lines
        
        return lines[-num_lines:] if len(lines) > num_lines else lines

def format_output(logs: List[Tuple[datetime, str]], show_service: bool = True) -> None:
    """Format and print the log output."""
    if not logs:
        print("No matching logs found.")
        return
    
    print(f"\nFound {len(logs)} matching log entries:")
    print("-" * 80)
    
    for timestamp, line in logs:
        if show_service:
            print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {line}")
        else:
            print(line)

def main():
    parser = argparse.ArgumentParser(
        description='Parse Docker Compose logs by time range',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --minutes 5
  %(prog)s --minutes 10 --file /var/log/docker-compose.log
  %(prog)s --minutes 15 --service web-app
  %(prog)s --since "2025-05-26T14:30:00" --until "2025-05-26T14:35:00"
  %(prog)s --minutes 5 --service api --tail-lines 5000
        """
    )
    
    # File options
    parser.add_argument(
        '--file', '-f',
        default='/var/log/docker-compose.log',
        help='Path to log file (default: /var/log/docker-compose.log)'
    )
    
    # Time range options (mutually exclusive)
    time_group = parser.add_mutually_exclusive_group(required=True)
    time_group.add_argument(
        '--minutes', '-m',
        type=int,
        help='Get logs from last X minutes'
    )
    time_group.add_argument(
        '--since',
        help='Start time (ISO format: 2025-05-26T14:30:00 or 2025-05-26 14:30:00)'
    )
    
    parser.add_argument(
        '--until',
        help='End time (ISO format, required with --since)'
    )
    
    # Filtering options
    parser.add_argument(
        '--service', '-s',
        help='Filter by service name'
    )
    
    parser.add_argument(
        '--tail-lines',
        type=int,
        help='Number of lines to read from end of file (default: auto-calculated)'
    )
    
    # Output options
    parser.add_argument(
        '--no-timestamp',
        action='store_true',
        help='Hide timestamp in output'
    )
    
    parser.add_argument(
        '--count-only',
        action='store_true',
        help='Only show count of matching lines'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.since and not args.until:
        parser.error("--until is required when using --since")
    
    try:
        # Initialize parser
        log_parser = DockerLogParser(args.file)
        
        # Get logs
        if args.minutes:
            print(f"Searching for logs from last {args.minutes} minutes...")
            if args.service:
                print(f"Filtering by service: {args.service}")
            logs = log_parser.get_logs_by_minutes(
                args.minutes, 
                args.service, 
                args.tail_lines
            )
        else:
            print(f"Searching for logs from {args.since} to {args.until}...")
            if args.service:
                print(f"Filtering by service: {args.service}")
            logs = log_parser.get_logs_by_timerange(
                args.since, 
                args.until, 
                args.service,
                args.tail_lines
            )
        
        # Output results
        if args.count_only:
            print(f"Found {len(logs)} matching log entries")
        else:
            format_output(logs, not args.no_timestamp)
            
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error parsing timestamp: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()