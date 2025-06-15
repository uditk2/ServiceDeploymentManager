#!/usr/bin/env python3
"""
Test script to verify if the log watcher is detecting file changes properly.
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from app.workspace_monitoring.compose_log_watcher import ComposeLogWatcher
from app.custom_logging import logger

def test_log_watcher():
    """Test if the log watcher can detect file changes"""
    
    print("=== Testing Log Watcher Detection ===")
    
    # Create a temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as temp_file:
        log_file_path = temp_file.name
        temp_file.write("Initial log entry\n")
    
    print(f"Created test log file: {log_file_path}")
    
    try:
        # Create and start the log watcher
        watcher = ComposeLogWatcher(
            stack_name="test-stack",
            compose_file="/tmp/test-compose.yml",
            project_name="test-project"
        )
        
        print("Starting log watcher...")
        watcher.start_watching(log_file_path)
        
        # Give the watcher time to initialize
        time.sleep(2)
        
        print("Watcher started. Now writing test log entries...")
        
        # Write some test log entries
        test_entries = [
            "Test log entry 1",
            "Test log entry 2 with ERROR pattern",
            "Test log entry 3 with WARNING pattern",
            "Test log entry 4 - normal log",
            "Test log entry 5 - final entry"
        ]
        
        for i, entry in enumerate(test_entries, 1):
            print(f"Writing entry {i}: {entry}")
            
            # Append to the log file (simulating how docker compose logs would write)
            with open(log_file_path, 'a') as f:
                f.write(f"{entry}\n")
                f.flush()  # Force immediate write
                os.fsync(f.fileno())  # Force OS to write to disk
            
            # Wait a bit between entries
            time.sleep(1)
        
        print("Finished writing entries. Waiting for processing...")
        
        # Wait for the watcher to process all entries
        time.sleep(5)
        
        # Get stats from the processor
        stats = watcher.get_stats()
        print(f"Final stats: {stats}")
        
        # Stop the watcher
        print("Stopping watcher...")
        watcher.stop_watching()
        
        # Check if the processor detected our test entries
        processor_stats = stats.get('processor_stats', {})
        processed_count = processor_stats.get('processed_count', 0)
        
        print(f"Expected: {len(test_entries)} entries")
        print(f"Processed: {processed_count} entries")
        
        if processed_count == len(test_entries):
            print("✅ SUCCESS: Log watcher detected all entries!")
            return True
        elif processed_count > 0:
            print(f"⚠️  PARTIAL: Log watcher detected {processed_count}/{len(test_entries)} entries")
            return False
        else:
            print("❌ FAILED: Log watcher detected no entries")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False
    finally:
        # Clean up
        try:
            os.unlink(log_file_path)
            print(f"Cleaned up test file: {log_file_path}")
        except:
            pass

def test_direct_file_monitoring():
    """Test direct file monitoring without the compose watcher wrapper"""
    
    print("\n=== Testing Direct File Monitoring ===")
    
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    
    class TestFileHandler(FileSystemEventHandler):
        def __init__(self):
            self.modification_count = 0
            
        def on_modified(self, event):
            if not event.is_directory:
                self.modification_count += 1
                print(f"File modified detected: {event.src_path} (count: {self.modification_count})")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as temp_file:
        log_file_path = temp_file.name
        temp_file.write("Initial content\n")
    
    log_dir = os.path.dirname(log_file_path)
    
    try:
        # Set up direct watchdog observer
        handler = TestFileHandler()
        observer = Observer()
        observer.schedule(handler, log_dir, recursive=False)
        observer.start()
        
        print(f"Started direct observer on directory: {log_dir}")
        print(f"Monitoring file: {log_file_path}")
        
        time.sleep(1)
        
        # Write test entries
        for i in range(3):
            print(f"Writing test entry {i+1}")
            with open(log_file_path, 'a') as f:
                f.write(f"Test entry {i+1}\n")
                f.flush()
                os.fsync(f.fileno())
            time.sleep(1)
        
        time.sleep(2)
        
        observer.stop()
        observer.join()
        
        print(f"Direct monitoring detected {handler.modification_count} modifications")
        
        return handler.modification_count > 0
        
    except Exception as e:
        print(f"Direct monitoring error: {str(e)}")
        return False
    finally:
        try:
            os.unlink(log_file_path)
        except:
            pass

if __name__ == "__main__":
    print("Testing log watcher functionality...\n")
    
    # Test 1: Full log watcher
    success1 = test_log_watcher()
    
    # Test 2: Direct file monitoring
    success2 = test_direct_file_monitoring()
    
    print(f"\n=== RESULTS ===")
    print(f"Log Watcher Test: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Direct Monitoring Test: {'✅ PASS' if success2 else '❌ FAIL'}")
    
    if not success1 and not success2:
        print("\n🔍 DIAGNOSIS: File monitoring system is not working")
        print("This could be due to:")
        print("- watchdog library not installed properly")
        print("- File system doesn't support inotify/fsevents")
        print("- Permission issues")
    elif not success1 and success2:
        print("\n🔍 DIAGNOSIS: Direct monitoring works, but ComposeLogWatcher has issues")
        print("The problem is likely in the ComposeLogWatcher implementation")
    elif success1:
        print("\n✅ DIAGNOSIS: Log watcher is working correctly!")
        print("The issue might be with how it's being used in the deployment flow")