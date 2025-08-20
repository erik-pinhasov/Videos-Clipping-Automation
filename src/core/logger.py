"""
Comprehensive logging system with progress tracking.
"""

import os
import sys
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Any


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    try:
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Create log filename with date
        log_filename = f"logs/automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Set third-party loggers to WARNING
        for logger_name in ['urllib3', 'requests', 'googleapiclient', 'google', 'yt_dlp']:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        
        print(f"Logging initialized - Log file: {log_filename}")
        
    except Exception as e:
        print(f"Logging setup failed: {e}")
        logging.basicConfig(level=logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_function_call(func):
    """Decorator to log function calls."""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


class ProgressLogger:
    """Simple progress logger for tracking operations."""
    
    def __init__(self, task_name: str, total: int):
        self.task_name = task_name
        self.total = total
        self.current = 0
        self.start_time = None
        self.logger = get_logger("Progress")
    
    def start(self):
        """Start progress tracking."""
        self.start_time = time.time()
        self.logger.info(f"Starting {self.task_name} (0/{self.total})")
    
    def update(self, increment: int = 1, message: str = ""):
        """Update progress."""
        self.current += increment
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        
        status = f"{self.task_name}: {self.current}/{self.total} ({percentage:.1f}%)"
        if message:
            status += f" - {message}"
        
        self.logger.info(status)
    
    def complete(self, message: str = ""):
        """Complete progress tracking."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        status = f"{self.task_name} completed in {elapsed:.1f}s"
        if message:
            status += f" - {message}"
        
        self.logger.info(status)