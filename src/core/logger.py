"""Logging system for YouTube to Rumble automation."""

import sys
import logging
from pathlib import Path
from datetime import datetime


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with file and console output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    try:
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Create timestamped log filename
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
        
        # Reduce noise from third-party libraries
        for logger_name in ['urllib3', 'requests', 'googleapiclient', 'google', 'yt_dlp']:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        
        print(f"Logging initialized - Log file: {log_filename}")
        
    except Exception as e:
        print(f"Logging setup failed: {e}")
        logging.basicConfig(level=logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)