"""
Centralized logging configuration for the YouTube Shorts Automation Pipeline.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        # Format the message
        return super().format(record)


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration with file and console handlers."""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler with daily rotation
    log_file = logs_dir / f"automation_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('google_auth_httplib2').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("🚀 YouTube Shorts Automation Pipeline Started")
    logger.info(f"📝 Log Level: {log_level.upper()}")
    logger.info(f"📁 Log File: {log_file}")
    logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified module."""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)


def log_function_call(func):
    """Decorator to log function calls with timing."""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        func_name = f"{func.__qualname__}"
        
        logger.debug(f"🔧 Calling {func_name}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"✅ {func_name} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {func_name} failed after {elapsed:.2f}s: {e}")
            raise
    
    return wrapper


def create_progress_logger(name: str, total: int) -> 'ProgressLogger':
    """Create a progress logger for tracking operations."""
    return ProgressLogger(name, total)


class ProgressLogger:
    """Logger for tracking progress of operations."""
    
    def __init__(self, operation_name: str, total: int):
        self.operation_name = operation_name
        self.total = total
        self.current = 0
        self.logger = get_logger(__name__)
        self.start_time = None
    
    def start(self):
        """Start the progress tracking."""
        import time
        self.start_time = time.time()
        self.logger.info(f"🏁 Starting {self.operation_name} (0/{self.total})")
    
    def update(self, increment: int = 1, message: str = ""):
        """Update progress."""
        self.current += increment
        percentage = (self.current / self.total) * 100
        
        status_msg = f"⏳ {self.operation_name}: {self.current}/{self.total} ({percentage:.1f}%)"
        if message:
            status_msg += f" - {message}"
        
        self.logger.info(status_msg)
    
    def complete(self, message: str = ""):
        """Mark operation as complete."""
        import time
        if self.start_time:
            elapsed = time.time() - self.start_time
            completion_msg = f"✅ {self.operation_name} completed in {elapsed:.1f}s"
        else:
            completion_msg = f"✅ {self.operation_name} completed"
        
        if message:
            completion_msg += f" - {message}"
        
        self.logger.info(completion_msg)