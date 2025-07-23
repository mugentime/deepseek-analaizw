"""
Logging configuration for the Efficient Trading Platform
"""

import logging
import os
from datetime import datetime

def setup_logging():
    """Setup logging configuration for the application"""
    
    # Get log level from environment variable
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Setup root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler
            logging.StreamHandler(),
            # File handler
            logging.FileHandler(
                f'logs/trading_platform_{datetime.now().strftime("%Y%m%d")}.log',
                mode='a'
            )
        ]
    )
    
    # Configure specific loggers
    loggers = {
        'werkzeug': logging.WARNING,  # Reduce Flask request logs
        'urllib3': logging.WARNING,   # Reduce HTTP request logs
        'requests': logging.WARNING,  # Reduce requests logs
        'app': getattr(logging, log_level),
        'rebalancing_module': getattr(logging, log_level)
    }
    
    for logger_name, level in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    # Log startup message
    logger = logging.getLogger('app')
    logger.info("=" * 50)
    logger.info("🚀 Efficient Trading Platform Starting")
    logger.info(f"Log Level: {log_level}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 50)

def get_logger(name):
    """Get a logger instance with the given name"""
    return logging.getLogger(name)