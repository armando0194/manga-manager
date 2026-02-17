#!/usr/bin/env python3
"""
Manga Manager - Main Processing Application

Monitors download directory for new CBZ files and processes them:
1. Validates and moves to processing directory
2. Standardizes filename and metadata
3. Manages covers
4. Moves to final manga library
"""

import time
import signal
import sys
from pathlib import Path

from config import Config
from database import Database
from file_watcher import FileWatcher
from utils import setup_logging, ensure_directory

class MangaManager:
    """Main application coordinator."""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logging(
            log_level=self.config.log_level,
            log_file='/logs/processor.log'
        )
        self.db = Database()
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("Manga Manager started")
        self._initialize_directories()
        
        # Initialize file watcher
        downloads_path = self.config.paths.get('downloads', '/downloads')
        self.file_watcher = FileWatcher(
            watch_path=downloads_path,
            callback=self.process_file,
            debounce_seconds=2
        )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _initialize_directories(self):
        """Ensure all required directories exist."""
        paths = self.config.paths
        
        # Create cover cache directory structure
        data_dir = Path(paths.get('data', '/data'))
        ensure_directory(data_dir / 'covers')
        
        self.logger.info("Directory structure initialized")
    
    def process_file(self, file_path):
        """Process a single CBZ file.
        
        Args:
            file_path: Path to CBZ file to process
        """
        self.logger.info(f"Processing file: {file_path.name}")
        
        try:
            # TODO: Implement actual processing pipeline
            # For now, just log that we received the file
            self.logger.info(f"File queued for processing: {file_path}")
            
            # Check if already processed (duplicate detection)
            file_hash = self.db.calculate_file_hash(file_path)
            
            if self.db.is_duplicate(file_hash):
                self.logger.warning(f"Duplicate file detected: {file_path.name}")
                return
            
            self.logger.info(f"New file confirmed: {file_path.name} (hash: {file_hash[:16]}...)")
            
        except Exception as e:
            self.logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
    
    def run(self):
        """Main application loop."""
        check_interval = self.config.check_interval
        
        self.logger.info(f"Starting monitoring (check interval: {check_interval}s)")
        
        # Start file watcher
        self.file_watcher.start()
        
        # Process any existing files
        self.file_watcher.scan_existing_files()
        
        while self.running:
            try:
                # Check for pending files that are ready
                self.file_watcher.check_pending()
                
                # Sleep until next check
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(check_interval)
        
        self._shutdown()
    
    def _shutdown(self):
        """Clean shutdown process."""
        self.logger.info("Shutting down gracefully...")
        self.file_watcher.stop()
        self.db.close()
        self.logger.info("Manga Manager stopped")

if __name__ == '__main__':
    manager = MangaManager()
    manager.run()
