import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger('manga-manager.watcher')

class CBZFileHandler(FileSystemEventHandler):
    """Handler for CBZ file system events."""
    
    def __init__(self, callback, debounce_seconds=2):
        """
        Args:
            callback: Function to call when a CBZ file is ready
            debounce_seconds: Wait time to ensure file is fully written
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._pending_files = {}  # file_path: timestamp
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process .cbz files
        if file_path.suffix.lower() != '.cbz':
            return
        
        logger.info(f"New CBZ file detected: {file_path.name}")
        self._pending_files[str(file_path)] = time.time()
    
    def on_modified(self, event):
        """Handle file modification events (writing in progress)."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        if file_path.suffix.lower() == '.cbz':
            # Update timestamp for debouncing
            self._pending_files[str(file_path)] = time.time()
    
    def check_pending_files(self):
        """Check if any pending files are ready for processing."""
        current_time = time.time()
        ready_files = []
        
        for file_path, timestamp in list(self._pending_files.items()):
            # File hasn't been modified for debounce_seconds
            if current_time - timestamp >= self.debounce_seconds:
                path = Path(file_path)
                
                # Verify file still exists and is accessible
                if path.exists():
                    try:
                        # Try to open to ensure it's fully written
                        with open(path, 'rb') as f:
                            f.read(1)
                        
                        logger.info(f"File ready for processing: {path.name}")
                        ready_files.append(path)
                        del self._pending_files[file_path]
                        
                    except (IOError, PermissionError) as e:
                        logger.debug(f"File not ready yet: {path.name} - {e}")
                else:
                    # File was deleted before processing
                    logger.warning(f"File disappeared before processing: {file_path}")
                    del self._pending_files[file_path]
        
        # Process ready files
        for file_path in ready_files:
            try:
                self.callback(file_path)
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)


class FileWatcher:
    """Watches directory for new CBZ files."""
    
    def __init__(self, watch_path, callback, debounce_seconds=2):
        """
        Args:
            watch_path: Directory to watch
            callback: Function to call when CBZ file is ready
            debounce_seconds: Wait time to ensure file is fully written
        """
        self.watch_path = Path(watch_path)
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        
        self.event_handler = CBZFileHandler(callback, debounce_seconds)
        self.observer = Observer()
        self.running = False
        
        logger.info(f"File watcher initialized for: {self.watch_path}")
    
    def start(self):
        """Start watching directory."""
        if not self.watch_path.exists():
            logger.warning(f"Watch directory does not exist: {self.watch_path}")
            self.watch_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created watch directory: {self.watch_path}")
        
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=False)
        self.observer.start()
        self.running = True
        
        logger.info(f"Started watching: {self.watch_path}")
    
    def stop(self):
        """Stop watching directory."""
        if self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            logger.info("File watcher stopped")
    
    def check_pending(self):
        """Check for files that are ready to process."""
        if self.running:
            self.event_handler.check_pending_files()
    
    def scan_existing_files(self):
        """Scan for existing CBZ files in directory (on startup)."""
        if not self.watch_path.exists():
            return
        
        logger.info("Scanning for existing CBZ files...")
        cbz_files = list(self.watch_path.glob('*.cbz'))
        
        if cbz_files:
            logger.info(f"Found {len(cbz_files)} existing CBZ file(s)")
            for cbz_file in cbz_files:
                try:
                    logger.info(f"Processing existing file: {cbz_file.name}")
                    self.callback(cbz_file)
                except Exception as e:
                    logger.error(f"Error processing {cbz_file.name}: {e}", exc_info=True)
        else:
            logger.info("No existing CBZ files found")
