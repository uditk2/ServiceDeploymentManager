import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(log_name='app', log_level=logging.INFO):
    """
    Configure logging with both file and console handlers.
    
    Args:
        log_name (str): Name of the logger and log file
        log_level (int): Logging level (e.g., logging.INFO, logging.DEBUG)
    
    Returns:
        logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create logger
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level)

    # Prevent logging from propagating to the root logger
    logger.propagate = False

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create and set up file handler (rotating log files)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f'{log_name}.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Create and set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Add handlers to logger if they haven't been added already
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Create default logger instance
logger = setup_logger()