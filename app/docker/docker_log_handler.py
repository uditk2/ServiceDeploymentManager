
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
                return CommandResult(success=False, error=stderr)

            if stdout and retain_logs:
                logger.info(f"Command output logged to {log_file}")

            return CommandResult(success=True, output=stdout)

        except Exception as e:
            error_msg = f"Error executing command {command}: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)


class ContainerLogHandler:
    def __init__(self, logs_path):
        self.redis_store = redis_store
        self.process_key_prefix = "container_logger:process:"
        self.hostname = "synergiqai"
        self.stop_event = Event()  # For graceful shutdown
        self.processes = {}  # Track processes by container name
        # Start cleaner as thread
        self.cleaner_thread = self.start_cleaner()
        self.project_logs_path = logs_path

    def start_cleaner(self):
        """Start the cleaner thread"""
        thread = Thread(target=self._run_cleanup_service, daemon=True)
        thread.start()
        return thread

    def setup_container_logging(self, container_name, retain_logs=False):
        try:
            log_dir = os.path.join(self.project_logs_path, container_name)
            os.makedirs(log_dir, exist_ok=True)

            log_file = os.path.join(log_dir, 'service.log')
            # Remove any existing log with the same name
            if os.path.exists(log_file) and not retain_logs:
                os.remove(log_file)
            handler = RotatingFileHandler(
                log_file,
                maxBytes=500*1024,
                backupCount=5
            )

            # Check if container exists and is running
            container_status = os.popen(f'docker inspect --format="{{{{.State.Status}}}}" {container_name}').read().strip()
            if container_status != "running":
                logger.error(f"Container {container_name} is not running, status: {container_status}")
                return False

            # Create a process to capture logs
            process = subprocess.Popen(
                ['docker', 'logs', '-f', container_name],
                stdout=handler.stream,
                stderr=subprocess.STDOUT,
                close_fds=True
            )

            # Monitor container status in a separate thread
            monitor_thread = Thread(
                target=self._monitor_container,
                args=(container_name, process.pid),
                daemon=True
            )
            monitor_thread.start()

            logger.info(f"Started logging process with {process.pid}")
            process_info = {
                'pid': process.pid,
                'container_name': container_name,
                'start_time': time.time(),
                'host': self.hostname,
                'status': 'running'
            }

            # Store in local dict for tracking
            self.processes[container_name] = {
                'process_info': process_info,
                'monitor_thread': monitor_thread
            }

            redis_key = f"{self.process_key_prefix}{self.hostname}:{container_name}"

            # Store process info in Redis
            self.redis_store.set_value(redis_key, json.dumps(process_info))

            logger.info(f"Container logs being written to {log_file} on host {self.hostname}")
            return True

        except Exception as e:
            logger.error(f"Error setting up container logging: {traceback.format_exc()}")
            return False

    def _monitor_container(self, container_name, log_pid):
        """Monitor container status and cleanup logging if container stops"""
        redis_key = f"{self.process_key_prefix}{self.hostname}:{container_name}"

        while not self.stop_event.is_set():
            try:
                status = os.popen(f'docker inspect --format="{{{{.State.Status}}}}" {container_name}').read().strip()
                if status not in ["running", "created"]:
                    logger.warning(f"Container {container_name} is not running (status: {status}), stopping logging")
                    self._cleanup_process(redis_key)
                    break
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error monitoring container {container_name}: {str(e)}")
                break

    def _run_cleanup_service(self):
        """Thread service to cleanup zombie processes"""
        while not self.stop_event.is_set():
            try:
                pattern = f"{self.process_key_prefix}{self.hostname}:*"
                process_keys = self.redis_store.get_keys_by_pattern(pattern)

                for key in process_keys:
                    if self.stop_event.is_set():
                        break

                    process_info_str = self.redis_store.get_value(key)
                    if not process_info_str:
                        continue

                    process_info = json.loads(process_info_str)

                    try:
                        logger.info(f"Checking process {json.dumps(process_info)}")
                        pid = int(process_info['pid'])
                        process = psutil.Process(pid)

                        if process.status() == psutil.STATUS_ZOMBIE or \
                           time.time() - float(process_info['start_time']) > 7200:
                            self._cleanup_process(key)

                    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                        self.redis_store.delete_key(key)

            except Exception as e:
                logger.error(f"Error in cleanup service: {traceback.format_exc()}")

            # Use standard time.sleep instead of gevent.sleep
            time.sleep(300)

    def shutdown(self):
        """Graceful shutdown method"""
        logger.info("Initiating container log handler shutdown")
        self.stop_event.set()

        # Cleanup all processes for this host
        pattern = f"{self.process_key_prefix}{self.hostname}:*"
        process_keys = self.redis_store.get_keys_by_pattern(pattern)

        for key in process_keys:
            self._cleanup_process(key)

        # Wait for cleaner thread to finish
        if self.cleaner_thread.is_alive():
            self.cleaner_thread.join(timeout=10)

    def _cleanup_process(self, redis_key):
        """Internal method to cleanup a process and its Redis entry

        Args:
            redis_key (str): Redis key for the process info

        Returns:
            bool: True if cleanup successful, False otherwise
        """
        try:
            # Get process info from Redis
            process_info_str = self.redis_store.get_value(redis_key)
            if not process_info_str:
                return False

            process_info = json.loads(process_info_str)

            # Only cleanup processes on this host
            if process_info['host'] != self.hostname:
                return False

            try:
                # Attempt to terminate the process
                logger.info(f"Cleaning up process {json.dumps(process_info)}")
                pid = int(process_info['pid'])
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

                logger.info(f"Cleaned up process {pid} for container {process_info['container_name']}")

                # Clean up from our local tracking dict
                container_name = process_info['container_name']
                if container_name in self.processes:
                    del self.processes[container_name]

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone or can't access it
                logger.debug(f"Process {process_info['pid']} already gone")

            finally:
                # Always clean up Redis entry
                self.redis_store.delete_key(redis_key)
                return True

        except Exception as e:
            logger.error(f"Error cleaning up process: {traceback.format_exc()}")
            return False