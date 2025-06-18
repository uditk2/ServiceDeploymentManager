import json
import psutil
import time
from logging.handlers import RotatingFileHandler
import os
import traceback
import shlex
import subprocess
from app.transient_store.redis_store import redis_store
from threading import Event, Thread
from app.custom_logging import logger
from .helper_functions import get_log_file_path
from app.workspace_monitoring.compose_log_watcher import ComposeLogWatcher


class CommandResult:
    def __init__(self, success: bool, output: str = None, error: str = None, deploy_info: str = None):
        self.success = success
        self.output = output
        self.error = error
        self.deploy_info = deploy_info

    def to_dict(self):
        """Convert CommandResult to a dictionary."""
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'deploy_info': self.deploy_info
        }
    def set_deploy_info(self, deploy_info: str):
        """Set deployment information."""
        self.deploy_info = deploy_info
        
    def __repr__(self):
        """Return a JSON string representation of the CommandResult object."""
        return json.dumps({
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'deploy_info': self.deploy_info
        })

class DockerCommandWithLogHandler:
    def __init__(self, logs_path=None):
        self.project_logs_path = logs_path

    def run_docker_commands_with_logging(self, command: str, container_name: str, retain_logs: bool = False) -> CommandResult:
        try:
            log_dir = os.path.join(self.project_logs_path, container_name)
            os.makedirs(log_dir, exist_ok=True)

            log_file = os.path.join(log_dir, 'build.log')

            # Remove any existing log with the same name
            if os.path.exists(log_file) and not retain_logs:
                os.remove(log_file)

            # Set up the rotating file handler
            handler = RotatingFileHandler(
                log_file,
                maxBytes=500*1024,
                backupCount=5
            )

            # Run the command and capture output
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = process.communicate()
            success = process.returncode == 0

            # Log the output to build.log
            with open(log_file, 'a') as f:
                f.write(f"Command: {command}\n")
                f.write(f"Output:\n{stdout}\n")
                if stderr:
                    f.write(f"Errors:\n{stderr}\n")
                f.write(f"Status: {'Success' if success else 'Failed'}\n")
                f.write("-" * 80 + "\n")

            if stderr and not success:
                logger.error(f"Command failed: {stderr}")
                return CommandResult(success=False, output=stdout, error=stderr)

            if stdout and retain_logs:
                logger.info(f"Command output logged to {log_file}")

            return CommandResult(success=True, output=stdout)

        except Exception as e:
            error_msg = f"Error executing command {command}: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)


class DockerLogHandler:
    def __init__(self, log_file_path):
        """
        Initialize a handler that captures command output to a log file
        
        Args:
            log_file_path (str): Path to the log file
        """
        self.log_file_path = log_file_path
        log_dir = os.path.dirname(log_file_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Create or truncate the log file
        with open(log_file_path, 'w') as f:
            f.write(f"=== Log started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")

    def run_command_with_logging(self, command: str) -> CommandResult:
        """
        Run a command and log the output to a file
        
        Args:
            command (str): Command to execute
            
        Returns:
            CommandResult: Result of the command execution
        """
        try:
            logger.info(f"Running command with logging: {command}")
            
            # Set up the logging handler with rotation
            handler = RotatingFileHandler(
                self.log_file_path,
                maxBytes=1024*1024,  # 1MB
                backupCount=5,
                mode='a'  # Append mode
            )
            
            # Add timestamp to the log
            with open(self.log_file_path, 'a') as f:
                f.write(f"\n=== Command executed at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Command: {command}\n\n")
            
            # Run the command and stream output to the log file
            with open(self.log_file_path, 'a') as log_file:
                process = subprocess.Popen(
                    shlex.split(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1  # Line buffered
                )
                
                stdout, stderr = process.communicate()
                success = process.returncode == 0
                
                # Write output and errors to the log file
                if stdout:
                    log_file.write(f"Output:\n{stdout}\n")
                if stderr:
                    log_file.write(f"Errors:\n{stderr}\n")
                log_file.write(f"Status: {'Success' if success else 'Failed'}\n")
                log_file.write("-" * 80 + "\n")
            
            if not success:
                logger.error(f"Command failed: {stderr}")
                return CommandResult(success=False, output=stdout, error=stderr)
            
            return CommandResult(success=True, output=stdout)
            
        except Exception as e:
            error_msg = f"Error executing command {command}: {traceback.format_exc()}"
            logger.error(error_msg)
            
            # Try to log the error to the file
            try:
                with open(self.log_file_path, 'a') as f:
                    f.write(f"ERROR: {error_msg}\n")
                    f.write("-" * 80 + "\n")
            except:
                pass
                
            return CommandResult(success=False, error=error_msg)


class DockerComposeLogHandler:
    """Handles consolidated logging from all containers in a Docker Compose project"""
    
    def __init__(self, logs_path):
        """
        Initialize the Docker Compose Log Handler
        
        Args:
            logs_path (str): Base directory for logs
        """
        self.project_logs_path = logs_path
        self.processes = {}  # Store processes by project name
        self.log_watchers = {}  # Store log watcher instances by project name
        self.stop_event = Event()
    
    def follow_compose_logs(self, compose_file, project_name, retain_logs=False):
        """
        Follow logs from all containers in a Docker Compose setup and write to a single log file.
        This is similar to running 'docker compose logs -f' but outputs to a file.
        
        Args:
            compose_file (str): Path to the docker-compose.yml file
            project_name (str): Docker Compose project name
            retain_logs (bool): Whether to retain existing logs (default: False)
            
        Returns:
            bool: True if logging was set up successfully, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.project_logs_path, exist_ok=True)
            
            # Set up a single log file for all containers in this compose project
            log_file = get_log_file_path(project_base_path=self.project_logs_path, project_name=project_name)
            
            # Remove existing log if not retaining
            if os.path.exists(log_file) and not retain_logs:
                os.remove(log_file)
                
            handler = RotatingFileHandler(
                log_file,
                maxBytes=1024*1024,  # 1MB
                backupCount=5
            )
            
            # Command to follow all logs from the Docker Compose project
            cmd = f"docker compose -f {compose_file} -p {project_name} logs -f --timestamps"
            
            logger.info(f"Starting Docker Compose logs for project {project_name}")
            
            # Create a process to capture logs from all containers
            process = subprocess.Popen(
                shlex.split(cmd),
                stdout=handler.stream,
                stderr=subprocess.STDOUT,
                close_fds=True
            )
            
            # Create and start log watcher for this stack
            log_watcher = ComposeLogWatcher(
                stack_name=project_name,
                compose_file=compose_file,
                project_name=project_name,
                project_path=self.project_logs_path
            )
            # For new deployments (retain_logs=False), start from beginning to capture full deployment
            # For restarts (retain_logs=True), resume from last position
            start_from_beginning = not retain_logs
            log_watcher.start_watching(log_file, start_from_beginning=start_from_beginning)
            self.log_watchers[project_name] = log_watcher
            
            # Start a monitoring thread for this process
            monitor_thread = Thread(
                target=self._monitor_compose_project,
                args=(project_name, compose_file, process.pid),
                daemon=True
            )
            monitor_thread.start()
            
            # Store process info
            self.processes[project_name] = {
                'pid': process.pid,
                'compose_file': compose_file,
                'project_name': project_name,
                'monitor_thread': monitor_thread,
                'log_file': log_file,
                'start_time': time.time()
            }
            
            logger.info(f"Docker Compose logs for project {project_name} being written to {log_file}")
            logger.info(f"Watchdog log watcher started for Docker Compose stack: {project_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Docker Compose logging: {traceback.format_exc()}")
            return False
    
    def _monitor_compose_project(self, project_name, compose_file, log_pid):
        """
        Monitor Docker Compose project and cleanup logging when project stops
        
        Args:
            project_name (str): Docker Compose project name
            compose_file (str): Path to the compose file
            log_pid (int): PID of the logging process
        """
        while not self.stop_event.is_set():
            try:
                # Check if the Docker Compose project is still running
                # This command lists running containers in the project
                cmd = f"docker compose -f {compose_file} -p {project_name} ps --services --filter status=running"
                result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
                
                running_services = result.stdout.strip().split('\n')
                running_services = [s for s in running_services if s]  # Remove empty strings
                
                if not running_services:
                    logger.warning(f"No running containers found for project {project_name}")
                    ## We need the logs for debugging, so we don't stop the logging process here
                    ## self._cleanup_process(project_name)
                    break
                    
                # Check at intervals
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error monitoring Docker Compose project {project_name}: {str(e)}")
                break
    
    def _cleanup_process(self, project_name):
        """
        Cleanup a logging process for a Docker Compose project
        
        Args:
            project_name (str): Name of the Docker Compose project
        """
        try:
            # Stop log watcher if it exists
            if project_name in self.log_watchers:
                logger.info(f"Stopping watchdog log watcher for stack: {project_name}")
                self.log_watchers[project_name].stop_watching()
                del self.log_watchers[project_name]
            
            if project_name not in self.processes:
                return False
                
            process_info = self.processes[project_name]
            
            try:
                # Attempt to terminate the process
                logger.info(f"Cleaning up logging process for Docker Compose project {project_name}")
                pid = process_info['pid']
                process = psutil.Process(pid)
                
                # Send SIGTERM
                process.terminate()
                
                # Wait for process to terminate
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    # If SIGTERM didn't work, force kill
                    process.kill()
                    process.wait(timeout=2)
                
                logger.info(f"Cleaned up logging process {pid} for Docker Compose project {project_name}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone or can't access it
                logger.debug(f"Process {process_info['pid']} already gone")
                
            finally:
                # Clean up from our tracking dict
                del self.processes[project_name]
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning up process for Docker Compose project {project_name}: {traceback.format_exc()}")
            return False
    
    def shutdown(self):
        """Graceful shutdown of all logging processes"""
        logger.info("Initiating Docker Compose log handler shutdown")
        self.stop_event.set()
        
        # Stop all log watchers
        for project_name, log_watcher in list(self.log_watchers.items()):
            logger.info(f"Stopping watchdog log watcher for stack: {project_name}")
            log_watcher.stop_watching()
        self.log_watchers.clear()
        
        # Clean up all processes
        for project_name in list(self.processes.keys()):
            self._cleanup_process(project_name)