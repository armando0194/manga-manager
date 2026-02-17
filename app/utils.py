import logging
import sys
from pathlib import Path

def setup_logging(log_level='INFO', log_file='/logs/processor.log'):
    """Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler (stdout)
            logging.StreamHandler(sys.stdout),
            # File handler
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    
    return logging.getLogger('manga-manager')


def ensure_directory(path):
    """Ensure directory exists, create if not.
    
    Args:
        path: Directory path (string or Path object)
    
    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
