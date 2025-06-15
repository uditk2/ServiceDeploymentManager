"""
Log Processor Module

This module contains various log processors that can be used to analyze and process
log lines from Docker Compose stacks.
"""

from app.custom_logging import logger
from .error_identifier import ErrorIdentifier

class DummyLogProcessor:
    """Dummy log processor class that gets invoked with logs from Docker Compose stacks"""
    
    def __init__(self, stack_name: str):
        self.stack_name = stack_name
        self.processed_count = 0
        self.error_count = 0
        self.warning_count = 0
    
    def process_log(self, log_lines: list):
        """
        Process a list of log lines from the Docker Compose stack
        
        Args:
            log_lines (list): List of log lines to process
        """
        logger.info(f"[LogProcessor-{self.stack_name}] Starting to process {len(log_lines)} log lines")
        
        result = ErrorIdentifier().identify_errors("\n".join(log_lines))
        if result and result["errors"]:
            ## for each error log, send it to /task-handler/api
            logger.info(f"[LogProcessor-{self.stack_name}] Identified {len(result['errors'])} error logs")

    def get_stats(self):
        """Get processing statistics"""
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'stack_name': self.stack_name
        }


class AdvancedLogProcessor(DummyLogProcessor):
    """Advanced log processor with more sophisticated analysis"""
    
    def __init__(self, stack_name: str):
        super().__init__(stack_name)
        self.performance_issues = 0
        self.deployment_events = 0
        
    def process_log_line(self, log_line: str):
        """Process log line with advanced analysis"""
        # Call parent processing first
        super().process_log_line(log_line)
        
        line_lower = log_line.lower()
        
        # Detect performance issues
        if any(pattern in line_lower for pattern in ['timeout', 'slow', 'performance', 'memory', 'cpu']):
            self.performance_issues += 1
            logger.warning(f"[AdvancedProcessor-{self.stack_name}] Performance issue detected: {log_line.strip()}")
        
        # Detect deployment events
        if any(pattern in line_lower for pattern in ['deployed', 'starting', 'stopped', 'restarted']):
            self.deployment_events += 1
            logger.info(f"[AdvancedProcessor-{self.stack_name}] Deployment event: {log_line.strip()}")
    
    def get_stats(self):
        """Get advanced processing statistics"""
        stats = super().get_stats()
        stats.update({
            'performance_issues': self.performance_issues,
            'deployment_events': self.deployment_events
        })
        return stats